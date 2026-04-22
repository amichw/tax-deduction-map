# CLAUDE.md — Project Conventions

## Project: Israel Tax Deduction Map (tax_map)

### After Every Task or Feature
1. Update `TASKS.md` — move item to Completed, add what was done
2. Update `README.md` if the feature changes usage or structure
3. Commit with a clear message ending with: `Co-Authored-By: Claude Sonnet 4.6`

### Commit Scope
Commit after each of these natural checkpoints:
- PDF parsed → CSV generated
- Geocoding complete
- Map HTML generated and working
- New filter or UI feature added
- Documentation updated

### Data Pipeline
The pipeline is strictly sequential:
```
parse_pdf.py         → data/settlements.csv
wikidata_geocode.py  → data/wikidata_cache.json  (bulk SPARQL, run once)
geocode.py           → data/settlements_geocoded.csv
                         (tier 1: wikidata_cache.json)
                         (tier 2: Nominatim API, cached in geocache.json)
                         (tier 3: data/overrides.csv — manual coordinates)
generate_map.py      → map.html (self-contained, embeds JSON)
```
Never edit `map.html` manually after `generate_map.py` has run — it will be overwritten.
Edit the template structure in `map.html` (before `generate_map.py` runs), then regenerate.

### Python Environment
- Use a venv or ask the user for one. Do NOT install packages globally.
- Required packages: `pdfplumber`, `requests` (standard library otherwise)
- `requests` is available system-wide on this machine

### Hebrew Text
- PDF extracts Hebrew in visual RTL order (characters reversed)
- `parse_pdf.py::reverse_hebrew()` converts to logical Unicode order
- Always store and display Hebrew in logical order
- When geocoding, use `name_hebrew` (logical order) + "ישראל"

### Map HTML Structure
- `map.html` contains a placeholder `SETTLEMENTS_DATA_PLACEHOLDER`
- `generate_map.py` replaces it with the actual JSON array
- The color scale and filter ranges are defined in `<script>` inside `map.html`
- If you add new data columns, update both `generate_map.py` (load_geocoded) and `map.html` (tooltip template)

### Geocoding
- Three-tier pipeline: Wikidata → Nominatim → overrides.csv (see Data Pipeline above)
- Wikidata: one SPARQL query against https://query.wikidata.org/sparql, no API key needed
  - Fetches all Israeli entities with Hebrew labels + P625 coordinates
  - Saved to data/wikidata_cache.json — do NOT delete (run wikidata_geocode.py to regenerate)
- Nominatim rate limit: 1 request/second — always enforce `time.sleep(1)` between calls
  - Only accept results where `class=place` to reject streets/neighborhoods/districts
  - Cache all results (hits and misses) in `data/geocache.json`
- Manual overrides: `data/overrides.csv` — columns: name_hebrew, lat, lon, source
  - Add entries here for settlements not found by Wikidata or Nominatim
- Validate all coordinates are within Israel bounding box before accepting
- All 488/488 settlements are currently geocoded (100%)
