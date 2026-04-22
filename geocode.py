"""
Geocode Israeli settlements using a three-tier pipeline:

  1. Wikidata cache  (data/wikidata_cache.json) — type-safe, bulk-fetched
  2. Nominatim       — place-type filtered (class=place only)
  3. Manual overrides (data/overrides.csv) — hardcoded coords for hard cases

Reads data/settlements.csv, writes data/settlements_geocoded.csv.
Nominatim calls cached in data/geocache.json; rate-limited to 1 req/sec.
"""

import csv
import json
import os
import re
import time

import requests

INPUT_CSV = "data/settlements.csv"
OUTPUT_CSV = "data/settlements_geocoded.csv"
GEOCACHE_FILE = "data/geocache.json"
WIKIDATA_CACHE_FILE = "data/wikidata_cache.json"
OVERRIDES_FILE = "data/overrides.csv"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "TaxMapIsrael/1.0 (educational project)"}

# Israel bounding box: lat 29.5–33.3, lon 34.3–35.9
ISRAEL_LAT = (29.4, 33.4)
ISRAEL_LON = (34.2, 36.0)

# Only accept Nominatim results that are actual settlements
PLACE_CLASSES = {"place"}
PLACE_TYPES = {"city", "town", "village", "hamlet", "locality", "isolated_dwelling", "suburb"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def in_israel(lat: float, lon: float) -> bool:
    return ISRAEL_LAT[0] <= lat <= ISRAEL_LAT[1] and ISRAEL_LON[0] <= lon <= ISRAEL_LON[1]


def load_json(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clean_name(name: str) -> str:
    """Remove spurious trailing-character space artifacts from PDF extraction."""
    return re.sub(r"\s([א-ת])$", r"\1", name.strip())


# ---------------------------------------------------------------------------
# Tier 1: Wikidata cache
# ---------------------------------------------------------------------------

def load_wikidata_cache(path: str) -> dict[str, tuple[float, float]]:
    """Load wikidata_cache.json → {name_hebrew → (lat, lon)} (skips None entries)."""
    raw = load_json(path)
    result = {}
    for name, coords in raw.items():
        if coords and coords[0] is not None:
            result[name] = (float(coords[0]), float(coords[1]))
    return result


def lookup_wikidata(name: str, wd_cache: dict[str, tuple[float, float]]) -> tuple[float | None, float | None]:
    if name in wd_cache:
        return wd_cache[name]
    return None, None


# ---------------------------------------------------------------------------
# Tier 2: Nominatim with place-type filter
# ---------------------------------------------------------------------------

def nominatim_search(query: str) -> tuple[float | None, float | None]:
    """Call Nominatim; only accept results with class=place and a settlement type."""
    params = {
        "q": query,
        "format": "json",
        "countrycodes": "il",
        "limit": 10,
        "accept-language": "he,en",
    }
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        for r in resp.json():
            cls = r.get("class", "")
            typ = r.get("type", "")
            lat, lon = float(r["lat"]), float(r["lon"])
            if cls in PLACE_CLASSES and typ in PLACE_TYPES and in_israel(lat, lon):
                return lat, lon
    except Exception as e:
        print(f"  Nominatim error: {e}")
    return None, None


def geocode_nominatim(name: str, geocache: dict) -> tuple[float | None, float | None]:
    """Try Nominatim with several query strategies; cache all results."""
    strategies = [
        f"{name}, ישראל",
        f"{clean_name(name)}, ישראל",
        re.sub(r"\s*\(.*?\)", "", name).strip() + ", ישראל",
    ]
    # Deduplicate while preserving order
    seen = []
    for s in strategies:
        if s not in seen:
            seen.append(s)

    for query in seen:
        if query in geocache:
            lat, lon = geocache[query]
            if lat is not None:
                return lat, lon
            continue  # cached miss

        lat, lon = nominatim_search(query)
        geocache[query] = [lat, lon]
        time.sleep(1)  # Nominatim rate limit

        if lat is not None:
            return lat, lon

    return None, None


# ---------------------------------------------------------------------------
# Tier 3: Manual overrides
# ---------------------------------------------------------------------------

def load_overrides(path: str) -> dict[str, tuple[float, float]]:
    """Load overrides.csv → {name_hebrew → (lat, lon)}."""
    if not os.path.exists(path):
        return {}
    result = {}
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row["name_hebrew"].strip()
            try:
                result[name] = (float(row["lat"]), float(row["lon"]))
            except (ValueError, KeyError):
                pass
    return result


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    os.makedirs("data", exist_ok=True)

    # Load all three sources
    wd_cache = load_wikidata_cache(WIKIDATA_CACHE_FILE)
    geocache = load_json(GEOCACHE_FILE)
    overrides = load_overrides(OVERRIDES_FILE)

    if wd_cache:
        print(f"Wikidata cache: {len(wd_cache)} entries loaded")
    else:
        print("WARNING: no wikidata_cache.json found — run wikidata_geocode.py first")

    print(f"Overrides: {len(overrides)} entries loaded")

    with open(INPUT_CSV, encoding="utf-8-sig") as f:
        settlements = list(csv.DictReader(f))

    total = len(settlements)
    counts = {"wikidata": 0, "nominatim": 0, "override": 0, "miss": 0}
    results = []

    for i, row in enumerate(settlements):
        name = row["name_hebrew"]
        lat = lon = None
        source = "miss"

        # Tier 1: Wikidata
        lat, lon = lookup_wikidata(name, wd_cache)
        if lat is not None:
            source = "wikidata"

        # Tier 2: Nominatim (only if Wikidata missed)
        if lat is None:
            lat, lon = geocode_nominatim(name, geocache)
            if lat is not None:
                source = "nominatim"

        # Tier 3: Manual override
        if lat is None and name in overrides:
            lat, lon = overrides[name]
            source = "override"

        counts[source] += 1
        status = "✓" if lat is not None else "✗"
        print(f"[{i+1}/{total}] {status} [{source}] {name} → {lat}, {lon}")
        results.append({**row, "lat": lat, "lon": lon})

        # Periodic geocache save
        if (i + 1) % 20 == 0:
            save_json(GEOCACHE_FILE, geocache)

    save_json(GEOCACHE_FILE, geocache)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["name_hebrew", "rate_percent", "ceiling", "deduction", "lat", "lon"],
        )
        writer.writeheader()
        writer.writerows(results)

    found = total - counts["miss"]
    print(f"\n--- Summary ---")
    print(f"Total: {found}/{total} geocoded ({found/total*100:.1f}%)")
    print(f"  Wikidata:  {counts['wikidata']}")
    print(f"  Nominatim: {counts['nominatim']}")
    print(f"  Override:  {counts['override']}")
    print(f"  Miss:      {counts['miss']}")
    print(f"Saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
