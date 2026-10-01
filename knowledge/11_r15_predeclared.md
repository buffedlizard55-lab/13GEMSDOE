# R15 — auditable predeclaration, 2026-10-01

**Recorded before implementing `gems.thermal`, geographic folds, or running R15.**
Scope: four not-yet-implemented observation/transform combinations in the inspected
13GEMSDOE source. This is NOT a claim of worldwide novelty. Concepts #1, #3 and #4
were previously proposed but not tested; #1 is now independently data-ready.
Never describe these as four newly discovered physical mechanisms.

## Values and decision

Maximize P(Win): prioritize independent information over another edge-map ensemble.
Own the Outcome: obtain data, measure, report failures, and keep the working download
available. No upload is automated. Format correctness, HTTP delivery, DrivenData
acceptance, and scientific submission clearance are FOUR separate assertions.

## Source-grounded ranking (DTI expectations are qualitative, not forecasts)

| Rank | Hypothesis / exact inputs | Physical transform / signature | Why off-catalogue? | Difference from implemented work | Expected DTI / cost / availability |
|---|---|---|---|---|---|
| 1 | Survey-corrected shallow-thermal corridors. GDR1391 `2m_temperature_probe_n83geo.shp`: NAD83 locations, `Area`, `T2m`, `F2mDAB`, `Date`; repeated `T2m_2…7`, `Date_2…7` for an uncertainty diagnostic only. | Source README defines DAB as temperature minus the area's background. Select DAB >= 3 degrees C, within-area groups of >= 3 warm probes within 1.5 km; weighted PCA axis ratio >= 4, perpendicular RMS <= 300 m. Draw only the measured span, no arbitrary regional halo/extrapolation. | Steam-heated/upflow corridors may be present beneath alluvium with weak relief. Heat is not displacement; outflow, seasonal solar effects and survey selection can fool this detector. | No implemented 13GEMSDOE detector reads these probe temperatures. Unlike paleo sinter/tufa halos, terrain flow, ridge crossings or static band6 radiometry, this uses measured, area-background-corrected shallow heat plus observed spatial alignment. H-G was a proposal, not an earlier measured experiment. | Small regional upside / high uncertainty; low CPU cost. **Data ready:** 3,800 source probes, 2,782 inside exact official footprint, 34 named areas; only 139 inside have >=2 dated valid measurements. Binary/archive hashes are in `reports/gdr1391_fetch.json`; source README inspected. |
| 2 | Displaced lithologic-marker matching. Provided RTP band2 + TMI14; verified USGS GeoDAWN K/Th/U (`radiometric_u8.tif`), with supplied detrended elevation12 as confounder control. | Across a prospective seam, correlate multichannel marker patches on opposite sides, test a consistent nonzero along-strike registration lag and local improvement over zero-lag match. Reject simple high-contrast contacts with no displacement consistency. | Offsets in rock-property patterns can reveal fault displacement even where an alluvial blanket obscures a scarp. Intrusive contacts, survey processing and repeating texture are confounders. | Existing worms/TDR/cross-gradient/consensus/R13 persistence detect edges, not a measured registration offset of matching markers. Needs a new registration estimator, not another weight on those maps. | Medium possible upside / low confidence; medium-high implementation cost. Input rasters fetched and hash-pinned by `fetch_external_data.py`. USGS DOI below; quantized derivatives must not be claimed as original native-resolution grids. NOT IMPLEMENTED. |
| 3 | Event-level focal-mechanism plane coherence. USGS ComCat hypocentres and moment-tensor/focal-mechanism products (strike, dip, rake, location/depth uncertainty). | Cluster independently reviewed event planes, account for BOTH nodal-plane alternatives and uncertainty, project supported shallow plane corridors; do not select a plane by withheld catalogue fit. | Active concealed faults may host coherent earthquake planes without a mapped surface trace; quiet faults are invisible to this method. | R7-3/R6 transtension use supplied smoothed density/strain; no source here reconstructs planes from individual events. Revives the unimplemented 2026-09-30 #1 proposal, rather than claiming it is newly conceived. | Medium possible / high variance; high acquisition/modelling cost. Official free endpoint discoverable; prior bbox counts are not footprint or usable-plane counts. Local event products NOT acquired; **not data-ready**, not yet viable for validation. |
| 4 | Groundwater-head response compartment boundaries. USGS Water Data field measurements, monitoring sites, well depth/aquifer, vertical datum and pumping metadata. | Harmonize units/datum/aquifer and acquisition time; test a persistent cross-boundary head offset and different time response, controlling for pumping and lithology. | Buried faults can impede/channel groundwater with no surface scarp. Hydraulic boundaries do not uniquely identify faults. | R8 surface drainage and proposed static chemistry/temperature features are not paired well-head time-response estimators. Revives an unimplemented proposal; avoids renaming it as new physics. | Low-to-medium possible / very sparse; high harmonization cost. Official free API exists; the previously observed single record does not establish a comparable network. **Not data-ready**; no viable-performance claim. |

### Official/manual verification links

- Competition target and format: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
- New pixels include extensions/splays: https://community.drivendata.org/t/where-do-you-draw-the-line/11536/2
- Pixel-exact known-fault masking: https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4
- INGENIOUS dataset: https://gdr.openei.org/submissions/1391 (DOI10.15121/1881483, CC-BY4)
- Exact thermal archive: https://gdr.openei.org/files/1391/2m_temperature_probe_INGENIOUS_regional_data.zip
- DOE thermal-measurement presentation (2010): https://www.energy.gov/sites/prod/files/2014/02/f7/validation_zehner_shallow_temperature.pdf
- DOE-funded final report (2014): https://gdr.openei.org/files/344/GTPMcGeeFinalReportEE0002830.pdf
- USGS GeoDAWN data: https://doi.org/10.5066/P93LGLVQ
- USGS ComCat and product API: https://earthquake.usgs.gov/data/comcat/ and https://earthquake.usgs.gov/fdsnws/event/1/
- USGS Water Data collection: https://api.waterdata.usgs.gov/ogcapi/v0/collections/field-measurements
- Structural inventory (426 systems examined; settings determined for >240): https://www.osti.gov/dataexplorer/biblio/dataset/1148722

The DOE presentation supports shallow surveys as a way to delineate some steam-heated
fault zones/outflow; it explicitly notes groundwater masking and poor applicability in
bedrock. It does NOT establish R15 performance or that every thermal anomaly is a fault.
The GDR README defines `F2mDAB`; zero DAB is a valid background value, not a missing-data
sentinel. Primary dates may be seasonal-correction dates, so do NOT treat all repeats as
independent untreated campaigns. No claim of seasonal causality is made.

## Frozen R15 experiment (before results)

- `thermal_corridors`: one binary 100 m raster from the threshold/PCA criteria above.
  PCA uses DAB-clipped weights in [3,30], observed stations in the same `Area` only.
  Neighbourhood distance 1,500 m, >=3 points, eigenvalue ratio >=4, perpendicular
  RMS <=300 m; endpoints are the extrema of measured projections. No known-fault
  geometry, labels, held-out scores, feature-based ranking or training is allowed
  to enter thermal field construction. Missing/out-of-range coordinates are excluded.
- Primary challenger `lattice_s5_plus_thermal`: union the thermal corridor with the
  unchanged stride5 reference. This directly tests incremental geological information,
  not a renamed coverage baseline. Standalone thermal is reported as a diagnostic.
  No sweeps or tuning on confirmation folds. Extra probability mass is charged in DTI.
- References: `lattice_s5` (CURRENT SHIPPED BEST), `lattice_s4`, `lattice_s6`, empty
  control, deterministic fault-blind 4% random support. Lattices rebuilt without
  hidden truth. Catalogue pixels are masked using the VISIBLE mask only per fold.
- Confirmation A: the existing system rules random/short/isolated/oriented/dense,
  three folds each, seed20260930 (corrected from20260928 after inspecting the existing R13 runner, BEFORE implementation/results), link8px, buffer5px, plus the three segment folds
  used by R13 lattice. Freshly rerun paired scores; don't compare numbers from
  different masks or use the submitted full-catalogue R11 raster as a leak-free reference.
- Confirmation B: four geographically blocked folds, 256px=25.6km tiles with
  2x2 checkerboard assignment. Entire held-out tiles' catalogue is hidden, visible
  labels outside tiles are removed within5px; evaluate tile interiors eroded3px
  (the metric radius) only. Geographic partitions are fixed without label-dependent
  selection. These are a new stress test, not the pre-existing R13 protocol.
- No model is fit: thermal construction is label-independent. These observations
  are public inputs; geoblocks hide labels, not public covariates. Report that boundary.
- Report per-fold TP/FP/FN, DTI, truth/evaluation pixel counts, exact-mask hashes,
  positive support/mass and paired deltas; deterministic source/code hashes.
- Gate: finite, in-range field; non-identical canonical footprint pixels; existing
  confirmation worst-rule DTI improvement >=0.002 AND >=14/18 paired wins against
  current lattice; geographic worst-rule improvement >=0.002 AND >=3/4 wins.
  All conditions must pass. Failure means **RESEARCH_ONLY_DO_NOT_SUBMIT**; the
  download primary stays unchanged. The threshold is a planning choice, not an
  organizer rule. No private-test/leaderboard gain is claimed either way.

## Outcome

Pending at predeclaration. Results go to `reports/holdout_r15_2026-10-01.json` and
`knowledge/12_r15_results.md`, never edited into this frozen specification.
