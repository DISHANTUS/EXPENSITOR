# User-study protocol

A small, defensible study to support the paper's usability claim. Designed to be
runnable by one student with a phone and 15–30 volunteers, and to produce exactly
the two numbers reviewers expect: a **SUS** usability score and a **task-time**
comparison (tap-a-suggested-reason vs. manual entry).

> **Ethics first.** Before recruiting anyone, check your institution's
> requirement for human-subjects research. Many student projects need an
> ethics/IRB waiver or approval even for a low-risk usability test. Get this in
> writing *before* you collect data, and keep it — reviewers and your advisor
> will ask. Use the [consent form](consent-form.md) with every participant.

## Research question
Does amount-aware reason suggestion reduce the effort of recording a recurring
expense, and is the app usable overall?

## Participants
- **N = 15–30** (state the exact number). Convenience sampling (classmates,
  friends) is acceptable for a system paper if you report it as a limitation.
- Record only: age range, whether they currently use any expense app
  (yes/no), and a participant ID. **No names in the data file.**

## Design
Within-subjects (each participant does both conditions), so each person is their
own control — this is what gives a small N statistical power.

- **Condition A (baseline):** record a spend by typing the reason manually.
- **Condition B (Expensitor):** record the same spend by tapping a suggested
  reason chip.
- **Counterbalance:** half the participants do A then B, half do B then A
  (alternate by participant ID) to cancel out learning effects.

## Procedure (≈10 min per participant)
1. Consent form signed.
2. 1-minute orientation: show them the add-expense screen once.
3. **Warm-up:** to make suggestions meaningful, pre-load ~10 realistic spends
   for the test account (e.g. chai ₹50, lunch ₹120, bus ₹15 across recent days)
   so the reason chips are populated. State this seeding in the paper.
4. **Task, condition A:** "Record that you spent ₹50 on chai" — by typing.
   Start a timer when they tap the amount field; stop when the expense saves.
5. **Task, condition B:** same spend, but tapping the suggested chip. Time it
   the same way.
6. Repeat steps 4–5 for 2–3 different spends (e.g. ₹120 lunch, ₹15 bus) and
   average the times per condition per participant.
7. Participant fills the [SUS questionnaire](sus-questionnaire.md) (10 items).
8. Optional: one open question — "anything confusing or missing?" — for
   qualitative colour in the paper.

## Measures (recorded per participant, see `data_template.csv`)
- `manual_time_s`, `tap_time_s` — mean seconds to record, per condition.
- `q1`…`q10` — SUS item responses (1–5).
- Demographics: `age_range`, `uses_expense_app`.

## Analysis
Run the provided script over the filled CSV:

```bash
python paper/user-study/analyze.py paper/user-study/data.csv
```

It reports the mean SUS score (0–100, with the standard interpretation band),
mean/median task times per condition, the percentage reduction, and a paired
t-test on the per-participant time difference. Report all of these, including the
p-value, honestly — a non-significant result is still a real result at small N.

## What to write in the paper
- Exact N, sampling method, seeding, and counterbalancing.
- SUS score with its adjective band; task-time means with the % reduction and
  the significance test.
- Threats: convenience sample, small N, single session, familiarity effects.
  State them plainly (the paper skeleton already has a Threats section).
