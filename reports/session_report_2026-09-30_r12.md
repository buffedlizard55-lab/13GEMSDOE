# Session report — 2026-09-30, session 6 (R12) — 13GEMSDOE

## What this session set out to do

1. **Make the submission download work.** The team reported that the file
   downloaded from the site's front page (`13gems-r11-greedy-mp.tif`,
   NaN-outside encoding) was rejected by the DrivenData form with
   `Predicted values must be in range [0, 1]`. Requirement: a working,
   obvious download at the very top of the site, no manual triage.
2. **Generate 3–5 new geological hypotheses not tried before**, ranked by
   expected DTI ÷ cost, and validate the top candidate on the
   spatially-blocked holdout **before** any submission slot.
3. Create a PR and merge it.

## 1. Download encoding — FIXED and verified (I-8 partially resolved)

Measured this session:

* The 8 archived historically-scored files (`data/scored/*`) are **all**
  NaN-outside float32 (7,111,787 NaN cells each). The team's own submission
  notes tie three of them to accepted scores **by sha256 prefix**
  (`f347b70daa`, `37f9d5b855`, `4e03fc9705`) — each prefix re-verified against
  the archived bytes. So the platform accepted NaN-outside files before.
* The same encoding was rejected on 2026-09-30 for
  `13gems-r11-greedy-mp.tif`. The team's round-12 upload is named
  `…_allfinite` (finite encoding family). **Conclusion (flagged):** the
  platform's range validation changed or is inconsistent. Not observable from
  here; logged in `reports/form_responses.json` + I-8.
* Action (predeclared triage step 2, made default):
  * `scripts/flip_primary_encoding.py` re-pointed the archived R11 artifact at
    its all-finite twin **without rebuilding the map** (a rebuild would drift
    bytes, I-15). Verified byte-level: 0 NaN, 0 Inf, range exactly [0.0, 1.0],
    272,853 positive cells, in-footprint pixels **identical** to the NaN
    variant, exactly 0.0 outside the footprint (score-neutral for a binary
    map: 0 is a non-prediction; TP_w and FP_w unchanged under any scorer).
  * Both zips (`13gems-r11-greedy-mp.zip`, `latest.zip`) now wrap the FINITE
    file (the old zip wrapped the rejected NaN encoding — a wasted-upload trap).
  * `scripts/make_submission.py` now writes `{name}.tif` all-finite (primary),
    `{name}_nanoutside.tif` (record-only strict variant), finite zips,
    `primary_upload` metadata.
  * Site: front-page hero's first button = the working all-finite file, with
    the form name + note printed next to it; executive summary steps 3–5 and
    the triage table rewritten around the recorded platform response.

**Still open (needs the team):** upload the all-finite file, then append the
form response to `reports/form_responses.json` and the receipt to
`reports/leaderboard_ledger.csv`. If the finite encoding is ever rejected
too, capture the exact message — that would be new evidence (next suspects:
ZIP wrapper, CRS/transform).

## 2. R12 — predeclared register, then measured

Register written and committed **before** any fold was scored:
`knowledge/08_r12_hypotheses.md`. Data re-staged from the pinned mirrors
(`scripts/fetch_data.py`, `scripts/fetch_external_data.py`), detector caches
rebuilt (483.8 s + 45 s; external AUCs match the archive exactly), then
`scripts/validate_r12_holdout.py` (214 s, protocol regression check PASS with
**zero** drift — pinned `requirements.txt` closed I-15's drift).

| config | tune worst | confirm worst | verdict |
|---|---|---|---|
| topo_05_sp3 (reference) | 0.03852 | 0.08687 | reference (exact reproduction) |
| greedy_r11 (reference to beat) | 0.03992 | 0.09168 | reference — SHIPPED |
| greedy_r12 (finer greedy, selected on tune) | 0.03864 | 0.08824 | LOSES (0/6 rules, 0/18 paired) |
| basinmag @0.10 % (true support) | 0.03829 | 0.08623 | LOSES (first VALID R11-2 measurement) |
| hyst_add005 / 010 / 020 | 0.03539 / 0.03395 / 0.03041 | 0.08219 / 0.07909 / 0.07354 | LOSE (clean dose-response) |

Findings:

* **Hysteresis (new connectivity transform) is a measured negative.** The
  sub-cut ridge tail adds recall (up to 0.3453) at marginal weighted precision
  below the metric's `0.2 × DTI` inclusion bar — I-13 again, now for
  connectivity. Closed as a standalone score lever.
* **R11-2 resolved: basin-floor magnetics validly LOSES** at support-level
  coverage (no I-14 padding).
* **Finer greedy:** step 1 measured the highest-precision block ever
  (`R10_vent@0.10 %`, pooled marginal precision 0.03236) but the frozen
  one-block recipe loses 0/18 paired folds vs R11's 3-step assembly:
  precision above the bar is necessary; accepted mass must also move the
  worst rule.
* **No slot spent. Artifact unchanged: `greedy_r11`, all-finite encoding.**

Diagnostics honesty note: the hysteresis add-backs cut through large tie
plateaus of the thinned ridge field (tie_fraction up to 4.40, recorded in the
report). Selection is deterministic; the LOSE verdicts do not hinge on tie
order.

## 3. Leaderboard (official public page, fetched this session)

DARD 0.3168 (#1, 11 subs) · alexoktaba 0.3042 (#2, 17) · joeyfezster 0.2919
(#3, 16) · xiaofanhu 0.2901 · HardcoreTechGod 0.2854 · mzoorob 0.2843 —
`reports/leaderboard_snapshot_2026-09-30.json`. Account-level bests, not
receipts. The prompt's "0.3049" does not appear on the current board.

## Flags for review (new/updated this session)

* **I-8 (updated):** platform range validator changed or is inconsistent
  (NaN-outside accepted 2026-09-27-ish, rejected 2026-09-30). External,
  unobservable from here.
* **I-17 (new):** 3 GB sandbox caps the in-memory ranked pool at 12 maps; the
  full 30-stem catalogue-free pool sweep needs a larger-RAM runner.
* The real `example_submission.tif` / `sample_submission.tif` structure remains
  unverified (I-1): still needs a DrivenData login.
* `12GEMSDOE`'s published files historically leaked the −3.4028e38 nodata
  sentinel into predictions (12GEMSDOE PR #8) — if the team submitted a file
  downloaded from *that* site, the range error may have had a different cause
  than our R11 file. Worth confirming which file was actually uploaded.

## Next steps (ranked)

1. Upload the all-finite `13gems-r11-greedy-mp_allfinite.tif`; record the
   response + receipt.
2. New physics, not finer re-cuts: R12-4 Euler depth-to-source (declared,
   deferred), per-domain greedy budgets, R11-3 GDR-1391 halos (needs egress).
3. Full 30-stem pool greedy on a larger-RAM runner (I-17).
4. Hysteresis only as marginal-precision-gated blocks inside the greedy.
5. Persist detector-map sha256s in `reports/detectors_manifest.json`.
