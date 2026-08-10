"""Evaluate the bank-SMS parser against a labelled test set.

Reports the numbers a systems paper needs:
  - Detection (is this a transaction?): precision / recall / F1 / accuracy,
    against a naive "any rupee amount = transaction" baseline, to quantify what
    the rejection rules (OTP/promo/balance/…) actually buy.
  - Field extraction on correctly-detected transactions: direction accuracy,
    amount exact-match, merchant exact & partial match.
  - A per-negative-class breakdown, so the hard cases (OTPs that name an amount)
    are visible rather than hidden in an aggregate.

Run inside the backend container:
    docker compose exec api python -m research.eval_sms

The dataset (research/datasets/sms_labeled.jsonl) is a hand-labelled seed set.
For a paper, extend it with real messages and the public Kaggle Indian-banking
SMS corpus; the harness is dataset-agnostic.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.intelligence.companion import sms_parser

_DATA = Path(__file__).parent / "datasets" / "sms_labeled.jsonl"
_BARE_AMOUNT = re.compile(r"(?:rs\.?|inr|₹)\s*[0-9]", re.IGNORECASE)


def _load() -> list[dict[str, Any]]:
    return [json.loads(line) for line in _DATA.read_text(encoding="utf-8").splitlines() if line.strip()]


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def _amounts_equal(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return a == b
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except InvalidOperation:
        return False


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", "", (s or "").lower())


def main() -> None:
    rows = _load()

    # --- detection: parser vs naive baseline -------------------------------
    det = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    base = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    per_class_fp: dict[str, int] = defaultdict(int)      # negatives wrongly flagged
    per_class_total: dict[str, int] = defaultdict(int)

    # --- field extraction (on correctly detected true transactions) --------
    field_n = 0
    dir_ok = amt_ok = merch_exact = merch_partial = merch_labelled = 0

    for r in rows:
        truth = bool(r["is_transaction"])
        parsed = sms_parser.parse(r["text"])
        pred = parsed is not None
        base_pred = bool(_BARE_AMOUNT.search(r["text"]))  # naive: names a rupee amount

        for tag, p in (("det", pred), ("base", base_pred)):
            d = det if tag == "det" else base
            if truth and p:
                d["tp"] += 1
            elif truth and not p:
                d["fn"] += 1
            elif not truth and p:
                d["fp"] += 1
            else:
                d["tn"] += 1

        if not truth:
            per_class_total[r["class"]] += 1
            if pred:
                per_class_fp[r["class"]] += 1

        if truth and pred:
            field_n += 1
            if parsed["kind"] == r["kind"]:
                dir_ok += 1
            if _amounts_equal(parsed["amount"], r["amount"]):
                amt_ok += 1
            if r["merchant"] is not None:
                merch_labelled += 1
                if _norm(parsed["merchant"]) == _norm(r["merchant"]):
                    merch_exact += 1
                    merch_partial += 1
                elif parsed["merchant"] and _norm(parsed["merchant"]) in _norm(r["merchant"]):
                    merch_partial += 1

    pos = sum(1 for r in rows if r["is_transaction"])
    neg = len(rows) - pos
    print(f"\nBank-SMS parser evaluation  —  {len(rows)} messages ({pos} transactions, {neg} non-transactions)\n")

    print("Detection (transaction vs not)")
    print(f"  {'method':<22}{'prec':>7}{'rec':>7}{'f1':>7}{'acc':>7}")
    for name, d in (("Expensitor rules", det), ("baseline: any Rs amount", base)):
        p, r_, f = _prf(d["tp"], d["fp"], d["fn"])
        acc = (d["tp"] + d["tn"]) / len(rows)
        print(f"  {name:<22}{p:>7.3f}{r_:>7.3f}{f:>7.3f}{acc:>7.3f}")

    print("\nField extraction (on correctly-detected transactions, n=%d)" % field_n)
    if field_n:
        print(f"  direction accuracy    {dir_ok / field_n:>7.3f}")
        print(f"  amount exact-match     {amt_ok / field_n:>7.3f}")
    if merch_labelled:
        print(f"  merchant exact         {merch_exact / merch_labelled:>7.3f}  (of {merch_labelled} with a labelled merchant)")
        print(f"  merchant partial       {merch_partial / merch_labelled:>7.3f}")

    print("\nFalse positives by non-transaction class (lower is better)")
    for cls in sorted(per_class_total):
        fp = per_class_fp[cls]
        tot = per_class_total[cls]
        flag = "  <-- leaks" if fp else ""
        print(f"  {cls:<16}{fp:>3}/{tot:<3}{flag}")
    print()


if __name__ == "__main__":
    main()
