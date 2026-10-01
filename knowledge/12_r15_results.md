# R15 thermal outcome — 2026-10-01

**RESEARCH_ONLY_DO_NOT_SUBMIT. No competition upload; zero slots used.**

Frozen specification: [11_r15_predeclared.md](11_r15_predeclared.md). Full per-fold components, mask hashes, source/code hashes and scorer parity: [report](../reports/holdout_r15_2026-10-01.json).

## Measured results

| Protocol | Current lattice mean DTI | Thermal union mean DTI | Paired wins | Worst-rule gain |
|---|---:|---:|---:|---:|
| Existing 18 system/segment folds | 0.11218396 | 0.11204439 | 0/18 | -0.00014033 |
| Four buffered geographic folds | 0.24217508 | 0.24201309 | 0/4 | -0.00016199 |

2,782 of3,800 probes intersected the exact valid footprint (34 survey areas). 279 unique stations passed the frozen DAB>=3C threshold; 48 local aligned neighbourhoods produced411 raster cells (0.00795% of footprint). Three duplicate warm coordinates did not count as independent corroboration. Only139 inside-footprint probes have multiple dated valid measurements; dates may be seasonal-correction dates, not independent raw campaigns.

The thermal union LOST on every paired fold. Standalone thermal mean DTI was0.00025029 (existing) and0.00020871 (geographic); it is not a regionally useful fault map under this test. All four improvement/win gates failed; non-identity and predeclaration-integrity checks passed.

## What this does / does not establish

- This rejects THIS frozen thin-corridor detector plus lattice union for submission, not shallow thermometry as a science.
- Sparse, prospect-selected data, seasonal/groundwater effects, inaccurate line placement and diffuse outflow are plausible limitations. None was isolated causally.
- DTI levels across the two protocols must not be compared as evidence of transfer. Geographic blocks restrict the scoring domain; the existing protocol penalizes predictions over nearly the entire valid region while hiding only part of the catalogue.
- All truth is public catalogue truth; no hidden-test or leaderboard score has been measured.
- No parameter sweep or retuning was performed after confirmation results. Broader halos would be a NEW predeclared experiment, not a retroactive success.
- Primary TIFF unchanged byte-for-byte. This is not a new submission produced by renaming the same raster.

## Next best use of work

Predeclare displaced-marker registration using the already obtained magnetic/radiometric inputs (#2), with synthetic displacement checks and the same current-best paired gates. Alternatively obtain event-level focal planes from official USGS products in an open-egress runner before calling #3 viable. Do not continue threshold sweeps on these confirmation folds.
