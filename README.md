# 13GEMSDOE — GEMS Prize Challenge working repository

**Live site:** https://buffedlizard55-lab.github.io/13GEMSDOE/
**Competition:** [DOE GEMS Prize on DrivenData](https://www.drivendata.org/competitions/306/competition-doe-gems/) · $300,000 · metric: distance-weighted Tversky index

> **Read [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) at the start of every
> session.** It is the standing brief — goals, non-negotiables, and the
> operating rules this project is built against. This README is the map; the
> charter is the mission. The verbatim brief is reproduced in full at the
> bottom of this file so that this page is self-contained.

---

## The 60-second orientation

| Question | Answer | Where |
|---|---|---|
| What is the metric, really? | A **distance-weighted F2 score**. `DTI = 1/(0.2/P + 0.8/R)`. Proved, not asserted. | [`reports/metric_audit.json`](reports/metric_audit.json) |
| Why were we stuck at 0.1563? | Mostly a **measurement artefact** — the leaderboard shows *best-ever* per account, and three accounts all read 0.1563. Two maps reported as 0.1563 share only 6.7 % of their support. | [Irregularity I‑3](knowledge/02_irregularities.md) |
| Why is *every* submission ≈ chance? | The chance DTI curve peaks at **0.145 near 5 % coverage**; our plateau of 0.1563 sits on it. The detector contributed ~10 %. | [Irregularity I‑9](knowledge/02_irregularities.md) |
| What should a submission look like? | **Binary, inclusive, and strike-decimated.** Any block of predictions with weighted precision above `0.2 × DTI` (≈ **3 %** today) raises the score. | [`knowledge/01_verified_facts.md` §2.1](knowledge/01_verified_facts.md) |
| How do we know an idea works before we spend a submission slot? | The **hide-and-recover holdout**: withhold whole fault systems, rebuild features from what remains, mask the rest pixel-exactly, score DTI on the withheld pixels alone under 5 withholding rules — *and* on the concealed subset. | [`src/gems/holdout.py`](src/gems/holdout.py) |
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
  detectors.py            the physical-signature detectors (H-A..H-E, R6-*, R7-*)
  rio.py                  raster I/O + the strict submission validator
scripts/
  fetch_data.py           reconstruct data/raw from official + mirrored sources
  audit_metric.py         proves the four results above
  audit_bands.py          measures what the 19 bands actually are; tests I-2
  analyze_scored.py       forensics on our previously-scored submissions
  chance_baseline.py      the random-map control every DTI must be read against
  build_detectors.py      compute and cache every detector map
  run_holdout.py          the v1 sweep
  run_holdout2.py         the v2 sweep (concealed subset, grid decimation)
  run_holdout3.py         the v3 sweep: R7 detectors + per-fold catalogue rebuild
  summarize_holdout.py    lift-over-chance verdict
  validate_composite.py   two-regime validation of the shipped hedge
  make_submission.py      build + validate + package a submission
reports/                  machine-readable evidence for every claim
docs/                     the GitHub Pages site (no build step)
```

---

## Latest review (2026-09-29, session 2)

`data/` **is** present in this session (recovered from this group's own public
repositories via `scripts/fetch_data.py`, blob SHAs pinned in
`reports/data_manifest.json`), so the full pipeline ran end to end:

* `scripts/audit_metric.py` → **ALL CHECKS PASSED** (12/12).
* `scripts/audit_bands.py` → **new**. Measures the 19 bands, and **disproves
  I-2's "band 6 is the radiometric total count" reading**: band 6 is bounded in
  [2.95°, 88.57°] with p99 = 29.1°, is smoother than the gradient bands it
  would have to differentiate, and matches none of eight standard magnetic edge
  angles (all |r| < 0.04). Band 6 is **UNIDENTIFIED**. It also settles that
  bands 10/16 are density-like, not distance-like, so `HD_strain` is not
  inverted.
* `scripts/build_detectors.py` → 21 detector maps, 426 s.
* `scripts/run_holdout3.py` → the R7 hypotheses, with catalogue-dependent
  detectors rebuilt per fold (fixing the `R6_horse_full` / `HD_strain` leak,
  irregularity I-12).
* `scripts/make_submission.py --recipe …` → validated GeoTIFF, all-finite twin,
  zip, and the exact Note to paste into the DrivenData form.

**Honest status.** No candidate on the hide-and-recover holdout beats a random
map of the same size by a wide margin under every withholding rule. The only
regime with real, large lift is **tip extension / correction of mapped traces**
(13.9–16.1× chance), which the organizers explicitly named. The full-system
withholding regime remains at ~1.0× chance for every detector including the new
R7 ones. See [`reports/holdout_verdict.json`](reports/holdout_verdict.json) and
the [Hypotheses page](docs/hypotheses.html).

---

## Reproduce everything

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install numpy scipy rasterio

python scripts/fetch_data.py        # data/raw (419 MB, gitignored)
python scripts/audit_metric.py      # proves the metric results
python scripts/audit_bands.py       # what the 19 bands actually are
python scripts/analyze_scored.py    # why 0.1563 repeated
python scripts/build_detectors.py   # ~7 min
python scripts/run_holdout3.py      # the sweep (~20 min, 3 GB RAM)
python scripts/make_submission.py --recipe best
```

`make_submission.py` refuses to emit a file unless
`validate_submission` passes: single-band float32, EPSG:32611, 3730×3292, exact
geotransform, and **every finite value inside [0, 1]** — the check that the
rejected submission failed. Every submission is written twice, NaN-outside and
all-finite, because DrivenData's range validator rejects NaN.

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
4. **Never report a DTI without the chance DTI at the same pixel count beside
   it.** `scripts/summarize_holdout.py` enforces this.
5. **Phase 2 is 83 % of the money** and its labels are built from *our own*
   predictions by expert review. A defensible, geologically-argued map is worth
   more than a leaderboard-tuned one.

---

# STANDING BRIEF — verbatim, read at the start of every session

> Audit the score before the model. Because the official FN_w equals |G| − TP_w,
> the distance-weighted Tversky index (DTI) reduces to
> TP_w / (0.2·TP_w + 0.2·FP_w + 0.8·|G|). That is a weighted harmonic mean of
> weighted recall (weight 0.8) and weighted precision (weight 0.2). Confirm it
> against the problem page's worked example (TP_w 3.00, FP_w 1.89, FN_w 2.00 →
> 0.60) and our local metric. Three consequences to test:
>
> A block of predictions raises the score only if its marginal weighted
> precision, ΔTP_w / (ΔTP_w + ΔFP_w), exceeds 0.2 × the current DTI. The best
> map is therefore probably far more inclusive than a calibrated 0.5 cutoff.
>
> Scaling all values up toward 1 always raises DTI, so the optimum is probably
> near-binary, with graded values useful mainly for ranking pixels.
>
> A relative gain in recall outweighs the same relative gain in precision
> whenever precision exceeds a quarter of recall. Settle "precision versus
> coverage" numerically rather than by assertion.
>
> Choose the cutoff, line spacing, ridge width and detector fusion by maximizing
> expected DTI on the holdout. TP_w takes a max over the 300 m neighborhood, so
> redundant nearby predictions add false-positive mass without extra credit.
>
> Rebuild validation around what the organizers have said officially. As of
> Sept 27, 2026, the DrivenData organizer on the forum (chrisk-dd) has stated
> four things:
>
> Known USGS/INGENIOUS fault pixels are masked from scoring in both rounds,
> using a pixel-exact mask identical to the training labels.
>
> A predicted pixel just beside a known trace is still fully penalized unless it
> is near a new-fault pixel.
>
> New-fault pixels can lie within 300 m of known traces.
>
> "New fault" means any fault pixel not already captured, including extensions,
> splays, parallel strands and corrections.
>
> These are in the "Scoring clarification" and "Where do you draw the line?"
> threads. The organizers declined to say which data or fault types the test
> faults came from, so any belief about how they were labeled is a hypothesis.
>
> Build a hide-and-recover holdout that mirrors this:
>
> Withhold whole fault segments or systems, with a buffer.
> Derive every catalogue-based feature only from what stays visible.
> Mask the visible faults exactly as described.
> Score DTI on the withheld pixels alone, under several withholding rules
> (random, short, isolated, and by age or slip-rate class where attributes
> exist). Flag any idea that wins under only one rule as fragile.
>
> Keep geographic block CV as a stress test, not the main check. The submission
> shares the training features' bounds and the test sets are chunks of the same
> region, so the real shift is unmapped faults among mapped ones, not new
> geography. Nothing gets a weekly submission slot until it beats the current
> best on this holdout.
>
> We need to figure out why we keep scoring 0.1563, are we copying the same work
> over and over again? we need to come up with different ideas, and not just the
> same idea tried a different way. Need to figure out why 5GEMSDOE and GEMSDOE1
> have the same score. We should not be generating the same score submissions,
> they should all be unique.
>
> Before implementing, generate 3–5 candidate geological hypotheses we haven't
> tried yet, each naming: the specific layer(s) involved, the physical signature
> being targeted (e.g., an edge-detection or curvature transform), why it should
> catch a fault missing from the USGS/INGENIOUS catalogue rather than one
> already in it, and how it differs from anything already implemented in this
> repo. Rank them by expected DTI improvement and implementation cost. Validate
> the top candidate on our spatially-blocked holdout set before touching a
> weekly submission slot — do not spend a submission slot on an idea that hasn't
> beaten the current holdout best. If a candidate can't be validated without new
> external data, name the specific free, official source needed and check it's
> obtainable before proposing the idea as viable.
>
> Work line by line verifying from official verified trusted sources, provide
> links for manual review. There should be no manual input, work on your own to
> complete tasks. Flag any irregularities for review. No hallucinations.
>
> The goal of this project is to get a full list that follow our requirements.
> No hallucinations. Verify line by line.
>
> We need to start doing heavy and deep research into the part of the project
> that matters the most, which is the scientific discovery of geothermal vents.
> We should store all of our information and knowledge that we can gather from
> official verified sources. This will serve as a starting point for other
> projects as well. We need to think outside the box but still be grounded in
> proper scientific research, we are ultimately aiming for a top prize that many
> others are competing for. So it's important to be contrarian but be smart
> about it. We need to find sources of data that others are overlooking or areas
> of the project when it comes to geothermal vents.
>
> 0.3049 is the highest score right now so we need to design a new strategy,
> research, testing, analyzing, and generating submission system than the
> current website. It should be unique, take unique approaches to generating a
> submission that can score higher than .3049.
>
> Put this prompt into the repo readme and read it everytime we work on the
> project as a starting point to make sure we are building what we are aiming
> for and have a strong base to continue building and improving on making
> something useful for everyday use. It should solve the problem of having to
> manually check everything ourselves and having an up to date current feed.
>
> We need to focus on being able to generate a submission into the competition.
> The site should be able to generate a TIF file that is required for
> submission. It should be as easy as download to click a File to submit into
> the competition. This needs to be in the executive summary or the very
> beginning of the site. it should be obvious when you visit the site.
>
> I tried to submit the document that i downloaded from the site but it returned
> this error on the submission form: "Predicted values must be in range [0, 1]".
> Also we need to give it a unique name and A short comment to help you or your
> team tell submissions apart later e.g. clustering with k=25.
>
> Create a executive summary subpage that explains exactly how to make a
> submission into the contest.
>
> The goal of this project is to place top of the leaderboard in this
> competition. We need to understand the problem, collect all the data and
> organize it into a clean easily auditable table with official verified links
> for manual verification.
>
> Our Core Values: **Maximize P(Win)** — in every decision, weigh tradeoffs,
> assess risk, and choose the path that maximizes the probability of success.
> **Own the Outcome** — own results end to end, not just an individual slice;
> when problems arise and we have the means to act, act without waiting for
> permission; treat failure and success as signals.
