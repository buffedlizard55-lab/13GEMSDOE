# Verified fact base — GEMS Prize Challenge

**Verification date: 2026-09-28, re-verified line by line 2026-09-29; leaderboard
snapshot refreshed 2026-09-30.** Every line below was fetched from the named official
URL during those sessions.
Anything I could **not** verify is in
[`02_irregularities.md`](02_irregularities.md) and is explicitly marked
`UNVERIFIED`. Nothing here is recalled from memory.

### Re-verification record, 2026-09-29

| Source | Fetched | Result |
|---|---|---|
| [problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) (both chunks) | ✅ | Metric formulas, α=0.2/β=0.8, R=300 m=3 px, worked example `TP_w 3.00 / FP_w 1.89 / FN_w 2.00 → 0.60`, and all four submission-format bullets confirmed **verbatim**. |
| [thread 11516 post 2](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/2) | ✅ | Quote matches the transcript word for word. |
| [thread 11516 post 4](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4) | ✅ | All three numbered answers match word for word. Post 4 is by `chrisk-dd`, dated Sep 21. |
| [thread 11536](https://community.drivendata.org/t/where-do-you-draw-the-line/11536) | ✅ | "new fault" = "any fault pixel not already captured by USGS/INGENIOUS" … "can include newly mapped geometry of an existing fault system" — verbatim. |
| [thread 11527 post 7](https://community.drivendata.org/t/how-were-the-new-test-faults-identified-data-sources-and-fault-types/11527/7) | ✅ | "We're not sharing details about the data sources, fault types, or coverage behind the test faults beyond what's in the problem description." — verbatim. |

**New in this re-verification, and it changes a conclusion.** The problem page's
provided-features figure is served as
`https://drivendata-public-assets.s3.amazonaws.com/gems_tc_tmi.png` and is
captioned *"A visualization of some of the GeoDAWN features: radiometric (left)
and magnetic (right) data."* The filename pairs `tc` with `tmi` under the label
"radiometric and magnetic", which is **first-party evidence that `tc` denotes the
radiometric total count**. The same page's feature list, however, names every
magnetic derivative explicitly (RTP, TMI, TMI vertical slope, TMI horizontal
slope, top-of-crustal magnetic source depth) and does **not** name a tilt angle
or a total curvature.

**RESOLVED 2026-09-30 (session 4) by direct measurement, not inference.**
`scripts/audit_band6_identity.py` → `reports/band6_identity.json`: band 6 matches
the dequantised official GeoDAWN radiometric **total count** channel
(`radiometric::rad_tc`, USGS DOI 10.5066/P93LGLVQ) with Spearman rho = **0.99998**,
Pearson r = 0.99902, OLS **slope 1.0073**, intercept −0.128, **R² = 0.9980**,
RMSE 0.196 band-6 units, median ratio 1.00000 (IQR 0.99867–1.00134), and matching
percentiles (p1 7.7223 vs 7.7140, p50 18.4817 vs 18.4559, p99 29.1005 vs 29.1002).
The independent percentile-quantised copy `geodawn_rad::TC` agrees in rank
(rho = 0.99995). The physical closure test also passes: band 6 ≈ 7.54 ×
(K + Th + U) with rho = 0.9958, R² = 0.9902 — a tilt angle or a curvature has no
reason to equal the sum of the three radiometric windows. **Band 6 is the
radiometric total count; its embedded description ("Tilt angle or total
curvature - magnetic field derivative for edge detection") is wrong.** The
earlier disproof rested on an unverified units assumption (that a count rate must
be 10²–10⁴ cps); the official grid itself lives in the 5.5–30.3 range with the
competition band keeping a tail to 88.57 that the 8-bit product clips at its
p99.5 quantisation limit. See I-2.

### Re-verification record, 2026-09-30 (session 4)

Fetched with `fetch_page`; forum threads read through Discourse's `/print` view so
that every post body, not just its header, is rendered.

| Source | Fetched | Result |
|---|---|---|
| [official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) (chunk 0) | ✅ | DARD 0.3168 (11 subs), alexoktaba 0.3042 (17), joeyfezster 0.2919, xiaofanhu 0.2901, HardcoreTechGod 0.2854, mzoorob 0.2843, GrigorSargsyan 0.2742, op01 0.2710. Snapshot in [`reports/leaderboard_snapshot_2026-09-30.json`](../reports/leaderboard_snapshot_2026-09-30.json). |
| [thread 11527 (all 10 posts)](https://community.drivendata.org/t/how-were-the-new-test-faults-identified-data-sources-and-fault-types/11527/print) | ✅ | Post 7 (`chrisk-dd`, Sep 23) matches the archived quote word for word, including the Phase-2 sentence. **No new organiser statement** in posts 8–10. |
| [thread 11536](https://community.drivendata.org/t/where-do-you-draw-the-line/11536) | ✅ | Still 2 posts; the "newly mapped geometry of an existing fault system" quote is unchanged. |
| [thread 11528](https://community.drivendata.org/t/paid-for-external-data-license/11528/print) | ✅ | External data allowed "provided that the participants possess a license that permits the data to be used in this challenge and shared with the sponsor for evaluation purposes." USGS public domain satisfies both clauses. |
| [thread 11524](https://community.drivendata.org/t/weekly-submissions/11524/print) | ✅ | `chrisk-dd`, Sep 17: *"The submission allowance resets based on a rolling window, not at a specific date and time."* → fact 1.9. |
| [thread 11529](https://community.drivendata.org/t/why-does-the-training-fault-labels-file-in-the-data-tab-have-a-single-band-while-the-labels-in-the-reference-solution-repo-have-19-bands/11529/print) | ✅ | `chrisk-dd`, Sep 23: the reference notebook's "19 bands in the label TIF" is *"an artifact / bug in the summary string that gets printed in the notebook"*; the label TIF has **one** band, as we measured. |
| [thread 11540](https://community.drivendata.org/t/team-member-eligibility-competition-homepage-vs-official-rules/11540/print) | ✅ | `hannahmoro`, Sep 29: the Official Rules take precedence over the homepage — every non-captain team member must be legally authorised to work in the U.S. → fact 1.10. |
| [thread 11516](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516) | ⚠️ | Re-fetch attempted twice on 2026-09-30; the fetch proxy returned `SignatureDoesNotMatch` both times. Posts 2 and 4 remain as verified verbatim on 2026-09-29 (table above); **not** re-verified this session. |

Competitor intel from the same threads (their words, not ours): `moongrega`
*"can't depend heavily on LiDar … using it for as little as possible"*, works from
conductance and area grids (11527 posts 4–6); thread 11531 is a competitor
recruiting a geologist for LiDAR fault mapping. Our R10 measurement is that the
1-m LiDAR morphometrics are the *second*-strongest external signal but still lose
to the topographic crest recipe — consistent with both.

---

## 1. Competition structure

| # | Fact | Source |
|---|------|--------|
| 1.1 | Task: predict pixel-wise presence of **geological faults** as indicators of geothermal resources. | [Problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) |
| 1.2 | The test set is a set of **newly identified faults not in the public USGS database**, manually labelled by fault experts. | [Problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) |
| 1.3 | The GeoDAWN region is chunked into a **public** and a **private** test set. The public leaderboard reports an account-level **Best public DW-Tversky** value; it is not a per-submission receipt. Snapshot on 2026-09-30: DARD 0.3168, alexoktaba 0.3042. | [Problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) · [official leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) · [`reports/leaderboard_snapshot_2026-09-30.json`](../reports/leaderboard_snapshot_2026-09-30.json) |
| 1.4 | **Initial/Phase‑1 round**: $50,000, split equally among top 5, scored on the private set. | [Problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) · [Official Rules §1.1](https://docs.nlr.gov/docs/fy26osti/96647.pdf) |
| 1.5 | **Final/Phase‑2 round**: $250,000 — $100k / $70k / $40k / $25k / $15k — re-scoring the *same* submissions against an **expanded** label set built by expert review of **every team's** submission. | [Problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) · [Official Rules §1.1](https://docs.nlr.gov/docs/fy26osti/96647.pdf) |
| 1.6 | Competitors must choose **a single submission** for scoring across both rounds, before the deadline, **without knowing private performance**. | [Problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) |
| 1.7 | Total prize pool $300,000; prize governed by 15 U.S.C. § 3719. | [Official Rules §1](https://docs.nlr.gov/docs/fy26osti/96647.pdf) |
| 1.8 | Eligibility: U.S. citizens/permanent residents (individual), U.S.-incorporated entities, U.S. accredited academic institutions. FFRDCs, non-DOE federal entities/employees, DOE employees & support contractors, DrivenData staff, under-18s, MFTRP participants and FCOC-controlled entities are **ineligible**. Eligibility is certified **under penalty of perjury** (18 U.S.C. §§ 1001, 287; 31 U.S.C. §§ 3729‑3733, 3801‑3812). | [Official Rules §1.3](https://docs.nlr.gov/docs/fy26osti/96647.pdf) |
| 1.9 | The three-scored-submissions allowance resets on a **rolling seven-day window**, not at a calendar-week boundary or a fixed time of day. Planning consequence: a slot freed by waiting is not predictable from the calendar; do not schedule three submissions in one day on the assumption of a Monday reset. | [forum 11524 post 2](https://community.drivendata.org/t/weekly-submissions/11524/2) (`chrisk-dd`, Sep 17) · [Official Rules §3.2](https://docs.nlr.gov/docs/fy26osti/96647.pdf) |
| 1.10 | Where the homepage and the Official Rules disagree on team eligibility, **the Official Rules take precedence**: the captain must be a U.S. citizen/permanent resident *and* every other member must be legally authorised to work in the U.S. | [forum 11540 post 2](https://community.drivendata.org/t/team-member-eligibility-competition-homepage-vs-official-rules/11540/2) (`hannahmoro`, Sep 29) · [Official Rules §1.3](https://docs.nlr.gov/docs/fy26osti/96647.pdf) |
| 1.11 | The training label TIF has **one band**. The reference-solution notebook's printed claim of 19 label bands is a bug in its summary string, confirmed by the organiser. | [forum 11529 post 2](https://community.drivendata.org/t/why-does-the-training-fault-labels-file-in-the-data-tab-have-a-single-band-while-the-labels-in-the-reference-solution-repo-have-19-bands/11529/2) (`chrisk-dd`, Sep 23) · our own rasterio read of `existing_faults.tif` |

> **1.5 is the strategically dominant fact.** 83 % of the money is in Phase 2, and
> Phase 2 labels are *created from our own submitted predictions*. A correct
> prediction of a fault nobody has mapped is worth more in Phase 2 than in
> Phase 1, because it can become ground truth. `chrisk-dd` restated this
> explicitly: *"the largest prize pool (Phase 2) will use a test set that is
> updated by expert review of all Phase 1 submissions, so your fault
> predictions have an impact on final evaluation even if they are not the most
> performant in Phase 1."*
> ([forum 11527 post 7](https://community.drivendata.org/t/how-were-the-new-test-faults-identified-data-sources-and-fault-types/11527/7))

---

## 2. The metric — quoted exactly

Source: [Problem description → Performance metric](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)

```
k(d) = max(1 - d/R, 0)                                   R = 300 m = 3 px @ 100 m

TP_w = sum_{g in G}  max_{x : d(x,g) <= R}  p(x) k(d(x,g))
FP_w = sum_{x : p(x)>0}  p(x) [ 1 - max_{g in G} k(d(x,g)) ]
FN_w = sum_{g in G} [ 1 - max_{x : d(x,g) <= R} p(x) k(d(x,g)) ]

DTI(alpha,beta) = TP_w / (TP_w + alpha FP_w + beta FN_w + eps)
alpha = 0.2   beta = 0.8
```

Official worked example: `TP_w = 3.00, FP_w = 1.89, FN_w = 2.00 → 0.60`.

### 2.1 Audited consequences (all machine-verified — `reports/metric_audit.json`)

| # | Result | Status |
|---|--------|--------|
| A1 | `FN_w ≡ |G| − TP_w` (same index set, same inner max, complementary summands). | **exact identity**, max err 7e‑15 over 60 random rasters |
| A2 | Therefore `DTI = TP_w / (0.2·TP_w + 0.2·FP_w + 0.8·|G|)`. | **exact**, max err 6e‑17 |
| A3 | Therefore `DTI = 1 / (0.2/P_w + 0.8/R_w)` — the weighted harmonic mean of weighted precision (0.2) and weighted recall (0.8). Since `β²=0.8/0.2=4`, **DTI is a distance-weighted F2 score**. | **exact**, max err 1e‑11 |
| A4 | Worked example reproduced from a raster: prediction pixels {(0,3),(0,7),(4,5)} on a 9×11 grid with a 5‑pixel vertical truth line give `TP_w=3.0000, FP_w=1.8856, FN_w=2.0000, DTI=0.6028 → 0.60`. | **reproduced** |
| A5 | A block of added predictions raises DTI **iff** its marginal weighted precision `ΔTP_w/(ΔTP_w+ΔFP_w) > 0.2 × DTI`. | **proved + 9/9 numerical trials agree** |
| A6 | Scaling every prediction up toward 1 **strictly** increases DTI: `DTI(c·p) = TP/(0.2TP + 0.2FP + 0.8|G|/c)`. A pixel exactly on truth has `k(0)=1` so it costs **zero** FP mass. The optimum is therefore **binary**; graded values only encode ranking. | **monotone over 8 scales** |
| A7 | A relative gain in recall beats the same relative gain in precision **iff** `P_w > 0.25 · R_w`. Elasticities always sum to 1. | **proved + 40/40 grid points agree** |

**A5 is a conditional decision rule, not a leaderboard forecast.** For a score
`DTI = d`, a block of added predictions helps iff its marginal weighted precision
exceeds `0.2 × d`. The arithmetic is exact; the applicable `d` must come from the
same evaluation set. The historical 0.1563 labels are not verified per-file public
scores and must not be used as “our current DTI.” For context only, at the official
2026-09-30 **account-level** leader score of 0.3168 the arithmetic value is 0.06336;
that is not a threshold estimate for any local file or private test. Tune coverage and
cutoffs on the known-truth holdout, not by assertion or leaderboard extrapolation.

**A6 + the max in TP_w motivate, but do not dictate, spacing.** Once a truth pixel's
maximum credit is saturated, a nearby redundant prediction may add false-positive
mass without more credit for that truth. Nearby predictions can still serve a
different truth pixel, so spacing is not a universal 300 m rule. Settle line spacing,
ridge width, and fusion numerically on the multiple-rule holdout; do not assume every
100 m-spaced or thick line is waste. The previous categorical wording is withdrawn.

---

## 3. Organizer statements — verified verbatim

### 3.1 Thread 11516, "Scoring clarification" — [link](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516)

**`chrisk-dd` (DrivenData Staff), Sep 16, post 2:**
> 1. Pixels corresponding to known USGS/INGENIOUS faults are masked / excluded from evaluation, so they do not count towards penalty terms.
> 2. Re-evaluation will also mask/exclude the existing USGS/INGENIOUS faults.
>
> We'll consider changing the description, but for scoring purposes it should not matter whether these known faults are included with predictions or not.

**`chrisk-dd` (DrivenData Staff), Sep 21, post 4:**
> 1. The mask is indeed pixel-exact - it is identical to the provided set of training fault labels.
> 2. Only new-fault ground truth is considered for scoring purposes. A predicted pixel that is near a known fault trace but far from a new-fault ground truth pixel will be fully penalized, i.e., the buffer does not apply to known faults.
> 3. A new-fault ground truth pixel can indeed lie within 300m of a known fault trace. Such pixels would constitute corrections or modifications to existing fault traces. Identifying these corrections is one outcome we are aiming for as part of this competition. Such corrections may already exist in the new-fault set, and may also exist in the final round evaluation set.

### 3.2 Thread 11536, "Where do you draw the line?" — [link](https://community.drivendata.org/t/where-do-you-draw-the-line/11536)

**`chrisk-dd` (DrivenData Staff):**
> For the purposes of this competition, "new fault" means "any fault pixel not already captured by USGS/INGENIOUS" and can include newly mapped geometry of an existing fault system.

### 3.3 Thread 11527, "How were the new test faults identified?" — [link](https://community.drivendata.org/t/how-were-the-new-test-faults-identified-data-sources-and-fault-types/11527/7)

**`chrisk-dd` (DrivenData Staff), post 7:**
> We're not sharing details about the data sources, fault types, or coverage behind the test faults beyond what's in the problem description.

### 3.4 Verdict on the four claims brought into this session

| Claim as stated to me | Verdict |
|---|---|
| Known USGS/INGENIOUS fault pixels are masked in **both** rounds, with a **pixel-exact** mask identical to the training labels. | ✅ **VERIFIED** — 11516 posts 2 and 4. |
| A predicted pixel just beside a known trace is **still fully penalized** unless near a new-fault pixel. | ✅ **VERIFIED** — 11516 post 4 item 2, verbatim: *"will be fully penalized, i.e., the buffer does not apply to known faults."* |
| New-fault pixels **can** lie within 300 m of known traces. | ✅ **VERIFIED** — 11516 post 4 item 3. |
| "New fault" = any fault pixel not already captured, incl. extensions, splays, parallel strands, corrections. | ✅ **VERIFIED** — 11536 (*"newly mapped geometry of an existing fault system"*) + 11516 post 4 item 3 (*"corrections or modifications to existing fault traces"*). |
| Organizers declined to say which data/fault types the test faults came from. | ✅ **VERIFIED** — 11527 post 7. |

**All four claims and the caveat are accurate.** No correction needed.

### 3.5 The operational consequence nobody has priced in

Posts 2 and 4 are only consistent under one reading, and it is the reading that
changes strategy:

* Predicting **exactly** the 60,988 training-label pixels is **score-neutral** —
  they are masked out entirely (post 2).
* Predicting the **1-pixel halo** around those traces is **fully penalized**
  (post 4 item 2) *unless* a new-fault pixel is within 300 m.
* But new-fault pixels **are** allowed inside that halo, and they are exactly
  the "corrections / modifications" the organizers say they want (post 4 item 3).

So the near-catalogue corridor is a **high-variance bet**, not free real estate.
Our own scored evidence confirms the downside: the submission that put 69.5 % of
its mass within 300 m of known traces (`gems6_hgb88`) scored **0.0286**, the
worst of eight. See `reports/scored_forensics.json`.

---

## 4. Data — official inventory

| File | Shape / type | Verified property |
|---|---|---|
| `training_features.tif` (mirrored as `gems-geodawn-numerical-features.tif`) | 3730×3292, **19 bands**, float32, EPSG:32611, 100 m, nodata −3.4028e38 | read locally |
| `existing_faults.tif` (training labels) | 3730×3292, int8, values {−1 nodata, 0, 1}; **60,988** fault pixels, **5,167,373** valid pixels (1.18 %) | read locally |
| `example_submission.tif` | 3730×3292, float32, nodata NaN, 5,167,373 finite | read locally — **see irregularity I‑1** |
| Grid geotransform | `(100, 0, 243350; 0, −100, 4508550)`; bounds `243350, 4135550 → 572550, 4508550` | read locally |

### 4.1 Band inventory (short codes are from the file; see irregularity I‑2 for the descriptions)

| # | code | official feature-group match ([problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)) |
|---|---|---|
| 1 | `mag_anom` | magnetics |
| 2 | `rtp` | "reduced-to-pole magnetic anomaly" ✅ named officially |
| 3 | `tmi_hg` | "horizontal slope of total magnetic intensity" ✅ |
| 4 | `geod_2ndinv` | "second invariant of the strain rate tensor" ✅ |
| 5 | `iso_grav_anom_slope` | "slope of the isostatic gravity anomaly" ✅ |
| 6 | `tc` | **ambiguous — see irregularity I‑2** |
| 7 | `geod_shearrate` | "shear strain rate" ✅ |
| 8 | `geod_dilaterate` | "dilatation rate" ✅ |
| 9 | `tmi_vg` | "vertical slope of total magnetic intensity" ✅ |
| 10 | `deq_n100a15` | "density of earthquakes" (dependent/declustered) |
| 11 | `iso_grav_anom_vg` | gravity derivative |
| 12 | `det_elev` | "detrended elevation" ✅ |
| 13 | `iso_grav_anom` | "isostatic gravity anomaly" ✅ |
| 14 | `tmi` | "total magnetic intensity" ✅ |
| 15 | `depth_to_base_surf` | "depth to conductive base surface" ✅ |
| 16 | `ieq_n100a15` | "density of earthquakes" (independent) |
| 17 | `cond_surf` | "surface conductivity" ✅ |
| 18 | `iso_grav_anom_hg` | gravity derivative |
| 19 | `det_elev_slope` | "slope of detrended elevation" ✅ |

---

### 4.2 Submission format — verified verbatim, 2026-09-29

Four bullets, quoted exactly from
[problem description → Submission format](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/):

1. "Your submission is in the same projected coordinate reference system as the
   training data (projected coordinate system for UTM zone 11N, EPSG 32611)"
2. "Your submission is at the same resolution as the training data (100m)"
3. "Your submission has the same bounds as the training data, and data outside
   the bounds is null or nan."
4. "Your submission contains a single layer with datatype of 32-bit float
   (`float32`) with values between 0 and 1 indicating the confidence or
   probability of fault presence, with higher values indicating higher
   probability."

Plus: *"A sample submission that predicts total fault absence is provided for
your reference on the data download page."* — the sentence that makes
irregularity I-1 decisive.

### 4.3 Provided-feature list — verified verbatim, 2026-09-29

The official list from the same page:

* "Surface conductivity and depth to conductive base surface"
* "Detrended elevation and the slope of detrended elevation"
* "Dilatation rate, shear strain rate, and the second invariant of the strain
  rate tensor"
* "Isostatic gravity anomaly and the slope of the isostatic gravity anomaly"
* "Magnetics including reduced-to-pole magnetic anomaly, total magnetic
  intensity, the vertical and horizontal slope of total magnetic intensity, and
  the top-of-crustal magnetic source depth estimate"
* "Density of earthquakes"

**Mapping to the 19 bands** (measured, `scripts/audit_bands.py`): the six bullets
account for 16 of the 19 bands. The three not named in any bullet are band 1
`mag_anom` (the base magnetic anomaly, i.e. the input to the RTP/TMI
derivatives), band 11 `iso_grav_anom_vg` and band 18 `iso_grav_anom_hg` (the
vertical and horizontal derivatives of the isostatic gravity anomaly), and band
6 `tc`. **No bullet names a tilt angle or a total curvature.** That is the
official basis for doubting band 6's embedded description — and band 6 is now
**identified by measurement** as the radiometric total count
(`reports/band6_identity.json`: rho 0.99998, R² 0.9980, slope 1.007 against the
official USGS `rad_tc` grid; closure rho 0.9958 against K + Th + U). Two
consequences: (i) `HE_lin_tc` is a genuine radiometric lineament feature, so its
geological story is restored; (ii) band 6 carries **no information we do not
already have** from the official release, so it is not an external-data gain.

---

## 5. Free, official external data that is *obtainable* (checked this session)

| Dataset | Why it matters | Link | Reachable from this sandbox? |
|---|---|---|---|
| INGENIOUS Great Basin Regional Dataset Compilation, DOI 10.15121/1881483, CC‑BY‑4.0 | **Quaternary Faults v2** carries `ages and slip rates` → the age/slip-rate holdout strata. Also Paleo Geothermal Features (sinter/tufa), 2 m temperature probes, Q volcanics, heat flow, MT conductance. | [gdr.openei.org/submissions/1391](https://gdr.openei.org/submissions/1391) | ❌ egress blocked — see limitation L‑2 |
| GeoDAWN airborne magnetic & radiometric surveys (USGS) | source of bands 1‑3, 6, 9, 14 | [usgs.gov/data/geodawn…](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and) · [ScienceBase 657e1d85](https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7) | ❌ egress blocked |
| USGS 3DEP 1 m DEM (`1m_DEM_links.csv`) | scarp detection | DrivenData data tab (login) | ❌ no auth |
| Official reference solution | baseline U-Net, confirms α=0.2/β=0.8 in the *training* loss | [github.com/drivendataorg/gems-prize-reference-solution](https://github.com/drivendataorg/gems-prize-reference-solution) | ✅ downloaded |

**Licence note:** INGENIOUS GDR 1391 is CC‑BY‑4.0, which satisfies the
competition's external-data rule ("participants possess a license that permits
the data to be used in this challenge and shared with the sponsor"). Attribution
required.
