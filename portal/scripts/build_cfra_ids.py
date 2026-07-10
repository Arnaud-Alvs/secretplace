# -*- coding: utf-8 -*-
"""
build_cfra_ids.py

Reads cfra_tradingid.xlsx and writes cfra_ids.json next to it.
Uses ONLY the Python standard library (no pip install needed).

An xlsx file is actually a ZIP archive containing XML files. This script
unzips it in memory and parses the XML directly.

Expected xlsx format (Sheet1, with header row) :
    col A = SP_ENTITY_NAME    (text)
    col B = SP_ENTITY_ID      (number)
    col C = SP_ISIN           (text, e.g. US0378331005)
    col D = SP_TRADING_ITEM_ID (number, e.g. 2590360)

Output JSON :
    { "ISIN": trading_item_id, ... }

Usage : double-click OR   python build_cfra_ids.py
Run this script each time the xlsx is refreshed.
"""

import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
XLSX_PATH = os.path.join(HERE, "cfra_tradingid.xlsx")
JSON_PATH = os.path.join(HERE, "cfra_ids.json")

# XML namespace used inside every xlsx
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def col_letter_to_index(letter):
    """Convert 'A' -> 0, 'B' -> 1, 'AA' -> 26, etc."""
    result = 0
    for ch in letter:
        result = result * 26 + (ord(ch.upper()) - ord('A') + 1)
    return result - 1


def split_cell_ref(ref):
    """Split 'B12' into ('B', 12). Column letters + row number."""
    i = 0
    while i < len(ref) and ref[i].isalpha():
        i += 1
    return ref[:i], int(ref[i:])


def read_shared_strings(zf):
    """Return the shared strings list from xl/sharedStrings.xml."""
    try:
        with zf.open("xl/sharedStrings.xml") as f:
            tree = ET.parse(f)
    except KeyError:
        return []
    strings = []
    for si in tree.getroot().findall(NS + "si"):
        # <si> can have a simple <t> or a rich text with multiple <r><t> runs
        parts = []
        for t in si.iter(NS + "t"):
            parts.append(t.text or "")
        strings.append("".join(parts))
    return strings


def read_sheet(zf, sheet_path, shared_strings):
    """Yield rows (list of cell values) from the given sheet xml."""
    with zf.open(sheet_path) as f:
        tree = ET.parse(f)
    root = tree.getroot()
    sheet_data = root.find(NS + "sheetData")
    if sheet_data is None:
        return

    for row in sheet_data.findall(NS + "row"):
        cells = {}  # col_index -> value
        for c in row.findall(NS + "c"):
            ref = c.attrib.get("r", "")
            col_letters, _ = split_cell_ref(ref) if ref else ("A", 1)
            col_idx = col_letter_to_index(col_letters)
            cell_type = c.attrib.get("t", "n")  # 'n'=number (default), 's'=shared string, 'str'=inline, 'b'=bool
            v = c.find(NS + "v")
            raw = v.text if v is not None else None

            if raw is None:
                cells[col_idx] = None
            elif cell_type == "s":
                try:
                    cells[col_idx] = shared_strings[int(raw)]
                except (ValueError, IndexError):
                    cells[col_idx] = raw
            elif cell_type == "str":
                cells[col_idx] = raw
            elif cell_type == "b":
                cells[col_idx] = (raw == "1")
            else:
                # number
                try:
                    if "." in raw or "e" in raw.lower():
                        cells[col_idx] = float(raw)
                    else:
                        cells[col_idx] = int(raw)
                except ValueError:
                    cells[col_idx] = raw

        # Convert dict -> list padded to max column index
        if cells:
            max_col = max(cells.keys())
            row_list = [cells.get(i) for i in range(max_col + 1)]
        else:
            row_list = []
        yield row_list


def main():
    if not os.path.isfile(XLSX_PATH):
        print("ERROR: file not found:", XLSX_PATH)
        print("Place cfra_tradingid.xlsx next to this script and try again.")
        input("Press Enter to quit...")
        sys.exit(1)

    print("Reading:", XLSX_PATH)

    with zipfile.ZipFile(XLSX_PATH) as zf:
        shared = read_shared_strings(zf)
        # The first sheet is usually xl/worksheets/sheet1.xml
        sheet_path = "xl/worksheets/sheet1.xml"
        if sheet_path not in zf.namelist():
            # Fallback: pick the first worksheet found
            for name in zf.namelist():
                if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                    sheet_path = name
                    break
        rows = list(read_sheet(zf, sheet_path, shared))

    if not rows:
        print("ERROR: no rows found in the xlsx.")
        input("Press Enter to quit...")
        sys.exit(1)

    print("Rows read:", len(rows))

    mapping = {}
    duplicates = []
    skipped = 0

    # Skip header (row 1)
    for row in rows[1:]:
        if not row or len(row) < 4:
            skipped += 1
            continue
        name = row[0]
        isin = row[2]
        trading_id = row[3]

        if not isin or not trading_id:
            skipped += 1
            continue

        isin = str(isin).strip().upper()
        try:
            trading_id = int(trading_id)
        except (TypeError, ValueError):
            skipped += 1
            continue

        # Duplicate ISIN policy: keep higher trading_id (newer S&P entity)
        if isin in mapping:
            duplicates.append((isin, name, mapping[isin], trading_id))
            if trading_id > mapping[isin]:
                mapping[isin] = trading_id
        else:
            mapping[isin] = trading_id

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2, sort_keys=True)

    print("Wrote   :", JSON_PATH)
    print("Entries :", len(mapping))
    print("Skipped :", skipped)
    if duplicates:
        print("Duplicates ({}), kept higher ID :".format(len(duplicates)))
        for isin, name, old, new in duplicates:
            print("  {} : {}  (kept {})".format(isin, name, max(old, new)))

    print("\nDone. You can now close this window.")
    input("Press Enter to quit...")


if __name__ == "__main__":
    main()
