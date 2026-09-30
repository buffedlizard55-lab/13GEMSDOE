# Irregularities flagged for review

Everything here was found by measurement or by fetching an official page during
this session. Each item states **what I verified**, **what I could not verify**,
and **what to do**. Nothing is asserted from memory.

---

## I‑1 🔴 CRITICAL — `example_submission.tif` is not an example submission

**Measured.** The file our pipeline has been using as the submission template,
`data/bridge/example_submission.tif` (git blob `7d865a99…`, present identically
in GEMSDOE, GEMSDOE2, GEMSDOE3, GEMSDOE4, 5GEMSDOE and as
`data/sample_submission.tif` in 6GEMSDOE), is **value-identical to
`existing_faults.tif`**:

```
example_submission finite mask == existing_faults valid mask : True
values identical where valid                                 : True
exact array equal (nan-aware)                                : True
ones in example_submission = 60,988   ones in existing_faults = 60,988
```

The official problem description says:

> "A sample submission that **predicts total fault absence** is provided for
> your reference on the data download page."
> — [problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)

Total fault absence means an all-zero raster. Ours contains 60,988 ones — the
entire known USGS/INGENIOUS catalogue.

**Why it matters.** Any pipeline that starts from this "template" and adds
predictions ships the whole known catalogue inside every submission. Per
[forum 11516 post 2](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516)
that mass is score-*neutral* (masked), so it does not directly hurt — but it
silently anchors every downstream thresholding, top‑k and normalisation step to
the catalogue, and it makes "coverage" statistics meaningless.

**Action.** Do not use that file as a template. `src/gems/rio.py` writes
submissions from the geotransform/footprint only. **Someone with a DrivenData
login must re-download `sample_submission.tif` from the
[data tab](https://www.drivendata.org/competitions/306/competition-doe-gems/data/)
and confirm whether the official file is all-zeros.** Either our mirror is
mislabelled, or the official sample is not what the page describes.

---

## I‑2 🟠 Band descriptions in the feature GeoTIFF look machine-written, and band 6 is still UNIDENTIFIED — the "radiometric total count" reading is now **disproved**

**Measured.** The 19 band descriptions embedded in
`gems-geodawn-numerical-features.tif` contain hedged, non-geophysical phrasing:

| band | embedded description | problem |
|---|---|---|
| 6 | `tc - Tilt angle **or** total curvature - magnetic field derivative for edge detection` | "or" — the writer did not know |
| 10 | `deq_n100a15 - Distance to earthquake …` | official page lists only "density of earthquakes" |
| 16 | `ieq_n100a15 - Earthquake intensity **or** density …` | "or" again |
| 15 | `depth_to_base_surf - … thickness of sedimentary cover` | official wording is "depth to conductive base surface" |

Real geophysical metadata does not say "or".

**What the earlier session claimed, and why it was wrong.** The previous
revision of this file asserted "with high confidence" that band 6 is the
**radiometric total count**. That was an inference from two true facts — that
GeoDAWN is officially *"a high-resolution lidar, magnetic, and radiometric
study"* ([Official Rules §2](https://docs.nlr.gov/docs/fy26osti/96647.pdf)) and
that the problem page's figure shows *"total radiometric counts per second"* —
plus the observation that "tc" is the standard abbreviation for Total Count.
**It was never tested against the raster.** `scripts/audit_bands.py` now tests
it, and the raster contradicts it:

1. **Band 6 is bounded in [2.953, 88.567] degrees with p99 = 29.10.** Airborne
   radiometric total count is an unbounded intensity in counts per second,
   typically 10²–10⁴. A band that never exceeds 88.6 and whose 99th percentile
   is 29.1 is not a count.
2. **Band 6 is smoother than the fields it would have to be derived from.**
   Lag‑1 autocorrelation after a 3‑px Gaussian blur: `tc` 0.9805, `rtp` 0.9836,
   `tmi` 0.9844, `tmi_hg` 0.9112, `tmi_vg` 0.8238. A "magnetic field derivative
   for edge detection" must be noisier than the field it differentiates; band 6
   is smoother than both supplied gradient bands.
3. **It is not any standard amplitude‑normalised magnetic edge angle either.**
   All eight candidates were computed and correlated against band 6
   (`reports/band_audit.json`): theta from `rtp` r = −0.0040, TDR from `rtp`
   r = +0.0177, theta from `tmi` r = −0.0029, TDR from `tmi` r = +0.0182, theta
   from `mag_anom` r = +0.0033, TDR from `mag_anom` r = −0.0324, theta from the
   supplied `tmi_hg`/`tmi_vg` r = −0.0018, |TDR| from the same r = −0.0018.
   Mean absolute differences are 18–47 degrees. **No candidate reproduces it.**

**Consequence for the code.** `HE_lin_tc` is built on the assumption that band 6
is a radiometric channel. That assumption is **disproved**, so `HE_lin_tc` must
be treated as an *unlabelled-input* lineament detector, not a radiometric one.
Its holdout numbers are still valid measurements of a detector; the geological
story attached to them is not.

**Second, separate question — settled.** Are bands 10 and 16 distances or
densities? Measured: median of `deq` inside catalogue pixels 776.8 vs 621.4
outside; `ieq` 935.1 vs 751.5 outside. Both are **higher** inside the catalogue,
so both behave as positive earthquake **intensity/density** quantities, not
distances. `HD_strain`'s use of `ieq` as a density is therefore **correct** —
no inversion bug. The two bands are near‑uncorrelated with each other
(r = 0.083), which is what makes them usable as two independent gates in R7‑3
rather than one duplicated signal.

**Action.** Confirm against the official data‑tab documentation (needs a
DrivenData login). Until then, band 6 is reported as **UNIDENTIFIED** and no
geological interpretation is attached to it.

**Addendum 2026‑09‑29 — the 51‑candidate best‑match search (`reports/band_audit.json`, 107 s).**
Rather than keep guessing, `scripts/audit_bands.py` now builds a bank of 51
physically standard transforms of the other 18 bands — gradient magnitude,
Gaussian Laplacian, 9‑px Gaussian, theta, TDR and vertical‑over‑horizontal
gradient over bands 1, 2, 12, 13, 14, 15, 17 and 19, plus theta / TDR /
vd‑over‑hg from the supplied `tmi_hg`/`tmi_vg` pair — and correlates every one
against band 6 with Spearman rho. **The best is `gauss9_b13` at rho = −0.3547**;
next are `gauss9_b19` −0.3270 and `gradmag_b12` −0.2997. Nothing reaches
|rho| = 0.5. Band 6 is therefore **UNIDENTIFIED by measurement**, on both sides:

* **For the radiometric reading (first‑party):** the problem page's figure asset
  is named `gems_tc_tmi.png` and is captioned "radiometric (left) and magnetic
  (right)", and the page's own feature list names no tilt angle and no total
  curvature — [problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/).
* **Against it (measured):** the array is strictly bounded in [2.953, 88.567]
  with p50 18.48 and p99 29.10, and is smoother than every supplied gradient
  band. A count in CPS is neither bounded at 88 nor smooth.

Both cannot be true of the same array. The two hypotheses are **not** in
conflict with each other — they are in conflict with each other's evidence, and
only the data‑tab documentation can settle it. **No code change is warranted**:
`HE_lin_tc` is already treated as an unlabelled‑input lineament detector, and its
holdout numbers (0.39–0.67 worst‑rule lift) are recorded as a measurement of
that detector, not as a radiometric hypothesis.

---

## I‑3 🔴 CRITICAL — the 0.1563 plateau is a *measurement* artefact, not a modelling plateau

Three things are simultaneously true, and together they explain the plateau.

**(a) The leaderboard column is "Best public", not "last submission".**
The column header on the
[leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)
reads verbatim: `Best public DW-Tversky (in descending order)`. Once an account
records 0.1563, it displays 0.1563 forever, regardless of what is submitted
afterwards.

**(b) Three *separate leaderboard accounts* sit at exactly 0.1563.**

| rank | account | submissions | best public |
|---|---|---|---|
| #26 | extradr19 | 3 | 0.1563 |
| #27 | SDCF9 | 3 | 0.1563 |
| #28 | smashi34 | 2 | 0.1563 |

The reported scores for GEMSDOE1, 5GEMSDOE and 8GEMSDOE are also 0.1563 —
three values, three accounts.

**(c) The two files reported as 0.1563 are not remotely the same map.**
Measured in `reports/scored_forensics.json`:

| pair | IoU of support | Pearson r |
|---|---|---|
| `gemsdoe1_ens12` vs `gems8_apex` (both reported 0.1563) | **0.0670** | **−0.546** |
| `gemsdoe1_ens12` vs `gemsdoe2_dualunion` (0.1563 vs 0.1560) | **0.9419** | — (both binary) |

Two maps sharing 6.7 % of their support and *anti-correlated* cannot produce
the same score to four decimals. Two maps sharing 94 % of their support scoring
0.1563 and 0.1560 obviously can.

**Independent corroboration.** `gems8_apex` puts **90.8 %** of its predicted
mass within 300 m of a known fault trace. The only other map that
catalogue-hugging is `gems6_hgb88` (69.5 %), and it scored **0.0286** — the
worst of the eight. Under the organizer's verified statement that a pixel near
a known trace but far from a *new*-fault pixel is "fully penalized", `gems8_apex`
should score in the same low range, not 0.1563.

**Conclusion.** `0.1563` is almost certainly the *account best* carried over
from one earlier submission, recorded three times. The team has been reading
the leaderboard's best-score column and attributing it to whatever was uploaded
most recently. **Most submissions' true scores are unknown.**

**Action (cheap, do this first).** DrivenData shows a per-submission score on
the *submissions* page of each account. Read the actual per-submission scores
and back-fill `reports/leaderboard_ledger.csv`. Until that is done, every
"which idea worked" conclusion drawn from these numbers is unsound. This is
also why the holdout in this repo exists: it is the only feedback channel we
control.

---

## I‑4 🔴 CRITICAL — apparent use of multiple DrivenData accounts (eligibility risk)

The scores reported to me match, one-for-one, the "Best public" values of
several **distinct** leaderboard accounts:

| reported | matching account | rank | submissions |
|---|---|---|---|
| 0.1563 ×3 | extradr19 / SDCF9 / smashi34 | #26/#27/#28 | 3 / 3 / 2 |
| 0.1461 (7GEMSDOE) | **wbg1** (named in the 10GEMSDOE notes) | #33 | 4 |
| 0.1193 (GEMSDOE3) | smrtdoog5 | #48 | 2 |
| 0.1294 (12GEMSDOE) | op01 → 0.1293 | #44 | 2 |

`SDCF9` and `wbg1` are written in the session notes as our own handles.

**Official position.** The rules require that *"Participants will submit a
**single entry**"* ([§1.1](https://docs.nlr.gov/docs/fy26osti/96647.pdf)), that
submissions are limited to *"three submissions per week"*
([§3.2](https://docs.nlr.gov/docs/fy26osti/96647.pdf)), and that an authorised
representative certifies eligibility **under penalty of perjury** citing
18 U.S.C. §§ 1001 and 287 ([§1.3](https://docs.nlr.gov/docs/fy26osti/96647.pdf)).
Section 1.3 also states: *"As soon as the prize administrator becomes aware
that a competitor is not eligible to win the prize, the competitor may be
disqualified."*

**I cannot verify account ownership from here** — that is an assertion about
people, not files. But if one group is operating several accounts to obtain
more than three submissions per week, the $300,000 is at risk no matter how
good the model is.

**Action.** Resolve this before any further modelling. If in doubt, ask the
organizers directly via `info@drivendata.org` or the forum; the
["Institutional Limit"](https://community.drivendata.org/t/institutional-limit/11526)
and ["Team member eligibility"](https://community.drivendata.org/t/team-member-eligibility-competition-homepage-vs-official-rules/11540)
threads show they answer this class of question. Consolidating onto one account
also *fixes* I‑3, because then the leaderboard best is attributable.

---

## I‑5 🟡 Two referenced repositories do not exist

`gh api repos/buffedlizard55-lab/9GEMSDOE` and `…/10GEMSDOE` both return
**HTTP 404**. The session notes list scores for both (`9GEMSDOE: 0.0107`,
`10GEMSDOE: h16-continuation… 0.0461`). Those artefacts are unrecoverable, so
their results cannot be audited or reproduced.

---

## I‑6 🟡 The leaderboard target has moved

The brief states the top score is **0.3049**. As fetched on 2026‑09‑28 the
public leaderboard top is **0.3168** (DARD, 11 submissions), with 0.2993
(alexoktaba) second. The bar for "top of the leaderboard" is 0.3168 and rising.
Our best *attributable* public score is 0.1563 — rank ~#26 of 50+.

---

## I‑7 🟢 Resolved — `nlr.gov` is correct

`docs.nlr.gov/docs/fy26osti/96647.pdf` looked like a typo for NREL. It is not.
[HeroX links to exactly that URL](https://www.herox.com/GEMSPrize/resource/2274)
and the rules document itself explains why: the American-Made program is
*"administered by **NLR**"* — the **National Laboratory of the Rockies**, which
also employs the geology experts who labelled the new faults
([§2, §3](https://docs.nlr.gov/docs/fy26osti/96647.pdf)). No irregularity.

---

## I‑8 🟠 The submission that was rejected

The reported rejection message is `Predicted values must be in range [0, 1]`.
The most likely causes, in order, and all now blocked by
`src/gems/rio.py::validate_submission`:

1. **NaN present.** The official format permits nan *outside the data bounds*,
   but a validator implemented as `arr.min() < 0 or arr.max() > 1` on a masked
   array, or one that rejects non-finite values, will fail. The presence of a
   file named `…_allfinite` in 12GEMSDOE suggests a previous session already
   suspected this.
2. **nodata written as `-3.4028e38` or `-9999`** instead of NaN, which puts a
   hugely negative value inside the band.
3. **float rounding above 1.0** after a rescale.

Every submission this repo writes is emitted in **two** variants — NaN-outside
and all-finite — and neither is released until the validator passes.

---

## Open questions (cannot be resolved from public sources)

**Q‑1.** Does predicted mass sitting *on* a masked known-fault pixel still earn
`TP_w` credit for a new-fault pixel within 300 m, or is it discarded entirely?
Posts 2 and 4 of thread 11516 are only mutually consistent under "discarded
entirely" (otherwise including the catalogue would strictly help, and the
organizer says it "should not matter"). We default to **discarded**, which is
conservative. `FoldScorer.build(..., ignore_pred_outside_eval=False)` flips it.

**Q‑2.** How many new-fault pixels are in the public test chunk? Our exact
inversion of the leaderboard scores bounds it: every map scoring 0.1563 must
have achieved weighted recall ≥ `0.8·DTI/(1−0.2·DTI)` = **0.1291**, and since
`FP_w ≤ total predicted mass`, `|G|_public ≤ 32,655` if recall was 0.30 and
≤ 78,697 if recall was 0.20 (see `reports/scored_forensics.json`).

---

## I‑9 🔴 CRITICAL — every scored submission is statistically indistinguishable from a random map

**Measured** (`reports/chance_baseline.json`, `scripts/chance_baseline.py`).

For a Bernoulli(c) random prediction the expected TP credit per ground-truth
pixel is the expected maximum of the kernel weights over the switched-on cells.
Sorting the 25 kernel weights descending,

```
r(c) = sum_j  w_j * c * (1-c)^(j-1)
DTI_chance = r / (0.2*r + 0.8 + 0.2*FP_w/|G|)
```

This closed form was validated against **105 measured random controls** on the
holdout: **median relative error 1.2 %, p90 4.1 %**.

Applied to our eight leaderboard-scored submissions, at the self-consistent
estimate |G|≈35,000 new-fault pixels in the public chunk:

| submission | public LB | coverage | chance DTI | **lift** |
|---|---|---|---|---|
| gemsdoe1_ens12 | 0.1563 | 3.35 % | 0.1370 | **1.14×** |
| gems8_apex | 0.1563 | 4.06 % | 0.1419 | **1.10×** |
| gemsdoe2_dualunion | 0.1560 | 3.55 % | 0.1387 | **1.12×** |
| gems7_halo15 | 0.1461 | 11.73 % | 0.1267 | **1.15×** |
| gems3_pindrop_nodes | 0.1193 | 3.00 % | 0.1333 | **0.90×** |
| gems3_pindrop_ridge | 0.1152 | 3.00 % | 0.1333 | **0.86×** |
| gems3_pindrop_discovery | 0.0830 | 3.00 % | 0.1333 | **0.62×** |
| gems6_hgb88 | 0.0286 | 3.00 % | 0.1333 | **0.21×** |

**The chance DTI curve peaks at 0.1449 at 5.4 % coverage.** Our plateau of
0.1563 sits almost exactly on it.

**This is the real explanation of the 0.1563 plateau**, and it subsumes I‑3.
Different ideas converged on the same number because **they were all converging
on the score that a random map of that size earns.** The coverage was the
score; the detector contributed ~10 %.

The ordering is stable across every plausible |G| (10k–160k): see the
sensitivity table in `reports/chance_baseline.json`. At every |G| the
leaderboard leader (0.3168) is roughly **2× whatever we achieve**, and
`gems6_hgb88` is 2–5× *worse* than random — catalogue echo is actively harmful,
exactly as the organizers' "fully penalized" statement predicts.

**Action.** Never report a DTI again without the chance DTI at the same pixel
count beside it. `scripts/summarize_holdout.py` now enforces this.

---

## I‑10 🟠 Plain hide-and-recover is biased toward topographic detectors

**Measured.** The withheld pixels are *catalogue* faults, and a Quaternary fault
catalogue is compiled largely from topographic scarp expression. So the
withheld set is, by construction, enriched in exactly the signature a
topographic detector finds — while the competition's real targets are faults
that signature **missed**.

Quantified: only **19.8 %** of catalogue pixels fall in the flattest 33 % of the
survey area, so catalogue faults are ~2× over-represented on slopes.

Scoring restricted to the withheld pixels with the weakest topographic
expression (`dti_concealed` in `reports/holdout_v2.json`), the topographic
baseline collapses from **1.06× chance to 0.51×**, while the
topography-independent detectors are roughly flat. The bias is real and
measurable.

**Action.** `scripts/run_holdout2.py` reports both. Any future candidate must be
reported on the concealed subset as well as the full withheld set.

---

## I-11 (new, 2026-09-29 session 2) — the hide-and-recover holdout is *structurally* biased against the hypotheses that matter

**Measured** (`scripts/audit_bands.py`, section "catalogue vs topography").

The withheld pixels in every fold are **catalogue** faults. Only **19.7 %** of
catalogue pixels fall in the flattest third of the survey area, while that
flattest third is **33.0 %** of the valid footprint — an over-representation
factor of **0.596**. Catalogue faults are therefore ~1.7x *over*-represented on
slopes and correspondingly under-represented on flat ground.

A Quaternary fault catalogue is compiled largely from topographic scarp
expression, so this is not a surprise; but it means the holdout's ground truth
is enriched in exactly the signature a topographic detector finds, and depleted
in exactly the signature the competition is asking for.

**Consequence.** `dti` on the full withheld set rewards topographic detectors for
the wrong reason. `dti_concealed` (the withheld pixels in the flattest third)
is the honest number, and it is reported beside every candidate in
`reports/holdout_v3.json`. On that subset the topographic baseline collapses to
**0.51x chance** while the topography-independent detectors are roughly flat —
so the ranking on the full withheld set is close to inverted on the concealed
subset. **Any candidate must be judged on both.**

**Action.** No candidate is promoted on `dti` alone. `scripts/run_holdout3.py`
writes both, and the verdict uses the concealed subset as a tie-breaker.

---

## I-12 (new, 2026-09-29 session 2) — three detectors were never validatable, and one was leaking

**Measured** by inspection of `scripts/run_holdout2.py` against
`scripts/build_detectors.py`.

1. **`R6_horse_full` was swept as if it were a physical detector.** It is built
   by `horsetail_splay(known, ...)` from the **full** catalogue, including the
   segments each fold withholds. Any holdout score it produced was leakage, not
   skill. `scripts/run_holdout3.py` now refuses to sweep any detector whose name
   ends in `_full` and rebuilds the catalogue-dependent ones per fold from the
   VISIBLE catalogue only.
2. **`HD_strain` was cached globally** even though its fault-density term is
   catalogue-derived. Same class of leak, smaller magnitude. Now rebuilt per fold.
3. **`R7_grain_full` produces only 1,748 non-zero pixels** out of 5,167,373
   valid (0.034 %). With the full catalogue there is almost nowhere left that
   qualifies as "catalogue-blind", so the submission-side version of R7-5 is
   effectively empty. The per-fold version has a smaller catalogue to be blind
   to and is the only version worth measuring. **Flagged: do not ship
   `R7_grain_full` in a submission expecting it to contribute.**

**Action.** Fixed in code; recorded here because the earlier
`reports/holdout_v2.json` and `reports/holdout_verdict.json` numbers for these
families are not trustworthy.
