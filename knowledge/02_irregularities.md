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

## I‑2 🟢 RESOLVED 2026-09-30 — band 6 **is** the radiometric total count; the embedded description is wrong (and this file's own "disproved" verdict is retracted below)

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

**Addendum 2026‑09‑30 (session 4) — RESOLVED by direct measurement against the official USGS release.**

`scripts/audit_band6_identity.py` → `reports/band6_identity.json` (28 s). The
test was written before it was run and its criterion is stated in the JSON:
band 6 is the total count iff Spearman rho > 0.999 **and** linear‑fit
R² > 0.99 against the official TC channel **and** rho > 0.99 against K + Th + U
from the same release. A tilt angle or a curvature cannot satisfy the closure
test. All three conditions pass:

| measurement | band 6 vs `radiometric::rad_tc` |
|---|---|
| Spearman rho | **0.99998** |
| Pearson r | 0.99902 |
| OLS band6 = a·rad_tc + b | a = **1.00729**, b = −0.12763 |
| R² / RMSE | **0.99804** / 0.19577 band‑6 units |
| median ratio (IQR) | 1.00000 (0.99867–1.00134) |
| percentiles p1 / p50 / p99 | 7.7223 / 18.4817 / 29.1005 vs 7.7140 / 18.4559 / 29.1002 |
| distinct values | 4,017,092 (float32) vs 255 (8‑bit product) |

Cross‑checks: the independently staged, percentile‑quantised `geodawn_rad::TC`
agrees in rank (rho 0.99995); the closure test gives band6 ≈ 7.543·(K + Th + U),
rho 0.99577, R² 0.99023 (`radiometric_u8`) and rho 0.99152 (`geodawn_rad_u8`).
Individual windows fall off exactly as physics requires — Th rho 0.913,
K 0.886, U 0.718.

**Why the earlier "disproof" was wrong, precisely.** Its first pillar was a units
assumption that was never checked against an official file: *"Airborne
radiometric total count is an unbounded intensity in counts per second, typically
10²–10⁴."* The official GeoDAWN radiometric TC grid itself lives in 5.47–30.27
over the footprint (p50 18.46), and band 6 spans 2.95–88.57 because it keeps a
tail that the 8‑bit product clips at its p0.5–p99.5 quantisation limits. The
slope of 1.007 and the ratio IQR of ±0.13 % say the two arrays are in the **same
units**, not merely the same ranks. The second pillar (band 6 is smoother than
the magnetic gradient bands) was correct and in fact *supports* the total‑count
reading: a raw radiometric intensity is smoother than a magnetic derivative. The
51‑candidate search inside the provided 18 bands could not find band 6 because
band 6 is not a transform of them — it is an independent survey channel.

**Consequences, all three recorded against ourselves.**

1. **Band 6 = radiometric total count.** The embedded description
   (`tc - Tilt angle or total curvature - magnetic field derivative for edge
   detection`) does not describe the array. That is a real documentation defect
   in the provided data and is worth raising with the organisers; it is not
   something we may silently reinterpret.
2. **`HE_lin_tc` is restored as a radiometric lineament detector.** The
   instruction above to treat it as an unlabelled‑input feature is withdrawn.
   Its holdout numbers were always measurements of this array; only the label was
   wrong.
3. **Band 6 is not new information.** It is the same field as the official TC we
   already staged, so the external‑data programme gains nothing from it — and any
   detector built on band 6 is built on provided data, which is what the R10
   audit assumed.

**Bonus finding (provenance).** Because the competition's own band 6 reproduces
the sibling‑repository re‑gridding of the USGS radiometric release to R² 0.998 on
the same 100 m grid, the staging pipeline in `scripts/fetch_external_data.py` is
independently validated against first‑party data: our dequantisation
(linear lo/hi from the provenance record) recovers the same field the organisers
shipped. That materially de‑risks every external product in
`data/external/`, not just the radiometric one.

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

## I‑8 🟡 PARTIALLY RESOLVED (2026-09-30 session 6) — the form's rejection of the NaN-outside encoding is CONFIRMED by a recorded platform response; the all-finite encoding is now the default upload. Validator behaviour is inconsistent across rounds (root cause external, unobservable from here)

The rejection message is `Predicted values must be in range [0, 1]`.

**What is now measured (sessions 3 → 6):**

1. (S3) The then-primary artifacts have zero NaN inside the footprint, zero finite
   values outside it, and in-footprint range exactly [0, 1]. A NoData-honouring
   (masked) read passes [0.0, 1.0]; a naive raw `all(0 ≤ v ≤ 1)` test fails on the
   NaN cells alone (`reports/latest_submission.json → platform_check_simulation`).
2. **(S6) REPRODUCED AGAINST A KNOWN FILE.** The team uploaded this repository's
   then-primary NaN-outside file (`13gems-r11-greedy-mp.tif`, downloaded from the
   site's front-page primary button) and the form returned the exact message above.
   First platform response recorded against a known file from this repo. Log:
   `reports/form_responses.json` (entry `user_reported_platform_response`).
3. **(S6) The validator is INCONSISTENT across rounds.** Three NaN-outside files
   were accepted and scored earlier (team-recorded sha256 prefixes
   `f347b70daa`, `37f9d5b855`, `4e03fc9705`; each re-verified against the archived
   bytes in `data/scored/` on 2026-09-30 — the prefixes in the team's own
   submission notes match the files bit-for-bit). The team's round-12 upload was
   named `…_allfinite`, i.e. the finite encoding family. Conclusion: the platform's
   range validation changed or is inconsistent; we cannot observe which (no
   access to the validator). **Flagged for review — this is an external,
   unverifiable-from-here behaviour change.**
4. (S3) Sibling repositories traced two concrete historical bugs that *would* trip
   a range check on their own files: NaN cells inside the footprint (6GEMSDOE
   PR #6) and the float32 nodata sentinel −3.4028e38 leaking into predictions
   (12GEMSDOE PR #8). No file published by 13GEMSDOE reproduces either.

**Action taken (2026-09-30, predeclared triage step 2 executed and made DEFAULT).**

* The **all-finite encoding is now the primary upload encoding** everywhere:
  `scripts/make_submission.py` writes `{name}.tif` all-finite (0.0 outside the
  footprint, no NoData tag) and `{name}_nanoutside.tif` as the record-only strict
  variant; `{name}.zip` and `latest.zip` wrap the finite file; the site's
  front-page primary button serves the finite file. For the already-archived R11
  artifact this was executed by `scripts/flip_primary_encoding.py`
  (`reports/primary_flip_2026-09-30.json`) WITHOUT rebuilding the map (a rebuild
  would drift the bytes, I-15): the finite twin is byte-identical to the NaN
  variant inside the footprint (verified), 0.0 outside, and 0-fill is
  score-neutral for a binary map (0 is a non-prediction; TP_w and FP_w unchanged
  under any scorer).
* **Every future form response must be appended to `reports/form_responses.json`**
  and the score receipt to `reports/leaderboard_ledger.csv`.
* If the all-finite primary is ever rejected: stop spending slots, capture the
  exact response; next suspects are the ZIP wrapper and CRS/transform.

**Still unresolved (external):** which validator code the platform runs and why it
changed. No public official source documents it; nothing further can be verified
from here.

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

---

## I-13 🟠 (new, 2026-09-30 session 4) — univariate signal ranking does NOT predict holdout DTI in this competition

**Measured.** The R10 external detectors are, as pixel classifiers against the
full provided catalogue, **better than any provided band**: AUC 0.5282–0.5770
(`reports/external_detectors_manifest.json`) against 0.5615 for the best provided
band (`geod_shearrate`) and 0.5755 for the best single external channel
(`topo::slope_std`). Ranked by AUC or by top-5 % catalogue recall, the predeclared
order was dzt > scarp > alter > vent.

**All 16 R10 configurations and all 8 R10b configurations nevertheless LOSE** to
`topo_05_sp3` on the paired hide-and-recover holdout (confirmation worst-rule mean
0.08687; best challenger 0.08593, best fusion 0.08286 — `reports/holdout_r10_2026-09-30.json`,
`reports/holdout_r10b_2026-09-30.json`).

**Why — and this is the irregularity to carry forward.** DTI is a distance-weighted
F2 (β = 2) over truth pixels with a 300 m kernel, so what a candidate adds is
measured by the **marginal weighted precision of the pixels it changes**, and the
audited inclusion threshold is 0.2 × DTI (0.0169 tune / 0.0195 confirmation). The
marginal precision of every external block we measured — 0.0094 (dzt), 0.0096
(scarp), 0.0138 (vent), 0.0141 (alter) at 2 % coverage; 0.0136–0.0166 at 0.5–1 %
coverage — sits **below** that threshold. AUC in the 0.50–0.58 band is simply not
enough separation to pay for pixels at a 1.2 % base rate under β = 2.

**Consequences.**

1. **Do not use AUC / top-k recall as a go–no-go signal again.** It ranked R10-3
   first and R10-4 last; the measured holdout order was almost the reverse
   (the vent conjunction was the best union partner and the best standalone of the
   family). Screening on univariate signal cost a full build-and-validate cycle.
2. **The binding constraint is recall, not precision.** External evidence raises
   precision (the w = 0.5 vent fusion reaches P_w 0.0294 vs 0.0276 with 19 % fewer
   pixels) and *lowers* recall (R_w 0.2487 vs 0.2874), which under β = 2 is at best
   a wash. Only an external product that puts pixels inside **300 m neighbourhoods
   of faults the topographic crest never touches** can raise DTI. Re-ranking or
   tightening the neighbourhoods we already hit cannot.
3. This is **not** a defect in the external data, which is hash-verified,
   licence-clean and — per I-2's provenance bonus — faithful to the same USGS
   release the organisers used. It is a property of the metric. Recorded so that
   nobody re-derives the same 24 configurations expecting a different answer.

---

## I-14 🟡 (new, 2026-09-30 session 4) — top-k over a sparse crest map silently selects by row-major position

**Measured.** The thinned crest variants carry very little mass: `R10_scarp`
89,438 non-zero pixels, `R10_alter` 81,972, `R10_dzt` 124,079 out of 5,167,373
valid (1.6–2.4 %). A "top 5 %" selection requests 258,369 pixels, so ~134k–177k
of the selected pixels would all have score exactly 0 and are chosen by
`np.argsort(..., kind="stable")` — i.e. by **position in the flattened grid**, a
spatial bias towards the top-left of the domain that has nothing to do with
evidence. The resulting map looks like a legitimate 5 % prediction and scores as
if it were one.

**Detected and handled, not smoothed over.** Every holdout row in R10 and R10b now
records `n_selected_at_zero_score` and `tie_fraction` per component; crest
configurations were capped at or below their own support mass (`scarpC_015`,
`dztC_02`, `alterC_015`). Across all 468 scored rows in the two runs,
`max_tie_fraction` = 0.00 and `max_zero_score_selections` = 0, so no verdict in
either run rests on tie order.

**Standing rule.** Never request a top-k mass larger than a map's non-zero support;
if a configuration needs it, ship the tie diagnostics with the row or discard the
row. `scripts/validate_r10_holdout.py` and `scripts/validate_r10b_holdout.py`
both enforce the reporting half of this rule.

## I-15 🟡 (new, 2026-09-30 session 5) — detector caches are not bit-reproducible across sessions

**Observed.** After `scripts/build_detectors.py` was re-run in a fresh sandbox
(numpy 2.4.6, scipy 1.17.1, rasterio 1.4.4), the unmodified
`scripts/validate_r10b_holdout.py` **failed its own protocol regression check**: the
reference `topo_05_sp3` reproduced the archived per-fold DTI only to within 1.45e-4
absolute (≤ 0.17 % relative; first folds: 0.0886693 vs 0.0886799, 0.0939307 vs
0.0939276). Earlier sessions never pinned library versions or recorded hashes of the
cached `.npy` maps, so the exact archived numbers cannot be regenerated.

**Action taken.** `scripts/validate_r11_holdout.py` reports the per-fold drift,
the library versions and the sha256 of `BASE_topo_ridge.npy`; it judges every
candidate against the **in-run** reference, and a WIN additionally requires the paired
confirmation gain to exceed 10× the largest drift. The tolerance change was recorded
in `knowledge/07_r11_hypotheses.md` before the verdict was read.
**Still open.** Pin versions (`requirements.txt`) and store map hashes in
`reports/detectors_manifest.json` on the next rebuild.

## I-16 🟡 (new, 2026-09-30 session 5) — the local win is measured on catalogue recovery, not on new faults

`greedy_r11` beats the reference 18/18 on hide-and-recover folds, but those folds
hide **known** faults (I-10). The public score of the uploaded file is the only
independent check. Record it in `reports/leaderboard_ledger.csv`; if it does not
exceed the group's best public score (0.1563), the proxy/leaderboard gap, not the
recipe, becomes the top research priority.
