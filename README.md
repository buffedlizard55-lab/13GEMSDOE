# 13GEMSDOE — competition download & auditable fault research

## ↓ Download the competition submission

**[DOWNLOAD SUBMISSION `.tif` — 1.7MB](docs/downloads/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif)** · **[One-TIFF `.zip`](docs/downloads/13gems_20261001_r13-lattice-s5_v2_nan-outside.zip)**

Unique filename: `13gems_20261001_r13-lattice-s5_v2_nan-outside.tif`.

Short note for the form:

```text
r13 lattice-s5 v2 20261001 | fault-blind every-5th-px grid, coverage baseline | local holdout 18/18 win, not a LB claim
```

**[Website](https://buffedlizard55-lab.github.io/13GEMSDOE/)** · **[Exact submission steps](https://buffedlizard55-lab.github.io/13GEMSDOE/docs/executive_summary.html)** · [Manifest / hashes](docs/downloads/submit.json)

Single float32 band; EPSG32611; 3730rows ×3292columns; 100m cells;
affine `(100,0,243350,0,-100,4508550)`. Inside the5,167,373-pixel footprint:
finite0/1. Outside:7,111,787 NaNs and NoData=nan, like the measured official
template. LZW, one-row strips, no predictor. Primary SHA256:
`b4570b406efec198eb2f4d142ad8d0d6184b14b66f2f52b5c4d697f0647dc9b2`.

**Local format checked is not DrivenData acceptance.** No current-file acceptance
receipt is available. The cause of the earlier range rejection is **UNRESOLVED**:
all three actual local TIFF readers decode that archived file correctly. Ignoring
Predictor2 in a simulation is not evidence of server behavior. The zero-filled
twin is diagnostic only, not an automatic second upload or new geological map.

## Current scientific decision — 2026-10-01

**No new experimental weekly slot is recommended.** The existing reference remains
unchanged byte-for-byte; it is a fault-blind coverage baseline, not a vent discovery.

Four unimplemented physical data/transform combinations were ranked and frozen in
[knowledge/11_r15_predeclared.md](knowledge/11_r15_predeclared.md) BEFORE implementation.
The top2m thermal-corridor experiment used a licensed official archive, not another
weight on the19-band edge ensemble.2,782 footprint probes yielded48 local aligned
neighbourhoods /411 pixels. Adding them **lost all18 existing and all4 geographic
paired folds** against the current reference. All required improvement/win gates
failed. [Full report](reports/holdout_r15_2026-10-01.json) · [Failure interpretation](knowledge/12_r15_results.md).
No confirmation-fold retuning; no publication as a new submission;0competition
uploads and0slots used by this work. R14 also failed its gate and is research-only.

| Protocol (public-label proxy) | Reference mean DTI | + Thermal mean DTI | Paired wins |
|---|---:|---:|---:|
|18existing system / segment folds|0.11218396|0.11204439|0/18|
|4buffered geographic blocks|0.24217508|0.24201309|0/4|

The protocols have different scoring domains. Do not compare absolute scores across
them or call either a hidden-test forecast. A new hypothesis must beat the CURRENT
best on paired existing holdouts and spatial-block stress folds before using a slot.
The next data-ready unimplemented mechanism is **displaced-marker registration**;
USGS event-plane and comparable groundwater-head acquisition remain incomplete.

## Repeated0.1563 and source irregularities

- Pinned trees verify exact historical ens12 blob reuse in GEMSDOE1 (`GEMSDOE`),
  5GEMSDOE and other earlier projects. The8GEMSDOE apex map is DISTINCT despite
  carrying the same reported0.1563 label (IoU0.06703 vs ens12). Byte/pixel/support
  identities are measurable; per-file score attribution is not established.
  [Prior-site audit](reports/sibling_site_audit_2026-10-01.json),
  [8map forensics](reports/scored_forensics.json), [score ledger](reports/leaderboard_ledger.csv).
- A one-off official leaderboard review of BOTH chunks on2026-10-01 shows
  **DARD0.3168**, alexoktaba0.3042, Batik Shirt Brothers0.2998. The brief’s0.3049
  target is stale. SDCF9/smashi34 have ACCOUNT-BEST0.1563 at#35/#36; ownership and
  individual uploaded files remain unverified. [Dated snapshot](reports/leaderboard_snapshot_2026-10-01.json).
- Band6 identity was rerun against independently pinned USGS radiometric derivatives:
  rho0.999978 /R²0.998037 against total count. The embedded tilt/curvature label is wrong.
- Old README advice promoted failed R14 and claimed a proven rejection root cause.
  Those claims are **withdrawn**, not silently carried forward.
  [Authoritative correction register](knowledge/13_audit_corrections_2026-10-01.md).

## Verification and daily review

**Publication status:** The earlier GitHub authentication failure is resolved.
The current PR/CI/merge attempt is recorded in `reports/site_review.json`; this
paragraph does not certify a merge or deployment before their actual results.
Local format verification is separate from deployed delivery and DrivenData acceptance.


The authoritative downloads are `docs/downloads/submit.json` schema2 (`primary` /
`hedge`); the build fails on missing/hash-mismatched assets. Every page, including
repository-root Pages, exposes the primary TIFF at its very top. Clipboard denial,
HTML masquerading as a TIFF, mobile first-fold visibility and one-file ZIP delivery
are explicit browser regression cases.

- [Three cumulative pass record](reports/site_review.json): implementation +
  verification; bug/edge-case review; requirements recheck. Exact final counts and
  honest access/compute limits live there; on-disk and deployed checks are separate.
- `.github/workflows/quality.yml`: pinned small official rasters, unit/metric/download/
  deterministic-build checks, local HTTP/browser/axe checks. No competition upload.
- `.github/workflows/source-review.yml`: daily bounded approved open-data/repository
  observations and change/failure artifact plus one reusable bot issue for the live Pages feed. No Git push to main, no DrivenData/forum polling; observed
  changes require source review, not automatic fact certification. Browser reads
  public GitHub workflow and bot-issue metadata, not a competition scraper. Failed observations retain previous successful values; scientific facts still need review.
- `.github/workflows/live-site.yml`: open-egress deployed root/docs TIFF+ZIP+manifest
  delivery smoke test. Real competition-form acceptance is a separate unavailable gate.
- [Curated official claims](reports/verified_sources_2026-10-01.json),
  [sources/feed page](docs/sources.html), [stored observations](reports/open_source_feed.json).

## Reproduce (not a manual data-placement handoff)

Acquisition, preparation, metric checks and the R15 model experiment were actually
executed in this session. Browser QA also ran using a locally recovered Chromium;
the standard install below is for the open-egress hosted runner. Large data are ignored and reproducibly recovered; do not commit
419MB features or training caches.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
bash scripts/download_competition_data.sh
.venv/bin/python scripts/prepare_data.py
.venv/bin/python scripts/fetch_external_data.py
.venv/bin/python scripts/audit_band6_identity.py
.venv/bin/python scripts/audit_platform_encoding.py
.venv/bin/python scripts/audit_metric.py
.venv/bin/python -m pytest tests -q
.venv/bin/python scripts/build_site.py --check
.venv/bin/python scripts/verify_download.py
.venv/bin/python scripts/verify_site_http.py
# Browser installation is performed by the open-egress quality runner:
.venv/bin/python -m playwright install --with-deps chromium
npm install --prefix .cache/browser --no-audit --no-fund axe-core@4.11.0
.venv/bin/python scripts/verify_site_browser.py --require-axe
# Reproduction of the FROZEN failed experiment; NEVER tune against its results:
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/validate_r15.py
```

The source thermal archive is autonomously obtained by the existing
`fetch-gdr1391.yml` runner; its recorded hashes and provenance are in
[reports/gdr1391_fetch.json](reports/gdr1391_fetch.json). Do not ask for file placement.
`make_submission.py` now exports checked **research-only** TIFF pairs to ignored
`data/research_exports/`; it cannot replace the live primary or `latest.*`.
Historical migration commands are retired BEFORE mutation. Publishing a new map
requires a reviewed current-best gate, not a schema1 alias or a renamed duplicate.

## Limits / next work

No authenticated DrivenData session, hidden truth or current-file acceptance receipt.
Sandbox direct TLS to public Pages/DOE/USGS is restricted; hosted-runner live
verification is reported separately. Two CPU cores /~3.8GiB RAM /no detected GPU:
the official U-Net was inspected, not trained. A working file/download is provided,
not a fabricated high leaderboard score. Eligibility, account ownership and legal
certifications are not inferred. GitHub PR/merge/deployment status must be read from
actual gh results, not dry-run push permissions.

Next: predeclare synthetic-tested displaced-marker registration against current
reference; obtain original native GeoDAWN precision before derivative-sensitive
claims; acquire uncertainty-bearing event products /harmonized well networks in an
open-egress runner; expand validation with independently sourced truth without
confirmation-fold leakage. Keep failure records, per-file identities and final AI
use/resource/data-licence disclosure. [Current plan](knowledge/12_r15_results.md).

## Core Values

**Maximize P(Win):** choose falsifiable independent measurements and a strict
current-best gate over cosmetic uniqueness or repeated fragile blends.
**Own the Outcome:** obtain data autonomously, verify delivered bytes, fix confusing
instructions, test failure paths, and disclose the result—even when the idea loses.
The competition target is unmapped fault geometry, not a generic geothermal vent map.

The full previous README is preserved as
[an explicitly superseded historical record](knowledge/archive/readme_through_session8.md).
The standing user prompt below is preserved verbatim, including now-stale hypotheses
and score references; it is not a source of updated competition facts. Read it at
the start of each session.

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

