# Session report — 2026-09-30, session 3 (R9)

## What this session did

1. **Rebuilt the environment from a clean checkout** (`scripts/fetch_data.py`
   mirrors, 28 s), reran the audit battery: `tests` 20/20 PASS (8 pre-existing +
   12 new R9 regression tests), `scripts/audit_metric.py` ALL CHECKS PASSED
   (including the official worked example TP_w 3.00 / FP_w 1.89 / FN_w 2.00 → 0.60).
2. **Implemented three genuinely new hypotheses** in `src/gems/detectors.py`
   (section R9), each answering the charter's four questions (layers, transform,
   why catalogue-missing, difference from prior work):
   * **R9-1 `strike_gap_close`** — strike-aligned gap completion of the fused
     binary prediction map (no band, no catalogue input).
   * **R9-2 `eq_lineaments`** — epicentral-alignment lineaments from the two
     near-uncorrelated seismicity bands (16, 10); first detector whose primary
     signal is seismicity itself.
   * **R9-3 `parallel_offset_correction`** — independent-physics edges running
     parallel to, but offset from, visible catalogue traces (the organizer-named
     "corrections" corridor), gated by physics rather than proximity.
3. **Predeclared, paired holdout validation** (`scripts/validate_r9_holdout.py`,
   report `reports/holdout_r9_2026-09-30.json`): identical folds/buffer/scorer/
   split to the R8 comparison; the reference `topo_05_sp3` is re-scored in-run and
   **reproduces the archived per-fold DTI values exactly** (protocol regression
   check PASS). Results (confirmation folds):
   * gapS (+32 px/fold): ΔDTI −0.00001 — tie, inert.
   * corrections (+26 px/fold): ΔDTI −0.00001 — tie, no-op as parameterized.
   * epicentral (+16,590 px/fold): ΔDTI −0.0021 — loses.
   * gapL (+145,608 px/fold): ΔDTI −0.0257 — loses badly.
   * **All verdicts LOSE**; no submission slot was spent.
4. **Metric consequence A5 measured, not just proved:** the loose gap-fill's
   marginal weighted precision was below `0.2 × DTI`, and it lost exactly as the
   audited algebra requires. The 0.08687-reference's decimation gaps are earning
   their keep on this holdout.
5. **Shipped the reference recipe as the primary downloadable artifact:**
   `13gems-toporef-holdoutref` (NaN-outside primary + ZIP + all-finite fallback),
   built by the new `--recipe topo_ref` in `scripts/make_submission.py`
   (`decimate_grid`, matching the holdout operator exactly). Format-validated,
   duplicate-checked against all 8 archived historical maps (no exact match),
   with the form's **unique name and note** printed on the site front page and a
   documented fallback path for the historical
   "Predicted values must be in range [0, 1]" rejection
   (`platform_check_simulation` in `reports/latest_submission.json`;
   irregularity I-8 narrowed).
6. **Site and knowledge base updated** (`scripts/build_site.py` regenerated):
   download-first hero, R9 verdict tables (index + evidence), R9 rows in the
   hypothesis register, 0.1563 question status section, executive-summary
   form-filling steps and error triage. README and PROJECT_CHARTER refreshed.

## Why GEMSDOE1 and 5GEMSDOE "have the same score"

Settled as a file question, unresolved as a score question: the two archived
0.1563-labelled files (`gemsdoe1_ens12`, `gems8_apex`) are different maps
(different bytes and canonical pixels; support IoU 0.06703), and the official
leaderboard column is an account-level best, not a per-file receipt
(irregularity I-3). No copying is implied by a matching rounded label; equally,
no score receipt exists to attribute. The productive response implemented this
session: structurally different candidate families, all gated on the paired
holdout before any slot.

## Limitations / blockers (unchanged unless noted)

* **L-1** No DrivenData auth: first-party rasters and the true
  `sample_submission.tif` cannot be re-downloaded here; mirrors only (I-1).
* **L-2** Sandbox egress beyond GitHub/PyPI fails at TLS: INGENIOUS GDR 1391,
  ScienceBase, ComCat bulk payloads, Landsat scenes remain un-staged
  (blocks H-F/H-G/H-H and the four screened external candidates).
* **L-3** The holdout is a proxy: its absolute DTI is not comparable to the
  leaderboard; only relative candidate ordering is meaningful.
* **New:** remote form acceptance remains unverified for both NoData encodings;
  the triage path and recording duty are documented in the executive summary.
