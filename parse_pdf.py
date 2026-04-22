"""
Parse income tax deduction table from PDF pages 20-32.
Extracts: settlement name (Hebrew), rate %, ceiling, and computes deduction.
Hebrew text in the PDF is stored in visual (RTL) order; we reverse it to logical Unicode order.
"""

import pdfplumber
import re
import csv
import os

PDF_PATH = "income-tax-deductions-2026.pdf"
OUTPUT_CSV = "data/settlements.csv"

# Pages 20-32 are 0-indexed as 19-31
PAGE_START = 19
PAGE_END = 32  # exclusive

ROW_PATTERN = re.compile(r"^([\d,]+)\s+(\d+)%\s+(.+)$")


def reverse_hebrew(text: str) -> str:
    """
    Reverse Hebrew text from visual (PDF extraction) order to logical Unicode order.
    Simple character reversal works for Hebrew since word and character order are both reversed.
    Post-processing removes PDF spacing artifacts around final Hebrew letters (ם ן ך ף ץ).
    """
    import re as _re
    result = text[::-1].strip()
    # Remove spurious space before final Hebrew letters at end of words
    # e.g., "אדוריי ם" → "אדוריים", "אופקי ם" → "אופקים"
    result = _re.sub(r" ([םןךףץ])(?=[ ()\u05d0-\u05ea]|$)", r"\1", result)
    return result


def parse_settlements(pdf_path: str) -> list[dict]:
    settlements = []
    seen = set()

    with pdfplumber.open(pdf_path) as pdf:
        for page_num in range(PAGE_START, PAGE_END):
            page = pdf.pages[page_num]
            text = page.extract_text()
            if not text:
                continue

            for line in text.splitlines():
                line = line.strip()
                m = ROW_PATTERN.match(line)
                if not m:
                    continue

                ceiling_str, rate_str, name_visual = m.groups()
                ceiling = int(ceiling_str.replace(",", ""))
                rate = int(rate_str)
                deduction = round((rate / 100) * ceiling)
                name_hebrew = reverse_hebrew(name_visual)

                # Deduplicate by Hebrew name
                if name_hebrew in seen:
                    continue
                seen.add(name_hebrew)

                settlements.append({
                    "name_hebrew": name_hebrew,
                    "rate_percent": rate,
                    "ceiling": ceiling,
                    "deduction": deduction,
                })

    return settlements


def main():
    os.makedirs("data", exist_ok=True)
    settlements = parse_settlements(PDF_PATH)
    print(f"Parsed {len(settlements)} settlements")

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f, fieldnames=["name_hebrew", "rate_percent", "ceiling", "deduction"]
        )
        writer.writeheader()
        writer.writerows(settlements)

    print(f"Saved to {OUTPUT_CSV}")

    # Show summary stats
    rates = sorted(set(s["rate_percent"] for s in settlements))
    deductions = sorted(set(s["deduction"] for s in settlements))
    print(f"Rates: {rates}")
    print(f"Deduction range: {min(deductions):,} – {max(deductions):,}")


if __name__ == "__main__":
    main()
