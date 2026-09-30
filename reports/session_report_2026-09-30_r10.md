# Session report — 2026-09-30, session 4 (R10 / R10b): official external data, measured and closed

**Repository:** `buffedlizard55-lab/13GEMSDOE` · branch `arena/01a0f3f0-13gemsdoe`
(base commit `bb235b3f1d237cacf88a0abf2e18080e58e6ca9c`)
**Status of every number below:** local catalogue hide-and-recover proxy
measurements. They are **not** public or private leaderboard performance, and none
of them is a receipt for any historical file label.

---

## 1. The one-paragraph version

Six free, official, public-domain USGS products were staged and hash-verified twice
each; four geological hypotheses were **predeclared before any map was built**; all
four were implemented, unit-tested and measured on the identical paired holdout
protocol, plus eight refinement configurations in a second predeclared round. **All
24 challenger configurations across R8, R9, R10 and R10b lose to `topo_05_sp3`**
(confirmation worst-rule mean DTI **0.08687**), so **no weekly submission slot was
spent** and the downloadable artifact is unchanged. On the way, one long-standing
irregularity was **resolved by measurement**: provided band 6 `tc` is the
**radiometric total count** (ρ 0.99998, R² 0.9980, slope 1.007 against the official
USGS grid, plus the K + Th + U closure test) — its embedded description is wrong, and
this repository's own earlier "disproved" verdict is retracted in place with its
reasoning preserved.

---

## 2. Compliance with the standing brief

| Brief requirement | Status | Evidence |
|---|---|---|
| 3–5 new geological hypotheses, each naming layers, physical signature, why it catches catalogue-missing faults, and how it differs from prior work; ranked by expected ΔDTI × cost | ✅ 4 predeclared + 2 screened out before build | `knowledge/06_r10_hypotheses.md` |
| If new external data is needed, name the free official source and verify obtainability **first** | ✅ verified before any detector code: licence, egress path, grid conformance, double hash verification | `reports/external_manifest.json`, `reports/external_provenance/` (11 records), `reports/external_audit.json` |
| Validate on spatially-blocked holdout **before** spending a submission slot | ✅ 306 + 162 paired fold scorings, protocol regression check PASS in both runs | `reports/holdout_r10_2026-09-30.json`, `reports/holdout_r10b_2026-09-30.json` |
| No slot spent on anything that has not beaten the current best under multiple withholding rules | ✅ **0 slots spent** — nothing passed the gate | §4 below |
| Ranked variants judged by direct paired holdout DTI, not chance ratios; no inference of hidden truth size from leaderboard scores | ✅ paired per-fold deltas only; no chance ratio appears anywhere in the R10 reports | `paired_vs_reference` blocks |
| Unique maps only; canonical pixel-identity check before writing artifacts | ✅ no new artifact was written this session, so no duplicate risk was created; the shipped artifact keeps its recorded identity checks | `reports/latest_submission.json` |
| Site: downloadable TIF first, unique name + note, executive summary with exact steps, [0,1]-rejection triage | ✅ preserved and rebuilt; hero still leads with the download; R10/R10b evidence added | `docs/index.html`, `docs/executive_summary.html`, `docs/evidence.html` |
| Deep research into geothermal-vent science from official verified sources; contrarian but grounded | ✅ vent conjunction built from `knowledge/04_geothermal_vents.md`; its predeclared mechanism was **wrong** and is corrected on the record rather than quietly dropped | §5 |
| No hallucination; verify line by line; provide links for manual review | ✅ every external claim carries a URL, a sha256 or a git blob SHA; every forum quote was re-fetched this session through Discourse `/print` | `knowledge/01_verified_facts.md` (re-verification record 2026-09-30), `docs/sources.html` |
| Flag irregularities rather than smoothing them over | ✅ 2 new irregularities (I-13, I-14), 1 resolution (I-2), 1 self-correction, 1 fetch failure recorded | §6 |
| Three passes: implement+verify → review for bugs/edge cases → re-check against the request | ✅ §7 | tests 52/52 |
| PR and merge to main, plus remaining work and blockers | ⚠️ **blocked on GitHub authentication** — work is committed locally as a single commit on `arena/01a0f3f0-13gemsdoe` but `git push`, `gh api` and `gh pr` all return *Bad credentials* / *token in GH_TOKEN is no longer valid*. Remaining work and blockers are documented (§9). | §8 |

---

## 3. What was built (files added or changed this session)

**New code**

| file | what it does |
|---|---|
| `src/gems/external.py` | provenance-driven loader for `data/external/`; dequantisation constants are read at run time from the sibling provenance records, never typed by hand; raises rather than guessing |
| `scripts/fetch_external_data.py` | stages the six products and verifies each twice (sha256 from provenance + git blob SHA-1 from the sibling tree) |
| `scripts/audit_external.py` | streaming audit: grid conformance, QFFDB catalogue gap, band identity vs official channels, per-channel AUC/novelty, common domain |
| `scripts/build_external_detectors.py` | builds the eight R10 maps one channel at a time (OOM discipline) and writes per-map AUC / top-5 % recall |
| `scripts/validate_r10_holdout.py` | predeclared paired validation, 17 configurations × 18 folds, tie diagnostics on every row |
| `scripts/validate_r10b_holdout.py` | refinement round: tune-only selection, confirmation read for the selected configuration and the reference only |
| `scripts/audit_band6_identity.py` | settles I-2 with a criterion written before the run (ρ > 0.999 ∧ R² > 0.99 ∧ closure ρ > 0.99) |
| `tests/test_r10.py`, `tests/test_r10b.py` | 20 new unit tests (52 total, all passing) |

**Changed**

`src/gems/detectors.py` (R10 detector section + `thin=` switches so the same
composites can serve either crest extraction or dense fusion), `knowledge/01`
(re-verification record 2026-09-30, facts 1.9–1.11, band-6 mapping corrected),
`knowledge/02` (I-2 resolved, I-13 and I-14 added), `knowledge/03` (R11 shortlist),
`knowledge/06` (R10 register + results + R10b predeclaration and result),
`README.md` (session-4 review, orientation rows, layout, reproduction commands),
`scripts/build_site.py` (+308 lines of generated evidence), `docs/*` (rebuilt).

---

## 4. Results

### 4.1 External data staging and verification

| product | bytes | sha256 ✓ | blob ✓ | official source |
|---|---|---|---|---|
| `lidar_scarp_features_u8.tif` | 36,943,606 | ✅ | ✅ | USGS 3DEP 1 m DEM (716 tiles) → 2 m morphometrics → 100 m aggregate |
| `geodawn_rad_u8.tif` | 26,612,970 | ✅ | ✅ | GeoDAWN radiometrics, DOI 10.5066/P93LGLVQ |
| `geodawn_extensions_u8.tif` | — | ✅ | ✅ | GeoDAWN derivative ratios + TMI-up150 |
| `radiometric_u8.tif` | — | ✅ | ✅ | GeoDAWN radiometrics (linear lo/hi quantisation) |
| `topo_u8.tif` | — | ✅ | ✅ | 3DEP topographic morphometrics (9 bands) |
| `qfaults_prior_u8.tif` | — | ✅ | ✅ | USGS QFFDB, DOI 10.5066/P9BCVRCK — **analysis only** (leakage risk) |

All six conform exactly to the competition grid (EPSG:32611, 100 m, 3730×3292,
transform 243350 / 4508550). Common domain 3,205,306 px (62.0 % of the footprint).
Licence: USGS public domain, which satisfies the organiser's condition that
participants hold a licence permitting use in the challenge **and** sharing with the
sponsor ([forum 11528](https://community.drivendata.org/t/paid-for-external-data-license/11528)).

### 4.2 Signal quality vs score (the central finding)

The R10 maps are **better pixel classifiers than any provided band** —
AUC 0.5282–0.5770 against 0.5615 for `geod_shearrate` — and still lose.

| map | AUC (full catalogue) | recall in own top 5 % | non-zero share of footprint |
|---|---|---|---|
| `R10_dzt_field` | **0.5770** | 0.0534 | 97.7 % |
| `R10_vent_dzt` | 0.5680 | 0.0831 | dense |
| `R10_scarp_field` | 0.5663 | 0.0541 | 74.0 % |
| `R10_vent` | 0.5660 | **0.0841** | dense |
| `R10_alter_field` | 0.5282 | 0.0691 | 31.1 % |
| thinned crests (dzt / scarp / alter) | 0.502–0.505 | 0.042–0.051 | 1.6–2.4 % |

Holdout outcome, confirmation folds (reference **0.08687** worst-rule mean):

| configuration | confirm worst | confirm mean | Δ mean | P_w | R_w | px | verdict |
|---|---|---|---|---|---|---|---|
| `topo_05_sp3` | **0.08687** | 0.09763 | — | 0.0276 | 0.2874 | 185,290 | REFERENCE |
| `topo05_plus_alter02_sp3` | 0.08593 | 0.09651 | −0.00113 | 0.0257 | 0.3363 | 233,565 | LOSES (1/6 rules) |
| `topo05_plus_vent02_sp3` | 0.08443 | 0.09633 | −0.00130 | 0.0260 | 0.3229 | 221,844 | LOSES (1/6) |
| `ventdzt_08_sp3` | 0.08396 | 0.09311 | −0.00452 | 0.0292 | 0.2198 | 134,376 | LOSES (1/6) |
| `vent_08_sp3` | 0.07526 | 0.09075 | −0.00688 | 0.0293 | 0.2031 | 124,009 | LOSES (1/6) |
| … 11 further R10 configurations | 0.05103–0.07490 | — | −0.0068…−0.0339 | — | — | — | all LOSE |
| `fuse_vent_w050_sp3` (R10b, tune-selected) | 0.08286 | 0.09771 | +0.00008 | 0.0294 | 0.2487 | 150,650 | LOSES (2/6 rules, 6/12 folds) |

Mechanism, measured twice: the marginal weighted precision of every external block
is below the metric's own inclusion bar `0.2 × DTI` — 0.0094 (dzt), 0.0096 (scarp),
0.0138 (vent), 0.0141 (alter) at 2 % coverage, and 0.0136–0.0166 at 0.5–1 %
coverage, against bars of 0.0169 (tune) and 0.0195 (confirmation). External
evidence buys precision and spends recall; under β = 2 that is a wash at best.

Protocol hygiene: both runs reproduced the archived reference per-fold DTI values
exactly (18/18 folds, 0 mismatches) before any verdict was read, and all 468 scored
rows report `tie_fraction` 0.00 with zero selections at score 0 — no verdict rests on
tie order (see I-14).

### 4.3 Band 6 identified (I-2 resolved)

| measurement | band 6 vs official `radiometric::rad_tc` |
|---|---|
| Spearman ρ | **0.99998** |
| Pearson r | 0.99902 |
| OLS `band6 = a·rad_tc + b` | a = **1.00729**, b = −0.12763 |
| R² / RMSE | **0.99804** / 0.19577 band-6 units |
| median ratio (IQR) | 1.00000 (0.99867–1.00134) |
| percentiles p1 / p50 / p99 | 7.7223 / 18.4817 / 29.1005 vs 7.7140 / 18.4559 / 29.1002 |
| closure band6 ≈ 7.543 × (K + Th + U) | ρ 0.99577, R² 0.99023 |
| individual windows | Th ρ 0.913, K 0.886, U 0.718 — exactly the physics of a total count |

Consequences: `HE_lin_tc` is restored as a genuine radiometric lineament detector;
band 6 carries **no** information we did not already have from the official release;
and, as a side benefit, the competition's own band reproducing our staged
re-gridding to R² 0.998 **independently validates the external staging pipeline**.

---

## 5. Self-correction recorded against ourselves

R10-4 (vent conjunction) was predeclared as "↓ standalone (F2 punishes low recall)".
The built map measured the **highest** top-5 % recall of the whole family (0.0841) —
the conjunction is not low-recall in the provided footprint. It still loses, for a
different reason than predicted (recall 0.2031 < reference 0.2874 while the precision
gain is too small to pay for it). The predicted *mechanism* was wrong; the predicted
*direction* was right. Both facts are in `knowledge/06_r10_hypotheses.md` rather than
being silently re-narrated.

---

## 6. Irregularities flagged this session

* **I-13 (new, 🟠)** — univariate signal ranking does not predict holdout DTI in this
  competition. AUC ranked dzt first and vent last; the measured holdout order was
  almost the reverse. Screening on AUC cost a full build-and-validate cycle. The
  binding constraint is recall, and only neighbourhoods the crest never touches can
  add any.
* **I-14 (new, 🟡)** — top-k over a sparse crest map silently selects by row-major
  position. The thinned crests carry 1.6–2.4 % non-zero pixels, so a "top 5 %"
  request would have filled ~134k–177k slots with score-0 pixels chosen by position —
  a spatial bias masquerading as a prediction. Detected before scoring; crest
  configurations were capped at their own support mass and every row now reports
  `n_selected_at_zero_score` and `tie_fraction`.
* **I-2 (resolved, 🟢)** — band 6 is the radiometric total count; its embedded
  description does not describe the array. That is a documentation defect in the
  provided data and is worth raising with the organisers. The earlier "disproved"
  verdict rested on an unverified units assumption (that a count rate must be
  10²–10⁴ cps); the official grid itself spans 5.47–30.27 here.
* **Verification gap, disclosed** — thread 11516 could **not** be re-fetched this
  session (the fetch proxy returned `SignatureDoesNotMatch` twice). Its two
  organiser quotes remain as verified verbatim on 2026-09-29 and are marked
  "not re-verified this session" in `knowledge/01_verified_facts.md`.
* **Egress limitation, unchanged** — `usgs.gov`, `sciencebase.gov`,
  `prd-tnm.s3.amazonaws.com`, `gdr.openei.org` and `drivendata.org` are TLS-blocked
  from this sandbox; official products reach it only through this group's sibling
  GitHub mirrors, each file verified against two independent pins. No submission can
  be uploaded from here — the site ships the artifact and the exact manual steps.

---

## 7. Three-pass record

* **Pass 1 — implement and verify.** Loader, four detectors, builder, two validation
  protocols, band-6 audit; 52 unit tests green; `build_detectors.py` regenerated the
  cached maps (418 s) so the R10 validation used freshly built inputs; both holdout
  runs exited 0 with protocol regression PASS.
* **Pass 2 — review for bugs and edge cases.** Found and fixed: (i) three degenerate
  R10 unit tests that asserted behaviour on **constant** synthetic fields, where any
  percentile normaliser is undefined — rewritten with varied fields plus a
  sparse-input regression test; (ii) `vent_conjunction` flooring an all-zero
  (dead-input) field to 1e-6 instead of vetoing — a dead channel now zeroes the
  conjunction; (iii) NMS crest fragmentation and `robust_norm` sparsity collapse —
  support-band counting and `_normalize_field`; (iv) the I-14 tie hazard, handled by
  capping crest mass and reporting tie diagnostics; (v) OOM (exit 137) in the first
  external audit — rewritten streaming, one channel at a time, and the same discipline
  applied to the detector builder on this 3.9 GB box; (vi) `audit_band6_identity.py`
  would have raised a bare `KeyError` if the criterion channel were ever renamed — now
  it refuses to issue a verdict instead of guessing (measurements re-run and confirmed
  bit-identical).
* **Pass 3 — re-check against the original request.** Hypotheses predeclared before
  implementation ✅; external source named and obtainability verified first ✅;
  holdout gate honoured — zero slots spent ✅; paired DTI only, no chance ratios, no
  inference from leaderboard scores ✅; site still download-first with name, note,
  executive steps and the [0,1] triage path ✅; knowledge stored from official sources
  with links ✅; user's brief reproduced verbatim in README and charter, re-read at the
  start of the session ✅.

---

## 8. Submission decision and repository state

**No submission slot was spent.** Nothing passed the predeclared gate, so the
recommendation is unchanged: the primary downloadable artifact remains
**`13gems-toporef-holdoutref.tif`** (`topo_05_sp3` — `BASE_topo_ridge` top 5 %,
`decimate_grid` spacing 3, binary, catalogue included), labelled
`BEST_LOCAL_REFERENCE_NOT_PRIVATE_TEST_CLAIM`, with the all-finite zero-fill twin as
the documented fallback if the form repeats its historical range error.

One *cost* result is worth keeping: `fuse_vent_w050_sp3` scores the same on the
confirmation mean (+0.00008) with **34,640 fewer pixels**. It is **not** an
improvement and must not be presented as one; it is only the measured option if a
future round needs a smaller map.

Site rebuilt (`docs/`, 5 pages, downloads intact). Tests 52/52 (43 carried over plus
9 new fusion/percentile tests). Worktree clean.

**PR and merge: NOT DONE — blocked, and reported as blocked rather than claimed.**
Everything above is committed as one commit on the session branch
`arena/01a0f3f0-13gemsdoe` (subject: *"R10/R10b: stage + measure official USGS
external data; resolve band-6 identity (I-2); no slot spent"*), but the push failed:

```
$ git push -u origin arena/01a0f3f0-13gemsdoe
fatal: could not read Username for 'https://github.com': terminal prompts disabled
$ gh auth status
X github.com: authentication failed - The github.com token in GH_TOKEN is no longer valid.
$ gh api repos/buffedlizard55-lab/13GEMSDOE
{ "message": "Bad credentials" }   # read access fails too, so no PR can be opened
```

No credentials were requested or stored in chat, per the project's rules. Once the
GitHub connection is restored in Arena, the remaining steps are exactly two:
`git push -u origin arena/01a0f3f0-13gemsdoe`, then open a PR from that branch into
`main` and merge it. Nothing in the commit depends on the merge having happened.

---

## 9. Remaining work (ranked) and blockers

The R11 shortlist, generated this session and constrained by I-13, is in
`knowledge/03_hypotheses.md`:

1. **R11-4 greedy marginal-precision assembly** (low cost) — stop adding blocks at the
   first one whose measured marginal precision falls below `0.2 × DTI`, turning the
   audited rule from a post-hoc diagnosis into the construction procedure. This is the
   only candidate that cannot add a losing block by construction.
2. **R11-2 basin-floor magnetic-continuity lineaments** (low cost, provided bands only)
   — strike-continuity rather than gradient magnitude, emitted only where the crest
   detector is silent, so every hit is a new 300 m neighbourhood.
3. **R11-1 basement-depth juxtaposition edges** (medium) — lateral step in
   depth-to-conductive-base under alluvium; provided-band version first, official grids
   only after obtainability is verified.
4. **R11-3 paleo-geothermal feature halos** (medium) — sparse, high-precision halos
   around mapped sinter/tufa and hot springs (INGENIOUS GDR 1391, CC-BY-4.0); the block
   shape the inclusion rule actually rewards.

**Blockers.**

* **Upload access.** No submission can be filed from this sandbox (egress blocked, no
  DrivenData credentials, and none should ever be requested in chat). The three-slot
  rolling allowance is therefore spent by a human following `docs/executive_summary.html`.
* **I-1 remains critical.** `example_submission.tif` is value-identical to
  `existing_faults.tif` in our mirror while the official page says the sample predicts
  total fault absence. Settling it needs one logged-in re-download; until then every
  format assumption derived from that file is provisional.
* **I-8 remains unresolved.** The historical "Predicted values must be in range [0, 1]"
  rejection has no confirmed cause; the triage path ships both encodings and asks the
  submitter to record which one the form accepted.
* **Phase-2 data obtainability.** The two most promising official products for R11-1 and
  R11-3 sit behind blocked hosts and are 12 GB+; they need an open-egress runner or a
  manual download before any code is written around them.
* **Label-set scope (I-10).** Catalogue hide-and-recover measures recovery of *known*
  faults, while the scored truth is *new* faults. Every number here inherits that gap;
  it is the largest single source of uncertainty in the gate and cannot be closed from
  public data.
