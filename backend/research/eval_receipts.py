"""Evaluate the receipt parser against labelled OCR text.

The total is the expense, so total accuracy leads. Item extraction feeds price
learning, so it's scored as precision/recall/F1 over (name, price) pairs.

Run inside the backend container:
    docker compose exec api python -m research.eval_receipts

The seed set (research/datasets/receipts_labeled.jsonl) is hand-labelled clean
text. For a paper, also run against ICDAR-2019 SROIE (the standard scanned-
receipt benchmark) to report on real OCR noise; the harness is dataset-agnostic
— feed it {text, merchant, total, items[]}.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.intelligence.companion import receipt_parser

_DATA = Path(__file__).parent / "datasets" / "receipts_labeled.jsonl"


def _load() -> list[dict[str, Any]]:
    return [json.loads(line) for line in _DATA.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def main() -> None:
    rows = _load()
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

        # Total (the expense amount).
        if r["total"] is not None:
            total_n += 1
            if _num_eq(parsed.get("total"), r["total"]):
                total_ok += 1

        # Merchant.
        if r["merchant"] is not None:
            merch_n += 1
            if _norm(parsed.get("merchant") or "") == _norm(r["merchant"]):
                merch_ok += 1

        # Line items as a set of (name, price) pairs.
        gold = {_item_key(i) for i in r["items"]}
        got = {_item_key(i) for i in parsed.get("items", [])}
        item_tp += len(gold & got)
        item_fp += len(got - gold)
        item_fn += len(gold - got)

    n = len(rows)
    receipts = sum(is_receipt_truth)
    print(f"\nReceipt parser evaluation  —  {n} samples ({receipts} receipts, {n - receipts} non-receipts)\n")

    p = det["tp"] / (det["tp"] + det["fp"]) if (det["tp"] + det["fp"]) else 0.0
    rec = det["tp"] / (det["tp"] + det["fn"]) if (det["tp"] + det["fn"]) else 0.0
    f1 = 2 * p * rec / (p + rec) if (p + rec) else 0.0
    print("Receipt detection (is this a receipt?)")
    print(f"  precision {p:.3f}   recall {rec:.3f}   f1 {f1:.3f}\n")

    if total_n:
        print(f"Total exact-match       {total_ok / total_n:.3f}  ({total_ok}/{total_n})")
    if merch_n:
        print(f"Merchant exact-match    {merch_ok / merch_n:.3f}  ({merch_ok}/{merch_n})")

    ip = item_tp / (item_tp + item_fp) if (item_tp + item_fp) else 0.0
    ir = item_tp / (item_tp + item_fn) if (item_tp + item_fn) else 0.0
    if_ = 2 * ip * ir / (ip + ir) if (ip + ir) else 0.0
    print("\nLine-item extraction  (name+price pairs)")
    print(f"  precision {ip:.3f}   recall {ir:.3f}   f1 {if_:.3f}   (tp={item_tp} fp={item_fp} fn={item_fn})")
    print()


if __name__ == "__main__":
    main()
