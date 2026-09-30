# Repository review — 2026-09-30

## Executive decision

**Do not upload a new submission from this checkout.** The current downloadable
R8 raster is explicitly review-only: its visible-catalogue reconstruction lost
to the local topographic comparator in the reported confirmation folds. This
checkout contains no `data/` directory. An ignored `.venv` was installed for
this review, allowing the metric audit and new serialization tests to run; the
holdout, historical TIFF audit, and fresh prediction generation remain blocked
on missing rasters. Saved holdout/forensic results are prior-run measurements,
not new experiments in this session.

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

### Submission artifact and holdout

- The site has an obvious landing-page download link to
  `13gems-r8-ensemble-20260930T014614Z.tif`, plus a ZIP and an executive
  workflow. It clearly labels the raster **review only / NOT CLEARED**. This is
  the correct safety posture: local GeoTIFF format checks do not establish a
  holdout win, remote form acceptance, or leaderboard performance.
- The archived provenance (`reports/latest_submission.json`) records the
  NaN-outside TIFF as locally format-conformant (one float32 band, expected
  grid/CRS/transform, finite valid-footprint values in `[0,1]`, no finite values
  outside the footprint). It records the zero-filled version as diagnostic
  only. The historical remote range rejection remains unexplained; this
  checkout does not contain the original rejected file/receipt needed for a
  direct forensic attribution.
- `reports/holdout_candidate_r8_2026-09-30.json` documents a prior local
  visible-catalogue rebuild and confirmation comparison. It reports R8 below
  the topographic comparator (worst-rule mean DTI 0.05584 versus 0.08687) and
  marks the scope as a local known-catalogue proxy, not private-test
  performance. This is prior-run evidence; it was not regenerated here.
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
leaderboard. Confirmed the supplied competition data and scientific Python
dependencies are absent from this checkout (`data/` and `.venv/` do not exist).

### Pass 2 — risk and edge-case audit

Checked the recorded GEMSDOE1/8GEMSDOE map identity pair rather than inferring
identity from equal 4-decimal labels. Audited handling of invalid values and
found silent clipping in raster serialization and a zero-coverage top-k corner
case. Also checked that the candidate's local holdout status and the page's
review-only download warning agree; they do.

### Pass 3 — correction and consistency review

Made output validation fail closed, guarded the zero-coverage path and CLI
parameters, and added focused regression tests. Re-read the changes against the
official `[0,1]` requirement and NaN-outside format text. No new submission was
generated, no submission slot was used, and no unvalidated candidate is
recommended.

## Verification run and limitations

- `.venv/bin/python -m py_compile src/gems/rio.py scripts/make_submission.py tests/test_rio.py` — PASS.
- `git diff --check` — PASS.
- `.venv/bin/python -m unittest discover -s tests -v` — 6 tests PASS,
  covering valid serialization, out-of-range values, NaNs, shape mismatches,
  and invalid NoData fills.
- `.venv/bin/python scripts/audit_metric.py` — all 12 checks PASS, including
  the official worked example and algebraic consequences.
- Historical TIFF pixel reread, holdout rerun, and fresh GeoTIFF export remain
  blocked on the absent competition data. Old JSON evidence must not be
  represented as newly reproduced.

## Open blockers and next actions

1. Restore the official competition rasters through the official authenticated
   DrivenData data tab (or verify permitted local mirrors and checksums as
   described in `knowledge/02_irregularities.md`); do not claim training data
   were fetched by this review.
2. The ignored `.venv` now contains NumPy, SciPy, and Rasterio; install any
   remaining project dependencies as needed and rerun the multiple-rule holdout
   with visible-
   catalogue-only feature rebuilds.
3. Acquire candidate #1's official USGS ComCat products and inspect actual
   coverage/product completeness before deciding whether focal-plane coherence
   is testable. If transport fails, report it as an acquisition blocker rather
   than pretending the idea was validated.
4. Do not expose a candidate as “ready to submit” until it has both passed
   strict format validation and beaten the current paired multi-rule holdout
   best. Keep the clear download available for review, but preserve the
   NOT_CLEARED warning until evidence changes.
5. Refresh the dated leaderboard snapshot from the official leaderboard on
   each research pass. The site currently links the live leaderboard but its
   embedded snapshot is static; automatic scheduled refresh is not implemented.
6. Once a valid experiment is actually uploaded, record the submission ID,
   exact file checksum, unique name/comment, and authenticated per-submission
   result. Until then, 0.1563 labels remain unverified attribution.

## Sources for manual review

- [Official competition overview/problem, metric, and submission format](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
- [Official current leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)
- [Official data page (login required)](https://www.drivendata.org/competitions/306/competition-doe-gems/data/)
- [USGS GeoDAWN data landing page](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and)
- [USGS ComCat FDSN event API](https://earthquake.usgs.gov/fdsnws/event/1/)
