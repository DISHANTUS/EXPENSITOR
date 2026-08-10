# Evaluation harness

Reproducible offline evaluation of Expensitor's three measurable components:
the bank-SMS parser, the receipt parser, and the adaptive reason-suggestion
ranking. Everything is deterministic (seeded) and runs from the checked-in
datasets against the app's own code — no external services, no network.

```bash
docker compose exec api python -m research.run_all        # all three
docker compose exec api python -m research.eval_sms       # individually
docker compose exec api python -m research.eval_receipts
docker compose exec api python -m research.eval_reasons
```

---

## Results (seed datasets)

### 1. Bank-SMS transaction extraction — `datasets/sms_labeled.jsonl` (51 messages)

| Method | Precision | Recall | F1 | Accuracy |
|---|---|---|---|---|
| **Expensitor (rules)** | **1.000** | 0.871 | **0.931** | 0.922 |
| Baseline: "any ₹ amount = txn" | 0.660 | 1.000 | 0.795 | 0.686 |

Field extraction on correctly-detected transactions (n=27): direction **1.000**,
amount exact-match **1.000**, merchant exact **0.926**. **Zero** false positives
across every non-transaction class (OTP, promo, balance, request, failed,
reminder, scheduled, refund, notice, unrelated).

**Reading:** the value is in *rejection* — perfect precision vs the naive
baseline's 0.66 — at the cost of missing ~13% of real transactions (formats the
rules don't yet cover). That precision/recall trade is the honest headline.

### 2. Receipt extraction — `datasets/receipts_labeled.jsonl` (15 samples)

| Metric | Score |
|---|---|
| Receipt detection F1 | 1.000 |
| Total exact-match | 1.000 (14/14) |
| Merchant exact-match | 1.000 (14/14) |
| Line-item extraction F1 | 0.971 (P 0.944 / R 1.000) |

### 3. Adaptive reason-suggestion ranking — 90-day synthetic history, held-out probes

| Method | Hit@1 | Hit@3 | MRR |
|---|---|---|---|
| **Expensitor (amount-aware)** | **0.667** | **0.778** | **0.731** |
| most-frequent | 0.222 | 0.444 | 0.414 |
| most-recent | 0.222 | 0.444 | 0.407 |
| random | 0.222 | 0.222 | 0.345 |

**Reading:** amount-awareness roughly **triples** Hit@1 over a frequency/recency
baseline. This is the app's most defensible individual contribution.

---

## Honest limitations (state these in the paper — reviewers will find them)

- **Seed datasets are small and hand-labelled.** The SMS/receipt numbers are on
  *clean* text, so they upper-bound real performance. A publishable version must
  re-run against:
  - the public **Kaggle Indian-banking-SMS** corpus (and real inbox messages),
  - **ICDAR-2019 SROIE** for receipt extraction under genuine OCR noise.
  The harness is dataset-agnostic — feed it the same JSONL shape.
- **The reason-ranking eval is synthetic.** It demonstrates the *mechanism* with
  no leakage, but a real logged-usage study (even 15–30 users) is what makes the
  claim land.
- **No live user study here.** Task-completion time and SUS require real
  participants (and, for a formal venue, consent/ethics approval). That is the
  single highest-value addition and cannot be synthesised.
- **The parsers are rule-based**, so they are a strong, explainable, on-device
  baseline — not a claim to beat transformer SOTA on accuracy. The contribution
  is the *system* (deterministic, offline, private), not a new extraction model.

---

## How this maps to a paper

| Paper section | Source |
|---|---|
| Related work | prior art in the repo root README + the venue guide |
| System / method | the app's `intelligence/` and `services/` modules |
| Evaluation | this harness; tables above |
| Reproducibility | seeded datasets + `run_all` in this directory |
| Threats to validity | the limitations above |

See [`PUBLISHING.md`](PUBLISHING.md) for the honest contribution framing, a
vetted venue list, and how to avoid predatory conferences.
