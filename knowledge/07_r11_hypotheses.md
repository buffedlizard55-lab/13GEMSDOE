# R11 predeclared register — written 2026-09-30 (session 5) BEFORE any fold was scored

Reference to beat: `topo_05_sp3` (BASE_topo_ridge top-5 %, 300 m grid decimation),
archived confirmation worst-rule-mean DTI **0.08687**
([`reports/holdout_candidate_r8_2026-09-30.json`](../reports/holdout_candidate_r8_2026-09-30.json)).
Fold set, seeds, 5-px buffer, FoldScorer, tune/confirm split: identical to
`scripts/validate_r10_holdout.py`; the reference row must reproduce the archived
per-fold DTI exactly (protocol regression check) before any verdict is read.

## Candidates (ranked by expected ΔDTI ÷ cost; source: knowledge/03_hypotheses.md R11 shortlist)

| Rank | ID | Layers | Signature | Why it targets catalogue-GAP faults | Difference from prior work | Data needed | Cost |
|---|---|---|---|---|---|---|---|
| 1 | **R11-4 greedy marginal-precision assembly** | reference + catalogue-free cached maps (listed in the script `POOL`) | blocks restricted to pixels **> 300 m from the current assembly**; accepted only while pooled tune-fold marginal weighted precision `ΔTP_w/(ΔTP_w+ΔFP_w) > 0.2·DTI` | each accepted block reaches neighbourhoods the crest never touches — the only mechanism I-13 allows to raise DTI | R8–R10b fixed coverages *then* measured; nothing used the audited inclusion rule as the stopping criterion, and nothing excluded the reference's own neighbourhood | none (provided bands + already-staged USGS products) | low |
| 2 | **R11-2 basin-floor magnetic continuity** (`R11_basin_mag`) | bands 2 `rtp`, 19 `det_elev_slope`, 15 `depth_to_base_surf` | along-strike-persistent crests of |∇RTP| minus its σ = 800 m Gaussian regional (gradient first — high-passing the field first produced parallel side-lobe crests in the synthetic unit test, fixed before any fold was scored), gated to lowest-slope tercile ∧ deepest-basement tercile | buried range-front faults have no scarp; the crest family has ~zero coverage on the basin floor | `BASE_tmi_hg` is magnitude-only and domain-wide; R7 cross-gradient is a product gate; neither is basin-gated nor persistence-filtered | none | low |
| 3 | R11-1 basement-depth juxtaposition edges | band 15, bands 11/18; optional USGS depth-to-basement grids | step in basement depth across a line | buried faults | not step-tested before | optional external (12 GB, obtainability unverified) | medium — **deferred** |
| 4 | R11-3 paleo-geothermal feature halos | INGENIOUS GDR 1391 (CC-BY-4.0) | sparse halos around mapped sinter/tufa/hot springs | ground evidence of fault-controlled upflow | independent data source | https://gdr.openei.org/submissions/1391 — host blocked from sandbox at last check | medium — **deferred** |

## Decision rule (identical to R10b)

* R11-2 standalone config `topo05_plus_basinmag{005,010}_sp3` (union at 0.5 % / 1 %) and
  the R11-4 greedy recipe `greedy_r11` are scored on all 18 folds.
* Selection = highest TUNE worst-rule-mean DTI. A candidate **WINS** only if it beats
  the reference on BOTH tune and confirmation worst-rule-mean DTI and is not worse on
  ≥ 4 of 6 confirmation rule means. Otherwise FRAGILE/LOSES. **No submission slot is
  spent unless a candidate WINS.**
* Greedy path (every step, every tested block, its pooled marginal precision and the
  bar) is reported in full because greedy selection is order-dependent.

Results: see `reports/holdout_r11_2026-09-30.json` and the section appended below after the run.

## Protocol amendment (recorded before the verdict was read) — irregularity I-15

The first two runs aborted on the protocol regression check: the in-run reference
`topo_05_sp3` differed from the archived per-fold DTI by up to 1.45e-4 (≤ 0.2 %
relative). The unmodified `scripts/validate_r10b_holdout.py` fails identically in this
session, so the cause is the rebuilt detector cache (numpy 2.4.6 / scipy 1.17.1; the
archive never pinned library versions or map hashes), not the R11 code. Amendment:
the check is relative (≤ 1 % of DTI), all verdicts are paired against the **in-run**
reference, and a WIN additionally requires the paired confirmation mean gain to
exceed **10×** the largest observed drift. The BASE_topo_ridge sha256 and library
versions are now written into the report.

## Results (appended after the run; `reports/holdout_r11_2026-09-30.json`)

| config | tune worst-rule | confirm worst-rule | confirm mean | verdict |
|---|---|---|---|---|
| `topo_05_sp3` (in-run reference) | 0.03852 | 0.08694 | 0.09765 | reference |
| `greedy_r11` | 0.03992 | **0.09175** | **0.10344** | **WINS** — 6/6 confirmation rule means, 18/18 paired folds, gain +0.00579 > 10× drift 0.00145 |
| `topo05_plus_basinmag005_sp3` | 0.03793 | 0.08573 | 0.0963 | **INVALID (I-14)** — see below |
| `topo05_plus_basinmag010_sp3` | 0.03760 | 0.08532 | 0.09599 | **INVALID (I-14)** |

Greedy path (tune folds only): step 1 `R10_vent`@0.25 % (marginal precision 0.0284 vs
bar 0.0169, ACCEPT) → step 2 `R8_tpi`@0.25 % (0.0264 vs 0.0172, ACCEPT) → step 3
`R10_dzt_field`@0.25 % (0.0269 vs 0.0176, ACCEPT) → step 4 best 0.0177 vs bar 0.0179 and
tune worst-rule fell → STOP. Selection diagnostics for every greedy block: tie fraction
≤ 0.0016, zero zero-score selections.

**Why this worked where R10/R10b failed** — the same external maps (vent, dzt) lost
as plain unions at 0.5–2 % because most of their mass landed within 300 m of pixels the
crest already predicted (zero new credit, full FP cost). Excluding the assembly's own
300 m neighbourhood and taking only the top 0.25 % raised their marginal precision
from 0.0094–0.0166 to 0.026–0.028, above the bar. This is the I-13 prediction confirmed.

**R11-2 is not a valid measurement.** `R11_basin_mag` has only 7,610 non-zero pixels;
the 0.5 % and 1 % unions requested 25,836 / 51,673, so up to 44,111 pixels per fold were
selected at zero score in row-major order — exactly the failure I-14 forbids. The rows
are kept for audit but carry no verdict. Retest next session at coverage ≤ 0.14 %
(its support), predeclared.
