# 13GEMSDOE — GEMS Prize Challenge working repository

**Submission site (download-first hero, executive summary, evidence, sources):**
https://buffedlizard55-lab.github.io/13GEMSDOE/docs/
**Repository front page rendered by Pages (this README):**
https://buffedlizard55-lab.github.io/13GEMSDOE/
**Competition:** [DOE GEMS Prize on DrivenData](https://www.drivendata.org/competitions/306/competition-doe-gems/) · $300,000 · metric: distance-weighted Tversky index

> **Read [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) at the start of every
> session.** It is the standing brief — goals, non-negotiables, and the
> operating rules this project is built against. This README is the map; the
> charter is the mission. The verbatim brief is reproduced in full at the
> bottom of this file so that this page is self-contained.

---

## Latest review — 2026-09-30, session 5 (R11: first holdout WIN)

**Download:** [`docs/downloads/13gems-r11-greedy-mp.tif`](docs/downloads/13gems-r11-greedy-mp.tif)
(zip: `13gems-r11-greedy-mp.zip`; range-error fallback: `13gems-r11-greedy-mp_allfinite.tif`).
Form name `13gems-r11-greedy-mp`; the note is printed on the
[site front page](https://buffedlizard55-lab.github.io/13GEMSDOE/docs/) and in
[`reports/latest_submission.json`](reports/latest_submission.json).

**Why the group kept getting 0.1563.** Settled as far as public data allows (I-3): the GEMSDOE1 and
8GEMSDOE 0.1563-labelled files are *different* maps (positive-support IoU 0.0670,
re-measured this session from `data/scored/`); the 5GEMSDOE file that produced its 0.1563
is **not mirrored** in any pinned source, so it cannot be compared (flagged). And the leaderboard column
is an **account-level best**, not a per-file receipt — a new file that scores lower leaves
the displayed value unchanged. Every earlier recipe was also a variant of the same
topographic-crest idea. The new recipe is a different *mechanism*, not a re-tuning.

**R11-4 greedy marginal-precision assembly — WINS** (predeclared in
[`knowledge/07_r11_hypotheses.md`](knowledge/07_r11_hypotheses.md) before any fold was
scored). Starting from `topo_05_sp3`, each candidate block is restricted to pixels
**> 300 m from everything already predicted** and accepted only while its pooled tune-fold
marginal weighted precision exceeds `0.2 × DTI` (audited inclusion rule). Accepted:
`R10_vent`@0.25 % → `R8_tpi`@0.25 % → `R10_dzt_field`@0.25 %; step 4 failed the bar → stop.
Confirmation worst-rule-mean DTI **0.09175 vs 0.08694** (+5.9 % mean), 6/6 rule means,
**18/18 paired folds**. First recipe in 25 challengers (R8–R11) to clear the gate.
Report: [`reports/holdout_r11_2026-09-30.json`](reports/holdout_r11_2026-09-30.json).

**Flags for review.** I-15: rebuilt detector caches reproduce archived reference DTI only
to ≤ 0.17 % (unpinned library versions) — verdicts are now paired in-run and the gain had
to beat 10× drift; versions pinned in `requirements.txt`. I-16: the win is on hidden
*known* faults; the public score is the real test. R11-2 (basin magnetics) is **invalid**,
not lost (I-14 under-support). Still no DrivenData credentials here: the upload is a
manual step (see the executive summary).

### Next steps (ranked)
1. **Upload `13gems-r11-greedy-mp.tif`** and log the score in `reports/leaderboard_ledger.csv`.
2. **R11-2 retest** at ≤ 0.14 % (its support) — predeclared.
3. **R12-1 greedy with a wider pool / finer steps** (0.1 % blocks, all catalogue-free maps
   incl. R7/R8 families) — same gate, tune-only selection.
4. **R12-2 per-region budget** — run the greedy separately per structural domain so the
   bar is applied where the fault density differs.
5. R11-1 basement-depth steps and R11-3 GDR-1391 paleo-geothermal halos (need egress to
   [gdr.openei.org/submissions/1391](https://gdr.openei.org/submissions/1391)).
6. Store map sha256 in `reports/detectors_manifest.json` (closes I-15).

### Previous review — 2026-09-30, session 4 (R10 / R10b: official external data)

This session went outside the provided 19 bands for the first time, under the
standing rule that external data must be **free, official, licence-clean and
verifiably obtainable** before any code is written around it.

**Data staged and verified.** Six USGS public-domain products were re-staged from
this group's sibling repositories by `scripts/fetch_external_data.py` and verified
twice each (sha256 from the sibling provenance record **and** git blob SHA-1 from
the sibling tree): 3DEP 1-m LiDAR morphometrics (12 bands), GeoDAWN radiometrics,
GeoDAWN derivative extensions, a 9-band topographic morphometric set, and the
QFFDB prior (analysis-only — leakage risk). Pins: `reports/external_manifest.json`,
provenance: `reports/external_provenance/` (11 records). Licence check: USGS work
is public domain, which satisfies the organiser's condition that participants hold
"a license that permits the data to be used in this challenge and shared with the
sponsor" ([forum 11528](https://community.drivendata.org/t/paid-for-external-data-license/11528)).
All six grids conform exactly to the competition grid (EPSG:32611, 100 m,
3730×3292) — `reports/external_audit.json`.

**Four hypotheses predeclared before any map was built**
([`knowledge/06_r10_hypotheses.md`](knowledge/06_r10_hypotheses.md)), ranked by
expected ΔDTI ÷ cost: R10-3 damage-zone texture (3DEP slope_std × profile
curvature), R10-1 1-m LiDAR morphometric scarp composite, R10-2 radiometric
alteration-ratio lineaments (U/K, U/Th), R10-4 geothermal-vent conjunction
(scarp × alteration × conductance × shallow conductive base). Two further
candidates were screened out on measurement before build: the QFFDB-minus-catalogue
difference (**1 pixel** — dead) and a LiDAR-coherence channel (AUC 0.4608 — below
chance).

**Result: every one of the 24 challenger configurations LOSES**
(16 in R10, 8 in R10b) against the paired reference `topo_05_sp3`
(confirmation worst-rule mean **0.08687**). Best challenger 0.08593
(`topo05_plus_alter02_sp3`), best fixed-budget fusion 0.08286
(`fuse_vent_w050_sp3`). Protocol regression checks passed in both runs; all 468
scored rows report `tie_fraction` 0.00. **No submission slot was spent.**
Reports: [`holdout_r10_2026-09-30.json`](reports/holdout_r10_2026-09-30.json),
[`holdout_r10b_2026-09-30.json`](reports/holdout_r10b_2026-09-30.json).

**Why, measured rather than asserted.** The external maps are *better pixel
classifiers than any provided band* (AUC 0.5282–0.5770 vs 0.5615 for
`geod_shearrate`) and still lose, because the marginal weighted precision of the
pixels they add — 0.0094–0.0166 depending on block and coverage — sits below the
metric's own inclusion bar `0.2 × DTI` (0.0169 tune / 0.0195 confirmation).
External evidence buys **precision** (0.0294 vs 0.0276 at 19 % fewer pixels for
the w = 0.5 vent fusion) and spends **recall** (0.2487 vs 0.2874); under β = 2
that trade is a wash at best. Carried forward as
[irregularity I-13](knowledge/02_irregularities.md): *univariate AUC is not a
go/no-go signal in this competition*, and only a product that reaches fault
neighbourhoods the topographic crest never touches can raise DTI.

**One irregularity resolved on the way — I-2.** Band 6 `tc` is the **radiometric
total count**, measured against the official USGS grid: Spearman ρ 0.99998,
Pearson r 0.99902, OLS slope 1.0073, R² 0.9980, median ratio 1.00000, matching
percentiles, plus the physical closure test band6 ≈ 7.54 × (K + Th + U) at
ρ 0.9958. Its embedded description ("Tilt angle or total curvature — magnetic
field derivative for edge detection") does **not** describe the array. The earlier
"disproved" verdict rested on an unverified units assumption and is retracted in
place, with the reasoning preserved
([`reports/band6_identity.json`](reports/band6_identity.json),
`scripts/audit_band6_identity.py`). The same match independently validates our
external staging pipeline: the sibling re-gridding reproduces the field the
organisers shipped.

New organiser statements verified verbatim this session: the submission allowance
resets on a **rolling window** (11524), the Official Rules take precedence on team
eligibility (11540), the label TIF has **one** band and the reference notebook's
"19 bands" is a printing bug (11529). The downloadable artifact is unchanged:
**`13gems-toporef-holdoutref.tif`**.

### Previous review — 2026-09-30, session 3 (R9)

Three new geological hypotheses were implemented, predeclared, and measured on the
paired holdout this session — none beat the local best, so the reference recipe was
shipped as the primary downloadable artifact instead.

* **R9-1 strike-aligned gap completion** (`strike_gap_close`): strict variant is
  inert (+32 px/fold, exact tie); the loose variant adds ~145,600 px/fold for
  **ΔDTI −0.0257** — its marginal weighted precision sat below the metric's own
  `0.2 × DTI` inclusion bar (audit A5), so the loss was predicted by the audited
  algebra and then measured.
* **R9-2 epicentral-alignment lineaments** (`eq_lineaments`, bands 16+10):
  +16,590 px/fold for ΔDTI −0.0021. The first detector whose primary signal is
  the seismicity fields themselves.
* **R9-3 parallel-offset "correction" edges** (`parallel_offset_correction`):
  near no-op (+26 px/fold) — the physics-gated corridor conjunction almost never
  fires; recorded as a negative result, not evidence about the hidden truth.

All three **LOSE** under the predeclared rule
([`reports/holdout_r9_2026-09-30.json`](reports/holdout_r9_2026-09-30.json));
the protocol regression check passed (the reference row reproduces the archived
per-fold DTI values exactly). No submission slot was spent. The downloadable
artifact is now **`13gems-toporef-holdoutref.tif`** — the exact `topo_05_sp3`
reference configuration (BASE_topo_ridge top-5 %, 300 m grid decimation, binary,
catalogue included), format-validated, duplicate-checked against all eight
archived historical maps, with the form's name and note printed on the front
page and a triage table for the historical
“Predicted values must be in range [0, 1]” rejection
([irregularity I-8](knowledge/02_irregularities.md)).

The official leaderboard fetched on 2026-09-30 showed DARD 0.3168 (#1) and
alexoktaba 0.3042 (#2), not the prompt's 0.3049. These are account-level best
public scores, not receipts for our local TIFFs.

## The 60-second orientation

| Question | Answer | Where |
|---|---|---|
| What is the metric, really? | A **distance-weighted F2 score**. `DTI = 1/(0.2/P + 0.8/R)`. Proved, not asserted. | [`reports/metric_audit.json`](reports/metric_audit.json) |
| Why do historical files carry the same 0.1563 label? | **Unresolved as a score question; settled as a file question.** The two 0.1563-labelled files are different maps (support IoU 0.067); the leaderboard column is an account-level best, not a per-file receipt. Rounded score equality is not map identity and not evidence of copying. | [Irregularity I‑3](knowledge/02_irregularities.md) · [`reports/scored_forensics.json`](reports/scored_forensics.json) |
| Can public scores be compared with the local chance baseline? | **No.** Public inference from account-best scores is withdrawn. `dti_chance()` is retained only for an approximate same-run random-control sanity check with known local truth and the eligible fold domain. | [Irregularity I‑9](knowledge/02_irregularities.md) |
| What should a submission look like? | Use the exact marginal rule `ΔTP_w/(ΔTP_w+ΔFP_w) > 0.2 × DTI` for the same evaluation set; select cutoff, coverage, spacing, and fusion on the holdout rather than from unverified public labels. R9 measured the rule: mass below the bar loses exactly as the algebra says. | [`knowledge/01_verified_facts.md` §2.1](knowledge/01_verified_facts.md) |
| How do we check an idea before a submission slot? | Use whole-system and segment hide-and-recover folds with buffers, visible-catalogue-only feature construction, an exact known-fault mask, withheld-truth-only DTI, and multiple rules. The low-slope slice is a stress test—not hidden-test ground truth. | [`src/gems/holdout.py`](src/gems/holdout.py) · [`reports/holdout_r9_2026-09-30.json`](reports/holdout_r9_2026-09-30.json) |
| Is the current downloadable artifact cleared to submit? | It **is the current local holdout reference** (`topo_05_sp3`) — the best available recipe under the gate — labelled `BEST_LOCAL_REFERENCE_NOT_PRIVATE_TEST_CLAIM`. No challenger (R8, R9, R10 or R10b) has beaten it. | [`reports/latest_submission.json`](reports/latest_submission.json) |
| Do the free official USGS products help? | **Measured: not on Phase-1 DTI.** Six hash-verified products, four predeclared hypotheses, 24 challenger configurations — all lose to `topo_05_sp3`. They beat every provided band on AUC and still fail the metric's marginal-precision bar. Their remaining value is Phase-2 defensibility. | [I-13](knowledge/02_irregularities.md) · [`reports/holdout_r10_2026-09-30.json`](reports/holdout_r10_2026-09-30.json) |
| What is band 6 (`tc`)? | **Radiometric total count**, measured against the official USGS grid (ρ 0.99998, R² 0.9980, slope 1.007, closure vs K+Th+U ρ 0.9958). The embedded "tilt angle or total curvature" description is wrong. | [`reports/band6_identity.json`](reports/band6_identity.json) · [I-2](knowledge/02_irregularities.md) |
| How do I actually submit? | Download the front-page GeoTIFF, paste the printed name and note into the form, and follow the five steps (including the [0, 1]-error triage path). | [Executive summary](docs/executive_summary.html) |

---

## The four results that should drive every decision

All four are machine-verified in `scripts/audit_metric.py` (`ALL CHECKS PASSED`)
and reproduce the organizers' own worked example (TP_w 3.00, FP_w 1.89,
FN_w 2.00 → 0.60).

1. **`FN_w ≡ |G| − TP_w`**, so `DTI = TP_w / (0.2·TP_w + 0.2·FP_w + 0.8·|G|)`
   and equivalently `DTI = 1/(0.2/P_w + 0.8/R_w)`. Since `β² = 4`, **DTI is a
   distance-weighted F2 score.**
2. **Inclusion rule.** A block of predictions raises DTI **iff** its
   marginal weighted precision exceeds `0.2 × DTI` for the same evaluation set.
   The historical 0.1563 file labels are not verified per-file scores. At the
   official account-level leader value 0.3168, the arithmetic is 6.3%—an
   illustration only, not a threshold for any local or private-test map.
3. **Binary is optimal.** `DTI(c·p) = TP/(0.2TP + 0.2FP + 0.8|G|/c)` strictly
   increases in `c`, and a pixel exactly on truth has `k(0)=1` so it costs zero
   FP mass. Graded values are only useful for *ranking* pixels.
4. **Recall dominates** whenever `P_w > 0.25 · R_w`. Elasticities always sum
   to 1, so this is a hard crossover, not a heuristic.

**Geometry corollary.** `TP_w` takes a **max** over nearby predictions for each
truth pixel. Once that pixel's credit is saturated, a redundant neighbour may add
FP mass without more credit for that truth; another truth pixel nearby may still
benefit. Tune cutoff, line spacing, ridge width, and fusion on the multiple-rule
holdout; do not assume a universal 300 m decimation.

---

## Repository layout

```
PROJECT_CHARTER.md        standing brief — read first, every session
knowledge/
  01_verified_facts.md    every fact with the official URL it came from
  02_irregularities.md    things that are wrong or unverifiable, with actions (I-1..I-14)
  03_hypotheses.md        candidate geological hypotheses, ranked
  04_geothermal_vents.md  vent science from official sources (contrarian, cited)
  05_hypothesis_screen_2026-09-30.md   screened-out candidates and why
  06_r10_hypotheses.md    R10/R10b predeclared register, decision rule, results
src/gems/
  metric.py               the official DTI, transcribed and audited
  fastscore.py            exact fast scorer (verified == metric.py)
  holdout.py              hide-and-recover fold construction
  detectors.py            the physical-signature detectors (H-A..H-E, R6-*, R7-*, R10-*)
  external.py             provenance-driven loader for data/external (no hand-typed constants)
  supervised.py           supervised baselines
  rio.py                  raster I/O + the strict submission validator
tests/                    43 unit tests: rio, R9, R10 detectors (`unittest discover -s tests`)
scripts/
  fetch_data.py           reconstruct data/raw from official + mirrored sources
  fetch_external_data.py  stage + double-verify the six official external products
  audit_external.py       grid conformance, catalogue gap, band identity, channel novelty
  audit_band6_identity.py settles I-2: band 6 vs official TC, with the closure test
  build_external_detectors.py  the eight R10 maps + per-map AUC/top-5% manifest
  validate_r10_holdout.py      predeclared paired validation of the four R10 hypotheses
  validate_r10b_holdout.py     predeclared refinement round: low-coverage unions + rank fusion
  audit_metric.py         proves the four results above
  audit_bands.py          measures what the 19 bands actually are; tests I-2
  analyze_scored.py       file/pixel identity and support for historical TIFFs; score labels unverified
  chance_baseline.py      local random-map DTI only when holdout truth size is known
  build_detectors.py      compute and cache every detector map
  run_holdout.py          the v1 sweep
  run_holdout2.py         the v2 sweep (concealed subset, grid decimation)
  run_holdout3.py         the v3 sweep: R7 detectors + per-fold catalogue rebuild
  validate_ensemble_holdout.py  R8 recipe vs baseline (visible-only, paired)
  validate_r9_holdout.py  paired predeclared validation of the R9 hypotheses
  summarize_holdout.py    direct-DTI ranking; local random-control sanity check only
  validate_composite.py   two-regime validation of the shipped hedge
  make_submission.py      build + identity-check + format-validate; never grants score clearance
reports/                  machine-readable evidence for every claim
docs/                     generated GitHub Pages site (`scripts/build_site.py`), served at /docs/
```

---

## Local proxy evaluation and review status (2026-09-30)

All results below are local catalogue hide-and-recover measurements, **not**
public/private leaderboard performance. Use `.venv/bin/python`; system Python
in this workspace lacks the scientific dependencies.

* `scripts/audit_metric.py` → **12/12 checks pass**, including a numerical
  reconstruction of the official worked example. This verifies the DTI algebra,
  not hidden-test performance.
* `scripts/build_detectors.py` → 29 input-derived detector maps built in about
  502 seconds. Generated `data/derived/` is local/ignored.
* `scripts/chance_baseline.py` → public chance/lift inference remains
  **withdrawn** because it inferred hidden truth size from account-level scores
  and reused that estimate. The helper is retained only for a limited local
  random-control sanity check with known truth and each fold's eligible area; it
  is not a candidate-ranking or submission-clearance metric.
* `scripts/summarize_holdout.py` → candidate tables rank by direct worst-rule
  mean DTI, using confirmation rows when available. Historical candidate-to-chance
  ratios with a full-grid denominator are withdrawn; the low-slope slice is a
  robustness test, not a hidden-test analogue. See
  [`knowledge/03_hypotheses.md`](knowledge/03_hypotheses.md) and I-9/I-11.
* `scripts/analyze_scored.py` → eight historical TIFFs have exact file, canonical
  pixel, support, and unmasked-support hashes in
  `reports/scored_forensics.json`. The two files with historical 0.1563 labels
  have different file/pixel hashes (support IoU 0.06703; unmasked-support IoU
  0.06232). These labels are not receipts; no score is attributed to a local
  file. High overlap also does not mean exact duplicate (for example, the
  ens12/dualunion support IoU is 0.94191, but their file and pixel hashes differ).
* `scripts/fetch_external_data.py` → six official products staged into
  `data/external/` (~150 MB, gitignored), each verified against a pinned sha256
  **and** a pinned git blob SHA-1; `reports/external_manifest.json` records both.
* `scripts/audit_external.py` (streaming, one channel at a time — a first version
  was OOM-killed on this 3.9 GB box) → grid conformance for all six products,
  the QFFDB catalogue gap (**1 px**, hypothesis dead), band identity against
  official channels, per-channel AUC/novelty, and the 3,205,306-px common domain.
* `scripts/build_external_detectors.py` → eight R10 maps in `data/derived/`
  (43 s) plus `reports/external_detectors_manifest.json`.
* `scripts/validate_r10_holdout.py` / `validate_r10b_holdout.py` → 306 + 162
  paired fold scorings, both protocol regression checks PASS, all challengers
  LOSE (see the session-4 review above).
* `scripts/audit_band6_identity.py` → I-2 resolved (28 s).
* `scripts/validate_ensemble_holdout.py` → tested a visible-only reconstruction
  of the archived R8 recipe against `BASE_topo_ridge|cov0.05|sp3`. The report
  uses 15 whole-system folds across five withholding rules plus three raw
  8-connected segment folds, about 25% withheld fault mass, and a 5-pixel
  buffer. Catalogue-derived rays/horsetail features are rebuilt from each fold's
  visible catalogue; the visible-fault mask is pixel-exact, predictions are
  scored on withheld truth only, and a separate lowest-slope-third slice is
  treated as a stress test. See
  [`reports/holdout_candidate_r8_2026-09-30.json`](reports/holdout_candidate_r8_2026-09-30.json).

On the held-back confirmation folds, the local topo baseline scored worst-rule
mean DTI **0.08687** / overall mean **0.09763**, with mean weighted precision
0.0276 and recall 0.2874. The per-fold R8 union scored **0.05584** / **0.06615**,
with precision 0.0161 and recall 0.3292. Its effective positive support was
about 7.16% of the fold evaluation domain versus 3.62% for the topo baseline.
None of the tested coverage, spacing, width, and fusion variants beat that
baseline on the confirmation summary. These numbers concern catalogue recovery
under this protocol only; they do not predict the undisclosed target. The archived
full-catalogue raster is not itself holdout-scored because that would leak its
catalogue-derived tip/horsetail geometry.

**Submission decision (2026-09-30, session 4 — unchanged from session 3):** no R10
or R10b challenger passed the predeclared gate, so no slot is spent and the
recommendation stands.

**Submission decision (2026-09-30, session 3):** the primary downloadable artifact is
`13gems-toporef-holdoutref` — the reference recipe itself (`BASE_topo_ridge` top-5 %,
`decimate_grid` spacing 3, binary, catalogue included). It is labelled
`BEST_LOCAL_REFERENCE_NOT_PRIVATE_TEST_CLAIM`: local proxy evidence only, remote
acceptance unverified. Its NaN-outside GeoTIFF passes local grid, CRS, affine
transform, dtype, band-count, range, and footprint-NoData checks, and its
platform-check simulation documents how masked vs naive raw readers see the file.
The archived R8 artifact remains on disk as a demoted, NOT_CLEARED comparator.
Historical file notes/scores are not public score receipts. The official
account-level leaderboard snapshot is DARD 0.3168 / alexoktaba 0.3042 as of
2026-09-30; neither value is tied to a local TIFF.

---

## Reproduce everything

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install numpy scipy rasterio

.venv/bin/python -m unittest discover -s tests # strict submission-write regression tests
.venv/bin/python scripts/fetch_data.py        # data/raw (419 MB, gitignored)
.venv/bin/python scripts/audit_metric.py      # proves the metric results
.venv/bin/python scripts/audit_bands.py       # what the 19 bands actually are
.venv/bin/python scripts/analyze_scored.py    # file/pixel identity; labels are not receipts
.venv/bin/python scripts/audit_band6_identity.py   # settles I-2 (~30 s)
.venv/bin/python scripts/fetch_external_data.py    # stage + verify data/external (~150 MB)
.venv/bin/python scripts/audit_external.py         # grid/gap/identity/novelty audit (~140 s)
.venv/bin/python scripts/build_detectors.py   # ~7 min (418 s measured this session)
.venv/bin/python scripts/build_external_detectors.py   # the eight R10 maps (~45 s)
.venv/bin/python scripts/validate_r10_holdout.py    # predeclared R10 validation (~90 s)
.venv/bin/python scripts/validate_r10b_holdout.py   # predeclared R10b refinement (~66 s)
.venv/bin/python scripts/run_holdout3.py      # historical full sweep (~82 min, 3 GB RAM)
.venv/bin/python scripts/validate_ensemble_holdout.py # targeted visible-only ensemble holdout
.venv/bin/python scripts/make_submission.py --recipe best
```

`make_submission.py` first hashes canonical float32 scored-grid pixels and
positive support against existing download/scored TIFFs, blocking an exact pixel
duplicate (NaN and outside-footprint encodings normalize to zero). It also records
that distinct maps can still round to the same public score; no score uniqueness is
promised. The script checks the one-band float32 grid, EPSG:32611, 3730×3292 shape,
affine transform, finite in-footprint values in `[0,1]`, and supplied footprint mask.
The writer now rejects invalid predictions before opening an output file; it does
not clip bad values or silently turn in-footprint NaNs into zeros.
The primary GeoTIFF and ZIP use NaN outside the footprint, as the official format
text requires; an all-finite zero-fill twin is diagnostic only and is **not** treated
as format-equivalent. Local checks do not prove remote acceptance. The historical
server-side range rejection remains unexplained.

**A unique, format-valid GeoTIFF is not automatically a *beating* candidate.** Every
artifact built by the script carries an explicit clearance field. The current
`--recipe topo_ref` artifact is the holdout reference itself and is labelled
`BEST_LOCAL_REFERENCE_NOT_PRIVATE_TEST_CLAIM`; anything built from an untested recipe
is marked `NOT_CLEARED` until it beats the reference under paired direct-DTI
multi-rule confirmation. Check `submission_clearance` and the latest holdout report
before using a submission slot. The writer rejects invalid predictions before opening
an output file; it does not clip bad values or silently turn in-footprint NaNs into
zeros. The primary GeoTIFF and ZIP use NaN outside the footprint, as the official
format text requires and as the official sample's own structure uses; an all-finite
zero-fill twin is shipped as the documented fallback if the form repeats its historical
range error (see the executive summary's triage table).

---

## Standing rules for this project

1. **No submission slot is spent on an idea that has not beaten the current
   best on the hide-and-recover holdout.** Three submissions per week, total
   ([Official Rules §3.2](https://docs.nlr.gov/docs/fy26osti/96647.pdf)).
2. **A candidate that wins under only one withholding rule is fragile** and is
   reported as such. The legacy `make_submission.py --recipe best` selector uses
   `reports/holdout_results.json` and the worst-rule DTI there; it does not read
   the newer R8 comparison report or confer submission clearance.
3. **Every factual claim carries the official URL it came from.** If it cannot
   be verified from a public official source, it goes in
   `knowledge/02_irregularities.md` marked `UNVERIFIED`, not into the analysis.
4. **Rank candidate variants by direct, paired holdout DTI—not chance ratios.**
   A same-fold random-map DTI may be shown as a limited local control only when
   its actual support, withheld-truth size, and eligible eval-domain are known;
   do not treat the approximation as universal calibration, a submission gate,
   or a public/private baseline. Never infer truth size or chance from leaderboard
   scores.
5. **Never repeat an identical prediction as a new submission.** The builder
   checks canonical pixel identity against existing maps; distinct maps can still
   round to the same score, so no unique-score promise is made.
6. **Phase 2 is 83 % of the money** and its labels are built from *our own*
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
