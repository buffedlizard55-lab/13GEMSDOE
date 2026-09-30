# Fresh geological-hypothesis screen — 2026-09-30

## Decision and scope

Four directions are ranked below for **research priority**, not for submission.
The ranks are qualitative geological priors; no numeric DTI forecast is defensible
before a leak-safe holdout. **None is approved as viable yet**, because the required
external inputs have not been fully acquired, footprint-checked, and evaluated.
The #1 direction is therefore a data-acquisition priority only. No new detector,
holdout result, or submission is claimed in this screen.

A candidate counts as new here only in the narrow, auditable sense that the reviewed
13GEMSDOE work and the linked 14–17 research pages show no matching data/transform
combination. This is not a claim of worldwide scientific novelty. Team-repository
claims below are reported in those repositories and were not independently reproduced.

The competition target is any fault pixel not already captured by USGS/INGENIOUS,
including extensions, splays, parallel strands, and corrections
([organizer clarification](https://community.drivendata.org/t/where-do-you-draw-the-line/11536)).
Known catalogue pixels are masked pixel-exactly, nearby predictions are penalized
unless close to new-fault truth, and new-fault truth can itself be within 300 m of a
known trace ([organizer scoring clarification, post 4](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4)).
The organizers have not disclosed which sources or fault types produced the test
truth ([organizer reply](https://community.drivendata.org/t/how-were-the-new-test-faults-identified-data-sources-and-fault-types/11527/7)).

## Prior-art screen: repositories 13–17

The reviewed material already covers relay/termination/splay geometry; magnetic and
gravity edges; radiometrics; scarp and lidar morphology; drainage/flow; strain and
smoothed seismicity; surface conductivity and basement-depth structure; paleoshoreline;
transtensional coupling; and catalogue geometry. Examples are documented in the
[13GEMSDOE hypothesis register](03_hypotheses.md), [14GEMSDOE hypotheses and round
pages](https://buffedlizard55-lab.github.io/14GEMSDOE/docs/hypotheses.html),
[15GEMSDOE audits](https://buffedlizard55-lab.github.io/15GEMSDOE/docs/audits.html)
and [hypotheses](https://buffedlizard55-lab.github.io/15GEMSDOE/docs/hypotheses.html),
[16GEMSDOE register](https://buffedlizard55-lab.github.io/16GEMSDOE/docs/research/hypothesis_register.html),
and [17GEMSDOE findings](https://buffedlizard55-lab.github.io/17GEMSDOE/docs/findings.html)
and [hypotheses](https://buffedlizard55-lab.github.io/17GEMSDOE/docs/hypotheses.html).
These are team-authored sources, not independent reproductions.

The four proposals are distinguished from that prior art by the *specific new
observation* they require: event-level focal-mechanism planes (not smoothed seismic
density), a multi-date satellite thermal/moisture residual (not static radiometry),
well-head response across time/space (not static chemistry or surface drainage), or
coherence across separately depth-integrated MT products (not one surface-conductivity
or basement raster). Related concepts were tried; the listed observation/transform
is the novelty claim and must be checked against the linked registers before coding.

## Ranked candidates

### 1. Event-level focal-mechanism plane coherence — medium upside, low confidence

- **Inputs/layers:** USGS ComCat earthquake hypocentres plus event moment-tensor /
focal-mechanism products with nodal-plane strike, dip, rake, and uncertainty; optionally
use the provided magnetic/gravity edge rasters only as an independent comparison, not
as labels.
- **Physical signature:** spatially coherent hypocentre clusters whose reviewed nodal
planes share strike/dip and project toward a common shallow fault surface. Score a
thin corridor around the consensus surface trace, weighted down for depth, plane
ambiguity, and location uncertainty. Two nodal planes are generally possible; do not
choose the one that best matches the known catalogue during validation.
- **Why it could find uncatalogued faults:** active blind or buried structures can host
seismicity without a mapped surface scarp. Event geometry can also reveal an active
splay or extension not represented by a smoothed regional seismicity band. This will
miss quiet/inactive faults and may confuse unrelated events; seismicity is not proof of
a surface fault.
- **Difference from prior attempts:** this is not another positive gate on the supplied
`ieq_n100a15` / `deq_n100a15` smoothed event-density bands and is not the existing
R7-3 seismicity gate. The proposed feature uses event-by-event focal mechanisms and
plane geometry, which the reviewed 13–17 work did not identify as an implemented
feature. That precise absence is a repository-review finding, not a claim that no
external team has ever used it.
- **Expected DTI impact:** **medium possible / high variance**, principally for active,
scarpless faults; no numeric score prediction. Candidate rank reflects its independent
geometric information, not a measured gain.
- **Cost:** **medium-high** — fetch/filter products, resolve nodal-plane ambiguity,
account for magnitude-dependent completeness and location uncertainty, then rasterize
at a physically justified support width before tuning coverage and spacing.
- **Required official data and availability check:** USGS [ComCat](https://earthquake.usgs.gov/data/comcat/)
and its [FDSN event API](https://earthquake.usgs.gov/fdsnws/event/1/). A bbox count
query for the GeoDAWN bounding rectangle, 2000-01-01 through 2026-09-30, returned
17,178 M≥2 events and 478 M≥3 events with `producttype=moment-tensor`. These are
**bounding-box counts**, not exact intersections with the valid raster footprint, and
do not establish that all products contain usable nodal planes. The API/count query
was reachable through the web reader. Local Python requests to the same USGS host
closed TLS before returning data, so a local event table/feature raster has **not**
been obtained. Availability is partial; this is **not yet viable for validation**.
  - [M≥2 count query](https://earthquake.usgs.gov/fdsnws/event/1/count?starttime=2000-01-01&endtime=2026-09-30&minmagnitude=2&minlatitude=37.33119286569775&maxlatitude=40.72787799633184&minlongitude=-120.03717095080793&maxlongitude=-116.14092181157623)
  - [M≥3 moment-tensor count query](https://earthquake.usgs.gov/fdsnws/event/1/count?starttime=2000-01-01&endtime=2026-09-30&minmagnitude=3&producttype=moment-tensor&minlatitude=37.33119286569775&maxlatitude=40.72787799633184&minlongitude=-120.03717095080793&maxlongitude=-116.14092181157623)

### 2. Persistent Landsat thermal / moisture residual corridors — low-to-medium upside

- **Inputs/layers:** USGS Landsat Collection 2 Level-2 surface-temperature and surface-
reflectance products, their QA/cloud masks, and repeated cloud-screened seasonal
composites. Use sensor-specific thermal-band names; do not conflate Landsat 5/7 and
8/9 band schemas.
- **Physical signature:** recurring narrow surface-temperature or moisture/vegetation
residuals after controlling for acquisition date, elevation, illumination, land cover,
and cloud/shadow quality. A candidate fault corridor would need spatial continuity and
repeatability across independent dates/seasons; one hot or green pixel is not evidence.
- **Why it could find uncatalogued faults:** fault-controlled upflow, seepage, or
permeability may create surface thermal/moisture contrasts beneath alluvium without a
scarp. The proposed residual is a time-series signal, not a claim that thermal
anomalies uniquely identify faults; irrigation, lithology, shadow, and weather are
major confounders.
- **Difference from prior attempts:** prior work includes GeoDAWN radiometric layers,
static INGENIOUS geothermal/hydrochemical points, and R8 terrain/hydrology features.
This proposal requires multi-date satellite surface-temperature/reflectance assets and
seasonal residualization; it is not a new name for radiometric edge detection.
- **Expected DTI impact:** **low-to-medium**, with potential concentrated in covered
basins; high false-positive risk. No numeric score prediction.
- **Cost:** **high** — STAC scene filtering, atmospheric/QA checks, cloud masking,
seasonal compositing, topographic/land-cover controls, and reproducible reprojection.
- **Required official data and availability check:** USGS [Landsat Collection 2
Level-2 STAC](https://landsatlook.usgs.gov/stac-server/collections/landsat-c2l2-sr).
A January 2020 bbox search returned 875 items; the inspected Landsat 7 Level-2 item
reported 61% cloud cover. A bbox result count is not a cloud-free coverage count over
the exact valid raster polygon, and a single item is not a usable time series. Metadata
is discoverable, but the scene stack/usable coverage has not been built; **not yet
viable for holdout evaluation**.

### 3. Groundwater-head discontinuity / response compartments — low-to-medium upside

- **Inputs/layers:** USGS Water Data API groundwater-level field measurements
(parameter code `72019` where applicable), monitoring-location metadata, and verified
well construction/aquifer/datum fields. Only compare observations with compatible
units, aquifer intervals, datum, and measurement protocol.
- **Physical signature:** persistent head offsets or different temporal response on
opposite sides of a candidate corridor, after controlling for well depth, aquifer,
seasonality, pumping, and measurement datum. This tests whether a fault behaves as a
hydraulic barrier/conduit; it does not use raw head value as a line detector.
- **Why it could find uncatalogued faults:** a buried fault can compartmentalize or
channel groundwater under a basin even where there is no surface scarp. The signal is
not fault-specific: aquifer boundaries, pumping, and well construction can create the
same pattern.
- **Difference from prior attempts:** existing H3-style concepts use static well/spring
temperature or chemistry; R8 uses surface drainage/flow accumulation. No reviewed
13–17 attempt was identified that estimates a spatial groundwater-head discontinuity
from repeated well measurements across both sides of a candidate trace.
- **Expected DTI impact:** **low-to-medium**, probably sparse and geographically
uneven; no numeric score prediction.
- **Cost:** **high** — station census, datum/aquifer harmonization, time-series quality
control, spatial pairing, and strong protection against well-network sampling bias.
- **Required official data and availability check:** the [USGS Water Data API
field-measurements collection](https://api.waterdata.usgs.gov/ogcapi/v0/collections/field-measurements)
and [API migration documentation](https://api.waterdata.usgs.gov/docs/ogcapi/migration/).
A bbox query returned one groundwater-level record inside the extent: parameter
`72019`, 3.64 ft, dated 1976-05-05, with a *Local Assumed Datum*. This proves the
endpoint is populated in the broad area, not that it has a sufficiently dense or
comparable network. No station census or paired-well availability analysis has been
completed; **not yet viable**.

### 4. Cross-depth MT conductor-edge persistence — low upside, high scale risk

- **Inputs/layers:** the USGS ScienceBase Great Basin conductance products for the
2–12, 12–20, 20–50, 50–90, and 90–200 km depth-integrated intervals, registered to
the official 100 m prediction grid only after their native CRS, resolution, and
footprint are verified.
- **Physical signature:** a lateral conductance edge that recurs at a consistent
location across adjacent depth intervals, distinguished from a single-slice edge or
regional basin trend. The output should remain at the native information scale; a
100 m resampling must not be described as 100 m geological resolution.
- **Why it could find uncatalogued faults:** a deep, vertically extensive fluid or
lithologic boundary may persist below basin fill even when surface relief is weak.
Conductance is not fault-specific and regional conductors may dominate.
- **Difference from prior attempts:** reviewed work used `cond_surf`,
`depth_to_base_surf`, magnetic/gravity edges, and multi-band edge consensus. The new
part is depth-interval persistence across the five Great Basin MT products; it is a
narrow novelty gap, not a wholly new geophysical family.
- **Expected DTI impact:** **low**, with upside limited to broad structural corridors;
scale mismatch and false precision may overwhelm the signal. No numeric score prediction.
- **Cost:** **medium-high** — retrieve files, verify resolution/projection/coverage,
reproject correctly, and test persistence without leaking catalogue-derived features.
- **Required official data and availability check:** USGS [ScienceBase item
62979746d34ec53d276c113b](https://www.sciencebase.gov/catalog/item/62979746d34ec53d276c113b),
[DOI 10.5066/P9TWT2LU](https://doi.org/10.5066/P9TWT2LU). Official metadata lists the
five depth-integrated products. The binary grids, native resolution, and exact valid-
footprint coverage were not verified locally; prior sandbox download attempts failed
at transport. **Not yet viable** until the rasters and metadata are inspected.

## Validation gate for candidate #1

The proposed leader is not a submission candidate until its event data are staged.
If acquisition succeeds, build the focal-plane feature without using withheld-fault
geometry. Then compare it against the current best local holdout baseline under whole-
system and segment hide-and-recover folds, with spatial buffers; rebuild every
catalogue-derived feature from the visible catalogue only; apply the pixel-exact known-
fault mask; and score only withheld truth. Use multiple rules (random, short,
isolated, and attribute-stratified only where attributes exist), report paired per-fold
DTI and coverage/precision trade-offs, and reserve any hyperparameter selection for
training folds or an inner validation split. Report local chance only with each fold's
known hidden-truth size. These proxy folds are not private-test performance.

That validation was **not run**: no ComCat event table or focal-plane raster is in the
workspace, and no new candidate was implemented. No submission slot should be used.
