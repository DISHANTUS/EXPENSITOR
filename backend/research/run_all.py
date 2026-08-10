"""Run every evaluation and print the combined results.

    docker compose exec api python -m research.run_all

Produces the tables that go straight into the paper's Evaluation section.
Everything is deterministic (seeded) and reproducible from the checked-in
datasets and the app's own parser/ranking code — no external services.
"""

from __future__ import annotations

import asyncio
import logging

logging.disable(logging.INFO)

from research import eval_receipts, eval_reasons, eval_sms  # noqa: E402


def main() -> None:
    print("=" * 68)
    print("Expensitor — reproducible evaluation")
    print("=" * 68)
    eval_sms.main()
    eval_receipts.main()
    asyncio.run(eval_reasons.main())
    print("=" * 68)
    print("Notes: SMS/receipt numbers are on hand-labelled seed sets; for a paper,")
    print("extend with the Kaggle Indian-bank-SMS corpus and ICDAR-2019 SROIE to")
    print("report under real OCR/format noise. Reason-ranking is a seeded synthetic")
    print("held-out eval; a real-usage log would strengthen it further.")
    print("=" * 68)


if __name__ == "__main__":
    main()
