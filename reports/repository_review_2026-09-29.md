# Repository review — 2026-09-29

## Scope and evidence

Reviewed the current checkout, README/charter, metric implementation and audit, detector inventory, forensic report, holdout reports, and submission tooling. The official problem statement was retrieved from [DrivenData problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/). No competition data are present in `data/` in this checkout. The metric audit was run after creating an ignored local virtual environment with NumPy/SciPy/Rasterio installed.

## Findings

1. **The repeated 0.1563 does not establish duplicate predictions.** `reports/scored_forensics.json` records distinct files with distinct SHAs/support; the comparison between `gemsdoe1_ens12_LB0.1563.tif` and `gems8_apex_LB0.1563.tif` reports support IoU 0.06703. Scores displayed to four decimal places can coincide for materially different maps. This is not evidence that one exact file was uploaded twice. Preserve per-submission IDs and exact prediction checksums when adding future results.
2. **Metric implementation passed the local audit.** `python scripts/audit_metric.py` completed with `ALL CHECKS PASSED`. The worked example gives 0.6026517, rounding to the official 0.60, and randomized checks confirmed the reduced identity and weighted harmonic-mean form. The marginal-precision, scaling, and elasticity checks also passed in the script's synthetic tests. This verifies local code against its stated formulas, not the organizer's hidden implementation beyond the published example/specification.
3. **Several genuinely different detector ideas are already coded.** `src/gems/detectors.py` contains upward-continuation worms, tilt derivative/theta, flat-ground basement hinge, strain residual, and oriented lineaments. `reports/detectors_manifest.json` records the bands and timing. They are not a list of future ideas; they have been implemented. The existing `reports/composite_validation.json` is evidence of evaluation on its recorded holdout regimes, but it is not proof of performance on the competition's unknown labels.
4. **Fresh top-candidate validation was not possible in this checkout.** `data/` is absent and the required competition rasters are gitignored. Therefore this session did not rerun the full holdout, independently reproduce the candidate ranking, or generate a fresh submission. No weekly submission should be made on the basis of this review. The previous report JSONs are retained as prior-session evidence and should not be described as freshly reproduced.
5. **Official metric nuance:** the DrivenData problem page describes detection of faults and the distance-weighted Tversky score; the local audit reconstructs the worked example. Verify mask semantics against the scoring clarification/forum and official downloadable scoring materials before treating all mask/neighbor behavior encoded locally as independently established. A local passing test alone is not an official confirmation.
6. **Submission-score irregularity:** the user-supplied score of 0.3049 differs from the charter's stored 0.3168 leaderboard figure (and older page content may change). The leaderboard was not successfully retrieved in this review; neither number is asserted as the current leader here. Update leaderboard facts only from a dated, directly verified official leaderboard snapshot.

## Three-pass review record

- **Pass 1 — inventory:** mapped repository components and located the existing reports, metric implementation, detectors, and data-dependent holdout path.
- **Pass 2 — verification:** ran the metric audit; it passed. Checked the local forensic report for whether matching displayed scores meant identical prediction files; recorded distinct files/support.
- **Pass 3 — gap check:** confirmed no `data/` raster files are available, so no fresh candidate holdout run or submission artifact could honestly be claimed. Left this explicit rather than treating old JSON as a new experiment.

## Next actions (in order)

1. Restore official input rasters into ignored `data/` through the documented official-data workflow; retain source URLs/checksums and confirm band descriptions/grid against first-party metadata.
2. Rerun the prescribed fold-generation and hide-and-recover suite, including withheld systems/segments with buffers and exact visible-catalogue feature derivation; include random, short, isolated, and attribute-based folds only when attributes are present. Keep geographic block CV as a stress test.
3. Compare each genuinely distinct detector and fusion against the current best using paired per-fold DTI, report worst-rule as well as mean, and flag rules with insufficient withheld truth. Do not select based on leaderboard feedback.
4. Resolve `tc` band semantics and the official masked-pixel scoring behavior from verified source metadata/scoring clarification before relying on those assumptions.
5. Record every submission's exact file SHA-256, recipe/version, unique name/comment, validation report, and per-submission (not best-ever) score. Four-decimal score equality is not a uniqueness test.
6. Refresh the public site only from dated verified evidence; distinguish current official facts from prior-run results and hypotheses.

## Limitations

This checkout does not include competition rasters, a currently verified leaderboard snapshot, or private-label access. Consequently no valid fresh holdout comparison, hidden-set estimate, or claim of beating the current holdout best can be made here. The local mathematical audit does not independently validate geologic truth or the organizers' complete scoring implementation.
