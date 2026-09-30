# R10 candidate hypotheses — predeclared, ranked, 2026-09-30 (session 4)

Written **before** any R10 fold was scored. Ranking uses only measurements that
already exist at the time of writing
([`reports/external_audit.json`](../reports/external_audit.json), 139 s run) plus
the archived holdout results. Expected gains are *hypotheses to be tested*, not
results. The predeclared decision rule is at the bottom of this file.

---

## 0. What changed this session: four official datasets became obtainable

Limitation **L-2** said external scientific data was unreachable from this
sandbox. That is still true of the *original* hosts — `sciencebase.gov`,
`usgs.gov`, `gdr.openei.org`, `prd-tnm.s3.amazonaws.com` all fail TLS here
(re-measured 2026-09-30, [`reports/external_manifest.json`](../reports/external_manifest.json)
egress note). What changed is that this group's **own sibling repositories
already staged those official products from open-egress GitHub Actions runners**,
with provenance and digests recorded. `scripts/fetch_external_data.py` re-stages
them and verifies **every byte twice** (sha256 pinned in the sibling provenance
file + git blob SHA-1 pinned from the sibling git tree). All six verified OK.

| Product | Channels | Official source | Licence | Verified |
|---|---|---|---|---|
| `geodawn_rad_u8.tif` | K, Th, U, TC | [GeoDAWN airborne magnetic & radiometric surveys, USGS data release, DOI 10.5066/P93LGLVQ](https://doi.org/10.5066/P93LGLVQ) · [ScienceBase item 657e1d85d34e23d3533209f7](https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7) | USGS public domain | sha256 `c22420f7…` ✅ blob `80704748…` ✅ |
| `geodawn_extensions_u8.tif` | Th/K, U/K, U/Th, TMI↑150 m | same DOI | USGS public domain | sha256 `a35a9c6d…` ✅ blob `2fb1d57f…` ✅ |
| `radiometric_u8.tif` | rad_k, rad_th, rad_u, rad_tc, rad_thk, rad_uk, rad_uth (**physical units**, lo/hi pinned) | same DOI | USGS public domain | sha256 `6cb051f7…` ✅ blob `dfc512ff…` ✅ |
| `lidar_scarp_features_u8.tif` | ex_max, ex_mean, step_max, lapneg_max, lappos_max, downface_max, upface_max, cross_max, relief, coh100, strike, valid | [USGS 3DEP 1 m DEM](https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/), 716 tiles (706 ok), tile list OCR-recovered from the competition's own `Digital-elevation-model-links-JSON.pdf` | USGS 3DEP, no use restrictions; acknowledgment required | blob `da733b53…` ✅ |
| `topo_u8.tif` | slope_p90, slope_max, steep_frac, **slope_std**, relief_local, **curv_prof_absmax**, aspect_coherence, hs_lineament, dem_mean | USGS 3DEP DEM | USGS public domain | sha256 `a6398d99…` ✅ blob `5388687c…` ✅ |
| `qfaults_prior_u8.tif` | coarse_trace, fine_trace, lower_certainty_trace | [USGS Quaternary fault and fold database](https://earthquake.usgs.gov/static/lfs/nshm/qfaults/Qfaults_GIS.zip) · [DOI 10.5066/P9BCVRCK](https://doi.org/10.5066/P9BCVRCK) · [portal](https://www.usgs.gov/programs/earthquake-hazards/faults) | USGS public domain | sha256 `538b4573…` ✅ blob `b6b4c219…` ✅ |

All six grids are **pixel-exact** with the competition grid: EPSG:32611,
transform `(100, 0, 243350; 0, −100, 4508550)`, 3730×3292 — verified per file in
`reports/external_audit.json → grid_conformance` (all `all_ok: true`).

Coverage inside the 5,167,373-px footprint: radiometric/GeoDAWN 5,166,085 px
(99.97 %), `topo` 5,167,373 px (100 %), LiDAR morphometrics 3,893,184 px
(75.3 %; the directional channels `downface/upface/cross` 3,207,200 px = 62.1 %).
The intersection of every channel — the domain used for the fairness-controlled
statistics below — is **3,205,306 px (62.0 % of the footprint)**.

### 0.1 Two verification results that redirect the whole strategy

**(a) Irregularity I-2 is RESOLVED: band 6 `tc` *is* the radiometric total
count.** Spearman rho of the provided band 6 against the official GeoDAWN total-count
grid is **+1.000** (both independent products: `radiometric::rad_tc` and
`geodawn_rad::TC`). The previous session's "disproof" of the radiometric reading
rested on an assumed unit scale (counts per second, 10²–10⁴); the official
product's own pinned physical range for `rad_tc` is **5.468–30.272** (p0.5–p99.5,
[`5GEMSDOE` radiometric manifest](../reports/external_provenance/5GEMSDOE__data_aux_bridge_radiometric_manifest.json)),
which brackets band 6's measured p50 18.48 / p99 29.10 exactly. Band 6 is therefore
a radiometric channel, `HE_lin_tc` is a radiometric lineament detector, and —
decisively for strategy — **the competition gives us total count only: K, Th, U
and every alteration ratio are withheld.** Those are the standard geothermal
exploration channels.
Also measured: provided `tmi` (band 14) ≈ official `TMI_up150` (rho **+0.981**)
and `det_elev_slope` (band 19) ≈ `topo::relief_local` (rho **+0.965**), so the
supplied magnetics and topographic slope are largely redundant with what we can
rebuild externally; the *new* information is in the radiometric ratios and the
1-m-LiDAR morphometrics.

**(b) The "catalogue-difference" strategy is dead — measured, not assumed.**
Reproducing the test independently: of **60,939** QFFDB trace pixels inside the
footprint, exactly **1** has no provided training label within the metric's own
R = 300 m. Coverage fraction = 0.9999836. The provided `existing_faults.tif`
*already is* the USGS/INGENIOUS Quaternary compilation, so "predict what another
official catalogue has that this one lacks" has no mass. This is recorded as a
screened-out candidate (R10-X) so no future session re-spends time or a slot on it.
(QFFDB trace pixels *outside* the label footprint: 108,176 — see §R10-X for why
that is not usable either.)

### 0.2 The measured ranking input (univariate, common domain, 300 k sample)

AUC against the provided catalogue, and catalogue recall inside each channel's
own top 5 % — the same selection mass the submission recipe uses. Best
**provided** band for comparison: `geod_shearrate` **0.5615** (then
`geod_2ndinv` 0.5603, `ieq_n100a15` 0.5580, `det_elev_slope` 0.5469).

| rank | external channel | AUC | top-5 % recall | max \|rho\| vs any provided band |
|---|---|---|---|---|
| 1 | `topo::slope_std` | **0.5755** | 0.0593 | 0.751 (`det_elev_slope`) |
| 2 | `lidar::upface_max` | **0.5704** | 0.0463 | 0.645 (`det_elev_slope`) |
| 3 | `lidar::lappos_max` | 0.5695 | 0.0478 | 0.749 |
| 4 | `topo::curv_prof_absmax` | 0.5694 | 0.0410 | 0.648 |
| 5 | `lidar::lapneg_max` | 0.5626 | 0.0460 | 0.733 |
| 6 | `lidar::ex_max` | 0.5620 | 0.0443 | 0.664 |
| 7 | `lidar::downface_max` | 0.5616 | 0.0435 | 0.770 |
| 8 | `topo::slope_max` | 0.5573 | 0.0370 | 0.910 |
| 9 | `lidar::step_max` | 0.5570 | 0.0420 | 0.754 |
| 10 | `radiometric::rad_uth` | 0.5526 | 0.0815 | 0.679 (`tc`) |
| 11 | `radiometric::rad_uk` | 0.5504 | **0.0975** | **0.246** (`tc`) |
| 12 | `topo::hs_lineament` | 0.5553 | 0.0368 | 0.793 |
| — | `geodawn_extensions::UK` / `UTh` | 0.5499 / 0.5522 | 0.0965 / 0.0818 | 0.246 / 0.679 |

Reading: **every one of the top seven external channels beats the best provided
band univariately**, and `rad_uk`/`rad_uth` combine a decent AUC with the *two
highest top-5 % recalls in the whole study* and (for `rad_uk`) the **lowest
redundancy with anything the competition gave us**. That is the definition of
overlooked data.

---

## R10-1 — 1-m LiDAR morphometric scarp composite ("paired-crest scarp")

* **Layers.** `lidar_scarp_features_u8.tif` channels `step_max`, `ex_max`,
  `ex_mean`, `lapneg_max` (crest convexity), `lappos_max` (toe concavity),
  `upface_max` (uphill-facing/antislope face), `coh100` (structure-tensor
  coherence), `strike`; dequantised with the sibling-pinned rule
  `x = x_max · ((q−1)/254)²` for the sqrt-quantised channels.
* **Physical signature targeted.** A *fault scarp is not a steep place* — it is a
  **band-passed step** (10 m slope minus 50 m slope) with a **convex breakover
  paired with a concave toe** (a LoG sign pair at 6 m on the 50 m band-passed
  surface), often with an **uphill-facing** face on the downthrown side. The
  detector therefore takes the geometric mean of four normalised terms
  (step × slope-excess × crest-convexity × toe-concavity), boosts it by the
  antislope term, and then **requires along-strike persistence** (crest pixels
  with ≥ N crest neighbours within ±9 px along the local strike) so that the
  output is a 1-px line, not a blob — the metric pays for lines.
* **Why it should catch a fault missing from the USGS/INGENIOUS catalogue.**
  The compilation's own attribute fields (verified from the source archive's
  schema, [`external_provenance/7GEMSDOE__external_qfaults_observed_schema.json`](../reports/external_provenance/7GEMSDOE__external_qfaults_observed_schema.json))
  record **23,552 features mapped at 1:250,000**, 8,455 at 1:100,000 and
  **6,654 features with certainty "Poor"/"Unknown"**. A trace drawn at
  1:250,000 has ~100 m+ positional uncertainty and no ability to resolve a
  1–3 m scarp under alluvium or sagebrush; 1-m LiDAR resolves exactly that
  population. This is the classic "lidar reveals unmapped Quaternary faults"
  result, and it is the reason a competitor on the forum is recruiting a
  geologist for *"lidar fault mapping, Basin and Range"*
  ([forum 11531](https://community.drivendata.org/t/looking-for-a-geologist-teammate-lidar-fault-mapping-basin-and-range-to-join-a-working-ml-pipeline/11531)).
* **How it differs from anything in this repo.** Every detector implemented to
  date (H-A…H-E, R6-*, R7-*, R8-*, R9-*, BASE_*) reads **only the 19 provided
  bands or catalogue geometry**. The nearest relatives — `R8_openness`,
  `R8_tpi`, `R8_flow`, `BASE_topo_ridge` — all operate on the provided
  `det_elev`/`det_elev_slope`, which this session measured to be ~96 % redundant
  with a *coarse* relief measure. R10-1 is the first operator whose input is an
  independent 1-m-derived morphometric product; the paired crest/toe sign logic
  and the antislope term appear nowhere in `src/gems/detectors.py`.
* **Expected DTI improvement (hypothesis).** Positive, and the largest of the
  four: its channels hold the top-2/3/5/6/7 AUCs above. Best case it replaces
  `BASE_topo_ridge` as the ranking field at equal mass (top 5 %, spacing 3),
  which on the archived protocol would move confirmation worst-rule DTI above
  the reference **0.08687**. Magnitude unknown until measured; a 10–30 %
  relative gain would be a large move on this holdout.
* **Implementation cost.** Low-medium: one loader + one composite function;
  no per-fold rebuild (no catalogue input, so no leakage); ~2–4 min to build
  full-grid, ~3 min to validate.

## R10-2 — Radiometric alteration-ratio lineaments ("hydrothermal conduit")

* **Layers.** `radiometric_u8.tif` channels `rad_uk` (U/K), `rad_uth` (U/Th),
  `rad_thk` (Th/K), `rad_k`, `rad_tc`, dequantised to physical units with the
  pinned lo/hi per band; optionally cross-checked against
  `geodawn_extensions_u8.tif` (`UK`, `UTh`, `ThK`) which is an independent
  quantisation of the contractor's own ratio grids.
* **Physical signature targeted.** **Hydrothermal alteration changes surface
  K–Th–U systematically**: potassium metasomatism raises K and lowers Th/K and
  U/K; silicification and argillic/alunitic alteration raise U/K and U/Th
  (uranium is mobile in oxidising hydrothermal fluid, potassium and thorium are
  not); iron-oxide/hematite gossan raises Th/K and depresses K. The detector
  (i) high-passes each ratio against its own regional trend so only *local*
  anomalies remain, (ii) removes the part of the anomaly explainable by relief
  (a scalar least-squares fit against `relief_local`, keeping the positive
  residual) so bare-bedrock ridge lithology is not mistaken for alteration,
  (iii) combines U/K and U/Th by geometric mean (both must agree), (iv) extracts
  ridge crests (Hessian ridge + NMS thinning) and (v) keeps only crests with
  along-strike persistence — **linear alteration zones**, i.e. fluid conduits.
* **Why it should catch a catalogue-missing fault.** Permeable faults are the
  conduits that move hydrothermal fluid to the surface; alteration is a
  *chemical* footprint that survives when the *morphological* footprint has been
  buried by alluvium or erased by erosion — precisely the "no surface
  expression" population a topography-based compilation cannot contain. The
  measured redundancy is the argument: `rad_uk` has max |rho| = **0.246** against
  *any* of the 19 provided bands, so this is close to an orthogonal observation,
  and it has the **highest top-5 % catalogue recall of any channel measured**
  (0.0975 vs 0.0593 for the best topographic channel).
* **How it differs from anything in this repo.** No detector in
  `src/gems/detectors.py` touches radiometric chemistry. The only
  radiometric-adjacent work is `HE_lin_tc`, which is a *lineament* operator on
  total count (band 6 = TC, now proven) — TC is a single bulk-intensity channel
  with none of the K/Th/U fractionation information, and `HE_lin_tc` performs no
  high-pass, no relief-residual gating and no ratio algebra. This is the first
  alteration-chemistry detector, and it is the one that speaks directly to the
  charter's "scientific discovery of geothermal vents" priority.
* **Expected DTI improvement (hypothesis).** Moderate on the *catalogue* holdout
  (AUC 0.55 is below the LiDAR channels) but the highest expected value on the
  *actual target*, because the private truth is expert-labelled new faults and
  experts reviewing geothermal systems weight alteration evidence. On the
  holdout it may win as a **union partner** (extra recall at acceptable
  precision) rather than as a standalone ranking field.
* **Implementation cost.** Low-medium: dequantisation table already pinned;
  one function; no per-fold rebuild.

## R10-3 — Fault damage-zone texture ("slope heterogeneity", not slope magnitude)

* **Layers.** `topo_u8.tif` channels `slope_std`, `curv_prof_absmax`,
  `slope_p90`, `steep_frac`, `hs_lineament` (3DEP DEM at 100 m aggregation,
  physical lo/hi pinned).
* **Physical signature targeted.** A fault zone is a **damaged, fractured volume**:
  at sub-100 m scale its slope *variance* and *profile curvature* are anomalous
  even where its mean slope is ordinary. The transform is therefore not a
  gradient-magnitude ridge (that is `BASE_topo_ridge`) but a **second-moment
  texture ridge**: ridge crests of `slope_std` gated by `curv_prof_absmax`,
  thinned and strike-persistent.
* **Why it should catch a catalogue-missing fault.** `slope_std` is the single
  highest-AUC channel in this entire study (**0.5755**, above every provided
  band) while correlating only 0.751 with `det_elev_slope` — i.e. it separates
  faulted ground from merely steep ground. Buried/covered faults with no
  resolvable scarp but a shattered, differentially-eroded damage zone are
  exactly what a magnitude-only topographic detector misses.
* **How it differs from anything in this repo.** `BASE_topo_ridge`,
  `R8_openness`, `R8_tpi`, `R6_shore`, `R8_flow` are all functions of the
  provided elevation field's *first* derivatives or local relief. Nothing in the
  repo uses a sub-pixel **variance/texture** statistic, because the provided
  bands do not contain one; it only exists because a 3DEP DEM was aggregated at
  2–10 m working resolution.
* **Expected DTI improvement (hypothesis).** Positive as a ranking field;
  possibly the single best standalone replacement for `BASE_topo_ridge` given
  the AUC ordering. Cheapest of the four to test.
* **Implementation cost.** Low.

## R10-4 — Vent conjunction: structural conduit × alteration chemistry (× provided conductivity)

* **Layers.** R10-1 scarp composite **and** R10-2 alteration residual **and** the
  provided bands `cond_surf` (17) and `depth_to_base_surf` (15).
* **Physical signature targeted.** The geothermal **vent/upflow** model: fluid
  rises along a permeable structure (scarp/lineament), through a shallow
  conductive pathway (high surface conductivity, shallow conductive base), and
  leaves an alteration fingerprint at the surface (high U/K, U/Th). The detector
  is a **geometric-mean conjunction of three independent physics** — morphology,
  chemistry, electrical — each normalised, each high-passed against its own
  regional trend. Requiring all three suppresses each one's dominant false
  positive class (erosional scarps, lithologic bedrock chemistry, clay-filled
  basins) while preserving the intersection population.
* **Why it should catch a catalogue-missing fault.** Quaternary fault
  compilations are compiled from *geomorphic* evidence. A structure that is
  geomorphically subtle but hydrothermally active — the population that matters
  for a geothermal prize, and the population NLR's own experts were hired to
  label ([Official Rules §2](https://docs.nlr.gov/docs/fy26osti/96647.pdf)) — is
  systematically under-represented in the catalogue and over-represented in a
  three-physics conjunction. This is also the most defensible map for **Phase 2**,
  where 83 % of the prize is decided by expert review of our own predictions:
  a candidate feature with morphology + alteration + conductivity evidence is
  one an expert can accept.
* **How it differs from anything in this repo.** `R8_intersections` intersects
  *four ridge maps all derived from the provided bands*; `R7_consensus3/4` is an
  N-of-5 vote among provided-band edges; `seismicity_gate` and `R6_transt` are
  two-physics gates on provided bands. No existing operator combines an external
  morphology product, an external chemistry product and a provided electrical
  product, and none is vent-targeted.
* **Expected DTI improvement (hypothesis).** Highest precision, lowest recall —
  so on an F2-weighted metric it will probably **lose standalone** at small mass
  and may win as a *small additive block* whose marginal weighted precision must
  clear the audited A5 bar (`> 0.2 × DTI`). Predeclared: test it both standalone
  and as a ≤ 1.5 %-of-footprint additive block on top of the best ranking field.
* **Implementation cost.** Medium (depends on R10-1 and R10-2 existing first).

## R10-X — SCREENED OUT before implementation (two measured dead ends)

* **R10-X1 "catalogue difference" (QFFDB − provided labels).** Dead: 1 pixel of
  gap mass inside the footprint out of 60,939 (§0.1b). Cost of implementing:
  zero. Slots spent: zero.
* **R10-X2 "predict QFFDB traces outside the label footprint".** 108,176 QFFDB
  trace pixels lie outside the 5,167,373-px valid footprint. The official
  submission format requires data outside the bounds to be null/NaN
  ([problem description → Submission format](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)),
  and the scoring mask is the label raster's own valid mask, so mass there is
  either ignored or pure false-positive weight. Not viable; recorded so nobody
  re-derives it.

---

## Ranking (expected DTI improvement ÷ implementation cost)

| # | Candidate | Expected holdout ΔDTI | Cost | Rank rationale |
|---|---|---|---|---|
| 1 | **R10-3 damage-zone texture** | ↑ (channel AUC 0.5755, best measured) | **Low** | highest signal, lowest cost — test first |
| 2 | **R10-1 LiDAR scarp composite** | ↑↑ (5 of the top-7 AUCs; independent 1-m data) | Low-medium | biggest new-information content |
| 3 | **R10-2 alteration-ratio lineaments** | ↗ standalone / ↑ as union partner | Low-medium | near-orthogonal (max \|rho\| 0.246), best top-5 % recall |
| 4 | **R10-4 vent conjunction** | ↓ standalone (F2 punishes low recall), ↑ as small additive block | Medium | highest Phase-2/defensibility value, lowest expected Phase-1 DTI |
| — | R10-X1/X2 | n/a — measured dead | zero | screened out |

## Predeclared decision rule (identical to R8/R9, written before scoring)

* Primary metric: **confirmation worst-rule-mean DTI** across the six
  confirmation folds/rules of the archived protocol
  (`scripts/validate_r9_holdout.py` fold builder, seeds, 5-px buffer,
  `FoldScorer`, tune/confirm split).
* Paired reference: **`topo_05_sp3`** (confirmation worst-rule mean **0.08687**,
  mean 0.09763, precision_w 0.0276, recall_w 0.2874).
* A candidate **WINS** iff it beats the reference on **both** tune and
  confirmation worst-rule-mean DTI **and** is not worse on ≥ 4 of the 6
  confirmation rule means; **FRAGILE** if it beats overall but wins < 4 of 6;
  otherwise it **LOSES**.
* Protocol regression check: the reference row re-scored inside the R10 run must
  reproduce the archived per-fold DTI values to < 1e-6. If it does not, the run
  is invalid and nothing is concluded.
* **No weekly submission slot is spent unless a candidate WINS.**

---

## R10 result (measured 2026-09-30, `reports/holdout_r10_2026-09-30.json`)

Protocol regression check **PASS** (reference row reproduced the archived R8
per-fold DTI values exactly, 18/18 folds, 0 mismatches). 17 configurations x 18
folds = 306 scorings, 91 s. No tie hazard materialised: `max_tie_fraction` 0.00
and `n_selected_at_zero_score` 0 for every configuration.

**All 16 R10 candidates LOSE to `topo_05_sp3`.** Confirmation worst-rule-mean DTI
(reference **0.08687**):

| config | confirm worst | confirm mean | paired Δ mean | P_w | R_w | px | confirm rule-means won |
|---|---|---|---|---|---|---|---|
| `topo05_plus_alter02_sp3` | 0.08593 | 0.09651 | −0.00113 | 0.0257 | 0.3363 | 233,565 | 1/6 |
| `topo05_plus_vent02_sp3` | 0.08443 | 0.09633 | −0.00130 | 0.0260 | 0.3229 | 221,844 | 1/6 |
| `ventdzt_08_sp3` | 0.08396 | 0.09311 | −0.00452 | 0.0292 | 0.2198 | 134,376 | 1/6 |
| `topo05_plus_scarp02_sp3` | 0.08099 | 0.09269 | −0.00494 | 0.0250 | 0.3121 | 223,079 | 0/6 |
| `topo05_plus_dzt02_sp3` | 0.07937 | 0.09083 | −0.00681 | 0.0242 | 0.3179 | 234,913 | 0/6 |
| `ventdzt_05_sp3` | 0.07643 | 0.08548 | −0.01215 | 0.0310 | 0.1613 | 92,904 | 0/6 |
| `vent_08_sp3` | 0.07526 | 0.09075 | −0.00688 | 0.0293 | 0.2031 | 124,009 | 1/6 |
| `dztC_02_sp3` | 0.07490 | 0.08536 | −0.01227 | 0.0335 | 0.1460 | 77,139 | 0/6 |
| `alter_05_sp3` | 0.07337 | 0.08202 | −0.01562 | 0.0282 | 0.1670 | 106,146 | 0/6 |
| `vent_05_sp3` | 0.06784 | 0.08397 | −0.01366 | 0.0318 | 0.1497 | 84,098 | 0/6 |
| `alterC_015_sp3` | 0.06411 | 0.07273 | −0.02491 | 0.0328 | 0.1092 | 59,444 | 0/6 |
| `dzt_08_sp3` | 0.06334 | 0.07585 | −0.02178 | 0.0231 | 0.1888 | 145,501 | 0/6 |
| `scarpC_015_sp3` | 0.06020 | 0.07443 | −0.02321 | 0.0339 | 0.1101 | 57,320 | 0/6 |
| `dzt_05_sp3` | 0.05747 | 0.06848 | −0.02915 | 0.0234 | 0.1399 | 106,364 | 0/6 |
| `scarp_08_sp3` | 0.05632 | 0.07265 | −0.02498 | 0.0247 | 0.1491 | 107,600 | 0/6 |
| `scarp_05_sp3` | 0.05103 | 0.06373 | −0.03390 | 0.0249 | 0.1095 | 78,370 | 0/6 |

Verdict under the predeclared rule: **no R10 candidate WINS; no submission slot
is spent on any of them.**

### Why the unions lost — the audited inclusion rule, measured

The audited A5 rule (`reports/metric_audit.json`) says a block may be added only
if its **marginal weighted precision exceeds 0.2 x DTI** (tune threshold 0.0169,
confirmation threshold 0.0195). Measured marginal precision of the added block,
on **tune** folds (Δhits/Δpx vs the reference):

| added block @ 2 % coverage | Δpx (tune) | marginal precision | above 0.0169? |
|---|---|---|---|
| vent | +36,578 | 0.0138 | no |
| alter | +48,293 | 0.0141 | no |
| scarp | +37,791 | 0.0096 | no |
| dzt | +49,624 | 0.0094 | no |

Every 2 %-coverage union adds recall (0.312–0.336 vs 0.287) at a marginal hit
density **below** the inclusion threshold, so the F2-optimal stopping point is
before them. The unions are not "bad geology", they are priced out: the pixels
where the external evidence fires *and* the topographic ridge does not are, on
average, less likely to be catalogue faults than the next topographic pixel.

### Predeclaration correction (recorded against ourselves)

R10-4 was predeclared as "↓ standalone (F2 punishes low recall)". The built map
measured the **highest** top-5 % recall of the whole R10 family
(0.0841 full-catalogue, AUC 0.5660) — the conjunction is *not* low-recall in the
provided footprint. It still loses standalone (confirm worst 0.07526 at 8 %
coverage) because its recall (0.2031) stays below the reference (0.2874) while
its precision gain (0.0293 vs 0.0276) is too small to pay for it. The mechanism
we predicted was wrong; the direction of the verdict was right.

---

## R10b — predeclared refinement round (written before scoring)

Two mechanisms remain untested by R10, and both are cheap. They are predeclared
here, tune-selected, confirmation-verified, under the **same** fold builder,
seeds, buffer, scorer and verdict rule as R10.

* **Mechanism A — low-coverage union.** R10 measured the *average* quality of the
  top 2 % of each external map. The audited rule is a statement about the
  *margin*, so the very top of the map (0.5 %, 1 %) may clear the threshold even
  though the 0–2 % band does not. Configs: `topo05_plus_vent005_sp3`,
  `topo05_plus_vent01_sp3`, `topo05_plus_alter005_sp3`,
  `topo05_plus_alter01_sp3` (vent and alter are the two blocks with the highest
  measured marginal precision).
* **Mechanism B — fixed-budget rank fusion.** Instead of *adding* pixels, keep the
  reference mass (top 5 % of the fused ranking, spacing-3 decimation) and let the
  external evidence *replace* the weakest reference pixels. Fused score =
  `(1 − w) · pctl(topo) + w · pctl(external)`, where `pctl` is the tie-corrected
  (average-rank) percentile computed over the valid footprint only. Configs:
  `fuse_vent_w015_sp3`, `fuse_vent_w030_sp3`, `fuse_vent_w050_sp3`,
  `fuse_alter_w030_sp3`. Small w re-orders the topographic crest; large w admits
  vent-only peaks at fixed mass, so precision loss is bounded by construction.
* **Selection rule (predeclared):** the single configuration with the highest
  **tune** worst-rule-mean DTI (tie-break: tune mean DTI) is carried forward.
  Confirmation numbers for non-selected configurations are stored in the JSON for
  audit but were **not** inspected before the selection was made, and the verdict
  is issued for the selected configuration only.
* **Verdict rule:** identical to R10 — WINS iff it beats `topo_05_sp3` on both
  tune and confirmation worst-rule-mean DTI and is not worse on ≥ 4 of the 6
  confirmation rule means; FRAGILE if it beats overall but wins < 4 of 6;
  otherwise LOSES. Protocol regression check enforced before any verdict.
* **No weekly submission slot is spent unless a candidate WINS.**

### R10b result (measured 2026-09-30, `reports/holdout_r10b_2026-09-30.json`)

Protocol regression check **PASS**. 9 configurations x 18 folds = 162 scorings,
66 s. `max_tie_fraction` 0.00 everywhere.

Tune-fold selection (predeclared: highest tune worst-rule-mean DTI) picked
**`fuse_vent_w050_sp3`** — tune worst 0.04571 vs reference 0.03852, tune mean
+0.00114. Mechanism A (low-coverage unions) all scored *below* the reference on
tune mean and worst: the marginal precision of the added 0.5–1 % blocks measured
0.0136–0.0166, i.e. still at or below the 0.0169 tune inclusion threshold. The
external maps have no high-precision head; their whole body is uniformly
middling, so no coverage rescues a union.

Confirmation for the selected configuration only:

| config | confirm worst | confirm mean | paired Δ mean | P_w | R_w | px | rule-means won | paired folds won | verdict |
|---|---|---|---|---|---|---|---|---|---|
| `topo_05_sp3` | **0.08687** | 0.09763 | — | 0.0276 | 0.2874 | 185,290 | reference | reference | REFERENCE |
| `fuse_vent_w050_sp3` | 0.08286 | 0.09771 | +0.00008 | 0.0294 | 0.2487 | 150,650 | 2/6 | 6/12 | **LOSES** |

**Verdict: LOSES. No submission slot is spent.** The fusion is a near-wash on the
confirmation mean (+0.00008, 0.08 % relative) while being worse on the worst rule
(−0.00401): it buys precision (0.0294 vs 0.0276) with 19 % fewer pixels by giving
up recall (0.2487 vs 0.2874), and under beta = 2 that trade is at best neutral.
Recorded as a *cost* result, not a win: if a future round needs to shrink the
submission (e.g. to reduce expert-review burden in Phase 2), `fuse_vent_w050_sp3`
is the measured equal-score/34k-fewer-pixel option — but it is not an improvement
and must not be presented as one.

### R10/R10b closing statement

The four predeclared R10 hypotheses are **closed as Phase-1 DTI improvements**.
External USGS/GeoDAWN evidence (1-m LiDAR morphometrics, damage-zone texture,
radiometric alteration ratios, and their vent conjunction) is real, hash-verified,
license-clean and *individually better than any provided band* (AUC 0.528–0.577 vs
0.5615 for the best provided band), yet none of it beats — or usefully augments —
the topographic-crest recipe under any of the six withholding rules tested. The
reason is structural and now measured twice: the catalogue faults our reference
already finds are found by *topographic expression*, and the pixels where the
external evidence fires but topography does not are, on average, *less* likely to
be catalogue faults (marginal precision 0.0094–0.0166 vs a 0.0169–0.0195
threshold). The remaining value of this data is Phase-2 / defensibility value, not
Phase-1 score.
