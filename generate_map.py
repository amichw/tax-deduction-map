"""
Reads data/settlements_geocoded.csv and injects the data as JSON into map.html,
producing map.html in-place (the placeholder is replaced with real data).
"""

import csv
import json
import os
import re

GEOCODED_CSV = "data/settlements_geocoded.csv"
MAP_TEMPLATE = "map.html"
PLACEHOLDER = "SETTLEMENTS_DATA_PLACEHOLDER"
# Regex to find an already-injected JSON array on the SETTLEMENTS line
INJECTED_PATTERN = re.compile(r"(const SETTLEMENTS = )\[.*?\](;)", re.DOTALL)


def load_geocoded(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            lat = row["lat"]
            lon = row["lon"]
            if not lat or lat == "None":
                continue
            rows.append({
                "name": row["name_hebrew"],
                "rate": int(row["rate_percent"]),
                "ceiling": int(row["ceiling"]),
                "deduction": int(row["deduction"]),
                "lat": float(lat),
                "lon": float(lon),
            })
    return rows


def inject_data(template_path: str, settlements: list[dict], placeholder: str):
    with open(template_path, encoding="utf-8") as f:
        html = f.read()

    data_json = json.dumps(settlements, ensure_ascii=False, indent=None)

    if placeholder in html:
        # First run: replace the placeholder token
        html = html.replace(placeholder, data_json, 1)
    else:
        # Subsequent runs: replace already-injected JSON array
        html, count = INJECTED_PATTERN.subn(r"\g<1>" + data_json + r"\g<2>", html)
        if count == 0:
            print("WARNING: could not find SETTLEMENTS data to replace in map.html")
            return

    with open(template_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    if not os.path.exists(GEOCODED_CSV):
        print(f"ERROR: {GEOCODED_CSV} not found. Run geocode.py first.")
        return

    settlements = load_geocoded(GEOCODED_CSV)
    inject_data(MAP_TEMPLATE, settlements, PLACEHOLDER)

    print(f"Injected {len(settlements)} geocoded settlements into {MAP_TEMPLATE}")


if __name__ == "__main__":
    main()
