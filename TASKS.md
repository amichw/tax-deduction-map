# Task Tracking

## Completed

### Task 1 — Parse PDF to CSV ✅
- Extracted pages 20–32 of `income-tax-deductions-2026.pdf`
- Reversed Hebrew text from visual (PDF) order to logical Unicode order
- Cleaned PDF spacing artifacts around final Hebrew letters (ם ן ך ף ץ)
- Computed `deduction = rate_percent / 100 × ceiling`
- Output: `data/settlements.csv` — 488 settlements, rates 7–20%, deductions ₪10,265–₪53,568

### Task 2 — Geocode settlements ✅
- Used Nominatim (OpenStreetMap) API with Hebrew name + "ישראל"
- Multiple fallback search strategies (cleaned name, without parentheticals, English suffix)
- Rate-limited to 1 req/sec; results cached in `data/geocache.json`
- **463/488 settlements geocoded (94.9%)**
- 25 not found (mostly military camps, very new/small settlements, or OSM naming variants)
- Output: `data/settlements_geocoded.csv`

### Task 6 — Improve geocoding quality to 100% ✅
- **Problem**: 25 settlements not found; Nominatim could return wrong place types (streets/neighborhoods)
- **Solution**: Three-tier pipeline — Wikidata SPARQL → Nominatim with place-type filter → manual overrides
- Added `wikidata_geocode.py`: bulk SPARQL query fetches all Israeli entities with Hebrew labels + coords
  - Matching: exact → space-stripped (PDF artifact fix) → strip parentheticals
  - 378/488 matched via Wikidata
- Updated `geocode.py`: Wikidata-first, then Nominatim filtered to `class=place` only, then overrides
  - Nominatim added 60 more; overrides covered the final 50
- Added `data/overrides.csv`: 54 manually researched coordinates for hard cases
  - Military camps: מחנה טלי, מחנה יוכבד, מחנה יפה
  - Small/obscure settlements: ביריי ה, כחלה, שדמות מחולה, etc.
  - Variants/OSM-gaps: פורייה x3, פני חבר, קריית ארבע, etc.
- **Result: 488/488 geocoded (100%)**

### Task 3 — Interactive Leaflet map ✅
- Dark-themed map centered on Israel (CartoDB Dark Matter tiles)
- Circle markers, color-coded by deduction amount (blue=low → red=high)
- Marker radius scales with deduction
- Hover tooltips: settlement name, rate, ceiling, annual deduction
- Self-contained `map.html` (data embedded as JSON)

### Task 4 — Deduction filter ✅
- Min/Max deduction sliders (₪ range)
- Rate-percentage chip toggles (7% / 10% / 12% / 14% / 16% / 18% / 20%)
- Live marker count badge
- Markers hidden (opacity 0, pointer-events off) when filtered out

### Task 5 — Documentation ✅
- `README.md` — project overview, quickstart, data dictionary, structure
- `TASKS.md` — this file
- `CLAUDE.md` — project conventions for Claude

### Task 6 — Settlement search box ✅
- Text input with Hebrew RTL support in the filter panel
- Dropdown autocomplete after 2+ characters typed (client-side, instant)
- Filters to max 15 results; each keystroke narrows the list via `includes()`
- Selecting a result: pans map to zoom 13, opens tooltip, pulses marker for 2s
- Escape key / blur closes dropdown; `mousedown` + 150ms blur delay prevents race
- Implemented entirely in `map.html` (CSS + HTML + JS); survives `generate_map.py` regeneration

### Task 7 — Deploy to GitHub Pages ✅
- Created `.nojekyll` to prevent Jekyll processing Hebrew content
- Created `index.html` with meta-refresh redirect to `map.html`
- Published repo: https://github.com/amichw/tax-deduction-map
- Enabled GitHub Pages from `master` branch root
- Live URL: https://amichw.github.io/tax-deduction-map/

---

## Potential Future Enhancements
- [ ] Add English transliteration of settlement names
- [ ] Cluster nearby markers at low zoom levels
- [ ] Export filtered results as CSV download
- [ ] Add year-over-year comparison (2025 vs 2026)
- [ ] Mobile-responsive layout improvements
