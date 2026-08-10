# Paper skeleton

`expensitor.tex` — an IEEE conference (IEEEtran) skeleton for the system paper,
with the **real measured seed-set numbers** already in the evaluation tables and
every remaining gap marked in red as `[TODO: ...]`.

This is a scaffold, **not a submittable paper.** It gives you correct structure,
honest framing, and the numbers you already have, so you can focus on the parts
only you can produce: real-dataset results, the user study, and verified
citations.

## Compile

**Easiest — Overleaf:** create a project, upload `expensitor.tex`, set the
compiler to pdfLaTeX. It uses the standard `IEEEtran` class (built in).

**Locally** (needs a TeX distribution, e.g. TeX Live / MiKTeX):

```bash
cd paper
pdflatex expensitor.tex
pdflatex expensitor.tex      # second pass resolves references
```

The bibliography is inline (`thebibliography`), so no `bibtex` pass is needed
yet. If you switch to a `.bib` file, add a `bibtex` pass between the two
`pdflatex` runs.

## Before you submit — fill these in

The `[TODO]` markers in the `.tex` are the work that remains. Grouped:

**Must have**
- [ ] Author names, affiliation, email.
- [ ] Re-run `research/eval_sms` on the Kaggle Indian-bank-SMS corpus; update
      Table I and the `N`/`P`/`Q` counts. Real numbers will be lower — report
      them honestly.
- [ ] Re-run `research/eval_receipts` on **ICDAR-2019 SROIE**; update Table II.
      Clean-text 100%s are not credible to a reviewer without this.
- [ ] The repository URL in Reproducibility.

**Strongly expected at a real venue**
- [ ] A user study (N=15–30): SUS + task-completion time (tap-a-reason vs.\
      manual entry). Get institutional consent/ethics approval *before* running.
- [ ] The deterministic-vs-LLM baseline (run your local Ollama through the same
      harness) if you take that framing.

**Integrity — do this, don't skip it**
- [ ] **Verify every citation.** Several references are marked `[TODO: VERIFY]`
      because they were surfaced by a web search and I could not confirm they
      exist. Look each up in **DBLP** / **IEEE Xplore** / the publisher, read
      it, and only then cite it. Delete any you cannot confirm. Citing a paper
      you have not verified is a serious integrity problem and reviewers catch
      it.
- [ ] Remove the `\todo` command definition (and its uses) before submission so
      no red placeholders remain.

## Where the numbers come from

Every non-`[TODO]` number in the tables is produced by the harness in
[`../backend/research/`](../backend/research/README.md) and is reproducible with:

```bash
docker compose exec api python -m research.run_all
```

## Honest note on scope

This skeleton argues the defensible thesis from `research/PUBLISHING.md`: a
privacy-preserving, on-device, deterministic PFM companion, evaluated as a
system. It is written to be *truthful* — it states the rule-based ceiling and the
seed-set limitations plainly, because that honesty is what makes the privacy/
determinism trade-off a credible contribution rather than an excuse. Keep it that
way as you fill it in.
