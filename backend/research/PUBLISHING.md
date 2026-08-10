# Publishing guide (honest edition)

Written to help you target a **legitimate** IEEE/Springer venue and avoid the
much larger number of junk ones. Read the "what not to claim" and "predatory"
sections before anything else — they matter more than the venue list.

---

## 1. The contribution — what to claim, and what not to

**Do not claim** (reviewers will reject these on sight; the prior art is deep):
- "A novel expense tracker" / "an AI finance app." Hundreds exist.
- "Novel SMS transaction extraction." There is a named IEEE paper on exactly
  this (Kumar et al., *Rule-based transaction extraction from bank SMS alerts*,
  IEEE ICACCI 2019) and commercial products.
- "Novel receipt OCR." ICDAR-2019 SROIE and transformer models own this; a
  regex parser does not advance it.

**Do claim one sharp thesis** — the honest, defensible framings, strongest first:

1. **A privacy-preserving, on-device, deterministic personal-finance companion.**
   The novelty is architectural and empirical: everyone else is cloud + LLM +
   pooled data; this is offline-capable, explainable, no cloud OCR, no bank API,
   no shared model — evaluated for accuracy, latency, and offline behaviour.
   *This is your best shot.* It reframes "not SOTA accuracy" as a deliberate,
   measured trade for privacy and explainability.

2. **Amount-aware adaptive reason suggestion.** Your most genuinely new *method*.
   The ranking (amount-gate + recency-weighted frequency) triples Hit@1 over
   frequency/recency baselines. Small, but real and cleanly evaluated. Best as a
   *component* of framing (1), or a short/workshop paper on its own.

3. **A comparative study: deterministic vs LLM assistants for personal finance.**
   Accuracy, cost, latency, privacy, explainability. Needs you to actually run
   the LLM baseline (your local Ollama) through the same harness.

Whichever you pick, the paper is a **system + evaluation** paper, not a new-model
paper. That is a legitimate, accepted genre — if the evaluation is real.

---

## 2. What you still need before submitting

- **Real data, not just the seed sets.** Re-run `eval_sms` on the Kaggle
  Indian-bank-SMS corpus + your own inbox; `eval_receipts` on ICDAR-2019 SROIE.
  Report the numbers under real noise (they will drop — that's fine and honest).
- **An LLM baseline** through the same harness (framing 3, and strengthens 1).
- **A user study** — the single biggest lift. Even 15–30 participants: SUS
  score, task-completion time for "record a spend" (tap-a-chip vs type), and a
  short questionnaire. For a formal venue you likely need institutional consent /
  ethics sign-off — start that early.
- **Threats to validity** written honestly (small N, synthetic ranking eval,
  rule-based ceiling).

---

## 3. ⚠️ Predatory venues — the real risk

Far more "IEEE/Springer" conferences are junk than are reputable. A paper in a
predatory venue is worse than no paper — it signals you can't tell the
difference. Both IEEE and Springer *host* excellent venues and also lend their
names to low-selectivity ones.

**Red flags (walk away if you see these):**
- Unsolicited email invitations, flattering and urgent.
- Very broad, "multidisciplinary" scope; a call that would accept anything.
- Review turnaround of days; near-100% acceptance; "guaranteed publication."
- Registration fee emphasised over the science.
- No genuine, verifiable program committee.
- Not indexed in **Scopus**, **DBLP**, or **IEEE Xplore**.

**Verify every venue before submitting:**
- Use **Think · Check · Submit** (thinkchecksubmit.org).
- Check the venue/series is in **DBLP** (dblp.org) and **Scopus**.
- For journals, check they are **not** on Beall's list and **are** in the DOAJ
  (if open access) or a recognised index.
- Look up the **actual acceptance rate** and program committee names.

---

## 4. Legitimate venue candidates (verify current status yourself)

Reputable homes for a well-evaluated applied/systems paper. Selectivity and
relevance vary — confirm each is still indexed and reputable at submission time.

**IEEE (conferences):**
- IEEE **COMPSAC** (software & applications) — solid, applied-systems friendly.
- IEEE **CCNC** (consumer communications & networking) — good for a mobile
  consumer app with a systems/HCI angle.
- IEEE **TENCON**, IEEE **INDICON** — reputable regional conferences; realistic
  for a strong student paper.
- IEEE **BigData** / **ICDM** workshops — if you lean into the pattern/behaviour
  analytics.

**Springer:**
- **SN Computer Science** (journal) — indexed, reasonable bar, accepts applied
  systems work. A realistic target for a journal-length version.
- Springer **LNCS / LNNS / CCIS** proceedings — *only* for conferences you have
  independently verified are DBLP/Scopus-indexed and selective. Many
  LNNS/AISC-published Indian conferences are low-selectivity — check carefully.

**If you add a real user study**, HCI venues (ACM IUI, MobileHCI) fit the
companion/UX angle better — different publisher, often higher impact for this
kind of work.

**Honest expectation:** with framing (1) + real datasets + a small user study,
a mid-tier IEEE conference or SN Computer Science is realistic. A top-tier
journal or CHI/UbiComp is not, on the current scope. That is not a failure — a
clean, honest, reproducible paper in a real venue is a genuinely good outcome
for a student project, and the reproducible harness here is a real asset most
student submissions lack.

---

## 5. Submission checklist

- [ ] One sharp thesis (§1), stated in the abstract and intro.
- [ ] Related-work section that *cites the prior art honestly* (repo README has
      the leads) and positions the contribution against it.
- [ ] Evaluation on real datasets (Kaggle SMS, SROIE), not just the seed sets.
- [ ] Baselines + ablation (this harness) and, ideally, an LLM comparison.
- [ ] A user study with ethics/consent if the venue expects one.
- [ ] Threats to validity, stated plainly.
- [ ] Reproducibility: point to this `research/` harness and the seeded datasets.
- [ ] Venue verified via Think·Check·Submit + DBLP/Scopus.
- [ ] No inflated claims; the honest framing is the credible one.
