"""Convert the CORD receipt dataset to harness JSONL (with line items).

    python convert_cord.py path/to/cord/json_dir -o receipts_cord.jsonl

CORD (Consolidated Receipt Dataset) labels individual menu line items, so it is
the right public benchmark for the paper's LINE-ITEM extraction claim — SROIE
does not label items. This maps each receipt to {text, merchant, total, items[]}.

Targets the ORIGINAL CORD JSON (one file per receipt) with:
    valid_line[*].category   e.g. "menu.nm", "menu.price", "total.total_price"
    valid_line[*].group_id   groups the words of one line item together
    valid_line[*].words[*].text
Line items are reconstructed by pairing menu.nm (name) with menu.price /
menu.unitprice (price) sharing a group_id.

VERIFY BEFORE TRUSTING THE NUMBERS
----------------------------------
* CORD category names and packaging vary by release (the HuggingFace
  `naver-clova-ix/cord-v2` variant nests the parse differently). --preview prints
  the first receipts so you can eyeball name/price pairs before believing the F1.
* CORD receipts are Indonesian, with locale number formatting; our parser is
  tuned for English / ₹ receipts. Expect LOWER numbers than the clean seed set —
  that is the honest generalization result the paper's Limitations already flag,
  not a bug. Report it as such.
* This script never invents an item: if a group has no name or no price word, it
  is skipped, not guessed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

try:  # Windows consoles default to cp1252 and choke on ₹ / non-ASCII receipt text
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass


def _clean_amount(raw) -> str | None:
    if raw is None:
        return None
    m = re.search(r"[0-9][0-9.,]*", str(raw))
    if not m:
        return None
    return m.group(0).replace(",", "")


def _words(entry) -> str:
    return " ".join(w.get("text", "") for w in entry.get("words", [])).strip()


def _convert_one(doc: dict) -> dict:
    lines = doc.get("valid_line", [])
    text = "\n".join(_words(e) for e in lines if _words(e))

    by_group: dict[int, dict[str, list[str]]] = defaultdict(lambda: {"nm": [], "price": [], "unit": []})
    total = None
    for e in lines:
        cat = e.get("category", "")
        gid = e.get("group_id")
        val = _words(e)
        if cat == "menu.nm" and gid is not None:
            by_group[gid]["nm"].append(val)
        elif cat == "menu.price" and gid is not None:
            by_group[gid]["price"].append(val)
        elif cat == "menu.unitprice" and gid is not None:
            by_group[gid]["unit"].append(val)
        elif cat == "total.total_price" and total is None:
            total = _clean_amount(val)

    items = []
    for gid in sorted(by_group):
        g = by_group[gid]
        name = " ".join(g["nm"]).strip()
        price_raw = (g["price"] or g["unit"] or [None])[0]
        price = _clean_amount(price_raw)
        if name and price is not None:
            items.append({"name": name, "price": price})

    return {"text": text, "merchant": None, "total": total, "items": items}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cord_dir", type=Path, help="dir of per-receipt CORD .json files")
    ap.add_argument("-o", "--out", type=Path, default=Path("receipts_cord.jsonl"))
    ap.add_argument("--preview", type=int, default=3, help="print the first N converted rows to eyeball")
    args = ap.parse_args()

    rows = []
    for p in sorted(args.cord_dir.glob("*.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            continue
        if "valid_line" in doc:
            rows.append(_convert_one(doc))

    args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    with_items = sum(1 for r in rows if r["items"])
    total_items = sum(len(r["items"]) for r in rows)
    print(f"wrote {args.out}  —  {len(rows)} receipts, {with_items} with >=1 line item, "
          f"{total_items} items total")
    if not rows:
        print("No 'valid_line' docs found. If you have the HuggingFace cord-v2 variant, its parse is "
              "nested under ground_truth.gt_parse.menu — adjust _convert_one accordingly.")
    print("SPOT-CHECK the preview below before trusting the line-item F1:")
    for r in rows[: max(0, args.preview)]:
        print("\n--- preview ---  total:", r["total"])
        for it in r["items"][:6]:
            print(f"    {it['name']!r:40}  {it['price']}")


if __name__ == "__main__":
    main()
