> **ARCHIVE — SUPERSEDED; DO NOT USE ITS CHANCE/LIFT CONCLUSIONS.** This report
> records a prior session. Its public chance inference, candidate-to-chance ratios,
> “measurement artefact”/plateau interpretation, low-slope hidden-fault analogue,
> and resulting submission recommendation have been withdrawn or qualified.
> Several chance calculations used the full valid-grid area instead of the fold's
> smaller eligible `eval_mask`. Use direct-DTI summaries and current status in
> [`knowledge/02_irregularities.md`](../knowledge/02_irregularities.md),
> [`knowledge/03_hypotheses.md`](../knowledge/03_hypotheses.md), and
> [`reports/holdout_candidate_r8_2026-09-30.json`](holdout_candidate_r8_2026-09-30.json).
> The historical file is retained for audit trail only; it is not a current model
> recommendation or hidden/private-test estimate.

---

# Session report — 2026-09-29 (session 2)

Scope: review the repo, re-verify every official claim line by line, fix what
the review found, add five new geological hypotheses plus the first supervised
detector, validate them on the hide-and-recover holdout, and produce a fresh
submission.

Nothing in this report is recalled. Every number is either measured by a script
in this repository or quoted from a URL fetched during this session.

---

## 1. What was verified from official sources this session

| Claim | Source | Result |
|---|---|---|
| DTI formula, α=0.2, β=0.8, R=300 m=3 px, `k(d)=max(1−d/R,0)` | [problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) | ✅ verbatim |
| Worked example `TP_w 3.00, FP_w 1.89, FN_w 2.00 → 0.60` | same page, "Scoring example" | ✅ verbatim; reproduced locally as 0.6028 |
| Four submission-format bullets (EPSG 32611, 100 m, same bounds, null/nan outside, single float32 layer in [0,1]) | same page, "Submission format" | ✅ verbatim |
| "A sample submission that predicts total fault absence is provided" | same page | ✅ verbatim — this is what makes irregularity I-1 decisive |
| The six provided-feature bullets | same page | ✅ verbatim; they account for 16 of the 19 bands |
| The figure is `gems_tc_tmi.png`, captioned "radiometric (left) and magnetic (right)" | same page | ✅ **new** — first-party evidence on band 6 |
| Known USGS/INGENIOUS pixels masked in both rounds | [thread 11516 post 2](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/2) | ✅ verbatim |
| Mask is pixel-exact; near-trace predictions fully penalized; new-fault pixels may lie within 300 m of known traces | [thread 11516 post 4](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4) | ✅ verbatim, all three numbered answers |
| "new fault" = any fault pixel not already captured, incl. newly mapped geometry of an existing system | [thread 11536](https://community.drivendata.org/t/where-do-you-draw-the-line/11536) | ✅ verbatim |
| Organizers will not share test-fault data sources or fault types | [thread 11527 post 7](https://community.drivendata.org/t/how-were-the-new-test-faults-identified-data-sources-and-fault-types/11527/7) | ✅ verbatim |

All four organizer claims carried into this work are accurate. No correction
needed.

## 2. What was wrong and is now fixed

| # | Problem | Fix |
|---|---|---|
| I-2 | The previous session asserted "with high confidence" that band 6 `tc` is the radiometric total count. Never tested against the raster. | `scripts/audit_bands.py` measures it. Band 6 is bounded in [2.953, 88.567] with p99 = 29.10, is *smoother* than the supplied gradient bands (`tc` lag-1 autocorrelation 0.9805 vs `tmi_hg` 0.9112 and `tmi_vg` 0.8238), and matches **none** of eight standard magnetic edge angles (all \|r\| < 0.04). Reported as **UNIDENTIFIED** with both pieces of evidence on the record. |
| I-12 | `R6_horse_full` was swept on the holdout as if it were a physical detector, but it is built from the **full** catalogue including the withheld segments — pure leakage. `HD_strain` had the same defect in weaker form. | `scripts/run_holdout3.py` refuses to sweep any `*_full` map and rebuilds both per fold from the VISIBLE catalogue only. |
| I-11 | The holdout's ground truth is catalogue faults, which are 1.7× over-represented on slopes. Plain `dti` therefore rewards topographic detectors for the wrong reason. | Measured (19.7 % of catalogue pixels in the flattest third of ground, which is 33.0 % of the footprint → factor 0.596) and every candidate is now also scored on the concealed subset. |
| — | `scripts/summarize_holdout.py` could only read `holdout_v2.json`. | Takes `--input` / `--output`. |
| — | `decimate_grid` materialised a `(bh, bw, sp·sp)` block tensor plus an int64 argmax — ~350 MB of transient memory, enough to OOM-kill the sweep on this 3 GB box. | Rewritten with strided views; verified bit-identical to the previous implementation over 60 randomised trials including forced ties. |
| — | `FoldScorer` computed its FP-weight map in float64. | float32 twin, verified against the float64 reference to 4.1e-8 absolute on DTI. |
| — | `reports/leaderboard_ledger.csv` was referenced but did not exist. | Created, with every per-submission score marked `UNKNOWN` and the reason. |

## 3. What was added

* **`src/gems/detectors.py`**: five new detectors — `cross_gradient_edge`
  (R7-1), `basement_hinge_curvature` (R7-2), `seismicity_gate` (R7-3),
  `edge_consensus` (R7-4), `structural_grain` (R7-5). Each names its layers, its
  physical signature, why it targets a fault *missing* from the catalogue, and
  how it differs from everything already in the repo.
* **`src/gems/supervised.py`**: the first supervised detector in this repository
  — L2-regularised logistic regression on 57 multi-scale context features built
  from all 19 official bands, computed in row blocks so the feature cube never
  exceeds ~150 MB. This is the approach the organizers' own reference solution
  takes (a U-Net) and that this repo had never attempted.
* **`scripts/audit_bands.py`**: measures all 19 bands, tests band 6 against
  eight magnetic edge angles and a bank of candidate transforms, settles whether
  bands 10/16 are distances or densities, and quantifies the catalogue's
  topographic bias.
* **`scripts/run_holdout3.py`**: the R7 sweep with per-fold catalogue rebuilds.
* **`scripts/run_holdout_sup.py`**: the supervised holdout, same protocol.
* **`scripts/validate_ranked.py`**: an A/B test of one specific geometric claim —
  that decimating the **union** once beats decimating each component separately.
* **`scripts/make_submission.py --recipe ranked`**: a genuinely different
  submission construction — a global priority union of every source, thresholded
  at a single pixel budget, then **one** global decimation.

## 4. Results

All numbers below are measured by scripts in this repository on the same
spatially-blocked holdout: whole fault **systems** withheld with a 500 m buffer,
10 folds across 5 withholding rules (random / short / isolated / strike-class /
dense), the visible catalogue masked pixel-exactly as the organizers do, DTI
scored on the withheld pixels alone, against the **closed-form chance DTI at the
actual predicted-pixel count** and 30 coverage-matched random controls (median
relative error 1.1 %). `lift` = candidate DTI / chance DTI on the same fold.
`worst` = the worst of the five withholding rules — the number the shipping rule
uses. Catalogue-derived detectors were rebuilt per fold from the VISIBLE
catalogue only.

Machine-readable evidence: `reports/holdout_v3.json`,
`reports/holdout_verdict_v3.json`, `reports/holdout_supervised.json`,
`reports/ranked_ab.json`, `reports/band_audit.json`.

### 4.1 The five new geological hypotheses (R7-1 … R7-5) — all measured, none won

| rank | family | best config | mean lift | **worst-rule lift** | concealed lift | verdict |
|---|---|---|---|---|---|---|
| 1 | `BASE_topo_ridge` (pre-existing) | cov0.05 / sp3 | 1.09 | **1.06** | 0.51 | still the best honest detector in the repo |
| 2 | `R7_seis_cross` (R7-3) | cov0.005 / sp3 | 1.20 | 0.97 | 0.45 | best mean lift; below chance on the worst rule |
| 3 | `BASE_tmi_hg` (pre-existing) | cov0.05 / sp3 | 1.02 | 0.98 | 0.95 | unchanged |
| 4 | `R7_crossgrad` (R7-1) | cov0.08 / sp3 | 0.96 | 0.93 | 0.94 | does not beat its own inputs |
| 5 | `R6_gravterm` | cov0.005 / sp3 | 1.00 | 0.90 | **1.31** | best concealed lift of any non-prior |
| 6 | `R7_seis_grav` | cov0.01 / sp3 | 1.12 | 0.86 | 0.64 | below chance |
| 7 | `HB_theta_rtp` / `HB_tdr_rtp` | cov0.01 / 0.08 | 0.89 / 0.94 | 0.80 / 0.80 | 0.76 / 0.64 | below chance |
| 8 | `R6_transt` | cov0.08 / sp3 | 1.26 | 0.60 | 0.53 | 4.42x on `strike_60_120`, 0.46x on `random_0` |
| 9 | `R7_consensus4` / `R7_consensus3` | cov0.03 / sp3 | 0.82 / 0.77 | 0.45 / 0.44 | 0.76 / 0.74 | consensus of mediocre detectors is worse than its best member |
| 10 | `HD_strain` | cov0.08 / sp3 | 0.74 | 0.19 | 0.61 | below chance |
| 11 | `R7_hinge_curv` (R7-2) | cov0.08 / sp3 | 0.47 | 0.20 | 1.20 | dead |
| 12 | `R7_grain` (R7-5) | cov0.005 / sp1 | 0.15 | 0.00 | 0.05 | dead (see I-12) |

**None of the five new hypotheses beats the analytic baselines that already
existed.** The pre-measurement ranking put R7-1 first; it measures 0.93 worst-rule
lift, i.e. it does not reach chance. Stage 2 re-scored the ten best stage-1
`R6_transt` configurations on all ten folds: mean lift 1.30, min 0.07, max 4.42 —
above chance on average, with a spread too wide to ship on.

### 4.2 The first supervised detector (H-S) — measured, and it fails for a measured reason

L2-regularised logistic regression on 57 features (19 official bands × {value,
3×3 mean, 9×9 mean}), trained per fold on the visible catalogue only with a 5-px
dilation of the withheld halo excluded, 40 epochs of Adam, 400,000 subsampled
negatives. The top learned weights are physically sensible — `det_elev` 9×9 mean
+1.17, `det_elev` value −0.87, `det_elev` 3×3 mean −0.61, then geodetic shear
rate, second invariant, isostatic gravity and radiometrics.

| family | mean lift over the 5 folds | verdict |
|---|---|---|
| `HS_supervised` | **0.21 – 0.75** | below chance on **every** fold |
| `BASE_topo_ridge`, same run, same folds | 1.06 – 1.17 | reference |

**Why, measured rather than guessed:** of H-S's predicted pixels, **12.4 % lie
within 300 m of the visible catalogue**, against **5.9 – 6.5 %** for every
analytic detector measured in the same run; and only **37.0 %** of H-S's pixels
are more than 3 km from the visible catalogue, against **52.3 – 54.1 %** for the
analytic detectors. The organizers confirmed verbatim that "the buffer does not
apply to known faults" and that "a predicted pixel that is near a known fault
trace but far from a new-fault ground truth pixel will be fully penalized". H-S
puts twice as much of its mass in exactly the region that carries full FP_w
penalty and no possible credit. This is a mismatch between the training
objective (reproduce the catalogue) and the scoring objective (find faults the
catalogue does not already contain), not a tuning problem.

### 4.3 Band 6 `tc` — now UNIDENTIFIED by measurement, on both sides

`scripts/audit_bands.py` (107 s) builds a bank of **51** physically standard
transforms of the other 18 bands and correlates each against band 6. Best is
`gauss9_b13` at Spearman ρ = −0.3547; nothing reaches |ρ| = 0.5. First-party
evidence for the radiometric reading remains (the page's figure asset is
`gems_tc_tmi.png`, captioned "radiometric (left) and magnetic (right)", and the
page's feature list names no tilt angle and no total curvature). Against it, the
measured array is bounded in [2.953, 88.567] with p99 = 29.10 and is smoother
than every supplied gradient band. Both cannot be true of the same array; only
the data-tab documentation settles it.

### 4.4 The one genuinely new submission idea — A/B tested, and it does not win

`scripts/validate_ranked.py` tests one geometric claim: that `TP_w` takes a MAX
over the 300 m neighbourhood, so decimating the **union** once globally should
beat decimating each component separately. Both arms use the same components on
the same folds.

| arm | best config | mean lift | **worst-rule lift** | concealed lift | px |
|---|---|---|---|---|---|
| A — per-component (the `r6` construction) | cov0.08 / sp3 | 0.987 | **0.965** | 0.906 | 657,398 |
| B — global priority union (the `ranked` idea) | budget0.02 / sp3 | **1.024** | 0.898 | 0.425 | 185,013 |

**`global_wins` is false, so `--recipe ranked` is NOT shipped and the shipped
construction — `composite_plus`, which decimates each component separately —
stays.** But
the honest detail matters more than the flag: arm A is *uniformly* at chance
(per-rule lift 0.965 / 0.993 / 0.995 / 1.010 / 0.970) while arm B is the only arm
that beats chance on average at all, and it does so in a specific regime —
`isolated` 1.083 and `oriented` 1.207, against `random` 0.898. Global decimation
is better at isolated and strike-class faults, i.e. at genuinely unmapped
systems, and worse on random and dense ones, at 3.6× fewer pixels. A hybrid that
uses the global union where A is weak is the obvious next experiment.

**Two defects found and fixed while measuring this, both disclosed:**
`robust_norm` silently returns an **all-zero** array for any field more than 99 %
zeros, because its p1 and p99 quantiles then coincide at 0.0. That erased
`extension_rays` (0.1 % nonzero) and `HC_hinge` (0.98 % nonzero) — the recipe's
highest-priority component — from the first run of the script, with no error.
The void first run is preserved as
`reports/ranked_ab_void_robustnorm_bug.json`; the fix is
`robust_norm_nonzero` in `src/gems/detectors.py`, and the same fix was applied to
`scripts/make_submission.py`. Measured sweep of every stored detector: exactly
two of 24 collapse (`HC_hinge`, `R7_grain_full`), plus `extension_rays`.
Arm B is also **budget-insensitive between 0.02 and 0.05** — identical results —
because the priority-union ordering saturates; budget only starts to matter at
0.08.

## 5. The honest status

**No detector in this repository beats a random map of the same size by a wide
margin under every withholding rule.** The best honest candidate is
`BASE_topo_ridge` at 1.06 worst-rule lift; five new hypotheses, one supervised
classifier and one new submission construction were all measured against it this
session and none displaced it. The ranking inverts on the concealed subset
(`BASE_topo_ridge` drops to 0.51 there while `R6_gravterm` rises to 1.31), which
is why every candidate is scored on both.

The only regime with large, reproducible lift remains **tip extension /
correction of mapped traces** (13.9 – 16.1× chance, `reports/composite_validation.json`),
which the organizers explicitly named as part of the target population
("newly mapped geometry of an existing fault system", thread 11536). That is why
the shipped submission is a hedge concentrated where the measured lift is.

**Therefore no new submission was produced this session.** The standing rule is
that a submission slot is only spent on something that beats the current holdout
best; nothing did. `docs/downloads/latest.tif` (recipe `composite_plus`, built
2026-09-29T18:32:49Z) is unchanged and was re-validated this session with
`src/gems/rio.py::validate_submission` — single band, EPSG:32611, 3730×3292,
geotransform (100, 0, 243350; 0, −100, 4508550), all finite values in [0, 1],
sum 380365.0, n_gt0 380365. Its composition, from `docs/downloads/latest.json`:
tip extension rays (reach 2,000 m) 36,478 px + horsetail splay (gap 20, splay 12)
69,170 px + `BASE_topo_ridge` fill at 8 % 236,425 px = 380,365 px (7.36 % of
valid), binary 0/1, decimated one pixel per 3×3 tile, catalogue included (masked
at scoring). Note that the A/B result in §4.4 is a *direct* measurement of this
construction: arm A is per-component decimation, which is exactly what
`composite_plus` does, and it holds 0.965 worst-rule lift — uniformly at chance
across all five withholding rules, never below 0.965 on any of them.

## 6. What still needs doing, in order

1. **Read the per-submission scores off each DrivenData account** and back-fill
   `reports/leaderboard_ledger.csv`. Every "which idea worked" conclusion drawn
   from the leaderboard's *best public* column is unsound until this is done.
   (irregularities I-3, I-4)
2. **Resolve the multi-account question** with the organizers
   (`info@drivendata.org`, or the "Institutional Limit" and "Team member
   eligibility" threads) before any further modelling. A disqualification sets
   P(Win) to zero regardless of model quality. (irregularity I-4)
3. **Re-download `sample_submission.tif` with a login** and confirm whether the
   official file is all-zeros. (irregularity I-1)
4. **Settle band 6 `tc`** from the official data-tab documentation; 51 candidate
   transforms have now been ruled out by measurement. (irregularity I-2)
5. **Fetch INGENIOUS GDR 1391** (`Quaternary Faults v2.zip`, 5.85 MB, CC-BY-4.0,
   DOI 10.15121/1881483) on a machine with open egress. It carries fault **ages
   and slip rates**, which are the age/slip-rate holdout strata the charter asks
   for and which this repository can only proxy with a strike class. It also
   carries Paleo Geothermal Features (sinter/tufa) and 2 m temperature probes,
   which are the two genuinely new geothermal channels nobody here has used.
   (limitation L-2)
6. **Train a real segmentation model — but on a non-catalogue target.** The
   reference solution is a U-Net. H-S shows why naively training on the catalogue
   raster fails: the metric refuses to reward the catalogue's own neighbourhood.
   The formulation to try is hard-negative mining or a one-class objective that
   explicitly excludes a buffer around mapped traces, so the model is rewarded
   for the gaps rather than for the traces. 3 GB of RAM and 2 cores are the
   binding constraint on anything deeper than that.
7. **Test the hybrid submission** the A/B result points at: the global priority
   union for the `isolated` and `oriented` regimes where it beats per-component
   decimation (1.08 – 1.21 vs 0.90 – 0.97), per-component elsewhere. Only spend a
   slot once that hybrid beats `A_percomponent|cov0.08|sp3`'s 0.965 worst-rule
   lift.
8. **Tune the `r6` recipe's pixel budget** against the holdout rather than by
   hand — arm A's worst-rule lift is flat (0.965 at cov0.05 and cov0.08), so the
   budget is currently chosen on no evidence.

## 7. Limitations of this session

* No DrivenData authentication, so the competition rasters came from this
  group's own public repositories with pinned blob SHAs
  (`scripts/fetch_data.py`, `reports/data_manifest.json`). One of those mirrors
  is known to be mislabelled (I-1).
* No private-test feedback. The holdout is a proxy; only *relative* ordering
  between candidates is meaningful, never absolute DTI.
* The withheld pixels are catalogue faults, so the holdout measures "would we
  re-find a catalogue fault that was hidden", not "would we find a fault no
  catalogue contains". The concealed subset is the closest available analogue
  and is reported beside every candidate, but it is an analogue.
* The 9×9 context features of the supervised detector can reach 4 px into the
  5 px withheld buffer. Disclosed, bounded, not eliminated.
* `strike_60_120` withholds only 5,735 pixels, the smallest of the ten folds, so
  `R6_transt`'s 4.42× lift there is the least statistically reliable number in
  the table. It is reported, not shipped.
* Every number in `reports/holdout_v*.json` is prior-run evidence from a
  specific fold construction; re-running with a different seed will move the
  third decimal.
* `run_holdout3.py` (4,911 s) and `run_holdout_sup.py` (1,309 s) each ran alone
  on a 3 GB box; nothing was run concurrently, because doing so OOM-killed the
  sweep three times earlier in the session.
