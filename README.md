# 13GEMSDOE — GEMS Prize Challenge working repository

**Live site:** https://buffedlizard55-lab.github.io/13GEMSDOE/
**Competition:** [DOE GEMS Prize on DrivenData](https://www.drivendata.org/competitions/306/competition-doe-gems/) · $300,000 · metric: distance-weighted Tversky index

> **Read [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) at the start of every
> session.** It is the standing brief — goals, non-negotiables, and the
> operating rules this project is built against. This README is the map; the
> charter is the mission.

---

## The 60-second orientation

| Question | Answer | Where |
|---|---|---|
| What is the metric, really? | A **distance-weighted F2 score**. `DTI = 1/(0.2/P + 0.8/R)`. Proved, not asserted. | [`reports/metric_audit.json`](reports/metric_audit.json) |
| Why were we stuck at 0.1563? | Mostly a **measurement artefact** — the leaderboard shows *best-ever* per account, and three accounts all read 0.1563. Two maps reported as 0.1563 share only 6.7 % of their support. | [Irregularity I‑3](knowledge/02_irregularities.md) |
| What should a submission look like? | **Binary, inclusive, and strike-decimated.** Any block of predictions with weighted precision above `0.2 × DTI` (≈ **3 %** today) raises the score. | [`knowledge/01_verified_facts.md` §2.1](knowledge/01_verified_facts.md) |
| How do we know an idea works before we spend a submission slot? | The **hide-and-recover holdout**: withhold whole fault systems, rebuild features from what remains, mask the rest pixel-exactly, score DTI on the withheld pixels under 5 withholding rules. | [`src/gems/holdout.py`](src/gems/holdout.py) |
| How do I actually submit? | Open the site → the download button is the first thing on the page. | [Executive summary](docs/executive_summary.html) |

---

## The four results that should drive every decision

All four are machine-verified in `scripts/audit_metric.py` (`ALL CHECKS PASSED`)
and reproduce the organizers' own worked example (TP_w 3.00, FP_w 1.89,
FN_w 2.00 → 0.60).

1. **`FN_w ≡ |G| − TP_w`**, so `DTI = TP_w / (0.2·TP_w + 0.2·FP_w + 0.8·|G|)`
   and equivalently `DTI = 1/(0.2/P_w + 0.8/R_w)`. Since `β² = 4`, **DTI is a
   distance-weighted F2 score.**
2. **Inclusion rule.** A block of predictions raises the score **iff** its
   marginal weighted precision exceeds `0.2 × DTI`. At our 0.1563 that is
   **3.1 %**; at the leaderboard leader's 0.3168 it is **6.3 %**. A 0.5
   probability cutoff throws away enormous amounts of score.
3. **Binary is optimal.** `DTI(c·p) = TP/(0.2TP + 0.2FP + 0.8|G|/c)` strictly
   increases in `c`, and a pixel exactly on truth has `k(0)=1` so it costs zero
   FP mass. Graded values are only useful for *ranking* pixels.
4. **Recall dominates** whenever `P_w > 0.25 · R_w`. Elasticities always sum
   to 1, so this is a hard crossover, not a heuristic.

**Geometry corollary.** `TP_w` takes a **max** over the 300 m neighbourhood, so
a second predicted pixel within 3 px of the first earns *no* extra credit while
paying full FP mass. Thick ridges and 100 m-spaced lines are waste; the
efficient primitive is a **1-px line decimated to ~300 m spacing**. This is
swept, not assumed — see `--spacing` in the holdout results.

---

## Repository layout

```
PROJECT_CHARTER.md        standing brief — read first, every session
knowledge/
  01_verified_facts.md    every fact with the official URL it came from
  02_irregularities.md    things that are wrong or unverifiable, with actions
  03_hypotheses.md        candidate geological hypotheses, ranked
src/gems/
  metric.py               the official DTI, transcribed and audited
  fastscore.py            exact fast scorer (verified == metric.py)
  holdout.py              hide-and-recover fold construction
  detectors.py            the physical-signature detectors
  rio.py                  raster I/O + the strict submission validator
scripts/
  fetch_data.py           reconstruct data/raw from official + mirrored sources
  audit_metric.py         proves the four results above
  analyze_scored.py       forensics on our previously-scored submissions
  build_detectors.py      compute and cache every detector map
  run_holdout.py          the sweep: detector x coverage x spacing x fold
  make_submission.py      build + validate + package a submission
reports/                  machine-readable evidence for every claim
docs/                     the GitHub Pages site (no build step)
```

---

## Reproduce everything

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install numpy scipy rasterio

python scripts/fetch_data.py        # data/raw (418 MB, gitignored)
python scripts/audit_metric.py      # proves the metric results
python scripts/analyze_scored.py    # why 0.1563 repeated
python scripts/build_detectors.py   # ~2 min
python scripts/run_holdout.py       # the sweep
python scripts/make_submission.py --recipe best
```

`make_submission.py` refuses to emit a file unless
`validate_submission` passes: single-band float32, EPSG:32611, 3730×3292, exact
geotransform, and **every finite value inside [0, 1]** — the check that the
rejected submission failed.

---

## Standing rules for this project

1. **No submission slot is spent on an idea that has not beaten the current
   best on the hide-and-recover holdout.** Three submissions per week, total
   ([Official Rules §3.2](https://docs.nlr.gov/docs/fy26osti/96647.pdf)).
2. **A candidate that wins under only one withholding rule is fragile** and is
   reported as such. `make_submission.py --recipe best` selects on the
   *worst-case* rule, not the mean.
3. **Every factual claim carries the official URL it came from.** If it cannot
   be verified from a public official source, it goes in
   `knowledge/02_irregularities.md` marked `UNVERIFIED`, not into the analysis.
4. **Phase 2 is 83 % of the money** and its labels are built from *our own*
   predictions by expert review. A defensible, geologically-argued map is worth
   more than a leaderboard-tuned one.
