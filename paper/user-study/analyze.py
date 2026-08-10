"""Turn collected study data into the numbers the paper reports.

    python paper/user-study/analyze.py paper/user-study/data.csv

Reads the CSV (same columns as data_template.csv), computes:
  - SUS score per participant and the mean (with the standard adjective band),
  - task-time mean/median/SD per condition and the % reduction,
  - a paired t-test on the per-participant time difference.

Rows whose participant_id starts with "EXAMPLE" are ignored, so you can run it
against the template to see the format before you have real data. Pure standard
library — no dependencies. If SciPy is available it is used for an exact p-value;
otherwise the t-statistic and df are reported for you to look up.
"""

from __future__ import annotations

import csv
import math
import statistics
import sys
from pathlib import Path


def sus_score(responses: list[int]) -> float:
    """Standard SUS: odd items (1,3,5,7,9) score r-1; even items score 5-r;
    sum x 2.5 -> 0..100."""
    if len(responses) != 10:
        raise ValueError("SUS needs exactly 10 responses (q1..q10)")
    total = 0
    for i, r in enumerate(responses):
        total += (r - 1) if i % 2 == 0 else (5 - r)
    return total * 2.5


def band(sus: float) -> str:
    if sus >= 80.3:
        return "A (excellent)"
    if sus >= 68:
        return "above average"
    if sus >= 51:
        return "below average"
    return "poor"


def paired_t(diffs: list[float]) -> tuple[float, int, float | None]:
    """Return (t, df, p-or-None). p is exact if SciPy is present."""
    n = len(diffs)
    if n < 2:
        return (float("nan"), 0, None)
    mean = statistics.fmean(diffs)
    sd = statistics.stdev(diffs)
    t = mean / (sd / math.sqrt(n)) if sd > 0 else float("inf")
    df = n - 1
    p = None
    try:
        from scipy import stats  # type: ignore
        p = float(stats.t.sf(abs(t), df) * 2)  # two-tailed
    except Exception:
        pass
    return (t, df, p)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python analyze.py <data.csv>")
        raise SystemExit(2)

    rows = []
    with Path(sys.argv[1]).open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("participant_id") or "").upper().startswith("EXAMPLE"):
                continue
            rows.append(row)

    if not rows:
        print("No real participant rows found (EXAMPLE rows are ignored).")
        print("Fill data.csv with your collected data and re-run.")
        return

    sus_scores, manual, tap, diffs = [], [], [], []
    for r in rows:
        sus_scores.append(sus_score([int(r[f"q{i}"]) for i in range(1, 11)]))
        m, t = float(r["manual_time_s"]), float(r["tap_time_s"])
        manual.append(m)
        tap.append(t)
        diffs.append(m - t)

    n = len(rows)
    print(f"\nUser study — {n} participants\n")

    sus_mean = statistics.fmean(sus_scores)
    sus_sd = statistics.stdev(sus_scores) if n > 1 else 0.0
    print(f"SUS score:  mean {sus_mean:.1f}  (SD {sus_sd:.1f})  -> {band(sus_mean)}")

    print("\nTask time (seconds to record a spend)")
    print(f"  {'condition':<18}{'mean':>8}{'median':>8}{'SD':>8}")
    for name, xs in (("manual entry", manual), ("tap suggestion", tap)):
        sd = statistics.stdev(xs) if n > 1 else 0.0
        print(f"  {name:<18}{statistics.fmean(xs):>8.2f}{statistics.median(xs):>8.2f}{sd:>8.2f}")

    reduction = (statistics.fmean(manual) - statistics.fmean(tap)) / statistics.fmean(manual) * 100
    print(f"\n  reduction with suggestions: {reduction:.1f}%")

    t, df, p = paired_t(diffs)
    if p is not None:
        print(f"  paired t-test: t({df}) = {t:.3f}, p = {p:.4f}  "
              f"({'significant' if p < 0.05 else 'not significant'} at α=0.05)")
    else:
        print(f"  paired t-test: t({df}) = {t:.3f}  "
              f"(install scipy for an exact p, or look up t-critical for df={df})")
    print("\nReport ALL of these honestly, including a non-significant result.\n")


if __name__ == "__main__":
    main()
