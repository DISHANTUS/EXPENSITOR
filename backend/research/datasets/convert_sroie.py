"""Convert ICDAR-2019 SROIE ground truth to harness JSONL (total + merchant only).

    python convert_sroie.py path/to/sroie_dir -o receipts_sroie.jsonl

SROIE labels COMPANY, DATE, ADDRESS, TOTAL — it does NOT label line items. So this
produces {text, merchant=company, total, items: []}. Running eval_receipts on the
output measures receipt detection, TOTAL exact-match, and MERCHANT exact-match —
which is exactly the part of the receipt claim SROIE can support.

  -> For the paper's LINE-ITEM F1 claim, SROIE is the wrong dataset (no item
     labels). Use CORD instead (see convert_cord.py). Report each number against
     the dataset that actually labels it; do not carry the clean-seed line-item
     number over to SROIE.

Expected layout (common SROIE release): a directory holding, per receipt id,
    <id>.txt   OCR result — lines of  x1,y1,x2,y2,transcription   (or plain text)
    <id>.json  {"company","date","address","total"}
Point --box-dir / --entities-dir at wherever those live (defaults: same dir).
Confirm against your download; SROIE has been repackaged several ways.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:  # Windows consoles default to cp1252 and choke on non-ASCII receipt text
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

_COORD_LINE = re.compile(r"^\s*-?\d+\s*,\s*-?\d+\s*,")  # starts with two ints + comma => box format


def _clean_amount(raw) -> str | None:
    if raw is None:
        return None
    m = re.search(r"[0-9][0-9,]*(?:\.[0-9]+)?", str(raw))
    return m.group(0).replace(",", "") if m else None


def _text_from_box_file(path: Path) -> str:
    """SROIE OCR files are lines of `x1,y1,x2,y2,transcription`. Keep the text."""
    lines = []
    for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not ln.strip():
            continue
        if _COORD_LINE.match(ln):
            parts = ln.split(",", 8)
            lines.append(parts[8].strip() if len(parts) >= 9 else parts[-1].strip())
        else:
            lines.append(ln.strip())
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sroie_dir", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("receipts_sroie.jsonl"))
    ap.add_argument("--box-dir", type=Path, default=None, help="dir with <id>.txt OCR files")
    ap.add_argument("--entities-dir", type=Path, default=None, help="dir with <id>.json entity files")
    ap.add_argument("--preview", type=int, default=2, help="print the first N converted rows to eyeball")
    args = ap.parse_args()

    box_dir = args.box_dir or args.sroie_dir
    ent_dir = args.entities_dir or args.sroie_dir

    rows, missing_text, missing_total = [], 0, 0
    for ent_path in sorted(ent_dir.glob("*.json")):
        try:
            ent = json.loads(ent_path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            continue
        txt_path = box_dir / f"{ent_path.stem}.txt"
        if not txt_path.exists():
            missing_text += 1
            continue
        total = _clean_amount(ent.get("total"))
        if total is None:
            missing_total += 1
        rows.append({
            "text": _text_from_box_file(txt_path),
            "merchant": (ent.get("company") or None),
            "total": total,
            "items": [],   # SROIE has no line-item ground truth
        })

    args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"wrote {args.out}  —  {len(rows)} receipts "
          f"({missing_text} skipped for missing OCR text, {missing_total} without a labelled total)")
    print("NOTE: items=[] for every row — SROIE has no line items. eval_receipts will report "
          "line-item F1 as undefined (0 gold); use CORD (convert_cord.py) for that claim.")
    for r in rows[: max(0, args.preview)]:
        print("\n--- preview ---")
        print("merchant:", r["merchant"], "| total:", r["total"])
        print("text[:160]:", r["text"][:160].replace("\n", " ⏎ "))


if __name__ == "__main__":
    main()
