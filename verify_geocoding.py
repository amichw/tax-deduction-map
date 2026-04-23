"""
Cross-reference geocoding sources and flag coordinate disagreements.

For each settlement, compares:
  - current coords (settlements_geocoded.csv)
  - Wikidata coords (wikidata_cache.json)
  - Nominatim coords (geocache.json — checked via all query variants)

Flags any pair that disagrees by > 20 km (Haversine distance).
Writes data/coord_audit.csv and prints the top 20 worst disagreements.
"""

import csv
import json
import math
import os
import re

GEOCODED_CSV = "data/settlements_geocoded.csv"
WIKIDATA_CACHE = "data/wikidata_cache.json"
GEOCACHE = "data/geocache.json"
OVERRIDES_CSV = "data/overrides.csv"
OUTPUT_CSV = "data/coord_audit.csv"

FLAG_DISTANCE_KM = 20.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def haversine(lat1, lon1, lat2, lon2) -> float:
    """Return great-circle distance in km between two points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def load_json(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def clean_name(name: str) -> str:
    return re.sub(r"\s([א-ת])$", r"\1", name.strip())


def nominatim_queries(name: str) -> list[str]:
    """Return the same query variants used by geocode.py."""
    return list(dict.fromkeys([
        f"{name}, ישראל",
        f"{clean_name(name)}, ישראל",
        re.sub(r"\s*\(.*?\)", "", name).strip() + ", ישראל",
    ]))


# ---------------------------------------------------------------------------
# Load sources
# ---------------------------------------------------------------------------

def load_geocoded() -> list[dict]:
    rows = []
    with open(GEOCODED_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                lat = float(row["lat"]) if row["lat"] else None
                lon = float(row["lon"]) if row["lon"] else None
            except (ValueError, KeyError):
                lat = lon = None
            rows.append({**row, "lat": lat, "lon": lon})
    return rows


def load_wikidata() -> dict[str, tuple[float, float]]:
    raw = load_json(WIKIDATA_CACHE)
    result = {}
    for name, coords in raw.items():
        if coords and coords[0] is not None:
            result[name] = (float(coords[0]), float(coords[1]))
    return result


def load_nominatim_cache() -> dict[str, tuple[float | None, float | None]]:
    """Returns {query_string → (lat, lon)} — lat may be None for cached misses."""
    raw = load_json(GEOCACHE)
    result = {}
    for query, coords in raw.items():
        if coords and coords[0] is not None:
            result[query] = (float(coords[0]), float(coords[1]))
        else:
            result[query] = (None, None)
    return result


def lookup_nominatim(name: str, nom_cache: dict) -> tuple[float | None, float | None]:
    for query in nominatim_queries(name):
        if query in nom_cache:
            lat, lon = nom_cache[query]
            if lat is not None:
                return lat, lon
    return None, None


def load_overrides() -> dict[str, tuple[float, float]]:
    if not os.path.exists(OVERRIDES_CSV):
        return {}
    result = {}
    with open(OVERRIDES_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row["name_hebrew"].strip()
            try:
                result[name] = (float(row["lat"]), float(row["lon"]))
            except (ValueError, KeyError):
                pass
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading data sources...")
    settlements = load_geocoded()
    wd = load_wikidata()
    nom = load_nominatim_cache()
    overrides = load_overrides()

    print(f"  Settlements: {len(settlements)}")
    print(f"  Wikidata cache: {len(wd)} entries")
    print(f"  Nominatim cache: {len(nom)} queries")
    print(f"  Overrides: {len(overrides)} entries")

    audit_rows = []

    for row in settlements:
        name = row["name_hebrew"]
        cur_lat, cur_lon = row["lat"], row["lon"]

        wd_lat, wd_lon = wd.get(name, (None, None))
        nom_lat, nom_lon = lookup_nominatim(name, nom)
        ovr_lat, ovr_lon = overrides.get(name, (None, None))

        # Pairwise distances (only when both sources have coords)
        def dist(lat1, lon1, lat2, lon2):
            if None in (lat1, lon1, lat2, lon2):
                return None
            return haversine(lat1, lon1, lat2, lon2)

        d_cur_wd = dist(cur_lat, cur_lon, wd_lat, wd_lon)
        d_cur_nom = dist(cur_lat, cur_lon, nom_lat, nom_lon)
        d_wd_nom = dist(wd_lat, wd_lon, nom_lat, nom_lon)

        distances = [d for d in (d_cur_wd, d_cur_nom, d_wd_nom) if d is not None]
        max_dist = max(distances) if distances else None

        # Source agreement summary
        sources_with_coords = sum(x is not None for x in [cur_lat, wd_lat, nom_lat])
        agreement = "ok" if (max_dist is None or max_dist <= FLAG_DISTANCE_KM) else "DISAGREE"

        # Flag if any pair disagrees by > 20 km
        flagged = agreement == "DISAGREE"

        audit_rows.append({
            "name_hebrew": name,
            "rate_percent": row.get("rate_percent", ""),
            "current_lat": cur_lat,
            "current_lon": cur_lon,
            "wikidata_lat": wd_lat,
            "wikidata_lon": wd_lon,
            "nominatim_lat": nom_lat,
            "nominatim_lon": nom_lon,
            "override_lat": ovr_lat,
            "override_lon": ovr_lon,
            "dist_cur_wd_km": round(d_cur_wd, 1) if d_cur_wd is not None else "",
            "dist_cur_nom_km": round(d_cur_nom, 1) if d_cur_nom is not None else "",
            "dist_wd_nom_km": round(d_wd_nom, 1) if d_wd_nom is not None else "",
            "max_dist_km": round(max_dist, 1) if max_dist is not None else "",
            "sources_with_coords": sources_with_coords,
            "flag": agreement,
            "in_override": "yes" if ovr_lat is not None else "",
        })

    # Sort by max_dist descending for top-20 output
    flagged_rows = [r for r in audit_rows if r["flag"] == "DISAGREE"]
    flagged_rows.sort(key=lambda r: r["max_dist_km"] if r["max_dist_km"] != "" else 0, reverse=True)

    print(f"\n{'='*70}")
    print(f"FLAGGED: {len(flagged_rows)} settlements with disagreement > {FLAG_DISTANCE_KM} km")
    print(f"{'='*70}")

    top20 = flagged_rows[:20]
    if top20:
        header = f"{'Name':<20} {'Rate':>5}  {'MaxDist':>8}  {'CurLat':>8} {'CurLon':>8}  {'WdLat':>8} {'WdLon':>8}  {'NomLat':>8} {'NomLon':>8}  {'Ovr'}"
        print(header)
        print("-" * len(header))
        for r in top20:
            ovr = "OVERRIDE" if r["in_override"] else ""
            print(
                f"{r['name_hebrew']:<20} {r['rate_percent']:>5}  "
                f"{str(r['max_dist_km']):>8}  "
                f"{str(r['current_lat'] or ''):>8} {str(r['current_lon'] or ''):>8}  "
                f"{str(r['wikidata_lat'] or ''):>8} {str(r['wikidata_lon'] or ''):>8}  "
                f"{str(r['nominatim_lat'] or ''):>8} {str(r['nominatim_lon'] or ''):>8}  "
                f"{ovr}"
            )
    else:
        print("No disagreements found — all sources agree within 20 km.")

    # Write audit CSV
    os.makedirs("data", exist_ok=True)
    fieldnames = [
        "name_hebrew", "rate_percent",
        "current_lat", "current_lon",
        "wikidata_lat", "wikidata_lon",
        "nominatim_lat", "nominatim_lon",
        "override_lat", "override_lon",
        "dist_cur_wd_km", "dist_cur_nom_km", "dist_wd_nom_km",
        "max_dist_km", "sources_with_coords", "flag", "in_override",
    ]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(audit_rows)

    print(f"\nFull audit written to {OUTPUT_CSV}")
    print(f"Total flagged: {len(flagged_rows)} / {len(audit_rows)}")


if __name__ == "__main__":
    main()
