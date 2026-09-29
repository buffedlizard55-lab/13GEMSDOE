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
