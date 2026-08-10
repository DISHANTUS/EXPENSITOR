# How to submit — master checklist

Everything that can be pre-made is in this repo. This file is the ordered path
from "skeleton" to "submitted," separating what's **ready** from what only **you**
can do (identity, real data, real participants, verification).

## What's already made for you
- `expensitor.tex` — IEEE conference skeleton with your real seed-set numbers.
- `references.bib` — bibliography (entries to verify + placeholders).
- `cover-letter.md` — editor cover-letter template.
- `user-study/` — protocol, consent form, SUS questionnaire, data template, and
  `analyze.py` (turns collected data into the reported numbers).
- `../backend/research/` — the evaluation harness and `PUBLISHING.md` (venue
  list + predatory-venue warning).

## What only you can do (and why I can't)
These require your identity, your institution, real people, or real data. I will
not fabricate any of them — a made-up study or result would be research
misconduct and get the paper retracted.

1. **Author + affiliation** in `expensitor.tex`.
2. **Verify every citation** (see below).
3. **Real-dataset results** — re-run the harness on real data.
4. **User study** — run it with real participants + ethics approval.

## Step-by-step

### 1. Pick and verify the venue
Use `../backend/research/PUBLISHING.md`. Confirm the venue is indexed
(DBLP/Scopus/IEEE Xplore) and not predatory via **Think · Check · Submit**
(thinkchecksubmit.org). Note its **page limit**, **format** (IEEE vs. Springer
LNCS), and **deadline** before writing more — they change the template.

### 2. Get the real numbers
- **SMS:** download the Kaggle Indian-bank-SMS corpus, convert to the
  `{text, is_transaction, kind, amount, merchant, class}` JSONL shape, drop it
  in `backend/research/datasets/`, and re-run `eval_sms`. Update Table I.
- **Receipts:** register for **ICDAR-2019 SROIE**, convert to the
  `{text, merchant, total, items[]}` shape, re-run `eval_receipts`. Update
  Table II. (Clean-text 100%s are not credible without this.)
- Keep the seed-set numbers only as a secondary "controlled-input" row if useful.

### 3. Run the user study
Follow `user-study/protocol.md`. Get ethics approval **first**. Collect into
`user-study/data.csv`, then:
```bash
python paper/user-study/analyze.py paper/user-study/data.csv
```
Put the SUS score and task-time results into the paper's user-study subsection.

### 4. Verify citations
Open `references.bib`. Every entry marked `VERIFY` was surfaced by a web search
and is **unconfirmed** — look each up in DBLP / IEEE Xplore / the publisher,
read it, correct the fields, and **delete any you cannot confirm**. Do not cite
a paper you have not read.

### 5. Finalise the manuscript
- Fill all `[TODO]` markers; remove the `\todo` command definition so no red
  text remains.
- Fit the page limit; move detail to the harness/repo if over.
- Add an author bio/photo block only if the venue requires it.
- Spell-check; check every table/figure is referenced in the text.

### 6. Produce the submission PDF
- **IEEE:** generate the camera-ready-checkable PDF through **IEEE PDF eXpress**
  (the venue gives you a conference ID). It validates fonts/format.
- **Springer:** follow the venue's LNCS instructions; use the Springer template
  if required (the content ports over; the class differs).

### 7. Submit
- Create an account on the venue's system (usually **EDAS**, **CMT**, or
  **EasyChair**).
- Upload the PDF, the title/abstract/keywords, author list, and the topics.
- Attach the [cover letter](cover-letter.md) if requested.
- Declare any conflicts and confirm originality.

### 8. After submission
- Keep the reproducibility artefacts (this repo) linked and public — it's a real
  strength.
- Expect reviews in weeks–months; be ready to revise. Reviewers will probe the
  small N, the rule-based ceiling, and the datasets — the honest framing already
  in the paper is your defence.

## Integrity reminders
- No fabricated data, results, participants, or citations. Ever.
- Report non-significant or lower-than-hoped numbers honestly.
- Disclose that suggestions/history were seeded for the study.
- If you used any AI tools in the work, follow the venue's disclosure policy.
