## Why

The standing brief's first demand was *"DO NOT STOP WORKING UNTIL WE HAVE A WORKING DOWNLOAD FOR SUBMISSION."* The site had a download; what it did not have was a download in an encoding the platform has ever accepted. Sessions 6–7 had the two encodings **backwards**, on a guess. This PR replaces the guess with a measurement, closes the data blocker the brief named, and reports a research round that changed three standing assumptions.

## 1. Root cause of `Predicted values must be in range [0, 1]` — found, and the previous diagnosis falsified

`scripts/audit_platform_encoding.py` → `reports/platform_encoding_evidence.json` measured the official `sample_submission.tif` (sha256 `2176d08e…`, pin independently reproduced by 16GEMSDOE's CI), the 10 files this group has public scores for, the one file the form rejected, and every file this project ships:

| | rejected file<br>`archive/13gems-r11-greedy-mp.tif` | official `sample_submission.tif` | the 10 platform-scored files |
|---|---|---|---|
| NaN inside the 5,167,373-px footprint | **0** | 0 | 0 |
| finite cells outside the footprint | **0** | 0 | 0 (9 files) · 7,111,787 (1 all-finite twin) |
| NaN outside the footprint | **7,111,787** | 7,111,787 | 7,111,787 (9 files) |
| `GDAL_NODATA` | **nan** | nan | nan (all 10) |
| finite value range | **[0.0, 1.0]** | [0.0, 1.0] | [0.0, ≤1.0] |
| dtype / CRS / shape / transform | **identical** | float32 · EPSG:32611 · 3730×3292 · (100,0,243350,0,−100,4508550) | identical |
| Compression / tiling | DEFLATE / tiled | LZW / striped | DEFLATE (7) **and** LZW (2); tiled **and** striped |
| **TIFF `Predictor`** | **2** | **1 (none)** | **1 (6) and 3 (3) — never 2** |

The rejected file's NaN placement is *identical* to the official template's and to every scored file's. Its one deviation is `Predictor=2` — TIFF 6.0 horizontal differencing, defined for **integer** samples; the floating-point predictor is `Predictor=3` (TIFF Technical Note 3), which three of the scored files use correctly. A reader that decompresses but never runs the accumulator returns the stored differences reinterpreted as float32: for this exact file that decodes to **min −4.0, max 3.0** — outside `[0, 1]`, i.e. precisely the message the form returned. Reproduced, not asserted: `src/gems/encoding.simulate_ignored_predictor2`, pinned by `tests/test_encoding.py::TheRejectedFile`.

**So "the NaN caused it" was backwards** — a validator that rejected NaN as out of range would reject DrivenData's own template.

Actions: primary is now the NaN-outside file, hedge is the zero-filled file; `rio.write_submission` pins `predictor=1`; `frontdoor._all_ok` refuses to release any file whose predictor is not none; `submit.json` is schema 2 with a `schema_note` explaining the swap; the `latest_nan.*` / `latest_allfinite.*` aliases are retired and deleted because they inverted the roles (I-19); `latest.tif` is now the NaN-outside primary; `verify_download.py` grew from 47 to **80 checks** including tag-for-tag equality with the official template. Session-7 files are archived under `docs/downloads/archive/session7-superseded-*`, not deleted. **I-8 and I-18 closed; I-22 records the evidence.**

An over-claim of mine was caught in pass 2 and corrected everywhere: I had written that *no* all-finite file has an acceptance receipt. This repo's own `reports/form_responses.json` entry 5 says the 12GEMSDOE all-finite twin **is** team-recorded as accepted (account SDCF9, 0.1294 — the same score as its NaN-outside twin, as expected since encoding does not change footprint pixels). The accurate claim is now "**9 of the 10** audited scored files", with the 10th described as team-recorded and not receipted, and not distinguishable from one upload recorded twice. The primary/hedge ordering is unchanged: it rests on the official template's encoding and the official format text, not on that count.

## 2. The data blocker named in the brief is closed

The brief said training was blocked on `bash scripts/download_competition_data.sh` + `python scripts/prepare_data.py`. **Neither script existed in this repository.** Both now do, and both ran:

- all three official rasters placed in `data/raw/` **with no DrivenData login**, from the group's own hash-pinned public mirror, every part and the reassembled file verified: `training_features.tif` 418,912,844 B sha256 `4371c82e…`, `sample_submission.tif` `2176d08e…`, `labels.tif` `7ba308cc…`;
- the mirror's own `data/bridge/manifest.json` **resolves I-1**: the file called `example_submission.tif` *is* the official `sample_submission.tif`. The official sample really does carry 1.0 at the 60,988 catalogue pixels, contradicting the problem page's "predicts total fault absence" — a discrepancy in the official material, not a mislabelled mirror;
- `prepare_data.py` audits all 19 bands from their own GDAL tags: **every band carries the float32 sentinel `-3.4028235e38` on 3,061 pixels inside the scored footprint** (band 6: 3,073) — the mechanism by which invalid values reach a submission and produce the range error, now asserted on placement rather than remembered.
- Both name sets are staged (`labels.tif`/`existing_faults.tif`, etc.) and `gems.rio.resolve_raw` accepts either, so a fresh clone works whichever fetcher ran.

## 3. Two organiser statements, verified verbatim, both strategy-changing

1. **Known faults are masked out of scoring in BOTH rounds.** *"Pixels corresponding to known USGS/INGENIOUS faults are masked / excluded from evaluation, so they do not count towards penalty terms."* … *"for scoring purposes it should not matter whether these known faults are included with predictions or not."* — `chrisk-dd`, **DrivenData Staff**, 2026-09-16, [forum 11516 post 2](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/2). ⇒ every R8–R13 recipe here that advertised `include_known_catalogue: true` was buying **exactly zero** (**I-27**). New gate D4 requires ≥ 95 % off-catalogue emission.
2. **Phase 2 rewards credible geology, not only Phase-1 score.** *"the largest prize pool (Phase 2) will use a test set that is updated by expert review of all Phase 1 submissions, so your fault predictions have an impact on final evaluation even if they are not the most performant in Phase 1."* — `chrisk-dd`, 2026-09-23, [forum 11527 post 7](https://community.drivendata.org/t/how-were-the-new-test-faults-identified-data-sources-and-fault-types/11527/7). ⇒ a fault-blind lattice is not a claim an expert can verify and add to the label set. **$250,000** sits on that round versus $50,000 on Phase 1.

## 4. I-24 — the hide-and-recover proxy is structurally blind to near-catalogue strategies

`gems.holdout.group_systems(link_px=8)` merges traces within ~1.6 km into one system, so whatever is hidden is ≥ ~16 px from everything visible — **four to five times the metric's 300 m kernel**. Measured over 15 folds × 2 buffer settings (`scripts/r14_budget_curve.py`): ranking pixels by distance to the visible catalogue scores DTI ≤ **0.0146** at *every* budget from 0.5 % to 100 %, versus **0.1063** for a stride-5 lattice. `buffer_px` 5 vs 0 changes almost nothing (random@4 % 0.08417 vs 0.08361), so `link_px` is the cause. Real new faults are continuations, stepovers and parallel strands of mapped ones — inside the forbidden ring.

Raw geophysical **magnitude** rankings are also worse than uniform random at every budget (detrended-elevation slope peaks at 0.0254, TMI horizontal gradient 0.0265, gravity slope 0.0203, strain-rate second invariant 0.0503, max second directional derivative of elevation 0.0281, versus 0.0842 for random at 4 %). That is why six rounds of feature engineering never moved the needle.

Fix: `gems.holdout.tip_folds` — withhold only the outermost 8/16/32 px of every trace ≥ 20 px, **no** `link_px` grouping, so hidden truth abuts visible catalogue (max distance 6 px, inside the kernel). Every catalogue pixel is accounted for as hidden **or** visible, never neither.

## 5. I-26 — no local truth set predicts the recorded public scores

The 9 independent scored files were re-scored against 7 truth sets × 2 masking policies and Spearman-correlated with their recorded scores (`scripts/calibrate_truth_sets.py`):

| truth set | px | ρ (masked) | p | ρ (unmasked) | p |
|---|---|---|---|---|---|
| `known_hidden25` | 15,352 | 0.326 | 0.391 | **0.393** | 0.295 |
| `known_dense` | 60,988 | 0.343 | 0.366 | 0.343 | 0.366 |
| `sgmc_offcat_r32` | 34,907 | −0.368 | 0.330 | −0.368 | 0.330 |
| `sgmc_offcat_r8` | 70,762 | −0.418 | 0.262 | −0.418 | 0.262 |
| `sgmc_offcat_r3` | 83,636 | −0.444 | 0.232 | −0.444 | 0.232 |
| `sgmc_offcat_r0` | 105,589 | −0.452 | 0.222 | −0.452 | 0.222 |
| `sgmc_offcat_r16` | 56,917 | −0.502 | 0.168 | −0.502 | 0.168 |

**Nothing reaches significance at n = 9** (smallest p = 0.168) and the USGS State Geologic Map off-catalogue variants correlate *negatively*. 16GEMSDOE reports ρ = +0.518 (p = 0.048, n = 15) for its own `sgmc_gap`; **not reproduced here** and the difference is left unresolved rather than reconciled by assertion. Consequence accepted: the doctrine "the holdout best gets the slot" is a tie-breaker between local candidates, **not** a prediction — and the lattice's 18/18 win is not evidence of leaderboard value.

The SGMC truth raster is committed with full provenance and official source URLs (`data/external_sgmc/derived_sgmc_faults_100m_u8.tif`, 226,663 B, sha256 `d569d553…`, from [USGS MRData state geology NV](https://mrdata.usgs.gov/geology/state/shp/NV.zip) / [CA](https://mrdata.usgs.gov/geology/state/shp/CA.zip); `scripts/fetch_sgmc_truth.py`).

## 6. R14 — along-strike propagation is real, but the predeclared gate was not passed

Register predeclared at `knowledge/10_r14_hypotheses.md` (5 ranked hypotheses; addendum B written **before** the corrected run was read). Report: `reports/holdout_r14_2026-10-01.json`.

| map | tip folds worst-rule | tip folds mean | 15 old folds worst-rule | SGMC ≥16 px | paired tip wins | verdict |
|---|---|---|---|---|---|---|
| **`lattice_s5` (reference, shipped)** | 0.08801 | 0.11276 | **0.10657** | **0.23913** | — | reference |
| `halo@0.01` / `@0.02` / `@0.04` | 0.02095 / 0.02620 / 0.03871 | 0.04784 / 0.04950 / 0.05673 | 0.00000 | 0.00000 | 2/9 · 0/9 · 0/9 | fail |
| `tips_L5/L10/L20@0.01` | 0.06701 / 0.07859 / **0.09394** | 0.14770 / 0.16268 / **0.17433** | 0.00000 | ≈0 | 5/9 · 5/9 · 6/9 | fail D2, D3 |
| `tips_L20@0.02` | **0.10271** | 0.16396 | 0.00000 | 0.00227 | 6/9 | fail D2, D3 |
| `tips_L5/L10/L20@0.04` | 0.10197 / 0.10146 / 0.09822 | 0.11861 / 0.12991 / 0.13285 | 0.06079 / 0.04158 / 0.00000 | 0.12057 / 0.05820 / 0.00773 | 3/9 · 5/9 · 6/9 | fail D2, D3 |
| `union_tipsL20_1pct+lat7_4pct` | 0.12160 | 0.13985 | 0.06569 | 0.14042 | 6/9 | fail D2, D3, D5 |
| `union_tipsL20_2pct+lat7_4pct` | 0.11895 | 0.13668 | 0.05336 | 0.12549 | 6/9 | fail D2, D3, D5 |
| **`union_tipsL10_1pct+lat6_4pct`** | **0.12253** | 0.13203 | 0.07865 | 0.17339 | 6/9 | fail D2, D3, D5 |

**Winners: none.** Per the predeclared rule **no submission slot is spent** and the primary stays `lattice_s5`. What the run did establish:

- **Direction carries information proximity does not** (predeclared prediction **P2, confirmed**): at equal budget the along-strike ribbons beat the isotropic halo 0.1477 / 0.1627 / 0.1743 vs 0.0478 at 1 %, and 0.1186 / 0.1299 / 0.1329 vs 0.0567 at 4 %. Mechanism: at a 1 % budget the halo spends everything on the ~1-px ring around the *whole* visible catalogue (~150,000 px), of which only the pixels that actually continue a trace are truth.
- **P1 falsified** and recorded as falsified: the halo does *not* beat the lattice on the tip folds.
- **Best hedged candidate** `union_tipsL10_1pct+lat6_4pct` (ribbons at 1 %, then a stride-6 lattice filling a fixed 4 % total): **+39 %** on the tip-fold worst rule, **−0.0279** on the old folds (D3 allows 0.002), 6/9 paired (D2 wants 7), **100 % off-catalogue** in deployment (192,231 px, 3.7201 % of footprint). Published as a listed second candidate and an *experiment arm, not a recommendation*, because the two fold families disagree **by construction** (I-24) and no local truth set can adjudicate (I-26).
- **A tie-breaking bug was found, measured and fixed rather than hidden** (addendum B.1): the first run's bare `argpartition` put **959 of 1000** selections in the first row decile on a tied field and never sampled 7 of 10 deciles (I-14 recurring; pinned by `tests/test_r14.py::TieBreaking`). The fix moved some candidates by up to **11×** and left the tie-free reference untouched, so the entire first run is void. Stated plainly: the jitter does **not** explain the halo's weakness (it moved it ≤ 24 %).

## 7. Why 0.1563 repeats, and why 0.3049 is the wrong target

- The brief's target is **stale**. Fetched once on 2026-10-01 from the official public page (`reports/leaderboard_snapshot_2026-10-01.json`): **#1 DARD 0.3168** (11 submissions), #2 alexoktaba 0.3042 (18), #3 joeyfezster 0.2919 (16). `0.3049` appears nowhere in the snapshot. One group account is visible: **smrtdoog5 at rank 23 with 0.1894 on only 4 submissions** — higher than the 0.1563 this project's ledger records as the group's best.
- **Duplication is part of it and is verified** (I-20): blob `812e61b74050d1350cc2bde1fab0c76ead32e0c4` sits in `GEMSDOE`, `5GEMSDOE` and `GEMSDOE2` under names asserting 0.1563. `gems8_apex`'s 0.1563 is a *different* map (6.7 % shared positive support, Pearson −0.55), so duplication does not explain that one.
- **The leaderboard column is an account-level best** (I-3) and no per-submission receipt exists for any of the 10 rows.
- **New, from the metric algebra:** `DTI = 1/(0.2/P_w + 0.8/R_w)`. Reaching 0.3168 needs P_w ≈ 0.10–0.13 at R_w ≈ 0.5–0.7. The two group points that bracket it are `gems7_halo15` (1,828,699 px = 35.4 % coverage, 0.1461 — recall-rich, precision-poor) and `gemsdoe1_ens12` (172,974 px = 3.3 %, 0.1563 — the reverse). **Neither is near the optimum, and 0.3168 is not reachable by coverage geometry at all**: a blind lattice's arithmetic ceiling is ≈ 0.28 and only if the private truth set is as large as the entire public catalogue. The remaining gap is information, not budget.

**Recommended way to spend the three weekly uploads** (README §7): arm A = coverage (also the encoding receipt), arm C = the union, arm B = tips-only. All three format-proven, uniquely named and uniquely noted, so one public score each settles what no local proxy can. A first, because it is the encoding receipt. Whether a *rejected* upload consumes an allowance is undocumented in anything this project could fetch — ask `info@drivendata.org`.

## 8. Also in this PR

- Root `/.nojekyll` added (**I-23**): Pages source is the repo **root**, so `docs/.nojekyll` was inert and Jekyll processed every page and asset on every build.
- Site rebuilt from the manifest with a new front-page **Session 8** section; every page still puts the primary download in the first 4 KB of `<body>` and `docs/index.html`'s first `<a download>` is the primary (asserted by `verify_download.py`).
- `reports/form_responses.json` gains 9 entries, all `outcome=NOT_SUBMITTED_no_platform_response`, plus one recording that the session-7 A/B files were never submitted — so "published on the site" is never mistaken for "accepted by the platform".
- Stale second manifest `docs/downloads/latest.json` retired to the archive; `reports/latest_submission.json` annotated append-only with `superseded_by` (historical evidence is not edited).
- `PROJECT_CHARTER.md` §6.1: five standing amendments that came from measurement, and §7 updated.

## Verification at this commit

- `python scripts/verify_download.py` → **80/80 checks passed**
- `pytest tests -q` → **114 passed, 4 skipped** (the 4 skips need `data/external`, staged by `scripts/fetch_external_data.py`)
- `python scripts/audit_platform_encoding.py`, `python scripts/fetch_sgmc_truth.py`, `bash scripts/download_competition_data.sh` → all pass and are idempotent
- `python scripts/build_site.py` → site regenerated from the reports; nothing on it is typed by hand

## Known limitations / flagged for review

- **No DrivenData credentials**: cannot submit, cannot read the data tab, cannot observe the validator or the private labels. Acceptance remains unestablished for every file here — only the form's own response can establish it.
- **The live site is not updated until this merges.** GitHub Pages builds from `main`; this branch was not pushed while the token was invalid. Run `bash scripts/finish_pr.sh` after reconnecting GitHub.
- **Egress is blocked** here for `www.dropbox.com`, `gdr.openei.org`, `mrdata.usgs.gov` and `buffedlizard55-lab.github.io` (`curl: (35) SSL_ERROR_SYSCALL`), so the live Pages URL could not be fetched from the sandbox. The user's Dropbox mirrors were **not** used; the group's own hash-pinned mirror was, and all pins matched.
- **No GPU, 2 CPUs, 3 GB RAM.** The official reference solution is a U-Net (ResNet-18 encoder, 128-px patches, 5 MC splits); it cannot be trained here. Nothing supervised was trained this session — the R14 candidates are geometry-only by design, which is also what makes them auditable.
- **Band 6's identity is still contested (I-25)**: its own GDAL tag says "tilt angle or total curvature", 16GEMSDOE measured r = +0.997 against USGS GeoDAWN radiometric total count, 12GEMSDOE concluded top-of-crustal magnetic source depth. Not re-derived here, so the register uses it only as a positive-valued scalar.
- **H-R14-2/3/4/5 were predeclared but not implemented or measured.** No result for them exists and none is implied. H-R14-5 also needs a runner to fetch the 1 m 3DEP DEM; obtainability from this sandbox is **unverified**.
- The SGMC ≥16 px truth set inherits I-24's bias (it excludes everything near the catalogue by construction), so its column above is **not** an unbiased external check. `sgmc_offcat_r0` should be added next session.
- **No scraper or polling feed** for the leaderboard: DrivenData's Terms of Use prohibit using any robot, spider or other automatic device to access the site including for monitoring or copying. The snapshot is a one-off manual fetch, labelled as such; the automated feed covers official open-data hosts and this group's own repositories only.
