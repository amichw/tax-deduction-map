# מפת הטבות מס הכנסה — ישובים מוטבים 2026
**Israel Income Tax Deductions 2026 — Interactive Settlement Map**

An interactive map of Israel showing all "preferred settlements" (ישובים מוטבים) eligible for income-tax deductions under the 2026 tax year, based on the official ITA publication.

---

## Features
- **CSV dataset** — all 488 settlements with rate, ceiling, and computed annual deduction
- **Interactive Leaflet map** — dark-themed, zoomable map of Israel
- **Hover tooltips** — show settlement name, rate %, ceiling, and annual deduction for each marker
- **Color-coded markers** — deduction level visualized by color (blue → red = low → high)
- **Deduction range filter** — two sliders to show only settlements in a chosen ₪ deduction range
- **Rate % filter chips** — toggle settlements by their tax-deduction rate (7%, 10%, 12% …20%)

---

## Data Source
`income-tax-deductions-2026.pdf` — official 2026 income-tax deduction table (Chapter 8, pages 20–32).

Columns extracted:
| Column | Description |
|---|---|
| `name_hebrew` | Settlement name in Hebrew (logical Unicode order) |
| `rate_percent` | Deduction rate (7 / 10 / 12 / 14 / 16 / 18 / 20) |
| `ceiling` | Maximum deductible income (₪) |
| `deduction` | Annual tax deduction = `rate_percent/100 × ceiling` (₪) |
| `lat` / `lon` | WGS-84 coordinates (Wikidata / Nominatim / manual override) |

---

## Quickstart

### 1. Parse PDF → CSV
```bash
python3 parse_pdf.py
# Output: data/settlements.csv
```

### 2. Fetch Wikidata coordinates (bulk, one-time)
```bash
python3 wikidata_geocode.py
# Output: data/wikidata_cache.json (~378/488 settlements matched)
```

### 3. Geocode remaining settlements
```bash
python3 geocode.py
# Output: data/settlements_geocoded.csv
# Three-tier pipeline: Wikidata → Nominatim (place-type filtered) → manual overrides
# All 488/488 settlements geocoded (100%)
# Nominatim results cached in data/geocache.json
```

### 4. Build the map
```bash
python3 generate_map.py
# Output: map.html (self-contained, no server needed)
```

### 5. Open the map
Open `map.html` in any modern browser. No server required.

---

## Project Structure
```
tax_map/
├── income-tax-deductions-2026.pdf  # Source PDF
├── parse_pdf.py                    # PDF → CSV parser
├── wikidata_geocode.py             # Wikidata bulk geocoder (SPARQL)
├── geocode.py                      # Three-tier geocoder
├── generate_map.py                 # Injects CSV data into map.html
├── map.html                        # Interactive Leaflet map (output)
├── data/
│   ├── settlements.csv             # Parsed table (no coordinates)
│   ├── settlements_geocoded.csv    # With lat/lon (488/488)
│   ├── wikidata_cache.json         # Wikidata lookup cache (378 matches)
│   ├── geocache.json               # Nominatim API cache
│   └── overrides.csv               # Manual coordinates for hard cases (54 entries)
├── README.md
├── TASKS.md
└── CLAUDE.md
```

---

## Geocoding Pipeline

Three-tier lookup — all 488 settlements are geocoded:

| Tier | Source | Matched |
|---|---|---|
| 1 | [Wikidata](https://www.wikidata.org/) SPARQL (bulk, free, no key) | 378 |
| 2 | [Nominatim](https://nominatim.org/) with `class=place` type filter | 60 |
| 3 | `data/overrides.csv` — manually researched coordinates | 50 |
| **Total** | | **488/488 (100%)** |

Wikidata covers cities, kibbutzim, moshavim, and local councils as distinct entities, avoiding false matches to streets/neighborhoods.
Nominatim only accepts results where `class=place` to reject non-settlement results.
The overrides file handles military camps, very small communities, and OSM/Wikidata gaps.

## Notes
- The map is self-contained HTML — all data is embedded as JSON. Share `map.html` as a single file.
- `data/geocache.json` caches Nominatim API calls — do not delete; avoids re-running API queries.
- `data/wikidata_cache.json` caches the Wikidata SPARQL result — do not delete.
