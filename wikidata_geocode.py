"""
Wikidata bulk geocoder for Israeli settlements.

Runs one SPARQL query to fetch all Israeli localities with Hebrew labels + coordinates.
Saves data/wikidata_cache.json: {name_hebrew_from_csv → [lat, lon]}

Matching strategy (applied in order):
  1. Exact match on name_hebrew from CSV
  2. Space-stripped match (handles PDF artifacts like "ביריי ה" → "בירייה")
  3. Strip parentheticals + space-stripped match
"""

import csv
import json
import os
import re

import requests

SPARQL_URL = "https://query.wikidata.org/sparql"
INPUT_CSV = "data/settlements.csv"
OUTPUT_FILE = "data/wikidata_cache.json"

HEADERS = {
    "User-Agent": "TaxMapIsrael/1.0 (educational project)",
    "Accept": "application/sparql-results+json",
}

SPARQL_QUERY = """
SELECT ?label ?lat ?lon WHERE {
  ?item wdt:P17 wd:Q801 .
  ?item rdfs:label ?label .
  FILTER(LANG(?label) = "he")
  ?item p:P625 ?coord_stmt .
  ?coord_stmt psv:P625 ?coord_node .
  ?coord_node wikibase:geoLatitude ?lat .
  ?coord_node wikibase:geoLongitude ?lon .
}
"""

# Israel bounding box
ISRAEL_LAT = (29.4, 33.4)
ISRAEL_LON = (34.2, 36.0)


def in_israel(lat: float, lon: float) -> bool:
    return ISRAEL_LAT[0] <= lat <= ISRAEL_LAT[1] and ISRAEL_LON[0] <= lon <= ISRAEL_LON[1]


def strip_spaces(s: str) -> str:
    return s.replace(" ", "").replace("\u200f", "").replace("\u200e", "")


def strip_parens(s: str) -> str:
    return re.sub(r"\s*\(.*?\)", "", s).strip()


def fetch_wikidata() -> dict[str, tuple[float, float]]:
    """Fetch all Israeli settlement labels+coords from Wikidata. Returns {label → (lat, lon)}."""
    print("Querying Wikidata SPARQL endpoint...")
    params = {"query": SPARQL_QUERY, "format": "json"}
    resp = requests.get(SPARQL_URL, params=params, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    label_to_coords: dict[str, tuple[float, float]] = {}
    for row in data["results"]["bindings"]:
        label = row["label"]["value"]
        lat = float(row["lat"]["value"])
        lon = float(row["lon"]["value"])
        if in_israel(lat, lon):
            # Keep first occurrence (Wikidata may return multiple per label)
            if label not in label_to_coords:
                label_to_coords[label] = (lat, lon)

    print(f"  Got {len(label_to_coords)} unique Hebrew labels from Wikidata")
    return label_to_coords


def build_lookup(label_to_coords: dict[str, tuple[float, float]]) -> dict:
    """Build auxiliary lookup dicts for fuzzy matching."""
    exact = label_to_coords  # {label → coords}
    no_spaces = {}           # {label_no_spaces → coords}
    no_parens = {}           # {label_no_parens_no_spaces → coords}

    for label, coords in label_to_coords.items():
        ns = strip_spaces(label)
        if ns not in no_spaces:
            no_spaces[ns] = coords

        np_ns = strip_spaces(strip_parens(label))
        if np_ns not in no_parens:
            no_parens[np_ns] = coords

    return {"exact": exact, "no_spaces": no_spaces, "no_parens": no_parens}


def match_settlement(name: str, lookup: dict) -> tuple[float | None, float | None, str]:
    """Try to match a settlement name against Wikidata. Returns (lat, lon, strategy)."""
    # Strategy 1: exact
    if name in lookup["exact"]:
        lat, lon = lookup["exact"][name]
        return lat, lon, "exact"

    # Strategy 2: strip spaces (PDF artifact fix)
    ns = strip_spaces(name)
    if ns in lookup["no_spaces"]:
        lat, lon = lookup["no_spaces"][ns]
        return lat, lon, "no_spaces"

    # Strategy 3: strip parentheticals + spaces
    np_ns = strip_spaces(strip_parens(name))
    if np_ns and np_ns in lookup["no_parens"]:
        lat, lon = lookup["no_parens"][np_ns]
        return lat, lon, "no_parens"

    return None, None, "miss"


def main():
    os.makedirs("data", exist_ok=True)

    # Load settlement names from CSV
    with open(INPUT_CSV, encoding="utf-8-sig") as f:
        settlements = [row["name_hebrew"] for row in csv.DictReader(f)]
    print(f"Loaded {len(settlements)} settlements from {INPUT_CSV}")

    # Fetch from Wikidata
    label_to_coords = fetch_wikidata()
    lookup = build_lookup(label_to_coords)

    # Match each settlement
    cache: dict[str, list[float]] = {}
    found = 0
    misses = []

    for name in settlements:
        lat, lon, strategy = match_settlement(name, lookup)
        if lat is not None:
            cache[name] = [lat, lon]
            found += 1
            print(f"  ✓ [{strategy}] {name} → {lat:.4f}, {lon:.4f}")
        else:
            cache[name] = [None, None]
            misses.append(name)

    # Save cache
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    print(f"\nWikidata matched: {found}/{len(settlements)} ({found/len(settlements)*100:.1f}%)")
    if misses:
        print(f"Misses ({len(misses)}):")
        for m in misses:
            print(f"  ✗ {m}")
    print(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
