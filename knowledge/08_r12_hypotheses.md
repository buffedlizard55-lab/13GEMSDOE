# R12 predeclared register — written 2026-09-30 (session 6) BEFORE any fold was scored

Reference to beat: **`greedy_r11`** (R11-4 greedy marginal-precision assembly),
archived confirmation worst-rule-mean DTI **0.09175** vs 0.08694 for `topo_05_sp3`
([`reports/holdout_r11_2026-09-30.json`](../reports/holdout_r11_2026-09-30.json)).
Fold set, seeds, 5-px buffer, FoldScorer, tune/confirm split, spacing-3 decimation:
identical to `scripts/validate_r10_holdout.py` (as reused by R11). The in-run
`topo_05_sp3` row must reproduce the archived per-fold DTI within the relative
tolerance and every verdict is paired **in-run** (protocol amendment for I-15, R11).

This register was written and committed before `scripts/validate_r12_holdout.py`
was run. The only files consulted while writing it were prior reports and detector
caches — no new fold scoring.

## Candidates (ranked by expected ΔDTI ÷ cost)

| Rank | ID | Layers | Signature | Why it targets catalogue-GAP faults | Difference from prior work | Data needed | Cost |
|---|---|---|---|---|---|---|---|
| 1 | **R12-1 hysteresis crest continuation** (`hyst_topo_add005/010/020`) | band 4 `det_elev_slope` as already transformed into the cached `BASE_topo_ridge` ridge-strength field (Hessian σ=1.5, NMS-thinned, robust-normed) | Canny-style **two-threshold linking**: strong cores = the reference top-5 % crest (identical construction to `topo_05_sp3`); the weak response pool = ridge pixels ranked just below the cut that lie within **10 px (8-connected) of a strong chain**; linked weak pixels are grid-3 decimated like the reference and the added mass is capped at 0.5 % / 1 % / 2 % of the valid footprint | mapped traces end where mapping stopped, not where the structure ends; the crest response continues past the mapped end along strike, and the organizers define **extensions** as new faults. The metric's TP kernel is 300 m (3 px), so a linked continuation earns credit wherever the hidden extension runs within 300 m of the chain | **No connectivity-based transform exists in this repo** — every prior map is a global rank cut, a conjunction mask, or a distance field. R9-1 gap-close bridged *between catalogue endpoints* and lost on marginal precision; this grows *along the already-accepted strong chains from the detector response*, which is the opposite direction of information flow | none (cached map) | low |
| 2 | **R12-2 finer-step greedy over a widened pool** (`greedy_r12`) | 12 catalogue-free cached maps: the R11 pool (`R11_basin_mag`, `HA_worms_rtp`, `HB_tdr_rtp`, `R7_crossgrad`, `R8_tpi`, `R8_flow`, `R10_vent`, `R10_alter_field`, `R10_dzt_field`) plus `R7_hinge_curv`, `R8_openness`, `R8_isocoherence` | the R11-4 greedy with **finer blocks (0.10 % / 0.25 %)** and up to **6 steps**; same audited inclusion rule (>300 m from the assembly, pooled tune marginal weighted precision > 0.2 × DTI, tune worst-rule must improve) | the only mechanism (I-13) that can raise DTI: reach neighbourhoods the crest never touches; finer blocks extract the best sub-blocks near the acceptance boundary that R11's 0.25 % grid could not | R11-4 searched 9 maps × {0.25, 0.5, 1 %} × ≤4 steps; this searches 12 maps × {0.10, 0.25 %} × ≤6 steps. **Predeclared as an extension of the winning mechanism** (README next-step 3), not as a new mechanism | none (cached maps) | medium (runtime) |
| 3 | **R12-3 basin-floor magnetic continuity at its true support** (`topo05_plus_basinmag001/0014_sp3`) | bands 2 `rtp`, 19 `det_elev_slope`, 15 `depth_to_base_surf` (cached `R11_basin_mag`, 7,610 non-zero px = 0.147 % of valid) | plain union at 0.10 % / 0.14 % — **at or below the map's support**, so no row-major zero-score padding (the I-14 failure that invalidated R11-2) | buried range-front faults have no scarp; the crest family has ~zero coverage on basin floors; |RTP| crests gated to lowest-slope ∧ deepest-basement terciles target exactly those floors | retest predeclared in the R11 register ("retest next session at coverage ≤ 0.14 %"); not a new mechanism, but the first *valid* measurement of R11-2 | none (cached map) | low |
| 4 | R12-4 magnetic depth-to-source (Euler deconvolution, SI≈1) clusters as lineament seeds | band 2 `rtp` | Euler solution clusters = depth-resolved edges of magnetisation contrasts; deep-rooted, subdued-surface-expression structures | targets blind spot (a) — buried structures — at depths worms/TDR do not resolve | no potential-field *depth* transform exists in this repo (worms = multiscale edges; TDR/theta = angle filters; crossgrad = joint statistics). **Deferred, not run this session**: new physics code + unit tests needed; risk of subtle implementation error is high vs the two predeclared candidates above | none | medium–high — **deferred** |

## Decision rule (predeclared)

* All configurations scored on all 18 folds (6 tune, 12 confirmation), same
  FoldScorer, same `20260930` seeds: `topo_05_sp3`, `greedy_r11` (archived recipe
  rebuilt in-run: `R10_vent@0.25 %` → `R8_tpi@0.25 %` → `R10_dzt_field@0.25 %`,
  each restricted >300 m from the prior assembly), the three hysteresis budgets,
  `greedy_r12` (recipe found on tune folds only, then frozen), and the two
  basin-magnetics unions.
* Selection = highest **tune** worst-rule-mean DTI among the challengers.
* A challenger **WINS** only if it beats **both** in-run references (`topo_05_sp3`
  AND `greedy_r11`) on tune AND confirmation worst-rule-mean DTI, is not worse on
  ≥ 4 of 6 confirmation rule means, and its paired confirmation mean gain exceeds
  10 × the largest observed reference drift (I-15). Otherwise FRAGILE/LOSES.
* **No submission slot is spent unless a challenger WINS.** If nothing wins,
  `greedy_r11` remains the shipped artifact (now served in its all-finite,
  form-verified encoding — see `reports/primary_flip_2026-09-30.json` and I-8).
* Every greedy step's tested blocks, marginal precisions and bars are reported in
  full (order-dependence audit); every top-k records tie diagnostics (I-14).

## Memory limitation (new, flagged I-17)

The 3 GB sandbox caps the in-memory pool: each ranked map costs ~98 MB (float32
score + int32 order), so the widest defensible pool this session is 12 maps.
A full 30-stem pool sweep (all catalogue-free caches) is deferred to a larger-RAM
runner and listed in Next steps.

## Results (appended after the run — see `reports/holdout_r12_2026-09-30.json`)
