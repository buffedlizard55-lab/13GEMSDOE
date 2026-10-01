# SUPERSEDED historical README — preserved, not current advice

**Read [the current correction register](../13_audit_corrections_2026-10-01.md).**
This frozen historical text contains WITHDRAWN claims of a proven Predictor2
rejection cause, disproved NaN handling, per-file score acceptance receipts and
next-slot advice for failed R14. Do not execute its obsolete migration or branch
instructions. The original text below is retained for audit and prompt preservation.

---

# 13GEMSDOE — GEMS Prize Challenge working repository

## ⬇ DOWNLOAD THE SUBMISSION TIF (upload this to DrivenData)

| | file | use |
|---|---|---|
| **PRIMARY — upload this** | [`docs/downloads/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif`](docs/downloads/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif) (1.7 MB) · [.zip](docs/downloads/13gems_20261001_r13-lattice-s5_v2_nan-outside.zip) | float32 · EPSG:32611 · 3730×3292 · **NaN outside the survey footprint, `GDAL_NODATA=nan`, every footprint value finite and in [0, 1]** · LZW, one-row strips, **no predictor** — the byte encoding of the official `sample_submission.tif` **and of 9 of the 10 files this group has a public DrivenData score for** (the 10th is an all-finite twin, team-recorded not receipted). Content: fault-blind stride-5 lattice (R13-6), best local hold-out map; a coverage baseline, **not** a geological prediction |
| HEDGE — only if the form rejects the primary | [`docs/downloads/13gems_20261001_r13-lattice-s5_v2_zerofill.tif`](docs/downloads/13gems_20261001_r13-lattice-s5_v2_zerofill.tif) (1.0 MB) · [.zip](docs/downloads/13gems_20261001_r13-lattice-s5_v2_zerofill.zip) | Same predictions, 0.0 instead of NaN outside the footprint, no NoData tag, so it also passes a naive whole-array `[0, 1]` test. **Not** the official template's encoding. One all-finite file *is* team-recorded as accepted (12GEMSDOE `r7-nms3-dem10-scarp_0c9199f14e62_allfinite`, account SDCF9, score 0.1294 — the same score as its NaN-outside twin, as expected because encoding does not change footprint pixels; [`reports/form_responses.json`](reports/form_responses.json) entry 5). That is a team record, not a platform receipt, and it cannot be told apart from one upload recorded twice |
| **2nd candidate** | [`docs/downloads/13gems_20261001_r11-greedy-mp_v2_nan-outside.tif`](docs/downloads/13gems_20261001_r11-greedy-mp_v2_nan-outside.tif) (2.0 MB) · [.zip](docs/downloads/13gems_20261001_r11-greedy-mp_v2_nan-outside.zip) | Next slot: the R11 greedy recipe (a real map built from the geophysics/topography bands). Hedge: [`13gems_20261001_r11-greedy-mp_v2_zerofill.tif`](docs/downloads/13gems_20261001_r11-greedy-mp_v2_zerofill.tif) |

* **Unique file names:** `13gems_<date>_<recipe>_v<n>_<nan-outside|zerofill>`; never re-upload an old name (the generator refuses to overwrite one).
* **Short note to paste (primary):** `r13 lattice-s5 v2 20261001 | fault-blind every-5th-px grid, coverage baseline | local holdout 18/18 win, not a LB claim`
* **Short note to paste (2nd candidate):** `r11 greedy-mp v2 20261001 | topo ridge 5% + 3 greedy blocks | local holdout win, not a LB claim`
* Fixed aliases: [`latest.tif`](docs/downloads/latest.tif) = PRIMARY, [`latest_zerofill.tif`](docs/downloads/latest_zerofill.tif) = HEDGE. The old `latest_nan.*` / `latest_allfinite.*` aliases are **retired** — they inverted the roles (I-19). Manifest + hashes: [`docs/downloads/submit.json`](docs/downloads/submit.json) (schema 2).
* Form: <https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/> · step-by-step: [executive summary](https://buffedlizard55-lab.github.io/13GEMSDOE/docs/executive_summary.html).
* **Honest status:** no file from *this* repository has yet passed DrivenData's own validator — acceptance is only ever established by the form's own response, logged in [`reports/form_responses.json`](reports/form_responses.json). What *is* established, from bytes: the primary's encoding is the one the official template uses and the one all nine platform-scored group files use, and the one file the form rejected is the only file in this project's history written with `PREDICTOR=2`. Re-check any time: `python scripts/verify_download.py` (68 checks) and `python scripts/audit_platform_encoding.py`.

**Submission site:** https://buffedlizard55-lab.github.io/13GEMSDOE/ (download page) · https://buffedlizard55-lab.github.io/13GEMSDOE/docs/ (evidence, hypotheses, sources)
**Competition:** [DOE GEMS Prize on DrivenData](https://www.drivendata.org/competitions/306/competition-doe-gems/) · $300,000 · metric: distance-weighted Tversky index

> **Read [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) at the start of every
> session.** It is the standing brief — goals, non-negotiables, and the
> operating rules this project is built against. This README is the map; the
> charter is the mission. The verbatim brief is reproduced in full at the
> bottom of this file so that this page is self-contained.

---

## Latest review — 2026-10-01, session 8 (the rejection's real cause; the data blocker closed; R14/R15)

### 0. The one thing that matters most: the download is now the encoding the platform has actually accepted

The front door had the two encodings **backwards**. Sessions 6–7 shipped the zero-filled file as
primary because they believed the NaN cells caused the form's
`Predicted values must be in range [0, 1]` rejection. That belief is falsified by measurement
(`scripts/audit_platform_encoding.py` → [`reports/platform_encoding_evidence.json`](reports/platform_encoding_evidence.json)):

| | rejected file<br>`archive/13gems-r11-greedy-mp.tif` | official `sample_submission.tif`<br>sha256 `2176d08e…` | all 9 platform-scored group files |
|---|---|---|---|
| NaN inside the 5,167,373-px footprint | **0** | 0 | 0 |
| finite cells outside the footprint | **0** | 0 | 0 |
| NaN outside the footprint | **7,111,787** | 7,111,787 | 7,111,787 |
| `GDAL_NODATA` | **nan** | nan | nan |
| finite value range | **[0.0, 1.0]** | [0.0, 1.0] | [0.0, ≤1.0] |
| dtype / CRS / shape / transform | **identical** | float32 · EPSG:32611 · 3730×3292 · (100,0,243350,0,−100,4508550) | identical |
| Compression / tiling | DEFLATE / tiled | LZW / striped | DEFLATE (7) **and** LZW (2); tiled **and** striped |
| **TIFF `Predictor`** | **2** | **1 (none)** | **1 (6 files) and 3 (3 files) — never 2** |

The rejected file's NaN placement is *identical* to the official template's and to every file the
platform has scored. (The 10th audited file, `gems12_r7nms3_allfinite`, is the all-finite twin of a scored
NaN-outside submission and shares its recorded 0.1294 — see the HEDGE row above; it is team-recorded, not
receipted.) Its one deviation is `Predictor=2` — TIFF 6.0 horizontal differencing, defined
for **integer** samples; the floating-point predictor is `Predictor=3` (TIFF Technical Note 3), which
three of the nine scored files use correctly. A reader that decompresses but never runs the
accumulator returns the stored differences reinterpreted as float32: for this exact file that decodes
to **min −4.0, max 3.0** — outside `[0, 1]`, i.e. precisely the message the form returned. Reproduced,
not asserted: `src/gems/encoding.simulate_ignored_predictor2`, pinned by
`tests/test_encoding.py::TheRejectedFile`.

**Actions taken.** Primary is now the NaN-outside file; the zero-filled file is a labelled hedge.
`src/gems/rio.write_submission` pins `predictor=1`; `frontdoor._all_ok` refuses to release any file
whose predictor is not none; `submit.json` is schema 2 (`primary` / `hedge`, with a `schema_note`
explaining the swap); the aliases `latest_nan.*` and `latest_allfinite.*` are **retired and deleted**
because they inverted the roles (I-19); `latest.tif` is now the NaN-outside primary.
`scripts/verify_download.py` runs **80 checks** and all pass; `pytest tests -q` is **114 passed,
4 skipped**. Session-7 files are archived under `docs/downloads/archive/session7-superseded-*`, not
deleted. Irregularities **I-8 and I-18 are closed**; **I-22** records the evidence.

**Still honest:** no file *from this repository* has passed DrivenData's own validator. Acceptance is
established only by the form's own response, logged in [`reports/form_responses.json`](reports/form_responses.json).
What is established is that this encoding is the one DrivenData's own template uses and the one every
scored group file uses.

### 1. The data blocker named in the standing brief is closed

The brief said training was blocked on `bash scripts/download_competition_data.sh` +
`python scripts/prepare_data.py`. **Neither script existed in this repository.** Both now do, and both ran:

* [`scripts/download_competition_data.sh`](scripts/download_competition_data.sh) — places all three
  official rasters in `data/raw/` **without a DrivenData login**, from this group's own public mirror
  (`buffedlizard55-lab/GEMSDOE`, `data/bridge/`, itself populated on a GitHub-hosted runner from the
  official data tab), verifying every part and the reassembled file against published SHA-256 pins.
  `training_features.tif` 418,912,844 B sha256 `4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5`;
  `sample_submission.tif` sha256 `2176d08e…`; `labels.tif` sha256 `7ba308cc…`. All three match.
  The canonical-name mapping (`gems-geodawn-numerical-features.tif` == `training_features.tif`, etc.)
  comes from that repo's `data/bridge/manifest.json`, which also **resolves I-1**: the file we called
  `example_submission.tif` *is* the official `sample_submission.tif`, independently pinned to the same
  sha256 by 16GEMSDOE's CI. The official sample really does carry 1.0 at the 60,988 catalogue pixels,
  contradicting the problem page's "predicts total fault absence" — a discrepancy in the official
  material, not a mislabelled mirror.
* [`scripts/prepare_data.py`](scripts/prepare_data.py) — audits all 19 bands from the stack's own GDAL
  tags (never typed) → `data/derived/{band_index,band_stats,prepare_manifest}.json`. **Every band
  carries the float32 sentinel `-3.4028235e38` on 3,061 pixels inside the scored footprint**
  (band 6: 3,073). That is the mechanism by which invalid values reach a submission and produce the
  range error, and it is now asserted on placement rather than remembered.

### 2. Two organiser statements, verified verbatim, that change the strategy

1. **Known faults are masked out of scoring, in both rounds.** “Pixels corresponding to known
   USGS/INGENIOUS faults are masked / excluded from evaluation, so they do not count towards penalty
   terms.” “Re-evaluation will also mask/exclude the existing USGS/INGENIOUS faults.” “for scoring
   purposes it should not matter whether these known faults are included with predictions or not.” —
   `chrisk-dd`, **DrivenData Staff**, 2026-09-16,
   [forum 11516 post 2](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/2).
   ⇒ every R8–R13 recipe here that advertised `include_known_catalogue: true` was buying **exactly
   zero** (**I-27**). New gate D4 requires every candidate to be ≥ 95 % off-catalogue.
2. **Phase 2 rewards credible geology, not only Phase-1 score.** “We're not sharing details about the
   data sources, fault types, or coverage behind the test faults beyond what's in the problem
   description. Note that the largest prize pool (Phase 2) will use a test set that is updated by
   expert review of all Phase 1 submissions, so your fault predictions have an impact on final
   evaluation even if they are not the most performant in Phase 1.” — `chrisk-dd`, 2026-09-23,
   [forum 11527 post 7](https://community.drivendata.org/t/how-were-the-new-test-faults-identified-data-sources-and-fault-types/11527/7).
   ⇒ a fault-blind lattice is not a claim an expert can verify and add to the label set. $250,000 sits
   on that round versus $50,000 on Phase 1. This is a real, organiser-stated argument for shipping
   geologically interpretable traces even at some Phase-1 cost.

### 3. No local truth set predicts the recorded public scores (**I-26**)

`scripts/calibrate_truth_sets.py` re-scored the 9 independent platform-scored files against 7 truth
sets × 2 masking policies and Spearman-correlated each with the recorded public score
([`reports/truthset_calibration.json`](reports/truthset_calibration.json)):

| truth set | px | ρ (masked) | p | ρ (unmasked) | p |
|---|---|---|---|---|---|
| `known_hidden25` | 15,352 | 0.326 | 0.391 | **0.393** | 0.295 |
| `known_dense` | 60,988 | 0.343 | 0.366 | 0.343 | 0.366 |
| `sgmc_offcat_r32` | 34,907 | −0.368 | 0.330 | −0.368 | 0.330 |
| `sgmc_offcat_r8` | 70,762 | −0.418 | 0.262 | −0.418 | 0.262 |
| `sgmc_offcat_r3` | 83,636 | −0.444 | 0.232 | −0.444 | 0.232 |
| `sgmc_offcat_r0` | 105,589 | −0.452 | 0.222 | −0.452 | 0.222 |
| `sgmc_offcat_r16` | 56,917 | −0.502 | 0.168 | −0.502 | 0.168 |

**Nothing reaches significance at n = 9** (smallest p = 0.168) and the USGS State Geologic Map (SGMC)
off-catalogue variants correlate *negatively*. 16GEMSDOE reports ρ = +0.518 (p = 0.048, n = 15) for its
own `sgmc_gap`; **not reproduced here** — my `sgmc_offcat_r16` is similar in size but defined by
distance from the catalogue rather than by geologic-map attributes, and it comes out with the opposite
sign. Unresolved, and flagged rather than reconciled by assertion. The SGMC raster itself is committed
(`data/external_sgmc/derived_sgmc_faults_100m_u8.tif`, 226,663 B, sha256 `d569d553…`, provenance and
official source URLs in [`scripts/fetch_sgmc_truth.py`](scripts/fetch_sgmc_truth.py)).

**Consequence, accepted:** the doctrine “the holdout best gets the slot” cannot be used to claim any
local win will transfer, and the lattice's 18/18 win (I-21) is **not** evidence of leaderboard value.

### 4. The old proxy is structurally blind to the mechanism that matters (**I-24**)

`gems.holdout.group_systems(link_px=8)` dilates the catalogue by 8 px before labelling, so any two
traces within ~1.6 km become ONE system and are hidden together: whatever is withheld is ≥ ~16 px from
everything visible — four to five times the metric's 300 m kernel. Measured over 15 folds × 2 buffer
settings ([`reports/r14_budget_curve.json`](reports/r14_budget_curve.json),
[`scripts/r14_budget_curve.py`](scripts/r14_budget_curve.py)): ranking pixels by distance to the
visible catalogue scores DTI ≤ **0.0146** at *every* budget from 0.5 % to 100 %, while a fault-blind
stride-5 lattice scores **0.1063**. Real new faults are continuations, stepovers and parallel strands
of mapped ones — inside the forbidden ring. `buffer_px` 5 vs 0 changes almost nothing
(random@4 % 0.08417 vs 0.08361), so the blindness comes from `link_px`, not the buffer.

Raw geophysical **magnitude** rankings are also worse than uniform random at every budget:
detrended-elevation slope peaks at DTI 0.0254 (15 % coverage), TMI horizontal gradient 0.0265,
gravity slope 0.0203, strain-rate second invariant 0.0503, max second directional derivative of
elevation 0.0281 — against 0.0842 for random at 4 %. That is why six rounds of feature engineering
never moved the needle.

Fix: `gems.holdout.tip_folds` — withhold only the outermost 8/16/32 px of every trace ≥ 20 px, with
**no** `link_px` grouping, so hidden truth abuts visible catalogue (max distance 6 px, inside the
kernel). 9 folds; every catalogue pixel is accounted for as hidden **or** visible, never neither.

### 5. R14 result — along-strike propagation is real, but the predeclared gate was not passed

Register: [`knowledge/10_r14_hypotheses.md`](knowledge/10_r14_hypotheses.md) (predeclared, with
addendum B written before the corrected run was read). Report:
[`reports/holdout_r14_2026-10-01.json`](reports/holdout_r14_2026-10-01.json).

| map | tip folds<br>worst-rule | tip folds<br>mean | 15 old folds<br>worst-rule | SGMC ≥16 px | paired tip wins | verdict |
|---|---|---|---|---|---|---|
| **`lattice_s5` (reference, shipped)** | 0.08801 | 0.11276 | **0.10657** | **0.23913** | — | reference |
| `halo@0.01` / `@0.02` / `@0.04` | 0.02095 / 0.02620 / 0.03871 | 0.04784 / 0.04950 / 0.05673 | 0.00000 | 0.00000 | 2/9 · 0/9 · 0/9 | fail |
| `tips_L5@0.01` / `L10` / `L20` | 0.06701 / 0.07859 / **0.09394** | 0.14770 / 0.16268 / **0.17433** | 0.00000 | ≈0 | 5/9 · 5/9 · 6/9 | fail D2, D3 |
| `tips_L20@0.02` | **0.10271** | 0.16396 | 0.00000 | 0.00227 | 6/9 | fail D2, D3 |
| `tips_L5@0.04` / `L10` / `L20` | 0.10197 / 0.10146 / 0.09822 | 0.11861 / 0.12991 / 0.13285 | 0.06079 / 0.04158 / 0.00000 | 0.12057 / 0.05820 / 0.00773 | 3/9 · 5/9 · 6/9 | fail D2, D3 |
| `union_tipsL20_1pct+lat7_4pct` | 0.12160 | 0.13985 | 0.06569 | 0.14042 | 6/9 | fail D2, D3, D5 |
| `union_tipsL20_2pct+lat7_4pct` | 0.11895 | 0.13668 | 0.05336 | 0.12549 | 6/9 | fail D2, D3, D5 |
| **`union_tipsL10_1pct+lat6_4pct`** | **0.12253** | 0.13203 | 0.07865 | 0.17339 | 6/9 | fail D2, D3, D5 |

**Winners: none.** Per the predeclared rule no submission slot is spent and the primary stays
`lattice_s5`. What the run *did* establish:

* **Direction carries information that proximity does not** (predeclared prediction **P2, confirmed**):
  at every equal budget the along-strike ribbons beat the isotropic halo on the tip folds — at 1 %,
  0.1477 / 0.1627 / 0.1743 (L = 5/10/20 px) against 0.0478; at 4 %, 0.1186 / 0.1299 / 0.1329 against
  0.0567. Mechanism: at a 1 % budget the halo spends everything on the ~1-px ring around the whole
  visible catalogue (~150,000 px), of which only the pixels that actually *continue* a trace are truth.
* **P1 was falsified** and is recorded as falsified: the isotropic halo does *not* beat the lattice on
  the tip folds.
* **The best hedged candidate** is `union_tipsL10_1pct+lat6_4pct` (along-strike ribbons at 1 %, then a
  stride-6 lattice filling a fixed 4 % total): **+39 %** over the reference on the tip-fold worst rule
  (0.12253 vs 0.08801), **−0.0279** on the old folds' worst rule (gate D3 allows 0.002), 6/9 paired
  tip wins (gate D2 wants 7), and 100 % off-catalogue in deployment (192,231 px, 3.7201 % of the
  footprint). It is published as a **listed second candidate** — an experiment arm, not a
  recommendation — because the two fold families disagree *by construction* (I-24) and no local truth
  set can adjudicate (I-26).
* **A tie-breaking bug was found, measured and fixed rather than hidden** (addendum B.1): the first run
  selected top-K with a bare `argpartition`, which on a massively tied field put **959 of 1000**
  selections in the first row decile and never sampled 7 of 10 deciles (I-14 recurring; now pinned by
  `tests/test_r14.py::TieBreaking`). Adding a fixed seeded spatially uniform tie-break moved some
  candidates by up to **11×** (`tips_L5@0.04` on SGMC 0.01126 → 0.12057) and left the tie-free
  reference untouched, so the entire first run is void and only the corrected numbers are reported.
  Also stated plainly: the jitter does **not** explain the halo's weakness (it moved it ≤ 24 %).

### 6. Why 0.1563 repeats, and why 0.3049 is the wrong target

* The leaderboard target in the standing brief is **stale**. Fetched once on 2026-10-01 from the
  official public page ([`reports/leaderboard_snapshot_2026-10-01.json`](reports/leaderboard_snapshot_2026-10-01.json)):
  **#1 DARD 0.3168** (11 submissions), #2 alexoktaba 0.3042 (18), #3 joeyfezster 0.2919 (16),
  #4 xiaofanhu 0.2901, #5 HardcoreTechGod 0.2854. `0.3049` does not appear anywhere in the snapshot.
  One group account is visible: **smrtdoog5 at rank 23 with 0.1894 on only 4 submissions** — higher
  than the 0.1563 this project's ledger records as the group's best. `extradr19` is at rank 25
  (score not captured, recorded as not-captured rather than guessed).
* **Duplication is part of it, and it is verified**: git blob `812e61b74050d1350cc2bde1fab0c76ead32e0c4`
  (570,890 B) sits in `GEMSDOE`, `5GEMSDOE` and `GEMSDOE2` under names asserting 0.1563 (**I-20**).
  Identical bytes cannot score differently, so at least one of those labels is a copied artefact.
  `gems8_apex`'s 0.1563 is a *different* map (6.7 % shared positive support, Pearson −0.55), so
  duplication does not explain that one.
* **The leaderboard column is an account-level best**, so a run of weaker uploads leaves an old number
  on display (**I-3**), and no per-submission receipt exists for any row
  (`reports/leaderboard_ledger.csv`, `verified = NO` for all 10).
* **New, from the metric algebra:** `DTI = 1/(0.2/P_w + 0.8/R_w)`. Solving for the leader's 0.3168
  requires P_w ≈ 0.10–0.13 at R_w ≈ 0.5–0.7. The two group data points that bracket it are
  `gems7_halo15` (1,828,699 px = 35.4 % coverage, 0.1461 — recall-rich, precision-poor) and
  `gemsdoe1_ens12` (172,974 px = 3.3 %, 0.1563 — the reverse). **Neither is near the optimum, and
  0.3168 is not reachable by coverage geometry at all**: a blind lattice's arithmetic ceiling is
  ≈ 0.28 and only if the private truth set is as large as the entire public catalogue. The remaining
  gap is information, not budget.

### 7. Recommended way to spend the three weekly uploads (a designed experiment, not three guesses)

Allowance: three scored submissions per **rolling** 7-day window (Official Rules §3.2; staff, forum
11524). Whether a *rejected* upload consumes an allowance is undocumented in anything this project
could fetch — ask <info@drivendata.org> before relying on either answer. All three arms below are
format-proven, uniquely named and uniquely noted, so one public score each settles what no local proxy
can (I-26):

| arm | file | what one score tells us |
|---|---|---|
| **A — coverage** | `13gems_20261001_r13-lattice-s5_v2_nan-outside.tif` | whether the coverage plateau reproduces; also the first receipt for the corrected encoding |
| **B — propagation** | (build with `scripts/publish_r14_union.py`-style tips-only at 1 %) | whether along-strike continuation transfers, which P2 says is real information |
| **C — union** | `13gems_20261001_r14-union-tips10-lat6_nan-outside.tif` | whether the hedge dominates both, i.e. whether I-24's disagreement is resolvable by mixing |

Order matters: **A first**, because it is the encoding receipt; then C; then B. Record every response
in `reports/form_responses.json` and every score in `reports/leaderboard_ledger.csv` with its file
sha256, or the next session inherits the same ambiguity.

### 8. Limitations of this session (what I could not do or verify)

* **No DrivenData credentials.** Cannot submit, cannot read the data tab, cannot see the validator or
  the private labels. Acceptance remains unestablished for every file here.
* **Egress is blocked** for `www.dropbox.com`, `gdr.openei.org`, `mrdata.usgs.gov` and
  `buffedlizard55-lab.github.io` (`curl: (35) SSL_ERROR_SYSCALL`), so the live Pages URL could not be
  fetched from here; the download was verified against the committed bytes and the Pages build status
  (`gh api … /pages/builds/latest` → `built`, commit `ff76c37`). The user-supplied Dropbox mirrors were
  **not** used: the group's own hash-pinned mirror was, and all three pins matched.
* **No GPU, 2 CPUs, 3 GB RAM.** The official reference solution is a U-Net (ResNet-18 encoder,
  128-px patches, 5 Monte-Carlo splits); it cannot be trained here. Nothing supervised was trained
  this session — the R14 candidates are geometry-only by design, which is also what makes them
  auditable.
* **Band 6's identity is still contested** (**I-25**): its own GDAL tag says “tilt angle or total
  curvature”, 16GEMSDOE measured r = +0.997 against USGS GeoDAWN radiometric total count, 12GEMSDOE
  concluded it is the top-of-crustal magnetic source depth. Not re-derived here (no external
  radiometric raster staged), so the register uses it only as a positive-valued scalar.
* **H-R14-2/3/4/5 were predeclared but not implemented or measured** — no result for them exists and
  none is implied. H-R14-5 additionally needs a runner to fetch the 1 m 3DEP DEM; obtainability from
  this sandbox is **unverified**.
* The SGMC ≥16 px truth set inherits I-24's bias (it excludes everything near the catalogue by
  construction), so its column above is *not* an unbiased external check; `sgmc_offcat_r0` should be
  added next session.
* Root `/.nojekyll` added (**I-23**): Pages source is the repo root, so `docs/.nojekyll` was inert and
  Jekyll was processing every page and asset on every build.

## Latest review — 2026-10-01, session 7 (download front door; R13)

### 1. Download front door (the priority)
* The rejected file was `13gems-r11-greedy-mp.tif` (NaN outside the footprint, TIFF PREDICTOR=2; none of the previously scored files used predictor 2). `latest.tif` turned out to be **byte-identical to that rejected file** while the README claimed an all-finite default (**I-19**). Fixed: new A/B files, aliases, root `index.html` landing page, manifest-driven site, `scripts/verify_download.py`, `tests/test_frontdoor.py` (72 tests pass incl. `tests/test_r13.py`).
* Layout of A/B follows the official example (LZW, striped, no predictor). Pillow, rasterio/GDAL and tifffile all decode them identically. **Untested hypothesis, not a claim:** the old PREDICTOR=2 layout or the NaN cells triggered the form's error (**I-18**).

### 2. R13 batch (predeclared: [`knowledge/09_r13_hypotheses.md`](knowledge/09_r13_hypotheses.md))
18 hide-and-recover folds, rule frozen before running, protocol regression drift 0.0.

| challenger (Stage B = base + unchanged R11 blocks) | tune worst-rule DTI | confirm worst-rule DTI |
|---|---|---|
| reference `topo_05_sp3` | 0.03852 | 0.08687 |
| reference `greedy_r11` | 0.03992 | 0.09168 |
| R13-1 local-contrast crest (4 variants) | 0.0398–0.0404 | 0.0905–0.0922 |
| R13-2 scale-persistent crest `persist_gm` | **0.04237** (selected) | 0.09218 |
| R13-3 tile-quota budget (2 variants) | 0.0409–0.0411 | 0.0877–0.0904 |
| R13-4 paleo-geothermal halos, GDR 1391 (3 sizes) | 0.0390–0.0396 | 0.0904–0.0914 |

Verdict for the selected `persist_gm_greedy`: **FRAGILE** (rules won 3/6, paired folds 6/18). Stage A (information only): `persist_gm` alone beats `topo_05_sp3` in **17/18** folds (+1.7 % confirm mean) — the R11 blocks were tuned on the old base and no longer add to it; re-tuning the blocks on the new base is **R13b**, the first next step below. R13-4 was *run* (data staged by a GitHub runner, [`.github/workflows/fetch-gdr1391.yml`](.github/workflows/fetch-gdr1391.yml), CC-BY-4.0, sha256 in [`reports/gdr1391_fetch.json`](reports/gdr1391_fetch.json)): all three block sizes **LOSE** to `greedy_r11` (dose-response: more paleo pixels, lower DTI). R13-5 (Euler depth-to-source) stays deferred. Report: [`reports/holdout_r13_2026-10-01.json`](reports/holdout_r13_2026-10-01.json).

### 3. The finding that changes the plan: a fault-blind lattice beats every recipe on the proxy
[`scripts/null_baseline_holdout.py`](scripts/null_baseline_holdout.py) scores content-free maps on the same folds ([`reports/null_baseline_2026-10-01.json`](reports/null_baseline_2026-10-01.json)):

| map | DTI mean (18 folds) |
|---|---|
| everywhere = 1 | 0.0165 |
| random 5 % + spacing-3 decimation | 0.0902 |
| `topo_05_sp3` (R10–R12 reference) | 0.0933 |
| `greedy_r11` (previous holdout best) | 0.0988 |
| square lattice, every 4th / **5th** / 6th pixel | 0.0999 / **0.1122** / 0.1022 |

The kernel pays for being *within ~300 m* of a fault and Tversky β = 0.8 punishes misses four times harder than false alarms, so evenly spread coverage earns a lot and the topographic/geophysical crest maps carry little pixel-level catalogue information (full-catalogue AUC 0.50–0.58, in the R13 report). The lattice idea is **post-hoc in origin** (disclosed in the register, addendum A); it was then run under the *frozen* rule: `sq5` **WINS** — confirm worst-rule 0.1059 vs 0.0917, 6/6 rules, **18/18 paired folds**. Hybrids (lattice ∪ greedy_r11) lost to both `greedy_r11` and `sq5` (they predict twice the mass); triangular lattices scored slightly below square ones (`hex5` 0.1040 vs `sq5` 0.1059), so the covering-radius argument did not help. [`reports/holdout_r13_lattice_2026-10-01.json`](reports/holdout_r13_lattice_2026-10-01.json).

Per repository doctrine the holdout best gets the slot, so the lattice is file **A**. **Caveat that matters:** the proxy hides *known* faults; the leaderboard truth is *faults not in the catalogue* (I-10, I-16). Whether coverage transfers is unproven — **one leaderboard score is the experiment.** If A scores about the same as past files, the repeated 0.1563 is a coverage plateau and the next gains must come from information layered *on* a lattice; if A scores much lower, the proxy is the problem and the research priority flips to a new-fault proxy.

### 4. Why do we keep scoring 0.1563? (evidence tiers)
1. **Several repos hold the very same file (verified).** `GEMSDOE` (`data/evidence/runs/ens12-adopted-floor0.1-w0/submission.tif`), `5GEMSDOE` (same path, plus `data/evidence/leaderboard_anchor/gemsdoe-ens12-adopted-7f00890a.tif`) and `GEMSDOE2` (same path, plus `docs/gemsdoe2-recall-arm-7f00890a.tif`) all carry the identical git blob `812e61b74050d1350cc2bde1fab0c76ead32e0c4` (570,890 bytes), which is also `data/scored/gemsdoe1_ens12_LB0.1563.tif` here (checked with the GitHub trees API and `git hash-object`, 2026-10-01). Identical bytes score identically — if 5GEMSDOE (or GEMSDOE2's "recall arm") uploaded it, that 0.1563 is a copy (the folder and file names say so; no receipt proves any upload) (**I-20**).
2. **8GEMSDOE is a different map.** Its `gems8_apex` (blob `d3aac36c…`) shares 6.7 % of positive support with ens12 (Pearson −0.55; 91 % of its mass on/near the catalogue vs 20 %) — [`reports/scored_forensics.json`](reports/scored_forensics.json). Duplication does not explain it.
3. **The leaderboard column is an account-level best** ("Best public DW-Tversky"); it only moves when a submission beats it. Any run of weaker later uploads leaves 0.1563 on display. No per-file receipt exists (I-3).
4. **Hypothesis (new, unproven):** the metric is coverage-dominated (section 3), so very different maps can land at the same value. Consistent with item 2, not proven by it.

### 5. Limitations — what I could not do or verify
* **I cannot observe DrivenData's validator or submit** (no credentials, login-gated pages); the cause of the "[0, 1]" rejection is unknown and A/B is a hedge.
* **No per-file public score exists** for any file in this repo; all "0.1563" labels are team-recorded.
* **The proxy is not the leaderboard** (I-10, I-16), and section 3 shows it rewards coverage geometry. Every holdout "win" so far is measured against weak references.
* The crest/geophysics maps have near-chance pixel-level catalogue AUC; **I have not shown that any geological detector finds uncatalogued faults.**
* R13-6 is post-hoc in origin; ten challengers were searched in the main batch (guard: ≥ 14/18 paired folds).
* Sandbox: 3.9 GB RAM (I-17), no direct egress to `gdr.openei.org`/`usgs.gov` (a GitHub runner fetched GDR 1391 instead); a 30-map greedy was not run. No supervised/U-Net model was trained this session.
* Eligibility/licence questions for external data (CC-BY-4.0 GDR 1391) should be confirmed against the official rules before any final selection.

### 6. Suggestions / next steps (ranked)
1. **Submit A (lattice), then the 2nd candidate**, one per slot; record each response in [`reports/form_responses.json`](reports/form_responses.json) and the score in `reports/leaderboard_ledger.csv`. Keep the third slot in reserve. If A is rejected, try B, then email info@drivendata.org with the exact error (the forum names that address for technical help).
2. **R14 information on top of a lattice:** replace, don't union (union doubled the mass and lost) — e.g. stride-4 sampling inside the top-decile of the best information maps, stride-5/6 elsewhere; tune stride/phase on tune folds only.
3. **R13b:** re-tune the greedy blocks on the `persist_gm` base (Stage A won 17/18).
4. R13-4 follow-ups: 2-m temperature-probe halos (staged, unused), halo × lattice.
5. R13-5 Euler depth-to-source; per-domain budgets; 30-map greedy on a larger runner.
6. Build a **new-fault proxy** (e.g. hide whole USGS faults far from any visible one) so the gate is not coverage-dominated.

### 7. New irregularities (details in `knowledge/02_irregularities.md`)
I-17 RAM cap · I-18 TIFF PREDICTOR=2 untested cause · I-19 `latest.tif` was the rejected file · I-20 shared blob 812e61b7 · I-21 the proxy is coverage-dominated (null lattice > recipes).


## Previous review — 2026-09-30, session 6 (R12: the gate held; download encoding changed)

The team uploaded the NaN-outside primary `13gems-r11-greedy-mp.tif` and the DrivenData
form rejected it with **"Predicted values must be in range [0, 1]"**
([`reports/form_responses.json`](reports/form_responses.json)). Session 6 served an
"all-finite" variant (`..._allfinite.tif`) as the default. **Correction (session 7):**
that variant was never confirmed accepted by the form, and `latest.tif` was found to be
byte-identical to the *rejected* NaN file (irregularity I-19). Both legacy files now live
in `docs/downloads/archive/`; use the A/B files above.

**Irregularity I-8 partially resolved, new flag.** NaN-outside files from this
group *were* accepted and scored earlier — the pindrop trio recorded by sha256
prefixes `f347b70daa` / `37f9d5b855` / `4e03fc9705`, each re-verified this session
against the archived bytes in `data/scored/` — so the platform's range validation
**changed or is inconsistent**. That behaviour is external and cannot be observed
from here; flagged for review in
[`knowledge/02_irregularities.md`](knowledge/02_irregularities.md) (I-8) and
[`reports/form_responses.json`](reports/form_responses.json). Every future form
response must be appended there, and the receipt to `reports/leaderboard_ledger.csv`.

**R12: three new hypotheses predeclared before any fold was scored**
([`knowledge/08_r12_hypotheses.md`](knowledge/08_r12_hypotheses.md)) —
R12-1 *hysteresis crest continuation* (Canny-style two-threshold linking on the
`BASE_topo_ridge` ridge-strength field — the repo's first connectivity transform),
R12-2 *finer-step greedy over a widened 12-map pool* (0.10 % blocks, ≤ 6 steps),
R12-3 *basin-floor magnetics retested at its true support* (resolves R11-2's I-14
invalid measurement). Euler depth-to-source was declared and **deferred**, not run.

**Result: the gate held — nothing beat `greedy_r11`, so no slot was spent and the
artifact is unchanged.** Protocol regression check PASSED with **zero** drift (the
pinned `requirements.txt` versions eliminated I-15 this session). Challengers
(confirmation worst-rule-mean DTI): `greedy_r12` 0.08824 (**LOSES**, 0/18 paired
folds), `basinmag0001` 0.08623 (LOSES — first *valid* R11-2 measurement),
`hyst_add005/010/020` 0.08219 / 0.07909 / 0.07354 (LOSE with a clean dose-response
— recall rises to 0.3453 while marginal weighted precision stays below the metric's
`0.2 × DTI` inclusion bar). `greedy_r12`'s step 1 found the highest-precision block
ever measured (`R10_vent@0.10 %`, pooled marginal precision 0.0324) but the frozen
one-block recipe is a strict subset of R11's assembly — precision above the bar is
necessary, accepted mass must still move the worst rule.
Report: [`reports/holdout_r12_2026-09-30.json`](reports/holdout_r12_2026-09-30.json).

**Leaderboard (official public page, re-fetched 2026-09-30):** DARD 0.3168 (#1),
alexoktaba 0.3042 (#2), joeyfezster 0.2919 (#3) —
[`reports/leaderboard_snapshot_2026-09-30.json`](reports/leaderboard_snapshot_2026-09-30.json).
Account-level bests, not receipts.

### Next steps (session 6 list; item 1 superseded by the A/B files at the top)
1. **Upload file A at the top of this page** (or its .zip), with the printed name/note; append the form response to
   `reports/form_responses.json` and the score to `reports/leaderboard_ledger.csv`.
2. **New physics, not finer re-cuts** (R12's closing finding): candidates that can
   reach neighbourhoods the ridge family never touches — R12-4 Euler
   depth-to-source clusters (declared, deferred), per-domain budgets, and
   R11-3 GDR-1391 paleo-geothermal halos (need egress to
   [gdr.openei.org/submissions/1391](https://gdr.openei.org/submissions/1391)).
3. **Full 30-stem pool greedy** on a larger-RAM runner (I-17: this sandbox's 3 GB
   caps the in-memory pool at 12 ranked maps).
4. **Hysteresis inside the greedy**, not beside it: R12-1's linked pixels are only
   admissible through the marginal-precision gate (per-block), never as a flat
   budget add-on — the only lesson consistent with both R11 and R12.
5. Store map sha256 in `reports/detectors_manifest.json` (closes I-15 bookkeeping
   now that builds reproduce exactly).

### Previous review — 2026-09-30, session 5 (R11: first holdout WIN)

**R11-4 greedy marginal-precision assembly — WINS** (predeclared in
[`knowledge/07_r11_hypotheses.md`](knowledge/07_r11_hypotheses.md) before any fold was
scored). Starting from `topo_05_sp3`, each candidate block is restricted to pixels
**> 300 m from everything already predicted** and accepted only while its pooled tune-fold
marginal weighted precision exceeds `0.2 × DTI` (audited inclusion rule). Accepted:
`R10_vent`@0.25 % → `R8_tpi`@0.25 % → `R10_dzt_field`@0.25 %; step 4 failed the bar → stop.
Confirmation worst-rule-mean DTI **0.09175 vs 0.08694** (+5.9 % mean), 6/6 rule means,
**18/18 paired folds**. First recipe in 25 challengers (R8–R11) to clear the gate.
Report: [`reports/holdout_r11_2026-09-30.json`](reports/holdout_r11_2026-09-30.json).

**Flags for review (from session 5).** I-15: rebuilt detector caches reproduced archived
reference DTI only to ≤ 0.17 % (unpinned library versions) — verdicts are paired in-run and
the gain had to beat 10× drift; versions pinned in `requirements.txt` (this session the
drift measured exactly 0.0). I-16: the win is on hidden *known* faults; the public score is
the real test. R11-2 (basin magnetics) was invalid at R11 coverages (I-14) — retested
validly in R12 (LOSES; see above). Still no DrivenData credentials here: the upload is a
manual step (see the executive summary).

### Previous review — 2026-09-30, session 4 (R10 / R10b: official external data)

This session went outside the provided 19 bands for the first time, under the
standing rule that external data must be **free, official, licence-clean and
verifiably obtainable** before any code is written around it.

**Data staged and verified.** Six USGS public-domain products were re-staged from
this group's sibling repositories by `scripts/fetch_external_data.py` and verified
twice each (sha256 from the sibling provenance record **and** git blob SHA-1 from
the sibling tree): 3DEP 1-m LiDAR morphometrics (12 bands), GeoDAWN radiometrics,
GeoDAWN derivative extensions, a 9-band topographic morphometric set, and the
QFFDB prior (analysis-only — leakage risk). Pins: `reports/external_manifest.json`,
provenance: `reports/external_provenance/` (11 records). Licence check: USGS work
is public domain, which satisfies the organiser's condition that participants hold
"a license that permits the data to be used in this challenge and shared with the
sponsor" ([forum 11528](https://community.drivendata.org/t/paid-for-external-data-license/11528)).
All six grids conform exactly to the competition grid (EPSG:32611, 100 m,
3730×3292) — `reports/external_audit.json`.

**Four hypotheses predeclared before any map was built**
([`knowledge/06_r10_hypotheses.md`](knowledge/06_r10_hypotheses.md)), ranked by
expected ΔDTI ÷ cost: R10-3 damage-zone texture (3DEP slope_std × profile
curvature), R10-1 1-m LiDAR morphometric scarp composite, R10-2 radiometric
alteration-ratio lineaments (U/K, U/Th), R10-4 geothermal-vent conjunction
(scarp × alteration × conductance × shallow conductive base). Two further
candidates were screened out on measurement before build: the QFFDB-minus-catalogue
difference (**1 pixel** — dead) and a LiDAR-coherence channel (AUC 0.4608 — below
chance).

**Result: every one of the 24 challenger configurations LOSES**
(16 in R10, 8 in R10b) against the paired reference `topo_05_sp3`
(confirmation worst-rule mean **0.08687**). Best challenger 0.08593
(`topo05_plus_alter02_sp3`), best fixed-budget fusion 0.08286
(`fuse_vent_w050_sp3`). Protocol regression checks passed in both runs; all 468
scored rows report `tie_fraction` 0.00. **No submission slot was spent.**
Reports: [`holdout_r10_2026-09-30.json`](reports/holdout_r10_2026-09-30.json),
[`holdout_r10b_2026-09-30.json`](reports/holdout_r10b_2026-09-30.json).

**Why, measured rather than asserted.** The external maps are *better pixel
classifiers than any provided band* (AUC 0.5282–0.5770 vs 0.5615 for
`geod_shearrate`) and still lose, because the marginal weighted precision of the
pixels they add — 0.0094–0.0166 depending on block and coverage — sits below the
metric's own inclusion bar `0.2 × DTI` (0.0169 tune / 0.0195 confirmation).
External evidence buys **precision** (0.0294 vs 0.0276 at 19 % fewer pixels for
the w = 0.5 vent fusion) and spends **recall** (0.2487 vs 0.2874); under β = 2
that trade is a wash at best. Carried forward as
[irregularity I-13](knowledge/02_irregularities.md): *univariate AUC is not a
go/no-go signal in this competition*, and only a product that reaches fault
neighbourhoods the topographic crest never touches can raise DTI.

**One irregularity resolved on the way — I-2.** Band 6 `tc` is the **radiometric
total count**, measured against the official USGS grid: Spearman ρ 0.99998,
Pearson r 0.99902, OLS slope 1.0073, R² 0.9980, median ratio 1.00000, matching
percentiles, plus the physical closure test band6 ≈ 7.54 × (K + Th + U) at
ρ 0.9958. Its embedded description ("Tilt angle or total curvature — magnetic
field derivative for edge detection") does **not** describe the array. The earlier
"disproved" verdict rested on an unverified units assumption and is retracted in
place, with the reasoning preserved
([`reports/band6_identity.json`](reports/band6_identity.json),
`scripts/audit_band6_identity.py`). The same match independently validates our
external staging pipeline: the sibling re-gridding reproduces the field the
organisers shipped.

New organiser statements verified verbatim this session: the submission allowance
resets on a **rolling window** (11524), the Official Rules take precedence on team
eligibility (11540), the label TIF has **one** band and the reference notebook's
"19 bands" is a printing bug (11529). The downloadable artifact is unchanged:
**`13gems-toporef-holdoutref.tif`**.

### Previous review — 2026-09-30, session 3 (R9)

Three new geological hypotheses were implemented, predeclared, and measured on the
paired holdout this session — none beat the local best, so the reference recipe was
shipped as the primary downloadable artifact instead.

* **R9-1 strike-aligned gap completion** (`strike_gap_close`): strict variant is
  inert (+32 px/fold, exact tie); the loose variant adds ~145,600 px/fold for
  **ΔDTI −0.0257** — its marginal weighted precision sat below the metric's own
  `0.2 × DTI` inclusion bar (audit A5), so the loss was predicted by the audited
  algebra and then measured.
* **R9-2 epicentral-alignment lineaments** (`eq_lineaments`, bands 16+10):
  +16,590 px/fold for ΔDTI −0.0021. The first detector whose primary signal is
  the seismicity fields themselves.
* **R9-3 parallel-offset "correction" edges** (`parallel_offset_correction`):
  near no-op (+26 px/fold) — the physics-gated corridor conjunction almost never
  fires; recorded as a negative result, not evidence about the hidden truth.

All three **LOSE** under the predeclared rule
([`reports/holdout_r9_2026-09-30.json`](reports/holdout_r9_2026-09-30.json));
the protocol regression check passed (the reference row reproduces the archived
per-fold DTI values exactly). No submission slot was spent. The downloadable
artifact is now **`13gems-toporef-holdoutref.tif`** — the exact `topo_05_sp3`
reference configuration (BASE_topo_ridge top-5 %, 300 m grid decimation, binary,
catalogue included), format-validated, duplicate-checked against all eight
archived historical maps, with the form's name and note printed on the front
page and a triage table for the historical
“Predicted values must be in range [0, 1]” rejection
([irregularity I-8](knowledge/02_irregularities.md)).

The official leaderboard fetched on 2026-09-30 showed DARD 0.3168 (#1) and
alexoktaba 0.3042 (#2), not the prompt's 0.3049. These are account-level best
public scores, not receipts for our local TIFFs.

## The 60-second orientation

| Question | Answer | Where |
|---|---|---|
| What is the metric, really? | A **distance-weighted F2 score**. `DTI = 1/(0.2/P + 0.8/R)`. Proved, not asserted. | [`reports/metric_audit.json`](reports/metric_audit.json) |
| Why do historical files carry the same 0.1563 label? | **Unresolved as a score question; settled as a file question.** The two 0.1563-labelled files are different maps (support IoU 0.067); the leaderboard column is an account-level best, not a per-file receipt. Rounded score equality is not map identity and not evidence of copying. | [Irregularity I‑3](knowledge/02_irregularities.md) · [`reports/scored_forensics.json`](reports/scored_forensics.json) |
| Can public scores be compared with the local chance baseline? | **No.** Public inference from account-best scores is withdrawn. `dti_chance()` is retained only for an approximate same-run random-control sanity check with known local truth and the eligible fold domain. | [Irregularity I‑9](knowledge/02_irregularities.md) |
| What should a submission look like? | Use the exact marginal rule `ΔTP_w/(ΔTP_w+ΔFP_w) > 0.2 × DTI` for the same evaluation set; select cutoff, coverage, spacing, and fusion on the holdout rather than from unverified public labels. R9 measured the rule: mass below the bar loses exactly as the algebra says. | [`knowledge/01_verified_facts.md` §2.1](knowledge/01_verified_facts.md) |
| How do we check an idea before a submission slot? | Use whole-system and segment hide-and-recover folds with buffers, visible-catalogue-only feature construction, an exact known-fault mask, withheld-truth-only DTI, and multiple rules. The low-slope slice is a stress test—not hidden-test ground truth. | [`src/gems/holdout.py`](src/gems/holdout.py) · [`reports/holdout_r9_2026-09-30.json`](reports/holdout_r9_2026-09-30.json) |
| Is the current downloadable artifact cleared to submit? | **Yes, under the predeclared local gate** — `greedy_r11` beat the reference on tune and confirmation worst-rule-mean DTI (18/18 paired folds), labelled `CLEARED_LOCAL_HOLDOUT_WIN_NOT_PRIVATE_TEST_CLAIM`. No challenger since (R12: 5 configurations) has beaten it. It is a catalogue hide-and-recover proxy, **not** a predicted leaderboard score. | [`reports/latest_submission.json`](reports/latest_submission.json) · [`reports/holdout_r11_2026-09-30.json`](reports/holdout_r11_2026-09-30.json) |
| Which file encoding should be uploaded? | The **all-finite** one (front-page primary button): every cell in [0,1], 0.0 outside the footprint — passes strict and naive validators, score-neutral for a binary map. The form **rejected** the null/NaN-outside encoding on 2026-09-30; earlier it had accepted it. Validator behaviour flagged as changed/inconsistent. | [`reports/form_responses.json`](reports/form_responses.json) · [I-8](knowledge/02_irregularities.md) |
| Do the free official USGS products help? | **Measured: not on Phase-1 DTI.** Six hash-verified products, four predeclared hypotheses, 24 challenger configurations — all lose to `topo_05_sp3`. They beat every provided band on AUC and still fail the metric's marginal-precision bar. Their remaining value is Phase-2 defensibility. | [I-13](knowledge/02_irregularities.md) · [`reports/holdout_r10_2026-09-30.json`](reports/holdout_r10_2026-09-30.json) |
| What is band 6 (`tc`)? | **Radiometric total count**, measured against the official USGS grid (ρ 0.99998, R² 0.9980, slope 1.007, closure vs K+Th+U ρ 0.9958). The embedded "tilt angle or total curvature" description is wrong. | [`reports/band6_identity.json`](reports/band6_identity.json) · [I-2](knowledge/02_irregularities.md) |
| How do I actually submit? | Click the front page's first button (all-finite GeoTIFF), paste the printed name and note into the form, and follow the five steps (including the recorded-response triage path). | [Executive summary](docs/executive_summary.html) · [`reports/form_responses.json`](reports/form_responses.json) |

---

## The four results that should drive every decision

All four are machine-verified in `scripts/audit_metric.py` (`ALL CHECKS PASSED`)
and reproduce the organizers' own worked example (TP_w 3.00, FP_w 1.89,
FN_w 2.00 → 0.60).

1. **`FN_w ≡ |G| − TP_w`**, so `DTI = TP_w / (0.2·TP_w + 0.2·FP_w + 0.8·|G|)`
   and equivalently `DTI = 1/(0.2/P_w + 0.8/R_w)`. Since `β² = 4`, **DTI is a
   distance-weighted F2 score.**
2. **Inclusion rule.** A block of predictions raises DTI **iff** its
   marginal weighted precision exceeds `0.2 × DTI` for the same evaluation set.
   The historical 0.1563 file labels are not verified per-file scores. At the
   official account-level leader value 0.3168, the arithmetic is 6.3%—an
   illustration only, not a threshold for any local or private-test map.
3. **Binary is optimal.** `DTI(c·p) = TP/(0.2TP + 0.2FP + 0.8|G|/c)` strictly
   increases in `c`, and a pixel exactly on truth has `k(0)=1` so it costs zero
   FP mass. Graded values are only useful for *ranking* pixels.
4. **Recall dominates** whenever `P_w > 0.25 · R_w`. Elasticities always sum
   to 1, so this is a hard crossover, not a heuristic.

**Geometry corollary.** `TP_w` takes a **max** over nearby predictions for each
truth pixel. Once that pixel's credit is saturated, a redundant neighbour may add
FP mass without more credit for that truth; another truth pixel nearby may still
benefit. Tune cutoff, line spacing, ridge width, and fusion on the multiple-rule
holdout; do not assume a universal 300 m decimation.

---

## Repository layout

```
PROJECT_CHARTER.md        standing brief — read first, every session
knowledge/
  01_verified_facts.md    every fact with the official URL it came from
  02_irregularities.md    things that are wrong or unverifiable, with actions (I-1..I-21)
  03_hypotheses.md        candidate geological hypotheses, ranked
  04_geothermal_vents.md  vent science from official sources (contrarian, cited)
  05_hypothesis_screen_2026-09-30.md   screened-out candidates and why
  06_r10_hypotheses.md    R10/R10b predeclared register, decision rule, results
  07_r11_hypotheses.md    R11 predeclared register (greedy marginal-precision WIN)
  08_r12_hypotheses.md    R12 predeclared register (hysteresis / finer greedy / basin retest)
src/gems/
  metric.py               the official DTI, transcribed and audited
  fastscore.py            exact fast scorer (verified == metric.py)
  holdout.py              hide-and-recover fold construction
  detectors.py            the physical-signature detectors (H-A..H-E, R6-*, R7-*, R10-*)
  external.py             provenance-driven loader for data/external (no hand-typed constants)
  supervised.py           supervised baselines
  rio.py                  raster I/O + the strict submission validator
tests/                    43 unit tests: rio, R9, R10 detectors (`unittest discover -s tests`)
scripts/
  fetch_data.py           reconstruct data/raw from official + mirrored sources
  fetch_external_data.py  stage + double-verify the six official external products
  audit_external.py       grid conformance, catalogue gap, band identity, channel novelty
  audit_band6_identity.py settles I-2: band 6 vs official TC, with the closure test
  build_external_detectors.py  the eight R10 maps + per-map AUC/top-5% manifest
  validate_r10_holdout.py      predeclared paired validation of the four R10 hypotheses
  validate_r10b_holdout.py     predeclared refinement round: low-coverage unions + rank fusion
  validate_r11_holdout.py      predeclared R11 validation (greedy marginal-precision WIN)
  validate_r12_holdout.py      predeclared R12 validation (hysteresis / finer greedy / basin)
  flip_primary_encoding.py     one-time recorded flip: all-finite becomes the upload default
  audit_metric.py         proves the four results above
  audit_bands.py          measures what the 19 bands actually are; tests I-2
  analyze_scored.py       file/pixel identity and support for historical TIFFs; score labels unverified
  chance_baseline.py      local random-map DTI only when holdout truth size is known
  build_detectors.py      compute and cache every detector map
  run_holdout.py          the v1 sweep
  run_holdout2.py         the v2 sweep (concealed subset, grid decimation)
  run_holdout3.py         the v3 sweep: R7 detectors + per-fold catalogue rebuild
  validate_ensemble_holdout.py  R8 recipe vs baseline (visible-only, paired)
  validate_r9_holdout.py  paired predeclared validation of the R9 hypotheses
  summarize_holdout.py    direct-DTI ranking; local random-control sanity check only
  validate_composite.py   two-regime validation of the shipped hedge
  make_submission.py      build + identity-check + format-validate; never grants score clearance
reports/                  machine-readable evidence for every claim
  form_responses.json     append-only log of DrivenData form responses (encoding evidence)
  primary_flip_2026-09-30.json   byte-level record of the all-finite primary flip
  leaderboard_snapshot_2026-09-30.json  official public leaderboard snapshot (re-fetched)
docs/                     generated GitHub Pages site (`scripts/build_site.py`), served at /docs/
```

---

## Local proxy evaluation and review status (2026-09-30)

All results below are local catalogue hide-and-recover measurements, **not**
public/private leaderboard performance. Use `.venv/bin/python`; system Python
in this workspace lacks the scientific dependencies.

* `scripts/audit_metric.py` → **12/12 checks pass**, including a numerical
  reconstruction of the official worked example. This verifies the DTI algebra,
  not hidden-test performance.
* `scripts/build_detectors.py` → 29 input-derived detector maps built in about
  502 seconds. Generated `data/derived/` is local/ignored.
* `scripts/chance_baseline.py` → public chance/lift inference remains
  **withdrawn** because it inferred hidden truth size from account-level scores
  and reused that estimate. The helper is retained only for a limited local
  random-control sanity check with known truth and each fold's eligible area; it
  is not a candidate-ranking or submission-clearance metric.
* `scripts/summarize_holdout.py` → candidate tables rank by direct worst-rule
  mean DTI, using confirmation rows when available. Historical candidate-to-chance
  ratios with a full-grid denominator are withdrawn; the low-slope slice is a
  robustness test, not a hidden-test analogue. See
  [`knowledge/03_hypotheses.md`](knowledge/03_hypotheses.md) and I-9/I-11.
* `scripts/analyze_scored.py` → eight historical TIFFs have exact file, canonical
  pixel, support, and unmasked-support hashes in
  `reports/scored_forensics.json`. The two files with historical 0.1563 labels
  have different file/pixel hashes (support IoU 0.06703; unmasked-support IoU
  0.06232). These labels are not receipts; no score is attributed to a local
  file. High overlap also does not mean exact duplicate (for example, the
  ens12/dualunion support IoU is 0.94191, but their file and pixel hashes differ).
* `scripts/fetch_external_data.py` → six official products staged into
  `data/external/` (~150 MB, gitignored), each verified against a pinned sha256
  **and** a pinned git blob SHA-1; `reports/external_manifest.json` records both.
* `scripts/audit_external.py` (streaming, one channel at a time — a first version
  was OOM-killed on this 3.9 GB box) → grid conformance for all six products,
  the QFFDB catalogue gap (**1 px**, hypothesis dead), band identity against
  official channels, per-channel AUC/novelty, and the 3,205,306-px common domain.
* `scripts/build_external_detectors.py` → eight R10 maps in `data/derived/`
  (43 s) plus `reports/external_detectors_manifest.json`.
* `scripts/validate_r10_holdout.py` / `validate_r10b_holdout.py` → 306 + 162
  paired fold scorings, both protocol regression checks PASS, all challengers
  LOSE (see the session-4 review above).
* `scripts/audit_band6_identity.py` → I-2 resolved (28 s).
* `scripts/validate_ensemble_holdout.py` → tested a visible-only reconstruction
  of the archived R8 recipe against `BASE_topo_ridge|cov0.05|sp3`. The report
  uses 15 whole-system folds across five withholding rules plus three raw
  8-connected segment folds, about 25% withheld fault mass, and a 5-pixel
  buffer. Catalogue-derived rays/horsetail features are rebuilt from each fold's
  visible catalogue; the visible-fault mask is pixel-exact, predictions are
  scored on withheld truth only, and a separate lowest-slope-third slice is
  treated as a stress test. See
  [`reports/holdout_candidate_r8_2026-09-30.json`](reports/holdout_candidate_r8_2026-09-30.json).

On the held-back confirmation folds, the local topo baseline scored worst-rule
mean DTI **0.08687** / overall mean **0.09763**, with mean weighted precision
0.0276 and recall 0.2874. The per-fold R8 union scored **0.05584** / **0.06615**,
with precision 0.0161 and recall 0.3292. Its effective positive support was
about 7.16% of the fold evaluation domain versus 3.62% for the topo baseline.
None of the tested coverage, spacing, width, and fusion variants beat that
baseline on the confirmation summary. These numbers concern catalogue recovery
under this protocol only; they do not predict the undisclosed target. The archived
full-catalogue raster is not itself holdout-scored because that would leak its
catalogue-derived tip/horsetail geometry.

**Submission decision (2026-09-30, session 4 — unchanged from session 3):** no R10
or R10b challenger passed the predeclared gate, so no slot is spent and the
recommendation stands.

**Submission decision (2026-09-30, session 3):** the primary downloadable artifact is
`13gems-toporef-holdoutref` — the reference recipe itself (`BASE_topo_ridge` top-5 %,
`decimate_grid` spacing 3, binary, catalogue included). It is labelled
`BEST_LOCAL_REFERENCE_NOT_PRIVATE_TEST_CLAIM`: local proxy evidence only, remote
acceptance unverified. Its NaN-outside GeoTIFF passes local grid, CRS, affine
transform, dtype, band-count, range, and footprint-NoData checks, and its
platform-check simulation documents how masked vs naive raw readers see the file.
The archived R8 artifact remains on disk as a demoted, NOT_CLEARED comparator.
Historical file notes/scores are not public score receipts. The official
account-level leaderboard snapshot is DARD 0.3168 / alexoktaba 0.3042 as of
2026-09-30; neither value is tied to a local TIFF.

---

## Reproduce everything

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt      # numpy, scipy, rasterio, tifffile, pillow, imagecodecs

.venv/bin/python -m unittest discover -s tests # strict submission-write regression tests
.venv/bin/python scripts/fetch_data.py        # data/raw (419 MB, gitignored)
.venv/bin/python scripts/audit_metric.py      # proves the metric results
.venv/bin/python scripts/audit_bands.py       # what the 19 bands actually are
.venv/bin/python scripts/analyze_scored.py    # file/pixel identity; labels are not receipts
.venv/bin/python scripts/audit_band6_identity.py   # settles I-2 (~30 s)
.venv/bin/python scripts/fetch_external_data.py    # stage + verify data/external (~150 MB)
.venv/bin/python scripts/audit_external.py         # grid/gap/identity/novelty audit (~140 s)
.venv/bin/python scripts/build_detectors.py   # ~7 min (418 s measured this session)
.venv/bin/python scripts/build_external_detectors.py   # the eight R10 maps (~45 s)
.venv/bin/python scripts/validate_r10_holdout.py    # predeclared R10 validation (~90 s)
.venv/bin/python scripts/validate_r10b_holdout.py   # predeclared R10b refinement (~66 s)
.venv/bin/python scripts/validate_r11_holdout.py    # predeclared R11 validation (~300 s)
.venv/bin/python scripts/validate_r12_holdout.py    # predeclared R12 validation (~215 s)
.venv/bin/python scripts/validate_r13_holdout.py    # predeclared R13 batch (~6 min; needs data/external_gdr1391, staged by the runner workflow)
.venv/bin/python scripts/null_baseline_holdout.py   # content-free lattice/random baselines (~45 s)
.venv/bin/python scripts/validate_r13_lattice_holdout.py   # R13-6 lattices (~65 s)
.venv/bin/python scripts/publish_lattice_front_door.py     # publish the lattice A/B files + list the R11 alternate
.venv/bin/python scripts/build_site.py              # regenerate docs/ + root index.html from submit.json
.venv/bin/python scripts/verify_download.py         # 47 byte-level checks (add --live after Pages rebuilds)
.venv/bin/python scripts/run_holdout3.py      # historical full sweep (~82 min, 3 GB RAM)
.venv/bin/python scripts/validate_ensemble_holdout.py # targeted visible-only ensemble holdout
.venv/bin/python scripts/make_submission.py --recipe best
```

`make_submission.py` first hashes canonical float32 scored-grid pixels and
positive support against existing download/scored TIFFs, blocking an exact pixel
duplicate (NaN and outside-footprint encodings normalize to zero). It also records
that distinct maps can still round to the same public score; no score uniqueness is
promised. The script checks the one-band float32 grid, EPSG:32611, 3730×3292 shape,
affine transform, finite in-footprint values in `[0,1]`, and supplied footprint mask.
The writer now rejects invalid predictions before opening an output file; it does
not clip bad values or silently turn in-footprint NaNs into zeros.
Session 7: `make_submission.py` now publishes through `gems.frontdoor.publish` — an A file (0.0 outside
the footprint, no NaN, no NoData tag) and a B file (NaN outside), both LZW/striped/no predictor like the
official example, each re-read with three TIFF readers before anything is released. Local checks do not
prove remote acceptance; the historical server-side range rejection remains unexplained.

**A unique, format-valid GeoTIFF is not automatically a *beating* candidate.** Every
artifact built by the script carries an explicit clearance field. The current
`--recipe topo_ref` artifact is the holdout reference itself and is labelled
`BEST_LOCAL_REFERENCE_NOT_PRIVATE_TEST_CLAIM`; anything built from an untested recipe
is marked `NOT_CLEARED` until it beats the reference under paired direct-DTI
multi-rule confirmation. Check `submission_clearance` and the latest holdout report
before using a submission slot. The writer rejects invalid predictions before opening an output file; it does not clip bad values or silently turn in-footprint NaNs into zeros.

---

## Standing rules for this project

1. **No submission slot is spent on an idea that has not beaten the current
   best on the hide-and-recover holdout.** Three submissions per week, total
   ([Official Rules §3.2](https://docs.nlr.gov/docs/fy26osti/96647.pdf)).
2. **A candidate that wins under only one withholding rule is fragile** and is
   reported as such. The legacy `make_submission.py --recipe best` selector uses
   `reports/holdout_results.json` and the worst-rule DTI there; it does not read
   the newer R8 comparison report or confer submission clearance.
3. **Every factual claim carries the official URL it came from.** If it cannot
   be verified from a public official source, it goes in
   `knowledge/02_irregularities.md` marked `UNVERIFIED`, not into the analysis.
4. **Rank candidate variants by direct, paired holdout DTI—not chance ratios.**
   A same-fold random-map DTI may be shown as a limited local control only when
   its actual support, withheld-truth size, and eligible eval-domain are known;
   do not treat the approximation as universal calibration, a submission gate,
   or a public/private baseline. Never infer truth size or chance from leaderboard
   scores.
5. **Never repeat an identical prediction as a new submission.** The builder
   checks canonical pixel identity against existing maps; distinct maps can still
   round to the same score, so no unique-score promise is made.
6. **Phase 2 is 83 % of the money** and its labels are built from *our own*
   predictions by expert review. A defensible, geologically-argued map is worth
   more than a leaderboard-tuned one.

---

# STANDING BRIEF — verbatim, read at the start of every session

> Audit the score before the model. Because the official FN_w equals |G| − TP_w,
> the distance-weighted Tversky index (DTI) reduces to
> TP_w / (0.2·TP_w + 0.2·FP_w + 0.8·|G|). That is a weighted harmonic mean of
> weighted recall (weight 0.8) and weighted precision (weight 0.2). Confirm it
> against the problem page's worked example (TP_w 3.00, FP_w 1.89, FN_w 2.00 →
> 0.60) and our local metric. Three consequences to test:
>
> A block of predictions raises the score only if its marginal weighted
> precision, ΔTP_w / (ΔTP_w + ΔFP_w), exceeds 0.2 × the current DTI. The best
> map is therefore probably far more inclusive than a calibrated 0.5 cutoff.
>
> Scaling all values up toward 1 always raises DTI, so the optimum is probably
> near-binary, with graded values useful mainly for ranking pixels.
>
> A relative gain in recall outweighs the same relative gain in precision
> whenever precision exceeds a quarter of recall. Settle "precision versus
> coverage" numerically rather than by assertion.
>
> Choose the cutoff, line spacing, ridge width and detector fusion by maximizing
> expected DTI on the holdout. TP_w takes a max over the 300 m neighborhood, so
> redundant nearby predictions add false-positive mass without extra credit.
>
> Rebuild validation around what the organizers have said officially. As of
> Sept 27, 2026, the DrivenData organizer on the forum (chrisk-dd) has stated
> four things:
>
> Known USGS/INGENIOUS fault pixels are masked from scoring in both rounds,
> using a pixel-exact mask identical to the training labels.
>
> A predicted pixel just beside a known trace is still fully penalized unless it
> is near a new-fault pixel.
>
> New-fault pixels can lie within 300 m of known traces.
>
> "New fault" means any fault pixel not already captured, including extensions,
> splays, parallel strands and corrections.
>
> These are in the "Scoring clarification" and "Where do you draw the line?"
> threads. The organizers declined to say which data or fault types the test
> faults came from, so any belief about how they were labeled is a hypothesis.
>
> Build a hide-and-recover holdout that mirrors this:
>
> Withhold whole fault segments or systems, with a buffer.
> Derive every catalogue-based feature only from what stays visible.
> Mask the visible faults exactly as described.
> Score DTI on the withheld pixels alone, under several withholding rules
> (random, short, isolated, and by age or slip-rate class where attributes
> exist). Flag any idea that wins under only one rule as fragile.
>
> Keep geographic block CV as a stress test, not the main check. The submission
> shares the training features' bounds and the test sets are chunks of the same
> region, so the real shift is unmapped faults among mapped ones, not new
> geography. Nothing gets a weekly submission slot until it beats the current
> best on this holdout.
>
> We need to figure out why we keep scoring 0.1563, are we copying the same work
> over and over again? we need to come up with different ideas, and not just the
> same idea tried a different way. Need to figure out why 5GEMSDOE and GEMSDOE1
> have the same score. We should not be generating the same score submissions,
> they should all be unique.
>
> Before implementing, generate 3–5 candidate geological hypotheses we haven't
> tried yet, each naming: the specific layer(s) involved, the physical signature
> being targeted (e.g., an edge-detection or curvature transform), why it should
> catch a fault missing from the USGS/INGENIOUS catalogue rather than one
> already in it, and how it differs from anything already implemented in this
> repo. Rank them by expected DTI improvement and implementation cost. Validate
> the top candidate on our spatially-blocked holdout set before touching a
> weekly submission slot — do not spend a submission slot on an idea that hasn't
> beaten the current holdout best. If a candidate can't be validated without new
> external data, name the specific free, official source needed and check it's
> obtainable before proposing the idea as viable.
>
> Work line by line verifying from official verified trusted sources, provide
> links for manual review. There should be no manual input, work on your own to
> complete tasks. Flag any irregularities for review. No hallucinations.
>
> The goal of this project is to get a full list that follow our requirements.
> No hallucinations. Verify line by line.
>
> We need to start doing heavy and deep research into the part of the project
> that matters the most, which is the scientific discovery of geothermal vents.
> We should store all of our information and knowledge that we can gather from
> official verified sources. This will serve as a starting point for other
> projects as well. We need to think outside the box but still be grounded in
> proper scientific research, we are ultimately aiming for a top prize that many
> others are competing for. So it's important to be contrarian but be smart
> about it. We need to find sources of data that others are overlooking or areas
> of the project when it comes to geothermal vents.
>
> 0.3049 is the highest score right now so we need to design a new strategy,
> research, testing, analyzing, and generating submission system than the
> current website. It should be unique, take unique approaches to generating a
> submission that can score higher than .3049.
>
> Put this prompt into the repo readme and read it everytime we work on the
> project as a starting point to make sure we are building what we are aiming
> for and have a strong base to continue building and improving on making
> something useful for everyday use. It should solve the problem of having to
> manually check everything ourselves and having an up to date current feed.
>
> We need to focus on being able to generate a submission into the competition.
> The site should be able to generate a TIF file that is required for
> submission. It should be as easy as download to click a File to submit into
> the competition. This needs to be in the executive summary or the very
> beginning of the site. it should be obvious when you visit the site.
>
> I tried to submit the document that i downloaded from the site but it returned
> this error on the submission form: "Predicted values must be in range [0, 1]".
> Also we need to give it a unique name and A short comment to help you or your
> team tell submissions apart later e.g. clustering with k=25.
>
> Create a executive summary subpage that explains exactly how to make a
> submission into the contest.
>
> The goal of this project is to place top of the leaderboard in this
> competition. We need to understand the problem, collect all the data and
> organize it into a clean easily auditable table with official verified links
> for manual verification.
>
> Our Core Values: **Maximize P(Win)** — in every decision, weigh tradeoffs,
> assess risk, and choose the path that maximizes the probability of success.
> **Own the Outcome** — own results end to end, not just an individual slice;
> when problems arise and we have the means to act, act without waiting for
> permission; treat failure and success as signals.

### Session 7 addendum (2026-10-01) — paraphrase of the request, not verbatim

> The text above is the verbatim brief. For session 7 the request, condensed from the session record, was:
> put a **working, obvious, easy-to-download submission TIF at the very top of the site** (the previous NaN file
> failed with "Predicted values must be in range [0, 1]"; the form also wants a unique file name and a short note);
> keep the executive-summary subpage; **do not stop until the download works**; work autonomously, verify against
> official sources with links, flag irregularities; run in three passes (implement/verify, review, re-check against
> the request); continue the previous next steps; generate 3–5 untried, ranked hypotheses (layers, physical
> signature, why it catches uncatalogued faults, how it differs) from free official data, validate the top one on
> the spatially-blocked holdout **before** spending a slot; explain why scores repeat at 0.1563 (GEMSDOE1,
> 5GEMSDOE, 8GEMSDOE); add a limitations section and a suggestions list; finish with a PR merged into `main`.

<!-- End of preserved historical README. Use current README/corrections. -->
