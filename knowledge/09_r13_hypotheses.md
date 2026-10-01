# R13 hypothesis register — predeclared 2026-10-01 (session 7), before any R13 fold was scored

Status: **PREDECLARED.** The decision rule at the bottom is frozen before
`scripts/validate_r13_holdout.py` is run. Results go to
`reports/holdout_r13_2026-10-01.json` and are appended under "RESULT" at the bottom.

House rule (`PROJECT_CHARTER.md`): **no weekly submission slot is spent on an idea that
has not beaten the current holdout best.** The current holdout best is the R11 recipe
`greedy_r11` (confirmation worst-rule-mean DTI 0.09175 in R11, 0.09168 in the R12 in-run
reference).

Everything here is a *local hide-and-recover proxy on known faults*, not a leaderboard
estimate (irregularity I-16). The competition target is faults **not** in the
USGS/INGENIOUS catalogue
([problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)).

---

## What was reviewed so that these are not repeats

Prior registers: `03_hypotheses.md` (R1–R9), `05_hypothesis_screen_2026-09-30.md`,
`06_r10_hypotheses.md`, `07_r11_hypotheses.md`, `08_r12_hypotheses.md`. Existing detector
code: `src/gems/detectors.py` (worms, TDR, theta, basement hinge, strain, extension
rays, horsetail splay, paleoshoreline, cross-gradient, coherence breakdown, remanence,
intersection permeability, structural grain, parallel-offset, oriented persistence,
damage-zone texture, LiDAR scarp composite, alteration ratios, vent conjunction, basin
magnetics). Every map there is ranked by a **global** score cut. The topographic crest
map (`BASE_topo_ridge`) uses one Hessian scale (σ = 1.5 px) and a global robust
normalisation. No existing map varies it by *local* contrast, by *scale persistence* or
by *regional budget*, and none uses the INGENIOUS paleo-geothermal feature points
(R11-3 declared that idea; it was never run because the data could not be staged).

## Why the greedy family stopped paying (R12 closing finding, restated)

`greedy_r12` (finer steps, wider pool), hysteresis add-ons and basin magnetics all lost.
Blocks drawn from maps that all measure "the same crest" run into the metric's inclusion
bar: an added block helps only if its marginal weighted precision exceeds `0.2 × DTI`
(A5 in `knowledge/01_verified_facts.md`). More gain needs a *different base ordering* or a
*different physical observable*, not more blocks of the same kind.

---

## Ranked candidates

Ranking is by **expected DTI gain × probability it works ÷ cost**. The "prior" column is a
qualitative guess, not a forecast. "Layers" are provided GeoDAWN bands unless a free
official external source is named.

| rank | id | idea | layers | cost | prior |
|---|---|---|---|---|---|
| 1 | R13-4 | **paleo-geothermal feature halos** (new observation) | INGENIOUS GDR 1391 Paleo Geothermal Features (CC-BY-4.0) + ridge strength from band 19 | medium (data staged by runner; 1 map) | medium gain, high variance |
| 2 | R13-1 | **local-contrast crest normalisation** | band `det_elev_slope` (19) | low | small–medium |
| 3 | R13-2 | **scale-persistent crest** (σ = 1.0, 1.5, 2.5 px) | band 19 | low | small |
| 4 | R13-3 | **regional (tile-quota) budget** | `BASE_topo_ridge` cache | low | small |
| 5 | R13-5 | Euler depth-to-source clusters | band `rtp` (2) | high (new solver + tests) | small–medium; **deferred** |

All of R13-1…4 share one harness and are run in one predeclared batch
(`scripts/validate_r13_holdout.py`). R13-5 is declared and **deferred**.

### R13-4 — paleo-geothermal feature halos (rank 1, run now)

* **Layers / source:** INGENIOUS Great Basin Regional Dataset Compilation, **GDR submission
  1391**, file "Paleo Geothermal Features.zip"
  ([official page](https://gdr.openei.org/submissions/1391), DOI 10.15121/1881483, licence
  **CC-BY-4.0**). 726 sinter / tufa / travertine / silica-cemented-sand / alteration /
  explosion-crater points (NAD83 geographic).
* **Obtainability (verified):** this sandbox cannot reach `gdr.openei.org` (TLS egress
  blocked). The file was staged by a GitHub-hosted runner via
  `.github/workflows/fetch-gdr1391.yml` (run 36799195255, success, sha256 in
  `reports/gdr1391_fetch.json`, committed under `data/external_gdr1391/`). The official
  page lists the file as publicly accessible. Measured on the staged copy: 709 points
  fall on the 3730×3292 grid, **281 on label-valid pixels**; 65 lie within 300 m of the
  catalogue, 90 within 1 km, 135 within 3 km (so 146 are > 3 km from any catalogued trace).
* **Physical signature:** sinter and tufa are precipitated where thermal water reached
  the surface along a permeable fault or fracture zone; the deposit is *ground evidence of
  fault-controlled upflow*. Fossil spring deposits that are > 300 m from any catalogued
  trace mark structure the catalogue does not contain. A halo (σ = 1.5 km, cut at 3 km)
  multiplied by the **continuous (non-NMS) ridge strength** ranks the strongest linear
  topographic feature near each deposit — the likeliest trace of the feeding fault.
* **Why it can catch uncatalogued faults:** the information source (spring deposits mapped
  from field/literature) is independent of both the label raster and every GeoDAWN
  band; in a hide-and-recover test the points cannot leak, because they do not read the
  catalogue.
* **How it differs:** first use of the INGENIOUS point data. Prior geometry maps
  (`vent_conjunction`, R10) use the *Quaternary volcanic vent* layer plus alteration;
  they do not use spring deposits.
* **Test (Stage C):** `greedy_r11` + one extra block drawn from the halo×ridge map,
  budget ∈ {0.10 %, 0.25 %, 0.50 %} of the valid footprint, restricted to pixels
  > 300 m from the current assembly, spacing-3 decimation. Configs
  `greedy_r11_paleo010`, `greedy_r11_paleo025`, `greedy_r11_paleo050`.
* **Caveat declared in advance:** 2-m temperature probes (same release, 3,800 points) are
  staged but **not** used in this batch; hot-probe halos are a follow-up. A block of
  at most 0.5 % of the footprint can move DTI only a little; a WIN is judged by the rule
  below, not by the sign of a small delta.

### R13-1 — local-contrast crest normalisation (rank 2)

* **Layers:** band 19 `det_elev_slope` → Hessian ridge strength `s` (σ = 1.5 px, the same
  filter as `BASE_topo_ridge`).
* **Signature:** the catalogue is dominated by conspicuous range-front scarps. Young
  normal-fault scarps in alluvial basin fill are *subdued* — small absolute curvature but
  the strongest linear feature in a flat neighbourhood. A global cut ranks conspicuous
  relief first. Dividing `s` by a Gaussian-weighted local mean
  (`s' = s / (L_σ(s) + ε)^α`) ranks a pixel against its surroundings, as an analyst's eye
  does. That the catalogue is biased toward prominent scarps is a **hypothesis, not a
  measurement**; the hold-out can only test whether the reorder recovers *hidden known*
  faults better.
* **How it differs:** every repo ridge map is globally normalised.
* **Variants (frozen):** α ∈ {0.5, 1.0} × σ_loc ∈ {10, 30} px; ε = 5 % of the global mean
  of `s`. Configs `loc_a05_s10`, `loc_a05_s30`, `loc_a10_s10`, `loc_a10_s30`.

### R13-2 — scale-persistent crest (rank 3)

* **Layers:** band 19.
* **Signature:** a real scarp is a *linear* feature that persists across scales; pixel
  noise and small gullies do not. The geometric mean of ridge strengths at σ = 1.0, 1.5 and
  2.5 px (each divided by its own global mean over the footprint) keeps crests present at
  every scale. Not `worms` (persistence over upward-continuation height of potential-field
  gradients), not `oriented_persistence` (persistence along strike).
* **Config:** `persist_gm`.

### R13-3 — regional (tile-quota) budget (rank 4)

* **Layers:** cached `BASE_topo_ridge`.
* **Signature:** the global top-5 % cut spends the budget where relief is high; hidden
  faults are not guaranteed to be there. A per-tile percentile (64-px = 6.4-km tiles) forces
  every region to contribute. The dispersion idea is reported by 17GEMSDOE (team-authored,
  not independently reproduced).
* **Variants:** score `(1−λ)·global percentile + λ·tile percentile`, λ ∈ {0.5, 1.0}:
  `quota_l05_t64`, `quota_l10_t64`.

### R13-5 — Euler depth-to-source clusters (rank 5, **deferred**)

* **Layers:** band 2 `rtp` (∂x, ∂y by FFT, ∂z by FFT vertical derivative).
* **Signature:** windowed Euler deconvolution (structural index 0, contact/fault) yields a
  source depth per window; contacts whose solutions cluster at a consistent shallow depth
  along a line mark buried faults.
* **Why deferred:** the highest cost on the list (solver, unit tests, window-size
  sensitivity) with a low prior — the two magnetic candidates measured so far on the
  hold-out (R11-2 and R12-3 basin magnetics) both lost.

---

## Frozen protocol (identical to R10/R11/R12)

* 18 folds from `gems.holdout.build_folds` + `validate_r10_holdout.segment_folds` (hide
  25 %, 5-px buffer, 8-px link); tune folds = `validate_r10b_holdout.TUNE_FOLDS`, the rest
  are confirmation folds.
* Base block: candidate map, top 5 % of the valid footprint inside the fold's eval mask,
  spacing-3 `decimate_grid`. Reference map = `BASE_topo_ridge`.
* Stage A (`<cand>_05_sp3`): base block alone vs `topo_05_sp3` — information only.
* Stage B (`<cand>_greedy`): base block + the **unchanged** R11 recipe
  (`R10_vent@0.25 %`, `R8_tpi@0.25 %`, `R10_dzt_field@0.25 %`, each restricted to pixels
  > 300 m from the current assembly) vs `greedy_r11`.
* Stage C: `greedy_r11` + the R13-4 block (above).
* **Regression checks before any verdict is read:** (i) the locally rebuilt reference
  ridge map must equal the cached `BASE_topo_ridge.npy` (allclose); (ii) in-run
  `topo_05_sp3` must reproduce the archived per-fold DTI within 1 %.

## PREDECLARED DECISION RULE (frozen)

The single challenger is selected on **tune** folds only: maximum `dti_worst_rule_mean`
over all Stage B and Stage C configs (ties → `dti_mean`). It **WINS** only if **all** hold:

1. beats **both** in-run references (`topo_05_sp3`, `greedy_r11`) on tune **and**
   confirmation worst-rule-mean DTI;
2. confirmation rule means ≥ `greedy_r11` on ≥ 4 of 6 rules;
3. paired confirmation-mean gain vs `greedy_r11` exceeds 10 × the reference drift seen in
   the regression check;
4. beats `greedy_r11` on ≥ 14 of 18 paired folds (stricter than R12: ten challenger
   configs are searched — a multiple-comparison guard).

`FRAGILE` = rule 1 holds but 2, 3 or 4 fails. Everything else `LOSES`. **Only a WIN earns a
submission slot.** Stage A is information only. Per-config results for **all** challengers
(not just the selected one) are written to the report so selection effects stay visible.

---

# R13 addendum A — R13-6 coverage-geometry lattices (predeclared 2026-10-01, before this batch was run)

## Disclosure: why this was added AFTER the main R13 batch

The main R13 batch (below, "RESULT") produced no WIN. While interpreting it, a
**content-free null baseline** was run on the same folds
(`scripts/null_baseline_holdout.py` → `reports/null_baseline_2026-10-01.json`). It was
**seen before this addendum was written**, so the lattice idea is *post-hoc in origin*;
the safeguards are (a) the frozen rule below, (b) a fresh ten-fold-style paired test and
(c) the plain statement here. Null results (18 folds, local proxy; DTI mean / worst-rule
mean; predicted px):

| map (no fault information in any lattice) | DTI mean | worst rule | px |
|---|---|---|---|
| `topo_05_sp3` (R10–R12 reference) | 0.0933 | 0.0869 conf. | ≈185 k |
| `greedy_r11` (shipped recipe) | 0.0988 | 0.0917 conf. | ≈212 k |
| random 5 % + spacing-3 decimation (3 seeds) | 0.0902 ± 0.0001 | 0.084 | ≈212 k |
| square lattice stride 3 / 4 / **5** / 6 / 8 | 0.0839 / 0.0999 / **0.1122** / 0.1022 / 0.0790 | – | 570 k / 321 k / **205 k** / 142 k / 80 k |
| everywhere = 1 | 0.0165 | – | 5.1 M |

(Columns mix all-fold means and confirm worst-rule means as labelled in the JSON; the
comparison that matters is within one column of the report.) **A fault-blind stride-5
lattice outscored every recipe from R8 to R12 on the proxy.** Reason: the metric weights
a predicted pixel by its triangular-kernel proximity (300 m) to truth, so a pixel is
"almost right" anywhere within ~3 px of a fault; recall is cheap and the Tversky
`β = 0.8` penalises misses four times more than false alarms. The ridge/greedy recipes
have full-catalogue AUC ≈ 0.50–0.58 (see `map_statistics_full_catalogue`), i.e. they carry
little pixel-level catalogue information, and their gain over the references came largely
from *spatial spreading of the budget*.

This explains the repeated-score puzzle only as a **hypothesis**, not a proof (see README
"Why 0.1563 repeats"): if leaderboard scores are likewise dominated by coverage geometry,
very different maps (apex 91 % near-catalogue vs ens12 20 % near-catalogue, support IoU
0.067) can land on the same value.

## R13-6 candidates (frozen)

Layers: none (geometry only) plus, for hybrids, the unchanged `greedy_r11` chain.

| config | definition |
|---|---|
| `sq5`, `sq6` | square lattice, every K-th row and column (K = 5, 6) |
| `hex5`, `hex6` | triangular lattice with the **same pixel density** as the square one: spacing `a = K·√(2/√3)`, row pitch `a·√3/2`, alternate rows shifted `a/2` |
| `hyb_sq5`, `hyb_sq6`, `hyb_hex5`, `hyb_hex6` | lattice ∪ `greedy_r11` map (union; no thinning) |

Why a triangular lattice: for equal density it has a smaller covering radius than a
square one (0.62 vs 0.71 of the equivalent spacing), so more pixels lie within the
metric's 300 m kernel of any point.

**Decision rule: the frozen R13 rule above, unchanged** (select one on tune only;
must beat `topo_05_sp3` and `greedy_r11` on tune and confirmation worst-rule mean,
≥ 4/6 rules, > 10× drift, ≥ 14/18 paired folds). The lattice phase is fixed (origin 0).

## Limits that remain whatever the result

* The proxy truth is *known catalogued faults hidden by fold*; the leaderboard truth is
  *faults not in the catalogue* (I-10, I-16). Coverage geometry transfers only if the
  leaderboard truth is similarly spread — **unproven; one leaderboard score is the test**.
* A lattice contains no geology. If it wins, it wins as a **coverage-geometry baseline**
  and the honest research question becomes "what information beats a lattice", i.e. R13-4
  style evidence layered *on top of* a lattice, not instead of one.

---

# RESULT (2026-10-01) — filled after the runs

**Main batch** (`reports/holdout_r13_2026-10-01.json`, regression drift 0.0, rebuilt reference ==
cached `BASE_topo_ridge`): selected on tune = `persist_gm_greedy` (tune worst-rule 0.04237 vs
`greedy_r11` 0.03992) → confirmation worst-rule 0.09218 vs 0.09168, rules won 3/6, paired folds
6 wins / 12 losses → **FRAGILE, no slot.** All R13-1 (4), R13-3 (2) and R13-4 (3) configs also
failed to beat `greedy_r11` on confirmation worst-rule; R13-4 shows a clean dose-response
(0.10 % → 0.25 % → 0.50 % paleo pixels: confirm worst 0.09143 → 0.09096 → 0.09037, all below
0.09168). Stage A (information only): `persist_gm_05_sp3` beats `topo_05_sp3` in 17/18 folds
(confirm mean 0.09927 vs 0.09763) — the R11 blocks do not add to it (R13b candidate).

**Addendum A** (`reports/holdout_r13_lattice_2026-10-01.json`): selected on tune = `sq5`;
confirm worst-rule 0.1059 vs `greedy_r11` 0.0917 and `topo_05_sp3` 0.0869, 6/6 rules, **18/18
paired folds**, paired mean gain +0.0142 ≫ 10 × drift (0) → **WINS** under the frozen rule.
Triangular lattices (`hex5` 0.1040) and lattice ∪ `greedy_r11` hybrids (0.0803) did not do
better. Caveat: coverage-dominated proxy, post-hoc origin, unproven transfer (I-21).
