# Candidate hypotheses — targeting gaps in the mapped-fault catalogue

> **Evidence boundary:** the geological mechanisms below are hypotheses unless a
> cited source directly supports the underlying mechanism. “Expected DTI gain” and
> cost labels are qualitative planning judgments, not numerical forecasts. All
> local hide-and-recover results use known-catalogue truth and are proxy
> measurements—not public/private leaderboard performance.

## The premise, stated precisely

The test labels are, by the organizers' own definition, *"any fault pixel not
already captured by USGS/INGENIOUS"*
([forum 11536](https://community.drivendata.org/t/where-do-you-draw-the-line/11536)).
So the object of the search is not "a fault" — it is **a fault that a specific
compilation process failed to record**.

That compilation is the **USGS Quaternary Fault and Fold Database** plus the
INGENIOUS Quaternary fault compilation
([Official Rules §2](https://docs.nlr.gov/docs/fy26osti/96647.pdf):
*"The labels for this prize come from the USGS Quaternary Fault and Fold
Database and from a set of newly identified faults labeled by geology experts at
the National Laboratory of the Rockies (NLR) and USGS"*). A Quaternary fault
compilation records structures with demonstrable Quaternary surface
displacement, evidenced predominantly by **scarps visible in topography and
imagery**, trenching, and published geologic mapping.

Its systematic blind spots therefore are:

| # | Blind spot | Physical reason it is missed |
|---|---|---|
| B1 | **No surface scarp** | buried beneath Quaternary alluvium / playa fill |
| B2 | **Non-topographic surface expression** | expressed as lithologic, geochemical or hydrologic contrast, not relief |
| B3 | **Not demonstrably Quaternary** | a real fault with pre-Quaternary offset only — excluded from a *Quaternary* database but still "a fault pixel not already captured" |
| B4 | **Subtle vertical component** | strike-slip and oblique structures with little scarp |
| B5 | **Coarse historical mapping** | scale-limited legacy compilation |

**Prior-art scope:** eight historical TIFFs are available for structural
comparison, and several filenames carry score labels, but no per-submission
receipts tie those labels to the files (`reports/leaderboard_ledger.csv`). We
therefore cannot rank those maps by competition score. The data support a
methodological concern—not a performance conclusion—that repeating only
scarp/ridge detectors may miss other expressions of uncatalogued faults.

The H-A–H-E candidates use the supplied feature stack (H-D also uses the visible
catalogue per fold). Their mechanisms and expected gains remain hypotheses until
implemented and measured under a leak-free local protocol; none of those local
scores estimates hidden-test performance.

---

## H‑A · Multiscale potential-field "worms" 🥇

* **Layers:** `rtp` (band 2, reduced-to-pole magnetics), `iso_grav_anom` (band 13).
* **Transform:** Fourier upward continuation `F(k) → F(k)·exp(−|k|h)` for
  h ∈ {0, 0.5, 1, 2, 4, 8} km; horizontal-gradient magnitude at each height;
  Hessian ridge + non-maximum suppression to a 1-px crest; stack with a weight
  that increases with h.
  Implementation: `gems.detectors.worms`.
* **Blind spot attacked:** B1, B3.
* **Why it finds a *missing* fault.** The horizontal gradient of a potential
  field peaks over the lateral edge of a density or susceptibility contrast. As
  the field is upward-continued, short-wavelength contributions decay first.
  A **steeply-dipping, vertically-extensive** contrast — which is what a fault
  is — keeps producing a gradient maximum in nearly the same map position
  through several kilometres of continuation. Shallow sedimentary texture,
  cultural noise and survey artefacts do not. Persistence across height is
  therefore a *discriminator for faults specifically*, and it is completely
  independent of whether the structure reaches the surface. A fault under
  300 m of basin fill has no scarp and cannot be in QFaults, but it still
  offsets magnetic basement.
* **How it differs from prior work.** The repo used the *provided* single-scale
  gradient bands (`tmi_hg`, `iso_grav_anom_hg`, `iso_grav_anom_slope`) and
  generic ridge filters. Upward continuation is never computed anywhere, so
  cross-scale persistence — the part that does the discriminating — has never
  been available.
* **Expected DTI gain:** High. **Implementation cost:** Low (FFT, ~20 s/band).

---

## H‑B · Tilt-derivative zero contour and theta map 🥈

* **Layers:** `rtp` (2), `iso_grav_anom` (13).
* **Transform:** `TDR = atan2(∂F/∂z, |∇ₕF|)`, with the vertical derivative
  taken in the Fourier domain (multiply by `|k|`). Edge likelihood =
  `|∇ TDR|` gated by proximity to the TDR zero contour. Also the theta map
  `θ = acos(THDR/AS)`.
  Implementation: `gems.detectors.tdr_edge`, `theta_map`.
* **Blind spot attacked:** B1, B3, B4.
* **Why it finds a *missing* fault.** TDR is **amplitude-normalised**: it is
  bounded in (−π/2, π/2) and its zero crossing sits over a source edge
  regardless of how strong the anomaly is. A plain gradient detector ranks
  pixels by anomaly *amplitude*, so it re-finds the loud, shallow, already-mapped
  structures and buries the quiet ones. The unmapped population is quiet
  **by construction** — that is why it was not mapped. Amplitude normalisation
  is the single cheapest way to invert that selection bias.
* **How it differs from prior work.** Nothing in the repo computes a vertical
  derivative or a tilt angle from RTP. Band 6 `tc` was *assumed* to be a tilt
  angle because of its embedded description, but that description is almost
  certainly wrong (irregularity I‑2) — so the team believed it had a tilt
  transform when it did not.
* **Expected DTI gain:** High. **Implementation cost:** Low.

---

## H‑C · Concealed basement hinge under flat cover 🥉

* **Layers:** `depth_to_base_surf` (15, depth to conductive base surface),
  `det_elev_slope` (19).
* **Transform:** ridge of `|∇ depth_to_base_surf|`, NMS-thinned, then
  **multiplied by a flat-topography mask** (slope below the 55th percentile,
  smoothed). Implementation: `gems.detectors.basement_hinge`.
* **Blind spot attacked:** B1 — directly and exclusively.
* **Why it finds a *missing* fault.** A normal fault that offsets the basement
  but is blanketed by Quaternary fill produces a **step in basement depth and
  nothing at the surface**. The anti-topographic gate is the whole idea: it
  *inverts* the usual scarp hunt so the detector can only fire where a
  scarp-derived catalogue is structurally blind. Anywhere the range front is
  expressed topographically, this detector is switched off — precisely because
  those faults are already mapped.
* **Geothermal relevance.** Concealed intrabasin faults are the canonical
  hidden-geothermal target; it is the stated premise of the INGENIOUS project
  (*"accelerate discoveries of new, commercially viable **hidden** geothermal
  systems"*, [GDR 1391](https://gdr.openei.org/submissions/1391)) and of the
  prize itself (*"One major hurdle in this process is identifying new hidden
  geothermal prospects"*, [Official Rules §2](https://docs.nlr.gov/docs/fy26osti/96647.pdf)).
* **How it differs from prior work.** Conductivity and depth-to-basement were
  used as generic ML input features. The **conjunction** — require a basement
  step AND require no relief — is new, and it is the part that selects for
  catalogue-invisibility rather than for faultiness in general.
* **Expected DTI gain:** Medium-High. **Implementation cost:** Low.

---

## H‑D · Strain-budget residual

* **Layers:** `geod_2ndinv` (4), `ieq_n100a15` (16), plus fault density
  recomputed per holdout fold from the **visible** catalogue only.
* **Transform:** `clip(ŝ − 0.5·ê − 0.5·k̂, 0, 1)` on percentile-normalised,
  Gaussian-smoothed fields. Implementation: `gems.detectors.strain_residual`.
* **Blind spot attacked:** B1, B5 — as a *prior*, not a detector.
* **Why it finds a *missing* fault.** Geodetically measured strain must be
  accommodated by slip on structures. Where the second invariant of the
  strain-rate tensor is high but both earthquake density and mapped fault
  density are low, the accommodating structure is, by elimination, not in the
  catalogue. This is an argument from a **deficit**, which is qualitatively
  different from every amplitude-based detector.
* **Known weakness, stated up front.** The geodetic fields are heavily smoothed
  and have no pixel-scale information, so this can only ever localise a
  *corridor*, not a trace. It is therefore intended as a **multiplier on a
  sharp detector**, never as a standalone map. If it wins standalone on the
  holdout, that is evidence the holdout is too easy, not that the idea is good.
* **How it differs from prior work.** Strain bands were fed to gradient-boosted
  models and a "dilational annulus / top-k" was tried, but never as a residual
  conditioned on catalogue density.
* **Expected DTI gain:** Low-Medium. **Implementation cost:** Low.

---

## H‑E · Directional-coherence lineaments in non-topographic contrast

* **Layers:** `tc` (6 — see irregularity I‑2), `cond_surf` (17).
* **Transform:** oriented matched-filter bank — 12 strikes × 15 px (1.5 km)
  line kernels applied to the smoothed edge magnitude; take the maximum
  response. Implementation: `gems.detectors.directional_lineaments`.
* **Blind spot attacked:** B2 — directly.
* **Why it finds a *missing* fault.** Faults juxtapose different lithologies
  and act as conduits or barriers to groundwater, so they produce sharp,
  **linear** contrasts in near-surface potassium/uranium/thorium and in
  electrical conductivity even where there is no relief whatsoever. Coherence
  over 1.5 km separates a structural lineament from speckle.
* **Why radiometrics specifically.** GeoDAWN is officially *"a high-resolution
  **lidar, magnetic, and radiometric** study"*
  ([Official Rules §2](https://docs.nlr.gov/docs/fy26osti/96647.pdf)) and the
  problem page's own figure shows *"total radiometric counts per second"*. It
  is the least-exploited of the three GeoDAWN products, which is exactly where
  a contrarian edge should be looked for.
* **Honest overlap.** Radiometrics *does* appear in the repo — as an ML input
  raster (`radiometric_u8.tif`, `context_detector_prob_topo_rad.tif`). It has
  never been used as an **oriented lineament detector**. This is a smaller
  novelty gap than H‑A/H‑B, and it is contingent on I‑2 being resolved.
* **Expected DTI gain:** Medium. **Implementation cost:** Low.

---

## Ranking

| rank | hypothesis | expected DTI gain | cost | blind spot | novelty vs this repo |
|---|---|---|---|---|---|
| 1 | **H‑A** worms | High | Low | B1, B3 | complete |
| 2 | **H‑B** tilt / theta | High | Low | B1, B3, B4 | complete |
| 3 | **H‑C** basement hinge | Medium-High | Low | B1 | the conjunction is new |
| 4 | **H‑E** directional lineaments | Medium | Low | B2 | partial (radiometrics used as ML feature) |
| 5 | **H‑D** strain residual | Low-Medium | Low | B1, B5 | the deficit framing is new |

The local proxy-holdout results qualify this research ranking; they do not
measure hidden-test performance. See `reports/holdout_results.json` and the
[Hypotheses page](https://buffedlizard55-lab.github.io/13GEMSDOE/hypotheses.html).

---

## R6 — Earlier detector hypotheses (2026-09-29; historical)

All five were implemented in `src/gems/detectors.py` and cached as `R6_*.npy`.
Their original rankings and per-detector scores came from older local protocols and
are not expected private-test gains. A review found the historical holdout-v3 chance
comparison had used the full valid-grid count rather than each fold's smaller eligible
`eval_mask`; the old lift values are superseded. The corrected holdout-v3 summary is
DTI-ranked and its chance values are only local diagnostics. The current 18-fold
visible-only comparison tests the broader archived R8 recipe against a local topo
baseline; R8 loses, and does not establish whether an R6-only map would win. No full
R6 recipe has been cleared for upload.

### R6-1 · Horsetail splay / relay-ramp structural completion
- **Layers:** `existing_faults` geometry only (catalogue-derived, rebuilt per fold).
- **Signature:** Detects en-echelon step-overs within 20 px (2 km) where two subparallel (<30°) segments' tips are close; draws bridging line + emits fan of 5 rays ±35° at each tip (horsetail).
- **Why it could find an uncaptured fault:** a real relay ramp or splay may be unmapped or only partly captured; the organizer's definition includes newly mapped extensions, splays, parallel strands, and corrections. Whether this geometric prior improves discovery beyond catalogue proximity is uncertain.
- **Differs from prior repo:** `extension_rays` projects forward along an individual trace; this operator links nearby traces and adds a diverging fan. It is catalogue-derived and therefore must be rebuilt from each fold's visible geometry.
- **Expected DTI impact:** unknown. The prior tip-focused holdout measured a different target protocol and is not evidence of private-test gain. **Cost:** Low implementation, with substantial geometry/false-positive validation risk.

### R6-2 · Paleo-shoreline / lacustrine terrace scarp (intrabasin)
- **Layers:** `det_elev` (12), `det_elev_slope` (19).
- **Signature:** Second-derivative curvature ridge (Laplacian) on detrended elev, gated to low-slope (<45th percentile) AND low local variance (playa/lake bed), then directional coherence 12 px for shoreline continuity.
- **Why it could find an uncaptured fault:** if a Quaternary fault has a subtle scarp within a basin, detrended curvature and lateral continuity may help distinguish it from broad relief. The supplied 100 m elevation grid cannot establish decimetre-scale morphology; shoreline, depositional, and erosional lineaments are confounds. No claim is made that these features are absent from the catalogue or geothermal.
- **Differs:** BASE_topo_ridge emphasizes ridges; this candidate uses curvature plus low-slope/variance gates. It remains a topographic detector and may be redundant.
- **Expected DTI impact:** unknown; rank is qualitative only. **Cost:** Medium (curvature and gate sensitivity).

### R6-3 · Conductive-base step with conductivity coherence (improved HC)
- **Layers:** `depth_to_base_surf` (15), `cond_surf` (17), `det_elev_slope` (19).
- **Signature:** Product of gradient magnitudes of depth_to_base and cond_surf, ridge-thinned, gated by flat topography (55%) AND anti-topo (1 - topo_ridge strength), then oriented-filtered 15 px.
- **Why it could find an uncaptured fault:** a buried basement or lithologic boundary may coincide with a fault under weak relief, but depth and conductivity anomalies are not fault-specific and their co-location is not proof of faulting.
- **Differs from HC_hinge:** HC uses basement-depth gradient alone; this tests a joint depth/conductivity response plus flat/anti-topographic gates.
- **Expected DTI impact:** unknown. **Cost:** Low-to-medium (co-registration and scale checks).

### R6-4 · Gravity-gradient termination / intersection
- **Layers:** `iso_grav_anom_hg` (18), `iso_grav_anom_vg` (11), `iso_grav_anom` (13).
- **Signature:** Detect terminations of horizontal gravity gradient ridges (ridge pixel with only 1 neighbor), emit short continuation 12 px beyond termination outward. Intersections (high orientation variance) emit crossing splay.
- **Why it could find an uncaptured fault:** a gravity-gradient termination could be consistent with an unmapped structural edge or continuation, but it can also arise from data resolution, noise, processing, or non-fault density boundaries. The cited INGENIOUS analysis motivates testing the signature; it does not validate this detector.
- **Differs:** Uses candidate gravity-ridge terminations rather than catalogue fault tips.
- **Expected DTI impact:** unknown. **Cost:** Low-to-medium (termination thresholds and local filtering).

### R6-5 · Transtensional coupling / dilational jog
- **Layers:** `geod_shearrate` (7), `geod_dilaterate` (8), `geod_2ndinv` (4), `iso_grav_anom_hg` (18).
- **Signature:** Normalized shear * positive dilatation * second invariant, multiplied by gravity gradient ridge to localize to sharp trace, then oriented lineaments.
- **Why it could find an uncaptured fault:** a transtensional strain pattern may indicate distributed deformation where no clear surface scarp is mapped. Strain can be broad or reflect regional motion; it is not fault-specific, and any permeability interpretation is a hypothesis.
- **Differs from HD_strain:** HD used a deficit construction; this candidate multiplies shear and dilatation with a gravity-edge score as positive evidence.
- **Expected DTI impact:** unknown. Earlier fold-specific DTI values were mixed and protocol-dependent (for example, the cited isolated fold scored below topo); they do not establish a general or hidden-test gain. **Cost:** Medium.

### R6 ranking (historical qualitative order; not a current submission ranking)

| earlier research order | hypothesis | qualitative potential | cost | limitation / local note |
|---|---|---|---|---|
| 1 | **R6-1** horsetail splay | unknown | Low implementation | Catalogue-derived geometry; old tip-focused validation does not test the current target mix |
| 2 | **R6-3** conductive-base step | unknown | Low-to-medium | Joint layers may be correlated; no current full-recipe comparison |
| 3 | **R6-2** intrabasin curvature | unknown | Medium | Topography remains a confounded proxy; no confirmed Lahontan-specific coverage |
| 4 | **R6-4** gravity termination | unknown | Low-to-medium | Threshold/resolution sensitivity; old single-fold result is not a general rank |
| 5 | **R6-5** transtensional coupling | unknown | Medium | Earlier isolated-fold DTI was below topo; not a confirmed robust gain |

Historical per-fold DTI values at 2% target coverage: on `random_0`, topo 0.0599,
gravity termination 0.0426, TDR 0.0434, shoreline 0.0237, conductive-base 0.0112,
transtension 0.0083, and worms 0.0196. On `isolated_0`, topo 0.0722, transtension
0.0658, TDR 0.0592, gravity 0.0404, and worms 0.0384. These are isolated local
measurements from that historical protocol; they are not comparable to a private score
or enough to select a full ensemble.

**Current decision:** the old “R6 ensemble hedge” description and its chance-lift,
precision, and 300 m decimation claims are withdrawn as a submission recommendation.
No R6-only recipe has been evaluated under the latest full confirmation protocol.
The archived broader R8 recipe was rebuilt with visible-only catalogue geometry and
scored in the 18-fold local comparison: the topo baseline's confirmation worst-rule
mean DTI was 0.08687 (mean 0.09763), while the R8 union scored 0.05584 (mean 0.06615).
R8 had higher recall but lower precision and greater support; no R8 variant beat the
baseline. This catalogue-recovery result is a local proxy, not a private-test estimate.
See `reports/holdout_candidate_r8_2026-09-30.json`. No map is cleared for an upload.

---

## R9 — Three new hypotheses implemented and MEASURED (2026-09-30, session 3)

All three were implemented in `src/gems/detectors.py` and validated with a
predeclared, paired protocol (`scripts/validate_r9_holdout.py`): identical folds,
buffer, scorer, and tune/confirm split to the R8 comparison; the reference
`topo_05_sp3` is re-scored in the same run and **reproduces the archived per-fold
DTI values exactly** (protocol regression check PASS). Report:
`reports/holdout_r9_2026-09-30.json`. Predeclared verdict rule: WIN requires
beating the reference on tune AND confirmation worst-rule-mean DTI and not losing
more than 2 of 6 confirmation rule-means.

### R9-1 · Strike-aligned gap completion ("dotted-ridge closing") — LOSES
* **Layers:** the fused binary prediction map only (no band, no catalogue) — fold-independent by construction.
* **Transform:** `gems.detectors.strike_gap_close` — oriented closing (4 lattice directions), pure gap-fill: both-sides support requirement, anchor and solid-interior gates; axial reach 3 px, diagonal 2 px so every filled pixel is within the scorer's 300 m kernel of support on each side.
* **Why catalogue-missing:** per-pixel "new fault" definition + 300 m max kernel means a truth pixel inside a dash gap earns 0 TP_w, while a prediction there costs ≈0 FP_w if the line is real; legacy compilations record extensions/splays as short pieces (B5).
* **Measured outcome:** strict variant (min_side=2) adds only ~32 px/fold → exact tie (Δ −0.00001). Loose variant (min_side=1) adds ~145,608 px/fold, recall 0.2874→0.3269, precision 0.0276→0.0178, ΔDTI −0.0257 (0 wins / 12 folds). **The metric's own A5 rule predicted this: the added mass's marginal weighted precision was below 0.2 × DTI.** The decimation gaps are earning their keep — on this holdout, a ridge dash gap is usually NOT a concealed continuation.
* **Differs from prior work:** first operator that modifies the prediction's own support using its own geometry (rays/splays extrapolate from catalogue tips; nothing here reads the catalogue).

### R9-2 · Epicentral-alignment lineaments — LOSES
* **Layers:** `ieq_n100a15` (16) + `deq_n100a15` (10), near-uncorrelated (r = 0.083).
* **Transform:** `gems.detectors.eq_lineaments` — smooth, standardise, geometric mean, Hessian ridge, NMS crest, oriented-persistence gate (≥5 crest px within ±9 px along strike). Cached as `R9_eq_align.npy` (input-derived).
* **Why catalogue-missing:** active structures slip and produce earthquakes with no scarp (B1/B4); seismicity is independent of how a surface-evidence compilation was built.
* **Measured outcome:** at 1.5% coverage, +16,590 px/fold, ΔDTI −0.0021, 0/12 wins. Precision fell 0.0276→0.0264 while recall rose 0.2874→0.2983 — marginal precision just under the inclusion bar. Honest note from the design stage held: the supplied bands are smoothed densities, so this is a corridor-scale signal, not a trace.
* **Differs from prior work:** first detector whose PRIMARY signal is the seismicity fields themselves (H-D subtracts them; R7-3 gates other bands by them).

### R9-3 · Parallel-offset "correction" edges — LOSES (as a no-op)
* **Layers:** per-fold VISIBLE catalogue + `R7_crossgrad` edge field (rtp + iso_grav_anom; no catalogue input).
* **Transform:** `gems.detectors.parallel_offset_correction` — within a 1–4 px perpendicular ring of a visible trace, keep cross-gradient crest pixels parallel to local trace strike (≤25°) with an along-strike run ≥4 px; emits edge pixels only.
* **Why catalogue-missing:** organizer statement 3 (forum 11516 post 4): new-fault truth within 300 m of known traces = "corrections or modifications"; a laterally offset strong edge beside a coarse legacy trace is exactly that. The halo blanket control (`gems6_hgb88`, 0.0286) shows un-gated corridor mass is penalised — hence the physics gate.
* **Measured outcome:** ~26 px/fold, Δ −0.00001 — the conjunction (p97 crest ∧ ring ∧ parallel ∧ run) almost never fires on this grid. Recorded as a negative result: the operator as parameterized is a no-op, NOT evidence that corrections are absent from the hidden truth.
* **Differs from prior work:** first ALONG-TRACE operator (tips are R6-1/R6-2 territory; R7-5 gates on catalogue absence).

### R9 ranking (post-measurement; replaces the pre-implementation research order)

| rank | hypothesis | measured ΔDTI (confirm) | verdict | cost |
|---|---|---|---|---|
| 1 | R9-2 epicentral alignment | −0.0021 | LOSES (closest; the only challenger whose marginal precision is near the bar) | Low |
| 2 | R9-1 gap closing (strict) | −0.00001 (tie, +32 px) | LOSES (inert) | Low |
| 3 | R9-3 parallel-offset corrections | −0.00001 (tie, +26 px) | LOSES (inert as parameterized) | Medium |
| — | R9-1 gap closing (loose) | −0.0257 | LOSES badly (A5-predicted) | Low |

**Decision:** the reference recipe `topo_05_sp3` remains the local best and is shipped
as the primary downloadable artifact (`13gems-toporef-holdoutref`); no submission slot
is spent on any R9 idea. The R8 archive stays demoted.

---

## Hypotheses that need external data (named, checked, and *not* proposed as viable today)

**H‑F · Paleo-hydrothermal deposit alignment.** Sinter and tufa deposits mark
former hydrothermal upflow, and upflow in the Great Basin is fault-controlled —
so a line fitted through a chain of such deposits is a fault hypothesis with
independent physical support. Requires *Paleo Geothermal Features.zip* from
[GDR 1391](https://gdr.openei.org/submissions/1391) (CC‑BY‑4.0, 82 kB).
**Status: source verified to exist and be correctly licensed, but the download
is blocked from this sandbox (limitation L‑2). Not proposed as viable until a
machine with open egress fetches it.**

**H‑G · 2 m temperature-probe anomaly lineaments.** Shallow thermal anomalies
localise on permeable fault conduits. Requires *2m Temperature Probes.zip* from
the same GDR submission (1.03 MB). **Same status.**

**H‑H · Age/slip-rate-stratified holdout.** The charter asks for withholding
strata "by age or slip-rate class where attributes exist". Those attributes are
in *Quaternary Faults v2.zip* (5.85 MB, GDR 1391), which explicitly *"contains
updated quaternary fault traces, **ages, and slip rates**"*. **Same status** —
so the holdout currently substitutes a **strike-class** stratum, which is a
morphological proxy, and this substitution is declared in `src/gems/holdout.py`.

---

## Limitations

**L‑1 — No DrivenData authentication.** Cannot download `training_features.tif`,
`labels.tif`, `sample_submission.tif` or `1m_DEM_links.csv` first-party. The
rasters used here were recovered from this group's own public repositories;
blob SHAs are recorded. Irregularity I‑1 shows one mirrored file is mislabelled,
so this matters.

**L‑2 — Sandbox egress is restricted to GitHub.** Direct HTTPS to
`gdr.openei.org`, `docs.nlr.gov`, `www.drivendata.org` and S3 fails at the TLS
layer (`SSL_ERROR_SYSCALL`); only the GitHub API and the page-fetch tool work.
So official pages could be *read and quoted*, but external *binary* datasets
could not be downloaded. Every such dataset is named above with its exact URL,
size and licence so it can be fetched on an unrestricted machine.

**L‑3 — No private-test feedback.** The holdout is a proxy. Its absolute DTI is
not comparable to the leaderboard (different label set, different
|G|); only *relative* ordering between candidates is meaningful.

**L‑4 — 3 GB RAM / 2 cores.** Rules out training a deep segmentation model here.
Every detector in this repo is analytic and CPU-cheap by necessity. A GPU box
would allow a U-Net on the residual of these detectors.

---

## R7 — five NEW hypotheses (2026-09-29, session 2)

**Premise.** Everything above (H-A..H-E, R6-1..R6-5) attacks *edges* or
*specific morphologies* in a **single** physical field, or uses the catalogue
geometrically. The five hypotheses below attack the blind spot from three
directions that were not represented at all:

* combining **two independent physics** on the same geometry (R7-1),
* using a **different derivative order** on an existing layer (R7-2),
* using an **independent observation of fault activity** rather than of fault
  geometry (R7-3),
* requiring **N-of-M physical agreement** instead of one field's opinion
  (R7-4),
* detecting a **system-level property** (regional orientation coherence) rather
  than a pixel-level edge (R7-5).

All five are implemented in `src/gems/detectors.py`, cached by
`scripts/build_detectors.py`, and evaluated by `scripts/run_holdout3.py` under
five withholding rules plus the concealed subset.

### R7-1 · Cross-gradient structural edge

* **Layers:** `iso_grav_anom` (13) + `rtp` (2).
* **Transform:** at 0 / 1 / 3 km of upward continuation, compute both fields'
  horizontal gradients, their cosine of included angle, and gate on
  `min(norm|∇g|, norm|∇b|)` × clipped alignment; Hessian-ridge thin to 1 px;
  stack height-weighted. Implementation: `gems.detectors.cross_gradient_edge`.
* **Physical signature:** gravity measures density, magnetics measures
  susceptibility — two independent properties. A real structure produces a
  lateral contrast in **both**, and because a fault contact is one geometric
  surface the two gradient vectors point the **same way**. Non-structural
  gradients (artefacts, sedimentary texture, cultural noise, remanence) produce
  an edge in one field only, or in both pointing different ways. Directional
  coincidence between two independent measurements is a precision filter that
  says nothing about surface expression.
* **Why it catches a fault missing from the catalogue:** a buried fault that
  offsets magnetic basement makes a susceptibility edge *and* a density edge
  with no scarp, so it cannot be in a scarp-derived catalogue.
* **How it differs from this repo:** H-A worms each field separately and never
  compares them; H-B runs TDR on one field at a time; R6-3 requires
  `depth_to_base` and `cond_surf` to agree, which is a different pair and a
  different condition (product of amplitudes, not alignment of directions).
* **Expected DTI gain:** Medium. **Cost:** Low (~21 s).

### R7-2 · Basement hinge / flexure line (second derivative, not step)

* **Layers:** `depth_to_base_surf` (15), `det_elev_slope` (19).
* **Transform:** Laplacian of basement depth → Hessian ridge → NMS → flat-ground
  and anti-topographic gates → directional coherence.
  Implementation: `gems.detectors.basement_hinge_curvature`.
* **Physical signature:** the **maximum-curvature locus** of the conductive-base
  surface. H-C and R6-3 detect a *step* (first-derivative maximum). A listric
  normal fault, a monocline hinge and a drag-folded margin put their largest
  signal at the **hinge**, in the middle of the flexure rather than at its edge.
* **Why it catches a fault missing from the catalogue:** the flat-ground and
  anti-topographic gates mean it can only fire where a scarp-derived catalogue
  is structurally blind.
* **How it differs:** different derivative order from H-C/R6-3, and it
  deliberately does **not** require a conductivity contrast, so it fires on
  flexures invisible in `cond_surf`.
* **Expected DTI gain:** Medium. **Cost:** Low (~21 s).

### R7-3 · Seismicity-gated structural lineaments

* **Layers:** a sharp structural map + `ieq_n100a15` (16) + `deq_n100a15` (10).
* **Transform:** `robust_norm(structural)` × `(floor + (1−floor)·norm(Gauss(ieq)))`
  × the same for `1 − norm(deq)`. Implementation:
  `gems.detectors.seismicity_gate`; instantiated as `R7_seis_cross` (on R7-1)
  and `R7_seis_grav` (on R6-4).
* **Physical signature:** a fault that is *currently slipping* must produce
  earthquakes. The USGS/INGENIOUS compilation is a Quaternary surface-evidence
  database, so an active fault with no recognised scarp is absent from it while
  still being a fault. Seismicity is an independent observation of exactly the
  population the catalogue misses.
* **Measured support for the layer choice** (`scripts/audit_bands.py`): both
  `ieq` and `deq` have **higher** medians inside catalogue pixels than outside
  (935 vs 751 and 777 vs 621), so they behave as positive density/intensity
  quantities rather than distances — and they are near-uncorrelated with each
  other (r = 0.083), which is what makes them two usable gates rather than one
  duplicated signal.
* **How it differs from H-D:** H-D *subtracts* earthquake density from a strain
  budget (a deficit argument) and uses it as a smooth multiplier. This is a
  positive gate on a **sharp** detector, using `ieq` as evidence **for** a
  fault. R6-5 uses strain coupling, not seismicity.
* **Expected DTI gain:** Low-Medium. **Cost:** Low (~10 s).

### R7-4 · Multi-band edge consensus (N-of-5 within 300 m)

* **Layers:** `rtp` (2), `iso_grav_anom` (13), `cond_surf` (17),
  `depth_to_base_surf` (15), `tmi` (14).
* **Transform:** threshold each band's own gradient magnitude at its 90th
  percentile, dilate each binary edge by **3 px = 300 m**, and vote.
  Implementation: `gems.detectors.edge_consensus`; instantiated as
  `R7_consensus3` (3 of 5) and `R7_consensus4` (4 of 5).
* **Physical signature:** a fault juxtaposes rock of different susceptibility,
  density, conductivity and burial depth at the same place, so it moves **five
  independent physical quantities at once**. Noise, remanence and cultural
  signal move one or two. The vote is a joint detector whose false-positive
  structure is unlike any single-band detector's.
* **Why 3 px is not a free parameter:** it is the scorer's own 300 m tolerance,
  so two edges count as "the same edge" only within the distance the metric
  itself treats as a hit.
* **How it differs:** every existing detector is single-band, or a pair product
  (R6-3). An N-of-M consensus over five independent measurements is new.
* **Expected DTI gain:** Medium (precision-weighted). **Cost:** Low (~22 s).

### R7-5 · Regional structural grain where the catalogue is silent

* **Layers:** `rtp` (2) + `existing_faults` geometry, with the catalogue term
  rebuilt **per holdout fold from the visible catalogue only**.
* **Transform:** structure tensor of the gradient-orientation field;
  coherence `(λ1−λ2)/(λ1+λ2)`; inverted smoothed visible-catalogue density as a
  blindness gate; thin along the principal grain direction.
  Implementation: `gems.detectors.structural_grain`.
* **Physical signature:** a fault **system** imposes one preferred orientation
  over kilometres; isolated artefacts do not. Tensor coherence is high only
  where the orientation field is locally single-valued.
* **Why it catches faults missing from the catalogue:** the organizers define
  "new fault" to include "newly mapped geometry of an existing fault system" —
  extensions, splays and **parallel strands**. A parallel strand is at the same
  orientation as the mapped system and within a few km of it, so it is invisible
  to any single-edge detector and to a human mapper scanning imagery, yet it is
  a coherent extension of the regional grain. Gating on **catalogue silence**
  rather than distance to the catalogue is what distinguishes this from the halo
  controls.
* **How it differs:** nothing in this repo computes a regional
  orientation-coherence field, and nothing uses "the catalogue fails to explain
  the observed grain" as a detection criterion.
* **Known weakness, stated up front:** with the **full** catalogue the blindness
  gate leaves only **1,748** of 5,167,373 valid pixels (0.034 %) — the
  submission-side version is effectively empty (irregularity I-12). Only the
  per-fold version is measurable.
* **Expected DTI gain:** Unknown / probably low. **Cost:** Medium (~22 s).

### R7 ranking (before measurement)

| rank | hypothesis | expected DTI gain | cost | blind spot | novelty vs this repo |
|---|---|---|---|---|---|
| 1 | **R7-1** cross-gradient edge | Medium | Low | buried, no scarp | complete (two-field directional coincidence) |
| 2 | **R7-4** edge consensus N-of-5 | Medium | Low | any, precision-weighted | complete (N-of-M joint detection) |
| 3 | **R7-3** seismicity gate | Low-Medium | Low | active but scarp-less | complete (positive seismicity gate) |
| 4 | **R7-2** basement curvature hinge | Medium | Low | flexure/hinge | partial (new derivative order on a used layer) |
| 5 | **R7-5** structural grain | Unknown, probably low | Medium | parallel strands, systems | complete (system-level property) |

Local proxy-holdout results qualify this research ranking but do not predict
hidden-test performance; see `reports/holdout_v3.json` and
`reports/holdout_verdict_v3.json`.

---

## R7 empirical verdict (historical local DTI comparison; revised)

`reports/holdout_v3.json` contains a five-rule first-stage screen (random, short,
isolated, strike-class, and dense) plus later rows for configurations shortlisted by
the older chance/lift procedure. Those later rows are excluded from the revised
summary because their shortlist was not selected by direct DTI. The table below is
therefore a **five-fold screening result only**, not a ten-fold confirmation.
Catalogue-derived `HD_strain`/`R7_grain` features were rebuilt from visible geometry.
The low-slope slice is a stress test, not a hidden-test analogue. The older candidate
chance/lift values used the full valid-grid size instead of each fold's smaller eligible
`eval_mask`; they are withdrawn. The revised summary in
`reports/holdout_verdict_v3.json` ranks only direct DTI. A fresh DTI-selected
confirmation was not rerun because the ignored source rasters are not staged in this
checkout; no current R7 confirmation claim is made.

The historical screen's approximate local chance check used 30 same-run random
controls (median relative error 1.8%, p90 7.3%). This is an in-sample sanity check,
not a universal calibration, private-test baseline, or submission gate. In addition,
the local scorer conservatively clips predictions to each fold's eval mask; whether
predictions on masked known pixels can still supply TP to nearby new truth is
unresolved (Q-1).

| family | best configuration in this historical run | mean DTI | worst-rule mean DTI |
|---|---|---:|---:|
| `BASE_topo_ridge` | cov0.03 / sp3 | 0.07452 | 0.04976 |
| `BASE_tmi_hg` | cov0.03 / sp3 | 0.06904 | 0.04448 |
| `HB_tdr_rtp` | cov0.03 / sp3 | 0.06034 | 0.04128 |
| `R6_transt` | cov0.08 / sp3 | 0.06958 | 0.03269 |
| `R7_crossgrad` | cov0.05 / sp3 | 0.06623 | 0.03305 |
| `R7_seis_cross` | cov0.05 / sp3 | 0.05142 | 0.03294 |
| `R7_seis_grav` | cov0.05 / sp3 | 0.04937 | 0.03093 |
| `R7_consensus4` | cov0.03 / sp3 | 0.02809 | 0.01621 |
| `R7_consensus3` | cov0.03 / sp3 | 0.02645 | 0.01618 |
| `R7_hinge_curv` | cov0.08 / sp3 | 0.02871 | 0.00686 |
| `R7_grain` | cov0.08 / sp3 | 0.02548 | 0.00000 |

This five-fold screen ranks by local worst-rule mean DTI, not chance lift. It shows
that no R7 family beats the topo baseline on this historical protocol. Results remain
local catalogue-recovery measurements; the newer 18-fold R8 comparison is reported
separately. No private-test conclusion follows.

## H-S supervised baseline check (historical local DTI; 2026-09-29)

H-S is a logistic-regression model on 57 features (19 supplied bands × value,
3×3 mean, and 9×9 mean), trained separately on each fold's visible catalogue.
The historical run excludes the 5-pixel withheld halo from training context. Its
stored chance/lift fields used the full valid-grid area rather than each fold's
eligible `eval_mask`; those chance comparisons are withdrawn. Raw per-row DTI,
precision, and recall remain local measurements.

At the historical cov0.08/sp3 setting across five folds, H-S mean DTI was **0.04669**
(worst-rule mean **0.03267**); `BASE_topo_ridge` on the same folds and setting scored
**0.09946** (worst-rule mean **0.08216**). This supports only the local statement
that this version of H-S underperformed that local topo configuration.

The highest-magnitude coefficients in the `random_0` fit were associated with
`det_elev` context, strain, gravity, and RTP. These are fitted weights from one
training split, not independent evidence that those bands encode fault structure.
The measured tendency of H-S predictions to cluster near visible catalogue
geometry is a useful false-positive diagnostic, but does not reveal private-test
scores or establish why it underperformed. Any later supervised approach requires
its own visible-only training, leakage checks, and multi-rule confirmation DTI.

---

## R8 — five exploratory detector hypotheses motivated by geothermal literature (2026-09-30)

**Research motivation, not a claim about the test distribution.** Some geothermal
systems in the cited Great Basin literature are associated with fault steps,
intersections, accommodation zones, and fractured conduits. That does not establish
that the competition's uncaptured faults or undisclosed final labels are concentrated
there, nor that a line-intersection raster identifies vents or permeability. The
organizers have not disclosed the test-source mix. R8's terrain, hydrology, gravity,
and magnetic transforms are hypotheses to test against local holdout evidence.

* Faulds et al. 2013 structural inventory
  ([dataset 1148722](https://www.osti.gov/dataexplorer/biblio/dataset/1148722)):
  *\"Many geothermal systems occupy discrete steps in fault zones or lie in
  zones of intersecting, overlapping, and/or intermeshing faults\"*;
  *\"Geothermal systems are rare along major range-front faults, possibly due
  to both reduced permeability in thick zones of clay gouge\"*;
  *\"Step-overs, terminations, intersections, and accommodation zones
  correspond to long-term, critically stressed areas, where fluid pathways
  would more likely remain open in networks of closely-spaced,
  breccia-dominated fractures.\"*
* BRIDGE final report SAND2025-01826
  ([PDF](https://gdr.openei.org/files/1682/BRIDGE_Final_Report_SAND2025-01826.pdf)):
  *\"Overlapping, oppositely dipping normal fault systems generate multiple
  fault intersections in the upper part of the reservoir\"* which provide
  *\"convenient channel ways for geothermal fluids\"* and *\"highly fractured
  subvertical conduits that accommodate ascent of the hydrothermal fluids.\"*
* INGENIOUS hydrothermal reV work (Trainor-Guitton et al. 2025,
  [purl/3018341](https://www.osti.gov/pages/servlets/purl/3018341)): hidden
  hydrothermal estimates **must** include proxies for permeability and fluids,
  not temperature/heat flow alone; the 48 INGENIOUS features used are
  explicitly permeability proxies (earthquake rates, shear/dilatation,
  conductivity). Hidden systems are defined as those *\"where the permeability
  and fluids are not apparent at the surface\"*.

H-A..H-E / R6 / R7 largely propose line-like evidence; R8 adds point-density,
hydrology, and terrain transforms. Literature motivates these as possible
permeability or concealed-structure proxies, but it does not establish that a
particular signal identifies a fault or vent in this survey. R8 uses the supplied
feature bands and can be tested on local catalogue holdouts; that test remains a
proxy and does not validate performance on undisclosed new-fault labels.

### R8-1a · Topographic openness / sky-view factor for subtle scarps

* **Layers:** `det_elev` (12, detrended elevation).
* **Transform:** for each of 8 azimuths, maximum horizon inclination
  `atan((elev_neighbor - elev_center)/distance)` within 5 px (500 m); positive
  openness = `90° - mean(max_slope)`; edge is Hessian ridge + NMS of
  `|∇ openness|`. Implementation: `gems.detectors.topographic_openness`.
* **Physical signature (hypothesis):** horizon-angle variations may highlight
  some landform edges independently of hillshade illumination. The supplied
  elevation grid is 100 m; it cannot establish decimetre-scale scarp resolution,
  and ridges, drainage, erosion, or interpolation may create similar edges.
* **Why it might find a missing fault:** subtle intrabasin relief can be hard to
  distinguish from playa texture. An illumination-invariant horizon transform
  may complement slope-based screening, but performance depends on data
  resolution, noise, and geomorphic setting; it is not guaranteed to recover
  buried or sub-resolution faults.
* **How it differs:** BASE_topo_ridge uses Hessian ridge on `det_elev_slope`;
  R6_shore uses Laplacian curvature gated to flat with shoreline continuity.
  Openness uses horizon angle, not derivative.
* **Expected DTI impact:** unknown; rank is qualitative, not a score forecast.
  **Cost:** Low (~20 s). In the older five-fold raw-DTI comparison at cov0.05/sp3,
  openness mean DTI was 0.07807 versus 0.07844 for topo. Those are small local
  catalogue-recovery measurements, not hidden-test results. The old lift-over-chance
  values are withdrawn because that report used a mismatched chance domain.

### R8-1b · Multi-scale Topographic Position Index (TPI) for intrabasin scarps

* **Layers:** `det_elev` (12).
* **Transform:** TPI = elev - mean(elev in window) at radii 3, 6, 12 px
  (300 m / 600 m / 1.2 km); gradient magnitude of TPI → ridge → NMS;
  stack across scales. Implementation: `gems.detectors.tpi_multiscale`.
* **Physical signature (hypothesis):** local elevation residuals may emphasize
  some ridges or breaks at more than one window scale; their association with
  faults is not unique and no sub-pixel relief is resolved by the 100 m grid.
* **Why it could help:** a residual transform might add terrain context to
  slope/horizon edges, but it remains topographic and could recover the same
  non-fault landforms or known catalogue geometry.
* **How it differs:** openness uses horizon geometry; TPI uses elevation minus
  neighbourhood mean — different geomorphic operator; BASE uses curvature of
  slope.
* **Expected DTI impact:** unknown. **Cost:** Low (~12 s). In the older five-fold
  raw-DTI comparison at cov0.05/sp3, mean DTI was 0.06922 (topo 0.07844). This is a
  local result, not a calibrated chance comparison or private-test estimate.

### R8-2 · Fault-controlled drainage deflection (hydrologic lineament)

* **Layers:** `det_elev` (12) + `det_elev_slope` (19).
* **Transform:** D8 steepest-descent flow direction on filled `det_elev`,
  flow accumulation by processing cells in descending elevation order, then
  `log(1+accumulation)` → `|∇ log_acc|` → ridge + NMS → flat-ground gate
  (45th pct) → directional coherence 12 px. Falls back to a wetness proxy
  `log(1+10/(slope+0.5))` if numba unavailable.
  Implementation: `gems.detectors.flow_accumulation_anomaly`.
* **Physical signature (hypothesis):** drainage deflection or accumulation
  anomalies may mark a structure that changes near-surface flow. Lithology,
  climate, DEM artefacts, and anthropogenic drainage can produce similar
  patterns; a lineament is not by itself evidence of a fault.
* **Why it might find a missing fault:** if a mapped or buried structure
  influences drainage, a hydrologic transform may add evidence distinct from
  topographic slope or potential-field gradients. The flat-ground gate is a
  modeling choice to test, not proof that the hidden targets occupy playas.
* **How it differs:** this is the first explicit hydrology transform in the
  repository's detector register.
* **Expected DTI impact:** unknown. **Cost:** Medium (~12 s with numba; fallback
  behavior should be checked). In the older five-fold raw-DTI comparison at
  cov0.05/sp3, mean DTI was 0.07319 (topo 0.07844); this does not show an overall
  gain. The old lift fields are withdrawn because their chance denominator did not
  use the fold-specific eligible area. The low-slope slice is a robustness test,
  not the undisclosed new-fault population.

### R8-3 · Isostatic coherence breakdown (buried fault-bounded basin)

* **Layers:** `iso_grav_anom` (13) + `det_elev` (12).
* **Transform:** windowed Pearson r between gravity and topography via
  Gaussian-weighted means (σ=6 px ≈600 m): `r = cov(g,t)/[σ(g)σ(t)]`;
  breakdown = `1 - |r|`; modulated by joint gradient strength; ridge-thin.
  Implementation: `gems.detectors.isostatic_coherence_breakdown`.
* **Physical signature (hypothesis):** local gravity/topography decorrelation
  could indicate a subsurface or lithologic mismatch beneath subdued relief.
  Density contrasts, regional compensation, processing, and scale differences
  can also produce decorrelation; it is not a fault-specific signature.
* **Why it could help:** a buried structural boundary may lack a clear surface
  scarp, so comparing fields may add a different clue. The data alone do not
  show that a missing fault is present or that the catalogue is blind to it.
* **How it differs:** H-C/R6-3/R7-2 detect gradient magnitude of depth_to_base
  or grav+mag; R7-1 needs *parallel* gradients; this needs *decorrelation* of
  amplitudes — orthogonal.
* **Expected DTI impact:** unknown. **Cost:** Low (~17 s). In the older five-fold
  raw-DTI comparison at cov0.05/sp3, mean DTI was 0.03143 (topo 0.07844). The
  current R8 union comparison also did not establish a positive ensemble contribution.

### R8-4 · Magnetic remanence divergence (RTP vs TMI/mag_anom mismatch)

* **Layers:** `rtp` (2) + `tmi` (14) + `mag_anom` (1).
* **Transform:** `| robust_norm(rtp) - robust_norm(tmi) |` and same vs
  `mag_anom`; max; gradient → ridge. Implementation:
  `gems.detectors.remanence_divergence`.
* **Physical signature (hypothesis):** disagreement among RTP, TMI, and
  magnetic-anomaly transforms may reflect remanence, processing, or scaling
  differences and could highlight lithologic contacts. Such a mismatch is not
  itself evidence of a fault or of remanence.
* **Why it could help:** some lithologic boundaries may coincide with uncaptured
  faults and may be weak in topography, but no retrieved layer establishes that
  a particular mismatch is fault-related or absent from the catalogue.
* **How it differs:** H-A worms and H-B TDR operate on one field; R7-1 needs
  *parallel* gradients; remanence needs *position mismatch*, i.e. anti-
  correlation between fields derived from the same measurement.
* **Expected DTI impact:** unknown. **Cost:** Low (~18 s). In the older five-fold
  raw-DTI comparison at cov0.05/sp3, mean DTI was 0.04408 (topo 0.07844); this
  detector did not outperform the local comparator in that screen.

### R8-5 · Fault-intersection density as geothermal permeability proxy

* **Layers:** secondary, operates on ridge maps e.g. `BASE_topo_ridge`,
  `HA_worms_rtp`, `R7_crossgrad`, `R8_isocoherence` (any set).
* **Transform:** threshold each ridge map at 85th pct → binary line → dilate
  1 px → pairwise intersections (AND) → kernel density via Gaussian blur
  σ=6 px (600 m permeability halo) → `robust_norm_nonzero` → multiply by
  faint ridge skeleton to keep linear context. Implementation:
  `gems.detectors.intersection_permeability`.
* **Physical signature (hypothesis):** some fault intersections, step-overs,
  and accommodation zones may provide connected fracture permeability, as
  discussed in the cited geothermal literature. Many mapped intersections may
  be sealed, inactive, or products of map geometry; an intersection is not a
  vent label.
* **Why it might help:** if a missing fault is part of a permeable, connected
  structure, a junction-density feature could prioritize a different geometry
  from single-line detectors. It does not itself predict a missing fault trace
  and may add substantial false-positive area.
* **How it differs:** the repository had no explicit pairwise ridge-intersection
  density layer before this transform; its novelty is a point-density proxy.
* **Expected DTI impact:** unknown. **Cost:** Low (~5 s). In the older five-fold
  raw-DTI comparison at cov0.05/sp3, mean DTI was 0.02709 (topo 0.07844). The
  current visible-only ensemble comparison did not show a positive contribution
  from the full R8 union; a vent-specific benefit is unverified.

### R8 individual-detector screen (historical five-fold local DTI, not chance lift)

The older `reports/holdout_r8_quick.json` records direct DTI, precision, and recall
for five catalogue holdout folds at cov0.05/sp3. The following are unweighted means
across those five folds; “minimum” is the lowest single-fold DTI, not a worst-rule
mean. They are not private-test estimates and are not the newer 18-fold confirmation
summary. The companion `reports/r8_validation.json` lift/chance calculations are
withdrawn: they used the full valid-grid area rather than each fold's eligible domain.

| detector | mean DTI | min single-fold DTI | mean weighted precision | mean weighted recall | mean predicted support (px) | local observation |
|---|---:|---:|---:|---:|---:|---|
| `BASE_topo_ridge` | 0.07844 | 0.03852 | 0.02052 | 0.28519 | 185,351 | reference for this older screen |
| R8-1a openness | 0.07807 | 0.03883 | 0.02029 | 0.29074 | 190,830 | near tie on these five folds |
| R8-1b TPI | 0.06922 | 0.04362 | 0.01859 | 0.23544 | 163,796 | below the local topo mean |
| R8-2 flow | 0.07319 | 0.03715 | 0.01896 | 0.27563 | 193,181 | below the local topo mean |
| R8-3 isocoherence | 0.03143 | 0.02564 | 0.01240 | 0.05470 | 56,577 | low support and DTI in this screen |
| R8-4 remanence | 0.04408 | 0.02589 | 0.01936 | 0.06990 | 44,525 | low recall in this screen |
| R8-5 intersections | 0.02709 | 0.01376 | 0.01339 | 0.03893 | 36,384 | low DTI in this screen |

These are detector-level historical measurements only. They do not show that the
features identify hidden faults or geothermal vents, and do not validate the R8 union.

### R8 ensemble: visible-only, whole-system and segment proxy evaluation

A new, targeted comparison is recorded in
`reports/holdout_candidate_r8_2026-09-30.json`. It evaluates the R8 recipe by
rebuilding its catalogue-derived tip rays and horsetail features from each fold's
**visible catalogue only**; the archived full-catalogue TIFF is not scored
because that would leak withheld geometry. The test has 15 whole-system folds
(three replicates across random, short, isolated, strike-class, and dense rules)
plus three raw 8-connected raster-segment folds. Each targets about 25% hidden
catalogue mass, uses a 5-pixel (500 m) feature buffer, applies the exact
visible-fault mask, and computes DTI on withheld truth only. The low-slope slice
is reported as a stress test.

On the held-back confirmation folds, `BASE_topo_ridge|cov0.05|sp3` had
worst-rule mean DTI **0.08687** and mean DTI **0.09763** (mean weighted
precision 0.0276; recall 0.2874; effective support about 3.62% of the fold
evaluation domain). The R8 current union had worst-rule mean DTI **0.05584**
and mean DTI **0.06615** (precision 0.0161; recall 0.3292; support about
7.16%). The R8 recipe therefore traded more recall and substantially more
support for lower precision, and it did **not** beat this local baseline.

None of the predeclared R8 variants tested—reduced or increased component
coverage, spacing 1/2/3, dropping catalogue geometry or topography, two-vote
fusion, or one-pixel widening—beat the baseline on the confirmation summary.
Widening increased support but reduced DTI; the vote rule retained more
precision than the union but lost too much recall. These are local catalogue
holdout results, not estimates of the private test or final label set. **No R8
artifact is cleared for a submission slot.**

### What still needs external data (named, checked, not proposed as viable today)

* **Paleo-hydrothermal sinter/tufa alignment** — line through chains of
  former hydrothermal deposits (Paleo Geothermal Features.zip, GDR 1391,
  CC-BY-4.0, 82 kB) — vent ground truth proxy. Source verified but download
  blocked by sandbox egress (L-2). Not viable until fetched on open egress.
* **2 m temperature-probe anomaly lineaments** (2 m Temperature Probes.zip,
  1.03 MB, same GDR) — shallow thermal anomalies on permeable fault conduits.
* **Age/slip-rate-stratified holdout** — Quaternary Faults v2.zip (5.85 MB,
  GDR 1391, carries ages and slip rates) — needed to replace the strike-class
  proxy now used. Same status.

---

## Fresh external-data candidate screen (2026-09-30)

A separate, ranked screen of four narrowly novel data/transform combinations is
recorded in [`knowledge/05_hypothesis_screen_2026-09-30.md`](05_hypothesis_screen_2026-09-30.md).
It compares each proposal against the reviewed repositories 13–17, records official
source links and the extent of availability checks, and separates research priority
from viability. **None is currently approved as viable or evaluated on the prescribed
holdout.** No new submission is authorized by that screen.

### Scope correction for historical chance ratios

Chance/lift ratios in several historical hide-and-recover reports used the full
valid-grid area even though candidate predictions were restricted to a smaller
fold-specific `eval_mask`. Those candidate ratios and conclusions based on them are
withdrawn; they are not salvaged merely because withheld truth was known. The revised
summaries rank by direct local DTI. The optional corrected random-control comparison
uses each fold's eligible-domain size and known truth, but is an approximate same-run
sanity check that does not encode the exact spatial arrangement of the mask; it is not
a candidate-ranking metric, submission gate, or public/private baseline. The separate
public chance calculation that inferred hidden `|G|` from leaderboard scores is also
withdrawn; see [I-9 in `knowledge/02_irregularities.md`](02_irregularities.md).

---

## R11 shortlist — generated 2026-09-30 (session 4), constrained by what R10 measured

Ranked by expected ΔDTI × implementation cost. Every candidate below is filtered
through the lesson recorded as irregularity **I-13**: under a distance-weighted F2
(β = 2) with a 300 m kernel, only a block whose pixels land within 300 m of faults
the current recipe **never touches** can raise DTI, and its marginal weighted
precision must exceed `0.2 × DTI` (measured bar: 0.0169 tune / 0.0195
confirmation). Re-ranking or tightening neighbourhoods the topographic crest
already hits is now a measured dead end (24 configurations, R8–R10b).

| # | Candidate | Layers | Physical signature / transform | Why it can reach untouched faults | Difference from existing work | Cost |
|---|---|---|---|---|---|---|
| 1 | **R11-4 greedy marginal-precision assembly** | cached crest + curvature + `hs_lineament` + external `slope_std`, `rad_uk` | rank blocks by measured marginal precision on **tune** folds; add a block only while `ΔTP_w/(ΔTP_w+ΔFP_w) > 0.2 × DTI`, stop at the first block that fails | it cannot add a losing block by construction; it converts the audited inclusion rule from a post-hoc diagnosis into the assembly procedure | R8/R9/R10 guessed coverages and unions *then* measured them; nothing in the repo has used the rule as the stopping criterion. Caveat: greedy order-dependence, so the tune-fold path must be reported in full | **Low** (no new data, all maps cached) |
| 2 | **R11-2 basin-floor magnetic-continuity lineaments** | provided bands 2 `rtp`, 4 `tmi_hg`, 5 `tmi_vg`, 15 `depth_to_base_surf`; gate = lowest slope tercile **and** deepest conductive base | oriented persistence of short-wavelength magnetic gradient *along strike*, not gradient magnitude; emit only where the crest detector is silent | range-front faults under alluvium juxtapose magnetically contrasting units; the crest family has ~zero coverage there, so any hit is a **new** 300 m neighbourhood | `BASE_tmi_hg` is magnitude-only and domain-wide; R7 cross-gradient is a product gate. This is strike-continuity restricted to the disjoint basin-floor region | **Low** (provided bands only) |
| 3 | **R11-1 basement-depth juxtaposition edges** | provided band 15 `depth_to_base_surf`, bands 11/18 isostatic gravity derivatives; optional official depth-to-basement grids (DOI 10.5066/P9Z6SA1Z) | lateral *offset* (step) in basement depth along a linear feature, i.e. fault juxtaposition, rather than the gradient magnitude already tried | buried, basin-fill-bounded faults have no topographic expression at all — the single largest un-sampled region of the footprint | `R6_condbase` used a product of gradients; `R8_isocoherence` used windowed decorrelation. Neither tests for a *step in basement depth* nor restricts to the basin floor | **Medium** — provided-band version first; the official grids are 12 GB and their obtainability must be verified before any code is written |
| 4 | **R11-3 paleo-geothermal feature halos** | INGENIOUS GDR 1391 (CC-BY-4.0) paleo-geothermal features: sinter/tufa deposits, hot springs | sparse 300–900 m halos around each *mapped* feature, scored as a small additive block | a sinter deposit is direct field evidence of a long-lived, fault-controlled upflow conduit; the block is tiny, so its marginal precision can clear the bar where a 2 % field cannot | `R8_intersections` used ridge intersections as a vent *proxy*; this uses mapped geothermal features as ground evidence, an independent data source | **Medium** — egress to `gdr.openei.org` is blocked from this sandbox; per the standing brief the source must be verified obtainable (mirror or manual download) before implementation |

Screened out and not to be retried: QFFDB-minus-catalogue difference (1 px),
LiDAR coherence (AUC 0.4608), any further union of the R10 maps at 0.5–2 %
coverage (marginal precision 0.0094–0.0166, measured twice), and any fixed-budget
rank fusion of the R10 maps (measured: precision-for-recall wash).
