# Candidate hypotheses — targeting the blind spots of a scarp-derived catalogue

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

**The strategic error in the prior work is now measurable.** Our eight
leaderboard-scored submissions are dominated by topographic ridge detection and
catalogue-derived priors — i.e. by re-detecting exactly the signature the
catalogue already encodes. The most catalogue-hugging submission scored
**0.0286**, the worst of the eight (`reports/scored_forensics.json`). Better
scarp detection finds more of what is *already mapped*.

Each hypothesis below attacks a specific blind spot. **None requires external
data** — all five run on the 19 official bands. That is deliberate: it keeps
them validatable today.

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

Empirical holdout results supersede this ranking — see
`reports/holdout_results.json` and the [Hypotheses page](https://buffedlizard55-lab.github.io/13GEMSDOE/hypotheses.html).

---

## R6 — Five new hypotheses targeting remaining blind spots (2026-09-29)

All five are implemented in `src/gems/detectors.py` and cached in `data/derived/` as `R6_*.npy`. They were designed after the audit showing best honest lift only 1.055× worst-rule and after the composite_validation showing tip-extension rays at 16× chance vs isolated at 0.96×.

### R6-1 · Horsetail splay / relay-ramp structural completion
- **Layers:** `existing_faults` geometry only (catalogue-derived, rebuilt per fold).
- **Signature:** Detects en-echelon step-overs within 20 px (2 km) where two subparallel (<30°) segments' tips are close; draws bridging line + emits fan of 5 rays ±35° at each tip (horsetail).
- **Why missing:** Catalogue omits small linking faults at relay ramps, horsetails and intersections because they are short, discontinuous, or lack Quaternary scarp. Organizers explicitly include extensions, splays, parallel strands and corrections as new-fault pixels (forum 11516, 11536).
- **Differs from prior repo:** `extension_rays` projects forward along same strike; this detects NEARBY faults and bridges the gap, plus emits diverging fan.
- **Expected DTI gain:** High (relay ramps are prime geothermal: high fracture density). **Cost:** Low.
- **Holdout result:** Near-zero on system-withholding holdout because systems are grouped with 16 px link distance — pessimistic for tip extensions. On tip-extension holdout, extension_rays alone is 16× chance; horsetail should add orthogonal splay.

### R6-2 · Paleo-shoreline / lacustrine terrace scarp (intrabasin)
- **Layers:** `det_elev` (12), `det_elev_slope` (19).
- **Signature:** Second-derivative curvature ridge (Laplacian) on detrended elev, gated to low-slope (<45th percentile) AND low local variance (playa/lake bed), then directional coherence 12 px for shoreline continuity.
- **Why missing:** USGS QFaults focuses on range-front scarps; intrabasin scarps in Lake Lahontan lake beds are low-amplitude (decimetres) and invisible without detrending. They still cut Quaternary deposits, so they are Quaternary faults missing from catalogue. Classic hidden geothermal: intrabasin faults host springs.
- **Differs:** BASE_topo_ridge finds all ridges; this inverts mask to flat ground, uses curvature not slope, requires lateral continuity of shoreline.
- **Expected DTI gain:** Medium. **Cost:** Medium (needs variance + curvature).

### R6-3 · Conductive-base step with conductivity coherence (improved HC)
- **Layers:** `depth_to_base_surf` (15), `cond_surf` (17), `det_elev_slope` (19).
- **Signature:** Product of gradient magnitudes of depth_to_base and cond_surf, ridge-thinned, gated by flat topography (55%) AND anti-topo (1 - topo_ridge strength), then oriented-filtered 15 px.
- **Why missing:** Buried fault offsets conductive basement and juxtaposes different lithologies → conductivity contrast, but no surface scarp. Needs both depth and conductivity to agree.
- **Differs from HC_hinge:** HC used only depth_to_base gradient; this requires BOTH depth and conductivity, plus directional coherence, plus anti-topo gate.
- **Expected DTI gain:** Medium. **Cost:** Low.

### R6-4 · Gravity-gradient termination / intersection
- **Layers:** `iso_grav_anom_hg` (18), `iso_grav_anom_vg` (11), `iso_grav_anom` (13).
- **Signature:** Detect terminations of horizontal gravity gradient ridges (ridge pixel with only 1 neighbor), emit short continuation 12 px beyond termination outward. Intersections (high orientation variance) emit crossing splay.
- **Why missing:** INGENIOUS authors stated gravity-gradient terminations defined fault tips and crossings in their basin analysis (GDR 1391 report). Those are places where geophysical evidence says structure continues but surface mapping stopped.
- **Differs:** Uses geophysical ridge termination, not catalogue fault tip.
- **Expected DTI gain:** Low-Medium. **Cost:** Low but slow (generic_filter std).

### R6-5 · Transtensional coupling / dilational jog
- **Layers:** `geod_shearrate` (7), `geod_dilaterate` (8), `geod_2ndinv` (4), `iso_grav_anom_hg` (18).
- **Signature:** Normalized shear * positive dilatation * second invariant, multiplied by gravity gradient ridge to localize to sharp trace, then oriented lineaments.
- **Why missing:** Transtensional jogs are prime geothermal targets (high permeability) but may have subtle or no scarp because extension is distributed. Strain fields are smooth (no pixel trace) so need sharp multiplier.
- **Differs from HD_strain:** HD used deficit (strain minus faults minus eq); this uses product of shear and dilatation (coupling) as positive evidence.
- **Expected DTI gain:** Low on random, High on isolated/dense (measured 0.0658 on isolated_0 at 2% vs topo 0.0722). **Cost:** Medium.

### R6 Ranking (preliminary, before full holdout sweep)

| rank | hypothesis | expected DTI gain | cost | blind spot | holdout note |
|---|---|---|---|---|---|
| 1 | **R6-1** horsetail splay | High | Low | relay ramp / horsetail | pessimistic on system holdout, should shine on tip-extension |
| 2 | **R6-3** conductive-base step | Medium | Low | buried, no scarp | improves HC |
| 3 | **R6-2** paleo-shoreline scarp | Medium | Medium | intrabasin low scarp | targets Lahontan |
| 4 | **R6-4** gravity termination | Low-Medium | Low | termination | second best on random (0.0426) |
| 5 | **R6-5** transtensional coupling | Low on random, High on isolated | Medium | dilational jog | 0.0658 isolated, close to topo |

Empirical: On random_0 2% coverage, topo 0.0599, gravterm 0.0426, tdr 0.0434, shore 0.0237, condbase 0.0112, transt 0.0083, worms 0.0196. On isolated_0 2%, topo 0.0722, transt 0.0658, tdr 0.0592, grav 0.0404, worms 0.0384. So transt is competitive on isolated/dense.

Final unique strategy to beat 0.3049-0.3168: **R6 ensemble hedge** — tip-rays 20 px + horse splay + topo 3% + gravterm 1% + transt 1% + tdr 1% + shore 0.5% + cond 0.5%, all decimated 1-per-3px, binary, catalogue included. This is more inclusive (6.65% coverage, 344k px) than prior best, with high-precision tip extensions (37% precision) covering organizer-named extensions/splays/corrections, plus anti-topo buried detectors for hidden geothermal. Validated on hide-and-recover: topo alone 1.055× worst-rule, ensemble improves worst-rule isolated/dense to 1.06-1.13× (measured). Full validation requires run_holdout.py with R6 detectors (now wired).

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

Empirical holdout results supersede this ranking — see
`reports/holdout_v3.json` and `reports/holdout_verdict_v3.json`.

---

## R7 empirical verdict (measured 2026-09-29, `reports/holdout_v3.json`)

Protocol: whole fault systems withheld with a 500 m buffer, 10 folds across 5
withholding rules (random / short / isolated / strike-class / dense), visible
catalogue masked pixel-exactly, DTI scored on the withheld pixels only, against
the **closed-form chance DTI at the actual predicted-pixel count** and 30
coverage-matched random controls (median relative error 1.1 %). Catalogue-derived
detectors (`HD_strain`, `R7_grain`) were rebuilt per fold from the VISIBLE
catalogue only, so no withheld geometry is used to build the detector. Runtime
4,911 s.

`lift` = candidate DTI / chance DTI at the same pixel count on the same fold.
`worst` = the worst of the five withholding rules, which is the number the
shipping rule uses.

| rank | family | best config | mean lift | **worst-rule lift** | concealed lift | verdict |
|---|---|---|---|---|---|---|
| 1 | `BASE_topo_ridge` | cov0.05 / sp3 | 1.09 | **1.06** | 0.51 | still the best honest detector in the repo |
| 2 | `R7_seis_cross` | cov0.005 / sp3 | 1.20 | 0.97 | 0.45 | best mean lift, but below chance on the worst rule |
| 3 | `BASE_tmi_hg` | cov0.05 / sp3 | 1.02 | 0.98 | 0.95 | unchanged |
| 4 | `R7_crossgrad` | cov0.08 / sp3 | 0.96 | 0.93 | 0.94 | **R7-1 does not beat its own inputs** |
| 5 | `R6_gravterm` | cov0.005 / sp3 | 1.00 | 0.90 | 1.31 | best concealed lift of any non-prior (1.31) |
| 6 | `R7_seis_grav` | cov0.01 / sp3 | 1.12 | 0.86 | 0.64 | below chance |
| 7 | `HB_theta_rtp` / `HB_tdr_rtp` | cov0.01 / 0.08 | 0.89 / 0.94 | 0.80 / 0.80 | 0.76 / 0.64 | below chance |
| 8 | `R6_transt` | cov0.08 / sp3 | 1.26 | 0.60 | 0.53 | huge variance: 4.42x on `strike_60_120`, 0.46x on `random_0` |
| 9 | `R7_consensus4` / `R7_consensus3` | cov0.03 / sp3 | 0.82 / 0.77 | 0.45 / 0.44 | 0.76 / 0.74 | consensus of mediocre detectors is worse than the best member |
| 10 | `HD_strain` | cov0.08 / sp3 | 0.74 | 0.19 | 0.61 | below chance |
| 11 | `R7_hinge_curv` | cov0.08 / sp3 | 0.47 | 0.20 | 1.20 | dead |
| 12 | `R7_grain` | cov0.005 / sp1 | 0.15 | 0.00 | 0.05 | dead (see I-12) |

**Conclusions, stated plainly.**

1. **No R7 hypothesis beats the analytic baselines that already existed.** The
   pre-measurement ranking put R7-1 (cross-gradient edge) first; it measures
   0.93-0.96 worst-rule lift, i.e. it does not even reach chance. R7-4
   (consensus) and R7-5 (structural grain) are worse still.
2. **`BASE_topo_ridge` remains the single best honest detector** at 1.06
   worst-rule lift, and it is the same detector that led every prior run. Nothing
   measured in this session displaces it.
3. **The honest ceiling is low.** The best honest candidate is 1.06x chance on
   the worst rule. Every prior submission that scores above 0.15 on the public
   column does so by leaking the catalogue itself (see the `PRIOR_*` rows:
   2.56x-5.04x, all excluded). The measured gap between "what the data supports"
   and "what the leaderboard rewards" is the central finding of this project.
4. **`R6_transt` is the only detector with a genuinely large fold-specific
   signal** (4.42x on the strike-class fold with 5,735 withheld pixels). That
   fold is the smallest of the ten, so the number is the least statistically
   reliable in the table; it is reported, not shipped.
5. **Stage 2** re-scored the ten best stage-1 `R6_transt` configurations on all
   ten folds: mean lift 1.30, min 0.07, max 4.42. The mean is above chance, the
   spread is not.

## H-S empirical verdict (measured 2026-09-29, `reports/holdout_supervised.json`)

H-S is the first **supervised** detector in this repository: L2-regularised
logistic regression on 57 features (19 official bands x {value, 3x3 mean, 9x9
mean}), trained per fold on the VISIBLE catalogue only, with a 5-px dilation of
the withheld halo excluded from the training set so no withheld geometry can
leak through a 9x9 context mean. 40 epochs of Adam, 400,000 subsampled
negatives, inverse-frequency positive weighting.

| family | best config per fold | mean lift range over folds | verdict |
|---|---|---|---|
| `HS_supervised` | cov0.08 / sp3 on every fold | **0.21 - 0.75** | **below chance on every fold** |
| `BASE_topo_ridge` (same run, same folds) | cov0.05-0.08 / sp3 | 1.06 - 1.17 | reference |

**Top learned feature weights (fold `random_0`)** — physically sensible:

| rank | feature | weight |
|---|---|---|
| 1 | `det_elev` 9x9 mean | +1.1735 |
| 2 | `det_elev` value | -0.8712 |
| 3 | `det_elev` 3x3 mean | -0.6117 |
| 4 | `geod_shearrate` 3x3 mean | +0.4462 |
| 5 | `geod_2ndinv` 9x9 mean | -0.4148 |
| 6 | `geod_shearrate` 9x9 mean | +0.4095 |
| 7 | `geod_shearrate` value | +0.3906 |
| 8 | `geod_2ndinv` value | -0.3678 |
| 9 | `iso_grav_anom_vg` 9x9 mean | +0.3583 |
| 10 | `rtp` 9x9 mean | +0.3413 |

Detrended elevation dominates, then geodetic strain, then gravity and
radiometrics. The model is learning real structure.

**Why it nevertheless fails the holdout — measured, not guessed.** Of H-S's
predicted pixels, **12.4 % lie within 300 m of the VISIBLE catalogue**, against
**5.9-6.5 %** for every analytic detector measured in the same run; and only
**37.0 %** of H-S's pixels are more than 3 km from the visible catalogue, against
**52.3-54.1 %** for the analytic detectors. The organizers confirmed, verbatim,
that "the buffer does not apply to known faults" and that "a predicted pixel that
is near a known fault trace but far from a new-fault ground truth pixel will be
fully penalized" (forum 11516 post 4). H-S puts twice as much of its mass in
exactly the region that carries full FP_w penalty and no possible credit.

**Generalisation.** A supervised model trained on a 1.18 %-positive catalogue on
a 3 GB box reproduces the catalogue's own neighbourhood, and the metric
deliberately refuses to reward that neighbourhood. This is not a tuning problem;
it is a mismatch between the training objective (reproduce the catalogue) and
the scoring objective (find faults the catalogue does not already contain). Any
supervised approach here must be trained on a target that excludes the mapped
neighbourhood — a hard-negative-mining or one-class formulation — not on the
catalogue raster directly.
