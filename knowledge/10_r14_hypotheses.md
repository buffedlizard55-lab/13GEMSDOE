# R14/R15 hypothesis register — PREDECLARED

Written **2026-10-01, session 8**, before any candidate below was scored.
Doctrine (PROJECT_CHARTER §"Predeclare, then measure"): the hypotheses, the
folds, the decision rule and the stopping rule are fixed here first. A result
that was not predeclared is reported as post-hoc and labelled as such.

---

## 0. What changed before this register was written (all verified this session)

| # | Fact | Source, verified 2026-10-01 |
|---|---|---|
| F1 | **Known USGS/INGENIOUS fault pixels are masked / excluded from evaluation in BOTH rounds.** "Pixels corresponding to known USGS/INGENIOUS faults are masked / excluded from evaluation, so they do not count towards penalty terms." "Re-evaluation will also mask/exclude the existing USGS/INGENIOUS faults." "for scoring purposes it should not matter whether these known faults are included with predictions or not." | `chrisk-dd` (**DrivenData Staff**), forum topic 11516 post 2, 2026-09-16 — <https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/2> |
| F2 | **Staff will not disclose** the data sources, fault types or coverage behind the test faults. And: *"the largest prize pool (Phase 2) will use a test set that is updated by expert review of all Phase 1 submissions, so your fault predictions have an impact on final evaluation even if they are not the most performant in Phase 1."* | `chrisk-dd`, forum topic 11527 post 7, 2026-09-23 — <https://community.drivendata.org/t/how-were-the-new-test-faults-identified-data-sources-and-fault-types/11527/7> |
| F3 | `DTI = 1/(0.2/P_w + 0.8/R_w)` — a distance-weighted **F2**. A block of predictions raises DTI iff its marginal weighted precision exceeds `0.2 × DTI`. | derived and proved in `src/gems/metric.py`, `src/gems/audit.py` |
| F4 | **The official `training_features.tif` is now present locally and hash-verified**: 418,912,844 B, sha256 `4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5`. All 19 bands carry the float32 sentinel `-3.4028235e38` on **3,061 pixels inside the scored footprint** (band 6: 3,073). | `scripts/download_competition_data.sh`, `scripts/prepare_data.py`, `data/derived/band_stats.json` |
| F5 | Live leaderboard top: **#1 DARD 0.3168**, #2 alexoktaba 0.3042, #3 joeyfezster 0.2919. The `0.3049` in the standing prompt does not appear in the snapshot and is stale. | `reports/leaderboard_snapshot_2026-10-01.json`, fetched once from the official public page |
| F6 | **No local truth set in the tested family predicts the recorded public scores** (n = 9, all p ≥ 0.168; the SGMC off-catalogue variants correlate *negatively*, best `known_hidden25|unmasked` ρ = 0.393, p = 0.295). The sibling repo's ρ = 0.518 for its own `sgmc_gap` set is **not reproduced** here. | `scripts/calibrate_truth_sets.py`, `reports/truthset_calibration.json` |
| F7 | **The hide-and-recover proxy is structurally blind to near-catalogue strategies.** `gems.holdout.group_systems(link_px=8)` merges traces within ~1.6 km into one system, so whatever is hidden is ≥ ~16 px from everything visible. Measured: ranking by distance-to-visible-catalogue scores DTI ≤ 0.0146 at *every* budget from 0.5 % to 100 %, versus 0.1063 for a fault-blind stride-5 lattice. Real new faults are continuations and stepovers of mapped ones, i.e. they sit *inside* that forbidden 1.6 km ring. | `scripts/r14_budget_curve.py`, `reports/r14_budget_curve.json` |
| F8 | Raw geophysical magnitude rankings are **worse than uniform random** at every budget on the proxy: detrended-elevation slope peaks at DTI 0.0254 (15 % coverage) vs random 0.0842 (4 %); TMI horizontal gradient 0.0265; gravity slope 0.0203; strain-rate second invariant 0.0503; max second directional derivative of elevation 0.0281. | same report |

### Consequences accepted before measuring anything below

* **C1.** Because of F1, mass placed *exactly on* the catalogue is
  score-neutral. Every recipe in this repo that "includes the catalogue"
  (`include_known_catalogue: true`) buys nothing and should stop being
  described as a feature.
* **C2.** Because of F2, the submission has a **second, independent payoff**:
  Phase 2 re-scores the same file against a label set expanded by expert review.
  A fault-blind lattice is not a geological claim an expert can verify, so it
  contributes nothing to Phase 2 however it scores in Phase 1. This is a real
  argument for shipping a map of *credible traces* even at some Phase-1 cost.
* **C3.** Because of F6 and F7, **no local number in this register may be used
  to claim a leaderboard score**, and a proxy "win" is not sufficient on its own
  to justify a slot. The decision rule in §3 reflects that.
* **C4.** Because of F3, blind coverage has a hard ceiling. Solving
  `DTI = 1/(0.2/P + 0.8/R)` for the leader's 0.3168 requires
  P_w ≈ 0.10–0.13 at R_w ≈ 0.5–0.7. A fault-blind lattice reaches
  P_w ≈ 0.10 only if the private truth set is as large as the entire public
  catalogue, and then only at ~6 % coverage. **0.3168 is not reachable by
  coverage geometry**; it needs genuine information.

---

## 1. The new withholding rule that makes the interesting hypotheses measurable

F7 says the existing rules cannot see the mechanism that matters. So this
register adds one, declared before any candidate is scored.

**`tip` rule (new).** For each catalogue *segment* longer than `min_len` = 20 px,
walk the 8-connected skeleton from both endpoints and withhold the outermost
`tip_len` px (variants 8 / 16 / 32 px = 0.8 / 1.6 / 3.2 km) as the hidden
truth. Everything else in that segment stays visible. No `link_px` grouping is
applied, so hidden truth lies **immediately adjacent** to visible catalogue —
which is what "the map stops here but the fault continues" actually looks like.

*Why this is a fair proxy and not a rigged one:* the withheld pixels are chosen
**only from catalogue geometry** (segment endpoints), never from any feature
value, so no detector can be tuned on them. The visible remainder is the only
information any candidate may use. The rule is symmetric across candidates.

*What it can and cannot say:* it measures "can you extend a mapped trace into
its own continuation". It does **not** measure "can you find a fault where no
fault was ever mapped" — nothing local can, per F6.

Decision rule and folds are in §3.

---

## 2. The five hypotheses (ranked by expected DTI gain ÷ implementation cost)

### H-R14-1 — Along-strike propagation tips  ·  rank **1**  ·  cost LOW

* **Layers:** `labels.tif` geometry only. No geophysics.
* **Physical signature:** at each visible trace endpoint, estimate the local
  strike by principal-component analysis of the endpoint's 8-connected
  neighbourhood (window 9 px), then emit a **tapered ribbon** along that strike
  for `L` px beyond the tip (variants L = 5 / 10 / 20 px) with a perpendicular
  Gaussian of σ = 1 px and amplitude decaying linearly to 0 at L. Ridge-thin the
  result and cap total mass at a fixed budget.
* **Why it should catch a fault MISSING from the catalogue, not one already in
  it:** Quaternary fault traces in the Basin and Range terminate where *mapping*
  stopped — alluvial cover, map-sheet boundaries, LiDAR coverage gaps, or a
  mapper's confidence limit — far more often than where the *structure* stopped.
  A fault tip in the public catalogue is therefore the single highest-probability
  location for an expert-mapped continuation that the catalogue lacks. By
  construction the emitted pixels are **off-catalogue** (they lie beyond the
  visible trace), so they cannot be re-finding a mapped fault.
* **How it differs from everything implemented here:** the repo's connectivity
  work (R12 hysteresis crest continuation) links cells of a *ridge-strength
  field*; it never touches the catalogue's own geometry. `R10_vent` /
  `R8_tpi` / `R10_dzt_field` are scalar-magnitude top-K blocks. The 16GEMSDOE
  "complexity prior" multiplies a detector by an endpoint/junction boost — it
  does not extrapolate a direction. Nothing in this repo emits a pixel whose
  location is determined by a **catalogue-derived strike vector**.
* **Expected DTI gain:** HIGH under the `tip` rule (it is the rule's own
  generative mechanism — which is exactly why §3 requires it to *also* hold up
  under the pre-existing rules before it may take a slot). Under the old rules:
  ~0 by construction (F7), which is itself a prediction this register makes in
  advance and will be checked.
* **Falsifier:** if along-strike ribbons do **not** beat a distance-matched
  isotropic halo of the same budget under the `tip` rule, then *direction*
  carries nothing and only *proximity* does — a genuinely informative negative.

### H-R14-2 — Stepover / relay-ramp transfer zones  ·  rank **2**  ·  cost MEDIUM

* **Layers:** `labels.tif` geometry (segment graph).
* **Physical signature:** for every pair of visible segments whose strikes agree
  within 20° and whose perpendicular separation is 5–30 px (0.5–3 km) with
  overlapping along-strike extents, fill the quadrilateral bounded by the two
  facing tips — the **relay ramp**. Amplitude ∝ (overlap length) / (separation).
* **Why missing, not catalogued:** state and INGENIOUS maps draw the two
  through-going strands of a stepover and leave the connecting, en-echelon
  transfer structures unmapped, because they are short, discontinuous and
  partly buried. An expert re-mapping the region fills exactly that gap. The
  emitted pixels lie between traces, never on them.
* **Differs:** nothing in this repo computes pairwise trace geometry; the
  segment table (`gems.holdout.segment_table`) already has strike, extent and
  isolation per segment, so this is incremental on existing code but a new
  operator (pairwise, not per-pixel).
* **Expected:** MEDIUM-HIGH gain, but the eligible pixel population is small,
  so its effect on a coverage-dominated metric may be limited. Cost MEDIUM
  (pairwise geometry + a de-duplication pass).

### H-R14-3 — Conductivity × depth-to-basement anisotropy (buried faults)  ·  rank **3**  ·  cost MEDIUM

* **Layers:** band **17** (`Conductivity surface`) and band **15**
  (`Depth to basement surface`) — **neither has ever been used in this repo** —
  plus band 6 used *correctly* (see below).
* **Physical signature:** the **structure-tensor coherence** of each field,
  `(λ1 − λ2)² / (λ1 + λ2)²` over a 15 px window, where λ are the tensor's
  eigenvalues. Coherence is high on a *lineament* and low on a broad anomaly or
  on noise. Take the max over the two fields, restrict to pixels where
  depth-to-basement exceeds the local 45 px median (i.e. under basin fill), and
  ridge-thin.
* **Why missing, not catalogued:** a fault buried under alluvium has **no**
  topographic expression, so every topographic crest detector this repo has
  built is blind to it (F8 measures exactly that blindness). Buried normal
  faults in the NW Great Basin are the classic case where the basement offset
  and the conductivity contrast of the fault gouge/fill survive at the surface
  while the scarp does not. This is the class the public catalogue is most
  incomplete in.
* **Band 6 correction, inherited and flagged:** band 6's own GDAL tag says
  *"Tilt angle or total curvature - magnetic field derivative"*, but its values
  are all-positive (2.95–88.57, this session's `data/derived/band_stats.json`)
  while a tilt angle spans both signs, and 16GEMSDOE measured r = +0.997
  against the external USGS GeoDAWN **radiometric total count** (flag F01).
  12GEMSDOE independently concluded band 6 is the official *top-of-crustal
  magnetic source depth*. **The two sibling repos disagree.** This register
  therefore uses band 6 only as a *positive-valued scalar* and never as a
  signed angle, and flags the identity as unresolved (I-25) rather than picking
  a side on inherited authority.
* **Differs:** repo detectors are magnitude top-K on topography, magnetics,
  gravity and strain. Coherence (a ratio of directional variances) is a
  different operator class, and bands 15/17 are untouched.
* **Expected:** MEDIUM. Cost MEDIUM (structure tensor is two box filters and an
  eigen-decomposition per pixel; vectorisable).

### H-R14-4 — Dilatation zero-crossing coincident with a strain-invariant maximum  ·  rank **4**  ·  cost MEDIUM

* **Layers:** band **8** (`Geodetic dilatation rate`, range −16.5 … 34.52, the
  only signed strain band), band **4** (`Geodetic second invariant`, 1.2 … 87.45),
  band 7 (`shear rate`) as a tie-breaker.
* **Physical signature:** the **signed zero-crossing** of band 8 (dilatation
  flips from extensional to compressional across the structure) *co-located*
  within 1 px of a local maximum of band 4. Emit only the zero-crossing ridge,
  thinned to 1 px, weighted by the band-4 maximum.
* **Why missing, not catalogued:** a catalogue compiled from surface mapping
  omits structures that are straining geodetically but carry no scarp. "Actively
  deforming + no topographic expression" is precisely the un-mapped class, and a
  sign flip is a *differential-topology* signature that survives smoothing,
  unlike a magnitude threshold.
* **Differs:** this session measured raw magnitude rankings of bands 4/7/8 and
  they were worse than random (F8). The zero-crossing **coincidence** operator
  is not a magnitude ranking — it is a new operator on the same layers, and F8
  is the prior *against* magnitudes, not against it. Declaring that explicitly
  so the negative result is not quietly reused as a reason to skip this.
* **Expected:** MEDIUM-LOW. Cost MEDIUM.

### H-R14-5 — 1 m 3DEP scarp antislope + tectonic/fluvial discrimination  ·  rank **5**  ·  cost HIGH

* **Layers:** external — **USGS 3D Elevation Program (3DEP) 1 m DEM**. Free,
  official, public: landing <https://www.usgs.gov/3d-elevation-program>, index
  <https://prd-tnm.s3.amazonaws.com/index.html?prefix=StagedProducts/Elevation/1m/>.
  The competition itself ships `1m_DEM_links.csv` for exactly this purpose
  (problem description, <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>).
  **Obtainability:** not verifiable from this sandbox (egress to
  `prd-tnm.s3.amazonaws.com` and `gdr.openei.org` is blocked; `curl` returns
  `SSL_ERROR_SYSCALL`). The repo already has a working pattern for
  runner-fetched external data (`.github/workflows/fetch-gdr1391.yml`), so the
  route exists but is **unverified for this source** — recorded as an open item,
  not as "available".
* **Physical signature:** a fault scarp has an **asymmetric** cross-profile — a
  steep free face on one side, a gentler slope on the other — while a fluvial
  channel is V-shaped and symmetric. Detector: sign reversals of the
  along-profile slope ("antislope") plus a break-in-slope at a locally
  consistent elevation, aggregated to 100 m as the fraction of 1 m cells in the
  100 m pixel that are tectonic rather than fluvial.
* **Why missing, not catalogued:** 1 m LiDAR resolves scarps an order of
  magnitude finer than the 100 m competition grid. Experts map new faults from
  it. 7GEMSDOE's `lidarscarp-ridge-top2pct` map is recorded at public 0.1461, so
  the source demonstrably carries signal that survives to the board.
* **Differs:** this repo has never staged the 1 m DEM (limitation L-1). 12GEMSDOE
  used the 10 m DEM with NMS-3; 16GEMSDOE computed `lid1m_antislope` and
  `lid1m_tect_vs_fluv` and found them its 3rd/4th best exploratory correlates of
  public score (ρ = 0.518 / 0.450, both uncorrected p > 0.048, n = 15,
  Bonferroni threshold 0.00098 — i.e. **not significant after correction**,
  which is how it is reported here).
* **Expected:** MEDIUM-HIGH. Cost HIGH (runner fetch + reprojection + 1 m → 100 m
  aggregation over ~30 USGS quadrangles).

### Explicitly NOT proposed (already tried here or in a sibling repo)

Multi-scale / scale-persistent / local-contrast crest (R12, R13-1, R13-2);
hysteresis crest continuation (R12); greedy marginal-precision block assembly
(R11-4); tile-quota budget (R13-3); paleo-geothermal halos from GDR 1391
(R13-4, measured losing with a clean dose-response); basin magnetics (R11-2,
R12 retest); Euler deconvolution / depth-to-source (R13-5, still deferred — it
is a *depth* estimator and the target is a surface trace); fault-blind lattices
(R13-6, already shipped); CNN ensembles and gradient boosting on raw bands
(sibling repos, public 0.1563 / 0.0286).

---

## 3. Folds, decision rule, stopping rule (fixed before measuring)

**Folds.** Three families, all on the official footprint:

1. `tip_8`, `tip_16`, `tip_32` — the new rule, §1, 3 seeds each → 9 folds.
2. The repo's existing 15 folds (`random` / `short` / `isolated` / `oriented` /
   `dense`, 3 seeds, `hide_frac` 0.25, `link_px` 8, `buffer_px` 5) — unchanged,
   so nothing previously measured is invalidated.
3. `sgmc_offcat_r16` as a **single external truth set** (USGS State Geologic Map
   compilation faults ≥ 16 px from the catalogue, 56,917 px,
   `data/external_sgmc/derived_sgmc_faults_100m_u8.tif`, sha256
   `d569d5539972f86a7862add0ce6738275ffd56174b9ef1298b08b8ab1dcd700f`).

**Scoring.** `src.gems.metric.dti`, α = 0.2, β = 0.8, R = 3 px, verified against
`src.gems.fastscore.FoldScorer` before every run. Evaluation mask always
`footprint & ~visible_catalogue` (F1).

**Decision rule (all four must hold for a candidate to be recommended):**

* **D1** beats the shipped reference (`lattice_s5`) on the **worst-rule mean**
  over the 9 `tip` folds;
* **D2** beats it on ≥ 7 of 9 `tip` folds individually (paired);
* **D3** does **not** lose by more than 0.002 DTI on the worst rule of the 15
  pre-existing folds (so the candidate is not only good in the fold family
  designed for it);
* **D4** its emission is ≥ 95 % off-catalogue (i.e. it is not merely re-predicting
  masked pixels, which F1 says are worthless).

**Stopping rule.** If no candidate satisfies D1–D4, **no slot is spent** and the
shipped artifact stays the format-corrected `lattice_s5`. Per F6 no proxy win is
sufficient to *predict* a leaderboard score, so a win is reported as "passes the
predeclared local gate", never as an expected score.

**Slot policy.** Three scored submissions per rolling 7-day window (Official
Rules §3.2; staff clarification, forum topic 11524). Whether a *rejected* upload
consumes an allowance is undocumented in anything this project could fetch —
ask `info@drivendata.org` before relying on either answer.

---

## 4. Predeclared predictions (checked after, not before)

* **P1.** `halo_topK` (isotropic distance-to-visible-catalogue) will beat
  `lattice_s5` under the `tip` rule and lose to it under the old rules. If it
  wins under *both*, F7 is wrong and this register's premise is wrong.
* **P2.** H-R14-1 will beat `halo_topK` at equal budget under the `tip` rule
  (direction matters, not just proximity). If it does not, the falsifier in
  H-R14-1 fires.
* **P3.** H-R14-3 and H-R14-4 will not beat `lattice_s5` on the pre-existing 15
  folds (F8's prior), and their `tip`-rule result is unknown.
* **P4.** Nothing here will reach DTI 0.3168 on any local truth set, because
  F3 + F6 say the local truth sets are not the private one.

---

## Addendum B — predeclared BEFORE the corrected run was read (2026-10-01 session 8)

Two things were changed after the first run of
`scripts/validate_r14_hypotheses.py` and before its output was interpreted. Both
are declared here so neither can be mistaken for post-hoc tuning.

### B.1 A bug in the first run: tie-breaking by row-major position (I-14, recurring)

`gems.propagation.budget_from_intensity` selected a top-K with a bare
`np.argpartition`. Intensity fields built from a distance transform are
**massively tied**: the 1-px ring around a 60,988-px catalogue contains roughly
200,000 pixels that all carry the *same* score, so a K of 51,674 is filled by
whichever of them come first in flat index order — the northernmost slice of the
study area. The isotropic-halo control was therefore not measuring "proximity
without direction"; it was measuring "proximity, restricted to the north". Its
first-run numbers (DTI 0.039–0.057 on the `tip` folds, 0.0000 on the old folds
and on the SGMC truth set) are **void** and predictions **P1** and **P2** were
not legitimately tested by them.

Fixed: every budget selection now takes a fixed, seeded, spatially uniform
jitter field (`gems.propagation.make_jitter`, seed 20261001) scaled to 1e-7 of
the field's own range, so exact ties break uniformly while genuinely different
intensities keep their order. The largest-tie fraction of every deployment field
is recorded in the report (`tie_fractions_largest_tie_over_allowed`) so the
pathology cannot hide again. P1 and P2 are re-tested on the corrected run and
reported as re-tested.

**The mechanism is now measured, not asserted**
(`tests/test_r14.py::TieBreaking`, reproducible in <1 s): on a fully tied
100×100 field with K = 1000, a bare `argpartition` put **959 of the 1000
selected pixels in the first row decile** and never sampled 7 of the 10 deciles
at all; with the seeded jitter the decile counts are 93–116. A partially tied
field (a distinct top block over a tied remainder) is biased the same way
(960/1000 in the first decile). Note that `rows.max()` is the wrong statistic
for this — a handful of stragglers land far south and hide the concentration;
the decile histogram is the test.

**How much it changed, measured over two full runs of the same script** (worst-rule-mean DTI on the 9 `tip` folds / the 15 pre-existing folds / the SGMC ≥16 px truth set):

| candidate | no jitter (void) | with jitter (authoritative) |
|---|---|---|
| `halo@0.01` | 0.01848 / — / — | 0.02095 / 0.00000 / 0.00000 |
| `tips_L20@0.01` | 0.09389 / 0.00000 / 0.00001 | 0.09394 / 0.00000 / 0.00001 |
| `tips_L5@0.02` | 0.06199 / 0.00201 / 0.00263 | **0.08774 / 0.02975 / 0.02499** |
| `tips_L5@0.04` | 0.04394 / 0.00542 / 0.01126 | **0.10197 / 0.06079 / 0.12057** |
| `tips_L10@0.04` | 0.06693 / 0.00394 / 0.00319 | **0.10146 / 0.04158 / 0.05820** |
| `lattice_s5` (reference) | 0.08801 / 0.10657 / 0.23913 | 0.08801 / 0.10657 / 0.23913 (unchanged: no ties) |

So the instability was real and material — up to **11×** on the SGMC truth set —
but it was **not uniform across candidates**: the reference lattice has no ties
and did not move at all, while short-ribbon variants moved a great deal. Any
comparison taken from the first run was therefore between selections of
different stability, and the whole first run is void.

**What this does NOT explain, stated plainly so it is not over-claimed.** The
jitter changed the isotropic-halo control by at most 24 % (tip mean 0.0387 →
0.0478 at a 1 % budget; 0.0566 → 0.0567 at 4 %), so the halo's weakness is *not*
a tie-breaking artefact. Its real cause is budget allocation: at a 1 % budget
(51,674 px) the halo spends everything on the ~1-px ring around the whole
visible catalogue (~150,000 px), of which only the handful of pixels that
actually *continue* a trace are truth. Direction is what separates those from
the rest of the ring — which is prediction P2, and it survives the correction.

### B.2 Three new candidates: a coverage floor under a geological prior

The first run made the trade-off stark: propagation tips score far above the
reference on the `tip` folds and far below it on the pre-existing folds, because
the two fold families hide *different geometries* (adjacent continuations vs
whole systems ≥ 1.6 km away). Neither family is known to be the right one (F6).
Rather than pick a side on an unresolved question, this addendum predeclares the
hedge:

**`union_tipsL{L}_{t}+lat{s}_4pct`** — select the along-strike tip ribbons first
at budget *t*, then fill the remainder of a fixed **4 % total budget** with
points of a stride-*s* fault-blind lattice, never letting a coverage pixel
displace a tip pixel. Rationale, from F3: β = 0.8 pays four times what α = 0.2
charges, so recall is cheap to buy, but the total area is what sets the FP term,
so the total is held at the reference's own 4 % (206,695 px). If the tips are
right, the union keeps most of their gain; if they are wrong, the lattice floor
keeps the union near the reference instead of collapsing to it.

Predeclared variants (fixed before reading the corrected run):

| name | tip length | tip budget | lattice stride | total budget |
|---|---|---|---|---|
| `union_tipsL20_1pct+lat7_4pct` | 20 px (2 km) | 1 % | 7 | 4 % |
| `union_tipsL20_2pct+lat7_4pct` | 20 px (2 km) | 2 % | 7 | 4 % |
| `union_tipsL10_1pct+lat6_4pct` | 10 px (1 km) | 1 % | 6 | 4 % |

**Predeclared decision rule for the unions — identical to §3 (D1–D4), plus one
extra condition declared now:**

* **D5** the union must beat the reference on the worst-rule mean of **both**
  fold families (`tip` **and** the 15 pre-existing folds), or lose on neither by
  more than D3's 0.002. A union that wins one family and collapses in the other
  is not a hedge, it is a bet with extra pixels, and it does not pass.

**Predeclared expectation:** the unions will land between the two parents on
both families. If a union beats the reference on both families under D1–D5 it is
the recommended artifact, because it is the only candidate class that does not
require resolving F6 first.

### B.3 What may and may not be concluded from a PASS

Unchanged from §3 and F6: a PASS means "clears the predeclared local gate". No
number produced here is a leaderboard prediction, and the recommendation for how
to spend the three weekly uploads is made separately, in the README, using the
Phase-2 argument (F2) as well as the Phase-1 gate.
