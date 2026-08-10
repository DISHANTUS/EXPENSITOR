# System Usability Scale (SUS)

The standard 10-item SUS (Brooke, 1996). Ask each participant to rate every
statement from **1 = Strongly disagree** to **5 = Strongly agree**. Record the
raw 1–5 responses as `q1`…`q10` in `data.csv`; `analyze.py` does the scoring.

> Cite SUS properly in the paper: J. Brooke, "SUS: A quick and dirty usability
> scale," in *Usability Evaluation in Industry*, 1996. (Verify the exact
> reference in your citation manager.)

1. I think that I would like to use this system frequently.
2. I found the system unnecessarily complex.
3. I thought the system was easy to use.
4. I think that I would need the support of a technical person to be able to use this system.
5. I found the various functions in this system were well integrated.
6. I thought there was too much inconsistency in this system.
7. I would imagine that most people would learn to use this system very quickly.
8. I found the system very cumbersome to use.
9. I felt very confident using the system.
10. I needed to learn a lot of things before I could get going with this system.

**Scoring (handled by the script):** odd items score (response − 1); even items
score (5 − response); sum, multiply by 2.5 → a 0–100 score. ~68 is average;
>80 is good; <50 is poor.
