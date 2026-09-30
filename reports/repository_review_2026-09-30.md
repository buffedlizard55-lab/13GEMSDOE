# Repository review — 2026-09-30

## Executive decision

**Do not upload a new submission from this checkout.** The current downloadable
R8 raster is explicitly review-only: its visible-catalogue reconstruction lost
to the local topographic comparator in the confirmation folds, freshly rerun in
this review. Competition rasters were staged into ignored `data/` from the
team's public GitHub mirrors, not the authenticated first-party data tab. Grid
metadata and local hashes were checked, but the feature stack's exact official
provenance remains unverified. No weekly slot was used.

The most actionable reliability defect found in code review was that
`write_submission()` silently replaced non-finite inputs and clipped values to
`[0,1]`. That could conceal a bad upstream map instead of identifying it before
upload. The submission builder also had a zero-coverage edge case: `-0` slicing
in NumPy can select the entire ranked array. This review changes both behaviors
to fail closed and adds regression tests.

## Verified findings

### Score and repeated 0.1563 values

- The official problem page defines pixelwise predictions in `[0,1]`, the
  distance-weighted Tversky metric with a 300 m kernel, and GeoTIFF submission
  format: [DrivenData problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/).
- `scripts/audit_metric.py` was rerun in the review-created ignored `.venv` and
  reported `ALL CHECKS PASSED`, including raster reconstruction of the official
  worked example (`TP_w=3.00`, `FP_w≈1.89`, `FN_w=2.00`, DTI rounds to 0.60).
  This validates the local implementation against the published formula and
  example, not the private evaluator beyond those public specifications.
- `reports/scored_forensics.json` records the GEMSDOE1 and 8GEMSDOE TIFFs with
  the same *reported* 0.1563 label as **different** file hashes, different
  canonical pixel hashes, and different positive-support hashes. Their support
  IoU is 0.06703 (unmasked-support IoU 0.06232). Thus these two local maps are
  not copies under the recorded comparison. The score labels in filenames/team
  notes are not verified per-submission receipts; why those entries received
  the same rounded public score remains unknown. Distinct maps can legitimately
  round to the same score.
- The official leaderboard fetched during this review lists DARD at 0.3168
  (#1) and alexoktaba at 0.3042 (#2), in the account-level “Best public
  DW-Tversky” column: [live official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/).
  Therefore the prompt's 0.3049 figure is not the value visible in this fetch.
  Neither account-level value can be attributed to a local TIFF or individual
  upload.

### Input-data provenance and preparation

- `scripts/fetch_data.py` staged 19-band features (418,912,844 bytes), the
  fault label raster, sample file, and eight historical score-labeled rasters
  from the team's public GitHub repositories. It does **not** fetch the
  authenticated DrivenData source; its own header warns that these are mirrors
  and that at least one mirrored file is mislabeled.
- Raster inspection confirms the label/features share the expected 3730×3292
  EPSG:32611 100 m grid. The copied feature TIFF has 19 float32 bands and
  expected embedded descriptions. This is a structural check, not proof that
  every mirrored feature byte is identical to the official data-tab download.
- The mirrored `example_submission.tif` is not a valid test prediction: after
  treating NaN as outside-footprint zero, its in-footprint values exactly match
  `existing_faults.tif > 0` (all 60,988 known fault pixels). This reproduces the
  repository's existing warning; do not submit or treat that mirror as an
  independent prediction.
- There is no `scripts/prepare_data.py` in this repository despite the old
  README instruction. `scripts/build_detectors.py` performs the current cache
  preparation by writing `_valid.npy`, `_known.npy`, and detector arrays.
- The official USGS ComCat count endpoint was attempted directly from this
  environment and the TLS connection closed before returning a response. The
  previously researched count queries are not an acquired event dataset. Thus
  ComCat focal-plane coherence remains blocked and is **not validated/viable**.

### Submission artifact and holdout

- The site has an obvious landing-page download link to
  `13gems-r8-ensemble-20260930T014614Z.tif`, plus a ZIP and an executive
  workflow. It clearly labels the raster **review only / NOT CLEARED**. This is
  the correct safety posture: local GeoTIFF format checks do not establish a
  holdout win, remote form acceptance, or leaderboard performance.
- All committed download TIFFs were inspected: every finite value is in
  `[0,1]` and there are no infinities. The NaN-outside R8 TIFF was freshly
  checked against the staged label footprint with
  `src/gems/rio.py::validate_submission`: single-band float32, expected
  grid/CRS/transform, 5,167,373 finite in-footprint values, min 0.0, max 1.0,
  and no finite outside-footprint cells. The ZIP contains exactly that one
  TIFF. **Irregularity found and corrected:** `latest.tif` and `latest.zip` were
  stale all-finite aliases; they now point to/package the NaN-outside primary
  raster. The all-finite twins remain diagnostic only. This does not prove
  remote acceptance or explain the earlier range rejection; the rejected
  original and receipt were not provided.
- `scripts/build_detectors.py` completed from the mirrored feature raster in
  478 seconds and rebuilt 29 detector maps. `scripts/validate_ensemble_holdout.py`
  then reran the 18-fold comparison in 274 seconds (270 result rows). On its
  held-back confirmation folds, the local topo baseline had worst-rule mean DTI
  0.08687 / overall mean 0.09763; the R8 union had 0.05584 / 0.06615. R8's
  recall was higher but its precision lower; the union did not beat the baseline.
  The report explicitly limits these to a known-catalogue proxy, not hidden-test
  performance. See `reports/holdout_candidate_r8_2026-09-30.json`.
- `knowledge/05_hypothesis_screen_2026-09-30.md` already records four distinct
  geological directions (ComCat focal-plane coherence; repeated Landsat
  thermal/moisture residuals; groundwater-head compartments; cross-depth MT
  conductor persistence), prior-art distinctions, official data source checks,
  and why none can yet be called holdout-validated. The leading ComCat option
  is blocked on obtaining and inspecting a local event/product table. No new
  data-dependent detector was implemented in this review.

## Code changes made

1. `src/gems/rio.py::write_submission()` now rejects wrong grid/mask shape,
   empty footprint, non-finite in-footprint predictions, and any prediction
   outside `[0,1]`. It no longer silently clips or changes invalid scored values.
   It still writes NaN outside the footprint for the primary format.
2. `scripts/make_submission.py::build()` now validates coverage and spacing,
   checks the cached masks/detector grid, ignores non-finite detector scores,
   and explicitly rejects an empty eligible ranking. This removes the zero-
   coverage `-0` slicing hazard.
3. Submission names now have a conservative filename-stem allowlist and reject
   extensions/path-like names; invalid explicit coverage, spacing, reach, fill,
   and budget settings are reported instead of silently falling back or making
   accidental outputs.
4. Added `tests/test_rio.py` for compliant serialization and invalid range,
   NaN, shape, and NoData-fill rejection.

These changes improve artifact integrity; **they do not explain the historic
remote rejection or clear the R8 model for upload**.

## Three-pass review record

### Pass 1 — inventory and source review

Read `PROJECT_CHARTER.md` and the README standing brief first; mapped the
submission generator/validator, docs landing page and executive summary,
forensic evidence, metric audit, holdout summary, hypothesis screen, and input
data conventions. Retrieved the official problem description and live
leaderboard. The initial checkout lacked `data/` and `.venv/`; fetched the team's
mirrors, installed an ignored environment, and recorded the mirror provenance
caveat before running data-dependent checks.

### Pass 2 — risk and edge-case audit

Recomputed historical TIFF identity from the staged maps instead of inferring
identity from equal 4-decimal labels. Audited invalid-value handling and found
silent clipping in raster serialization plus a zero-coverage top-k corner
case. Rebuilt 29 detectors, reran the multiple-rule R8 confirmation holdout,
and checked that the landing page's review-only download warning matches the
holdout outcome. Direct ComCat API transport failed at TLS; no substitute or
synthetic event data was used.

### Pass 3 — correction and consistency review

Made output validation fail closed, guarded the zero-coverage path and CLI
parameters, and added focused regression tests. Re-read the changes against the
official `[0,1]` requirement and NaN-outside format text. The rebuilt R8 recipe
still failed to beat the comparator, so no candidate was marked cleared. No new
submission was generated and no submission slot was used.

## Verification run and limitations

- `.venv/bin/python -m py_compile src/gems/rio.py scripts/make_submission.py tests/test_rio.py` — PASS.
- `git diff --check` — PASS.
- `.venv/bin/python -m unittest discover -s tests -v` — 8 tests PASS,
  covering valid serialization, out-of-range values, NaNs, shape mismatches,
  invalid NoData fills, zero coverage, and nonpositive spacing.
- `.venv/bin/python scripts/audit_metric.py` — all 12 checks PASS, including
  the official worked example and algebraic consequences.
- Historical TIFF identity and the targeted R8 holdout were rerun against the
  staged group mirrors. Exact first-party feature provenance remains unresolved;
  the complete official authenticated data-tab download was not available.
- The new tests and audits do not validate the private-label distribution or
  explain the old server-side rejection. No new submission TIFF was created.

## Open blockers and next actions

1. Compare/replace the staged group mirrors with authenticated first-party
   DrivenData downloads. Record official checksums, band metadata, and source
   provenance; the current feature TIFF's exact match to the official download
   is unverified.
2. Acquire candidate #1's official USGS ComCat products and inspect actual
   coverage/product completeness before deciding whether focal-plane coherence
   is testable. If transport fails, report it as an acquisition blocker rather
   than pretending the idea was validated.
3. Do not expose a candidate as “ready to submit” until it has both passed
   strict format validation and beaten the current paired multi-rule holdout
   best. Keep the clear download available for review, but preserve the
   NOT_CLEARED warning until evidence changes.
4. Refresh the dated leaderboard snapshot from the official leaderboard on
   each research pass. The site currently links the live leaderboard but its
   embedded snapshot is static; automatic scheduled refresh is not implemented.
5. Once a valid experiment is actually uploaded, record the submission ID,
   exact file checksum, unique name/comment, and authenticated per-submission
   result. Until then, 0.1563 labels remain unverified attribution.

## Sources for manual review

- [Official competition overview/problem, metric, and submission format](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
- [Official current leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)
- [Official data page (login required)](https://www.drivendata.org/competitions/306/competition-doe-gems/data/)
- [USGS GeoDAWN data landing page](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and)
- [USGS ComCat FDSN event API](https://earthquake.usgs.gov/fdsnws/event/1/)
