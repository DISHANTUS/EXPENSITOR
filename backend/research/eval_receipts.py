"""Evaluate the receipt parser against labelled OCR text.

The total is the expense, so total accuracy leads. Item extraction feeds price
learning, so it's scored as precision/recall/F1 over (name, price) pairs.

`compute()` returns the numbers as a plain dict (consumed by make_results.py);
`main()` prints the human report. Run inside the backend container:
    docker compose exec api python -m research.eval_receipts

The seed set (research/datasets/receipts_labeled.jsonl) is hand-labelled clean
text. For a paper, also run against ICDAR-2019 SROIE (the standard scanned-
receipt benchmark) to report on real OCR noise; the harness is dataset-agnostic
— feed it {text, merchant, total, items[]}. See datasets/convert_sroie.py (note:
SROIE ground truth has no line items, so it scores total+merchant only).
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.intelligence.companion import receipt_parser

_DATA = Path(__file__).parent / "datasets" / "receipts_labeled.jsonl"


def _load(path: Path = _DATA) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _num_eq(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return a == b
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except InvalidOperation:
        return False


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _item_key(item: dict[str, Any]) -> tuple[str, str]:
    price = item.get("price")
    try:
        price = str(Decimal(str(price)))
    except (InvalidOperation, TypeError):
        price = str(price)
    return (_norm(str(item.get("name", ""))), price)


def compute(path: Path = _DATA) -> dict[str, Any]:
    """Run the evaluation and return every reported number as a plain dict.

    Deterministic: same dataset in, same numbers out. No side effects."""
    rows = _load(path)
    is_receipt_truth = [bool(r["total"] or r["items"]) for r in rows]

    det = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    total_ok = total_n = 0
    merch_ok = merch_n = 0
    item_tp = item_fp = item_fn = 0

    for r, truth in zip(rows, is_receipt_truth):
        parsed = receipt_parser.parse(r["text"])
        pred = parsed is not None

        if truth and pred:
            det["tp"] += 1
        elif truth and not pred:
            det["fn"] += 1
        elif not truth and pred:
            det["fp"] += 1
        else:
            det["tn"] += 1

        if not (truth and pred):
            continue

        if r["total"] is not None:
            total_n += 1
            if _num_eq(parsed.get("total"), r["total"]):
                total_ok += 1

        if r["merchant"] is not None:
            merch_n += 1
            if _norm(parsed.get("merchant") or "") == _norm(r["merchant"]):
                merch_ok += 1

        gold = {_item_key(i) for i in r["items"]}
        got = {_item_key(i) for i in parsed.get("items", [])}
        item_tp += len(gold & got)
        item_fp += len(got - gold)
        item_fn += len(gold - got)

    p = det["tp"] / (det["tp"] + det["fp"]) if (det["tp"] + det["fp"]) else 0.0
    rec = det["tp"] / (det["tp"] + det["fn"]) if (det["tp"] + det["fn"]) else 0.0
    f1 = 2 * p * rec / (p + rec) if (p + rec) else 0.0

    ip = item_tp / (item_tp + item_fp) if (item_tp + item_fp) else 0.0
    ir = item_tp / (item_tp + item_fn) if (item_tp + item_fn) else 0.0
    if_ = 2 * ip * ir / (ip + ir) if (ip + ir) else 0.0

    return {
        "n": len(rows),
        "receipts": sum(is_receipt_truth),
        "detection": {"precision": p, "recall": rec, "f1": f1},
        "total": {"exact": total_ok / total_n if total_n else 0.0, "n": total_n, "ok": total_ok},
        "merchant": {"exact": merch_ok / merch_n if merch_n else 0.0, "n": merch_n, "ok": merch_ok},
        "line_items": {"precision": ip, "recall": ir, "f1": if_, "tp": item_tp, "fp": item_fp, "fn": item_fn},
    }


def main() -> None:
    d = compute()
    print(f"\nReceipt parser evaluation  —  {d['n']} samples "
          f"({d['receipts']} receipts, {d['n'] - d['receipts']} non-receipts)\n")

    det = d["detection"]
    print("Receipt detection (is this a receipt?)")
    print(f"  precision {det['precision']:.3f}   recall {det['recall']:.3f}   f1 {det['f1']:.3f}\n")

    if d["total"]["n"]:
        print(f"Total exact-match       {d['total']['exact']:.3f}  ({d['total']['ok']}/{d['total']['n']})")
    if d["merchant"]["n"]:
        print(f"Merchant exact-match    {d['merchant']['exact']:.3f}  ({d['merchant']['ok']}/{d['merchant']['n']})")

    li = d["line_items"]
    print("\nLine-item extraction  (name+price pairs)")
    print(f"  precision {li['precision']:.3f}   recall {li['recall']:.3f}   f1 {li['f1']:.3f}   "
          f"(tp={li['tp']} fp={li['fp']} fn={li['fn']})")
    print()


if __name__ == "__main__":
    main()
