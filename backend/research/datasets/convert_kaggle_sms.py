"""Convert the Kaggle 'Indian Banking Transaction Text Dataset' to harness JSONL.

    python convert_kaggle_sms.py kaggle.csv -o sms_kaggle.jsonl
    python convert_kaggle_sms.py kaggle.csv --inspect        # print header + sample

Output line schema (exactly what eval_sms.py reads):
    {"text", "is_transaction", "kind", "amount", "merchant", "bank", "class"}

READ THIS BEFORE TRUSTING THE NUMBERS
-------------------------------------
* Column names change between Kaggle uploads. Run --inspect first, then set the
  --*-col flags (or edit COLUMN_MAP) to match YOUR file. The script fails loudly
  if the text column is missing rather than silently emitting blanks.
* Detection PRECISION needs NEGATIVES (OTP / promo / balance / request / …). This
  corpus, as published, is mostly genuine transactions; with no negatives the
  harness can only report RECALL on positives. Pass --with-seed-negatives to
  append the hand-labelled non-transactions from sms_labeled.jsonl so precision
  is meaningful, and say so in the paper (which rows produced which number).
* Fields this script cannot fill (merchant, kind) are written as null; the
  harness skips a field for a row where it is null, so partial labels are fine.
* Nothing here fabricates labels: is_transaction/kind come only from columns you
  point it at, or from an explicit default you choose with --assume-transaction.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

try:  # Windows consoles default to cp1252 and choke on non-ASCII SMS text
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# Best-guess column names — OVERRIDE with CLI flags after running --inspect.
COLUMN_MAP = {
    "text": "message",       # the SMS body
    "label": None,           # transaction vs not (0/1, yes/no); None => use --assume-transaction
    "type": None,            # debit/credit (for `kind`)
    "amount": None,          # transaction amount
    "merchant": None,        # payee / merchant
    "bank": None,            # sender bank
}

_EXPENSE = {"debit", "dr", "spent", "withdrawn", "withdrawal", "paid", "purchase"}
_INCOME = {"credit", "cr", "deposit", "received", "refund"}
_TRUE = {"1", "true", "yes", "y", "transaction", "txn", "financial"}
_FALSE = {"0", "false", "no", "n", "non-transaction", "spam", "otp", "promo"}


def _clean_amount(raw: str | None) -> str | None:
    if not raw:
        return None
    m = re.search(r"[0-9][0-9,]*(?:\.[0-9]+)?", str(raw))
    if not m:
        return None
    return m.group(0).replace(",", "")


def _kind(raw: str | None) -> str | None:
    if not raw:
        return None
    v = str(raw).strip().lower()
    if v in _EXPENSE:
        return "expense"
    if v in _INCOME:
        return "income"
    return None


def _is_txn(raw: str | None, default: bool | None) -> bool | None:
    if raw is None or str(raw).strip() == "":
        return default
    v = str(raw).strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    return default


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("sms_kaggle.jsonl"))
    ap.add_argument("--inspect", action="store_true", help="print header + first row, then exit")
    ap.add_argument("--text-col", default=COLUMN_MAP["text"])
    ap.add_argument("--label-col", default=COLUMN_MAP["label"])
    ap.add_argument("--type-col", default=COLUMN_MAP["type"])
    ap.add_argument("--amount-col", default=COLUMN_MAP["amount"])
    ap.add_argument("--merchant-col", default=COLUMN_MAP["merchant"])
    ap.add_argument("--bank-col", default=COLUMN_MAP["bank"])
    ap.add_argument("--assume-transaction", dest="assume", action="store_true",
                    help="rows with no label column are treated as transactions")
    ap.add_argument("--with-seed-negatives", action="store_true",
                    help="append the hand-labelled non-transactions from sms_labeled.jsonl")
    args = ap.parse_args()

    with args.csv.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        if args.inspect:
            print("columns:", header)
            first = next(reader, None)
            print("sample :", json.dumps(first, ensure_ascii=False, indent=2) if first else "(empty)")
            print("\nNow re-run with --text-col ... and the other --*-col flags to match these.")
            return
        if args.text_col not in header:
            sys.exit(f"text column {args.text_col!r} not in {header}. Use --inspect then --text-col.")

        default = True if args.assume else None
        rows_out, skipped = [], 0
        for row in reader:
            text = (row.get(args.text_col) or "").strip()
            if not text:
                skipped += 1
                continue
            is_txn = _is_txn(row.get(args.label_col) if args.label_col else None, default)
            if is_txn is None:
                sys.exit("no label column and --assume-transaction not set: cannot label "
                         "is_transaction without inventing it. Provide --label-col or --assume-transaction.")
            kind = _kind(row.get(args.type_col)) if (is_txn and args.type_col) else None
            amount = _clean_amount(row.get(args.amount_col)) if (is_txn and args.amount_col) else None
            merchant = (row.get(args.merchant_col) or None) if args.merchant_col else None
            bank = (row.get(args.bank_col) or None) if args.bank_col else None
            rows_out.append({
                "text": text,
                "is_transaction": is_txn,
                "kind": kind,
                "amount": amount,
                "merchant": merchant.strip() if isinstance(merchant, str) else merchant,
                "bank": bank.strip() if isinstance(bank, str) else bank,
                "class": (kind or "transaction") if is_txn else "unlabelled_negative",
            })

    if args.with_seed_negatives:
        seed = Path(__file__).parent / "sms_labeled.jsonl"
        negatives = [json.loads(l) for l in seed.read_text(encoding="utf-8").splitlines()
                     if l.strip() and not json.loads(l)["is_transaction"]]
        rows_out.extend(negatives)

    args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows_out), encoding="utf-8")
    pos = sum(1 for r in rows_out if r["is_transaction"])
    neg = len(rows_out) - pos
    with_merch = sum(1 for r in rows_out if r["is_transaction"] and r["merchant"])
    print(f"wrote {args.out}  —  {len(rows_out)} rows ({pos} transactions, {neg} non-transactions), "
          f"{skipped} blank rows skipped, {with_merch} with a merchant label")
    if neg == 0:
        print("WARNING: no negatives — detection precision is not measurable. "
              "Re-run with --with-seed-negatives, or add non-transaction rows.")
    print(f"Then:  docker compose exec api python -m research.eval_sms   "
          f"(point _DATA at {args.out.name}, or set it in eval_sms.py).")


if __name__ == "__main__":
    main()
