# Irregularities flagged for review

Everything here was found by measurement or by fetching an official page during
this session. Each item states **what I verified**, **what I could not verify**,
and **what to do**. Nothing is asserted from memory.

---

## I‑1 🔴 CRITICAL — `example_submission.tif` is not an example submission

**Measured.** The file our pipeline has been using as the submission template,
`data/bridge/example_submission.tif` (git blob `7d865a99…`, present identically
in GEMSDOE, GEMSDOE2, GEMSDOE3, GEMSDOE4, 5GEMSDOE and as
`data/sample_submission.tif` in 6GEMSDOE), is **value-identical to
`existing_faults.tif`**:

```
example_submission finite mask == existing_faults valid mask : True
values identical where valid                                 : True
exact array equal (nan-aware)                                : True
ones in example_submission = 60,988   ones in existing_faults = 60,988
```

The official problem description says:

> "A sample submission that **predicts total fault absence** is provided for
> your reference on the data download page."
> — [problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)

Total fault absence means an all-zero raster. Ours contains 60,988 ones — the
entire known USGS/INGENIOUS catalogue.

**Why it matters.** Any pipeline that starts from this "template" and adds
predictions ships the whole known catalogue inside every submission. Per
[forum 11516 post 2](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516)
that mass is score-*neutral* (masked), so it does not directly hurt — but it
silently anchors every downstream thresholding, top‑k and normalisation step to
the catalogue, and it makes "coverage" statistics meaningless.

**Action.** Do not use that file as a template. `src/gems/rio.py` writes
submissions from the geotransform/footprint only. **Someone with a DrivenData
login must re-download `sample_submission.tif` from the
[data tab](https://www.drivendata.org/competitions/306/competition-doe-gems/data/)
and confirm whether the official file is all-zeros.** Either our mirror is
mislabelled, or the official sample is not what the page describes.

---

## I‑2 🟠 Band descriptions in the feature GeoTIFF look machine-written, and band 6 is still UNIDENTIFIED — the "radiometric total count" reading is now **disproved**

**Measured.** The 19 band descriptions embedded in
`gems-geodawn-numerical-features.tif` contain hedged, non-geophysical phrasing:

| band | embedded description | problem |
|---|---|---|
| 6 | `tc - Tilt angle **or** total curvature - magnetic field derivative for edge detection` | "or" — the writer did not know |
| 10 | `deq_n100a15 - Distance to earthquake …` | official page lists only "density of earthquakes" |
| 16 | `ieq_n100a15 - Earthquake intensity **or** density …` | "or" again |
| 15 | `depth_to_base_surf - … thickness of sedimentary cover` | official wording is "depth to conductive base surface" |

Real geophysical metadata does not say "or".

**What the earlier session claimed, and why it was wrong.** The previous
revision of this file asserted "with high confidence" that band 6 is the
**radiometric total count**. That was an inference from two true facts — that
GeoDAWN is officially *"a high-resolution lidar, magnetic, and radiometric
study"* ([Official Rules §2](https://docs.nlr.gov/docs/fy26osti/96647.pdf)) and
that the problem page's figure shows *"total radiometric counts per second"* —
plus the observation that "tc" is the standard abbreviation for Total Count.
**It was never tested against the raster.** `scripts/audit_bands.py` now tests
it, and the raster contradicts it:

1. **Band 6 is bounded in [2.953, 88.567] degrees with p99 = 29.10.** Airborne
   radiometric total count is an unbounded intensity in counts per second,
   typically 10²–10⁴. A band that never exceeds 88.6 and whose 99th percentile
   is 29.1 is not a count.
2. **Band 6 is smoother than the fields it would have to be derived from.**
   Lag‑1 autocorrelation after a 3‑px Gaussian blur: `tc` 0.9805, `rtp` 0.9836,
   `tmi` 0.9844, `tmi_hg` 0.9112, `tmi_vg` 0.8238. A "magnetic field derivative
   for edge detection" must be noisier than the field it differentiates; band 6
   is smoother than both supplied gradient bands.
3. **It is not any standard amplitude‑normalised magnetic edge angle either.**
   All eight candidates were computed and correlated against band 6
   (`reports/band_audit.json`): theta from `rtp` r = −0.0040, TDR from `rtp`
   r = +0.0177, theta from `tmi` r = −0.0029, TDR from `tmi` r = +0.0182, theta
   from `mag_anom` r = +0.0033, TDR from `mag_anom` r = −0.0324, theta from the
   supplied `tmi_hg`/`tmi_vg` r = −0.0018, |TDR| from the same r = −0.0018.
   Mean absolute differences are 18–47 degrees. **No candidate reproduces it.**

**Consequence for the code.** `HE_lin_tc` is built on the assumption that band 6
is a radiometric channel. That assumption is **disproved**, so `HE_lin_tc` must
be treated as an *unlabelled-input* lineament detector, not a radiometric one.
Its holdout numbers are still valid measurements of a detector; the geological
story attached to them is not.

**Second, separate question — settled.** Are bands 10 and 16 distances or
densities? Measured: median of `deq` inside catalogue pixels 776.8 vs 621.4
outside; `ieq` 935.1 vs 751.5 outside. Both are **higher** inside the catalogue,
so both behave as positive earthquake **intensity/density** quantities, not
distances. `HD_strain`'s use of `ieq` as a density is therefore **correct** —
no inversion bug. The two bands are near‑uncorrelated with each other
(r = 0.083), which is what makes them usable as two independent gates in R7‑3
rather than one duplicated signal.

**Action.** Confirm against the official data‑tab documentation (needs a
DrivenData login). Until then, band 6 is reported as **UNIDENTIFIED** and no
geological interpretation is attached to it.

**Addendum 2026‑09‑29 — the 51‑candidate best‑match search (`reports/band_audit.json`, 107 s).**
Rather than keep guessing, `scripts/audit_bands.py` now builds a bank of 51
physically standard transforms of the other 18 bands — gradient magnitude,
Gaussian Laplacian, 9‑px Gaussian, theta, TDR and vertical‑over‑horizontal
gradient over bands 1, 2, 12, 13, 14, 15, 17 and 19, plus theta / TDR /
vd‑over‑hg from the supplied `tmi_hg`/`tmi_vg` pair — and correlates every one
against band 6 with Spearman rho. **The best is `gauss9_b13` at rho = −0.3547**;
next are `gauss9_b19` −0.3270 and `gradmag_b12` −0.2997. Nothing reaches
|rho| = 0.5. Band 6 is therefore **UNIDENTIFIED by measurement**, on both sides:

* **For the radiometric reading (first‑party):** the problem page's figure asset
  is named `gems_tc_tmi.png` and is captioned "radiometric (left) and magnetic
  (right)", and the page's own feature list names no tilt angle and no total
  curvature — [problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/).
* **Against it (measured):** the array is strictly bounded in [2.953, 88.567]
  with p50 18.48 and p99 29.10, and is smoother than every supplied gradient
  band. A count in CPS is neither bounded at 88 nor smooth.

These observations do not identify band 6. Only the data-tab documentation can
settle its meaning. `HE_lin_tc` is treated as an unlabelled-input lineament feature,
not as a verified radiometric or tilt measurement. Its historical chance/lift values
are withdrawn: they used a mismatched evaluation-domain denominator and should not
be cited as evidence for the feature or either geological interpretation.

---

## I‑3 🟠 UNRESOLVED — repeated 0.1563 labels do not establish a plateau or a measurement artefact

The official DrivenData leaderboard labels its score column **“Best public
DW-Tversky”** ([leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)).
That is an account-level best, not a receipt identifying the score of a particular
uploaded TIFF. The dated snapshot in `reports/leaderboard_snapshot_2026-09-30.json`
records DARD at 0.3168 and alexoktaba at 0.3042; those values are also account-level
best-public scores.

Several historical local TIFF filenames and team notes carry the value 0.1563.
However, `reports/leaderboard_ledger.csv` has `per_submission_score=UNKNOWN` for those
artifacts, and no per-submission receipt currently maps a public score to a local file.
The structural comparisons in `reports/scored_forensics.json` answer a different
question: they compare TIFF bytes, canonical pixel values, positive-pixel support,
and support overlap. A matching rounded label proves none of those identities; a
large or small support IoU does not verify which file received which score.

**Conclusion:** neither a modeling plateau nor a leaderboard measurement artefact is
established. The previous claim that the plateau was “almost certainly” an account-best
misread is withdrawn. Equal rounded scores are not a prediction-identity test, and
distinct maps may legitimately receive the same score rounded to four decimals.

**Action:** keep per-file public scores unknown until the DrivenData submission details
provide a receipt that can be tied to a submission ID and the exact GeoTIFF checksum.
Until then, do not use these score labels to decide which geological idea worked.

---

## I‑4 🟠 UNVERIFIED — account ownership and eligibility cannot be inferred from score matches

Earlier working notes associated some leaderboard handles with the project, but the
public leaderboard does not establish who controls an account. Similar account-best
scores or rankings are not evidence of common ownership, shared submissions, or an
eligibility violation. This repository therefore makes no allegation about account
ownership.

The official rules do impose entry and submission requirements
([Official Rules](https://docs.nlr.gov/docs/fy26osti/96647.pdf), §§1.1, 1.3, 3.2).
If internal account records raise a real compliance question, verify it with the
organizers rather than infer it from rounded leaderboard values. The earlier claim
that consolidating accounts would “fix” I‑3 is withdrawn; account consolidation cannot
supply the missing per-submission score-to-file evidence.

---

## I‑5 🟡 Two referenced repositories do not exist

`gh api repos/buffedlizard55-lab/9GEMSDOE` and `…/10GEMSDOE` both return
**HTTP 404**. The session notes list scores for both (`9GEMSDOE: 0.0107`,
`10GEMSDOE: h16-continuation… 0.0461`). Those artefacts are unrecoverable, so
their results cannot be audited or reproduced.

---

## I‑6 🟡 The leaderboard target has moved — dated account-level snapshot

The official leaderboard was fetched on **2026-09-30**. Its “Best public
DW-Tversky” column listed DARD at **0.3168** (#1) and alexoktaba at **0.3042** (#2)
([official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/);
see `reports/leaderboard_snapshot_2026-09-30.json`). The snapshot is time-sensitive
and reports account-level best-public scores, not per-submission receipts. No public
score is currently attributable to a local prediction file in this repository.

---

## I‑7 🟢 Resolved — `nlr.gov` is correct

`docs.nlr.gov/docs/fy26osti/96647.pdf` looked like a typo for NREL. It is not.
[HeroX links to exactly that URL](https://www.herox.com/GEMSPrize/resource/2274)
and the rules document itself explains why: the American-Made program is
*"administered by **NLR**"* — the **National Laboratory of the Rockies**, which
also employs the geology experts who labelled the new faults
([§2, §3](https://docs.nlr.gov/docs/fy26osti/96647.pdf)). No irregularity.

---

## I‑8 🟠 UNRESOLVED — the rejected file's remote validation cause is unknown

The reported rejection message is `Predicted values must be in range [0, 1]`.
It does not identify whether the remote validator saw a finite out-of-range value,
NaN/NoData, or another issue. `src/gems/rio.py::validate_submission` checks the
repository's local grid, dtype, band-count, NoData, and range rules; it does not
reproduce the remote validator.

The official problem page permits null/NaN outside the data bounds. The all-finite
variant writes zero outside the valid mask; no cited organizer statement establishes
that zero-fill is scoring-equivalent or accepted by the remote form. Retain both
variants for diagnosis, inspect each submitted file's stored values and NoData tag,
and record the official form's response before claiming a cause or fix.

---

## Open questions (cannot be resolved from public sources)

**Q‑1.** Does predicted mass sitting *on* a masked known-fault pixel still earn
`TP_w` credit for a new-fault pixel within 300 m, or is it discarded entirely?
Posts 2 and 4 of thread 11516 are only mutually consistent under "discarded
entirely" (otherwise including the catalogue would strictly help, and the
organizer says it "should not matter"). We default to **discarded**, which is
conservative. `FoldScorer.build(..., ignore_pred_outside_eval=False)` flips it.

**Q‑2.** How many new-fault pixels are in the public test chunk? **Unknown.**
The previous algebraic bounds used historical score labels attributed to local TIFFs;
that attribution has no per-submission receipt, and the official leaderboard provides
account-level best-public values. The numeric bounds are withdrawn. No independent
public truth-size estimate is available from this repository.

---

## I‑9 🟠 WITHDRAWN — public chance/lift estimates are circular and unsupported

The former public report (`reports/chance_baseline.json`, before withdrawal) inferred
an apparent hidden-truth pixel count from the same public score labels it then compared
with chance. `scripts/chance_baseline.py` used `implied_truth(mass, score)`, took a
median of those inferred counts, and reported chance/lift at that median. The value
`|G|≈35,262` was therefore **not an independent estimate**. Reusing it to explain the
input scores is circular. The input score-to-file attribution was also unverified.

Accordingly, the old public chance curve, per-artifact lift table, “every submission is
statistically indistinguishable from random” conclusion, and claimed public
score/coverage ordering are **withdrawn**. `reports/chance_baseline.json` now contains
only a withdrawal notice; it has no public truth-size estimate or score rows.

The function `dti_chance(mass, n_truth, n_valid)` is retained for **local
hide-and-recover diagnostics only**, when withheld truth and the eligible domain are
known independently. A review found that the older `summarize_holdout.py` passed the
full valid-footprint size even though candidate and control pixels were restricted to
a smaller fold `eval_mask`; the stored v3 calibration was therefore not on the right
domain and is superseded. The corrected script uses `valid_px - n_visible` (or an
explicit `n_eval_px`) and reports a 30-control, same-run diagnostic (median relative
error **1.8%**, p90 **7.3%**) for that historical run. The analytic approximation does
not represent the exact spatial arrangement of the fold mask; this is an in-sample
check on those local random controls, not a universal calibration, submission gate,
or public/private baseline. Candidate-to-chance ratios have been removed from the
primary summaries; candidate ranking uses direct DTI. The R8 confirmation is likewise
reported and selected by direct DTI, without an analytic chance comparison.

**Action:** use a chance comparator only when the same fold's actual withheld truth
size, effective predicted mass, and eligible evaluation area are known. Do not infer
truth size or chance from leaderboard scores. Local proxy results must not be
presented as private-test performance.

---

## I‑10 🟠 Catalogue hide-and-recover has a known scope mismatch

**Measured:** the local holdout withholds pixels from the existing catalogue; the
competition target is expert-labelled new-fault truth. In this catalogue, about
**19.8%** of known-fault pixels fall in the lowest-slope third of the valid area,
which occupies about **33.0%** of that area (`reports/holdout_v3.json`). This is a
measured topographic composition difference in the *training catalogue*.

It does **not** establish the terrain distribution of the undisclosed new-fault
labels, nor prove that the full holdout favors topographic methods on the private
test. The catalogue may reflect mapping practices, physical geology, or both.

**Action:** report DTI across the ordinary withheld catalogue pixels and the
lowest-slope-third slice as a robustness stress test. Do not call the latter an
“honest” hidden-test score or use its chance ratio as a private-test estimate.
The fold-construction and feature-rebuild protocol is documented in
`scripts/run_holdout3.py`.

---

## I-11 (revised 2026-09-30) — the low-slope subset is a stress test, not a hidden-fault analogue

The earlier notes described withheld catalogue pixels in the lowest-slope third
as “the honest number” and a proxy for hidden vents. That is too strong and is
withdrawn. The measured **19.7–19.8%** versus **33.0%** comparison describes the
existing catalogue only; it supplies no independent estimate of the hidden-test
fault population. Nor does it show that the private target is concentrated on flat
ground or that a ranking reversal transfers to the competition test.

`dti_concealed` remains useful as a **predeclared robustness slice**: it asks how
a detector behaves on one terrain subset of the known-catalogue holdout. Always
show it beside full-fold results and retain the subset definition (lowest-slope
third); do not promote a detector on that slice alone. The current 18-fold R8
recipe comparison and its limitations are recorded in
`reports/holdout_candidate_r8_2026-09-30.json`.

---

## I-12 (new, 2026-09-29 session 2) — three detectors were never validatable, and one was leaking

**Measured** by inspection of `scripts/run_holdout2.py` against
`scripts/build_detectors.py`.

1. **`R6_horse_full` was swept as if it were a physical detector.** It is built
   by `horsetail_splay(known, ...)` from the **full** catalogue, including the
   segments each fold withholds. Any holdout score it produced was leakage, not
   skill. `scripts/run_holdout3.py` now refuses to sweep any detector whose name
   ends in `_full` and rebuilds the catalogue-dependent ones per fold from the
   VISIBLE catalogue only.
2. **`HD_strain` was cached globally** even though its fault-density term is
   catalogue-derived. Same class of leak, smaller magnitude. Now rebuilt per fold.
3. **`R7_grain_full` produces only 1,748 non-zero pixels** out of 5,167,373
   valid (0.034 %). With the full catalogue there is almost nowhere left that
   qualifies as "catalogue-blind", so the submission-side version of R7-5 is
   effectively empty. The per-fold version has a smaller catalogue to be blind
   to and is the only version worth measuring. **Flagged: do not ship
   `R7_grain_full` in a submission expecting it to contribute.**

**Action.** Fixed in code; recorded here because the earlier
`reports/holdout_v2.json` and `reports/holdout_verdict.json` numbers for these
families are not trustworthy.
