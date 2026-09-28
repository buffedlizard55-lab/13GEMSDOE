# PROJECT CHARTER — read this first, every session

This is the standing brief for 13GEMSDOE. It is the *starting point* for every
working session: read it, check the current state against it, then work. It
exists so that no session has to rediscover the mission, and so that what we
build is genuinely useful day to day rather than a pile of one-off experiments.

---

## 1. The goal

Place **top of the leaderboard** in the
[DOE GEMS Prize Challenge](https://www.drivendata.org/competitions/306/competition-doe-gems/),
and — more importantly — contribute *real* geological discoveries, because
**83 % of the $300,000 is in Phase 2, whose labels are created by expert review
of our own submitted predictions.**

Current state (2026‑09‑28): leaderboard #1 = **0.3168**. Our best attributable
public score = **0.1563** (~rank #26).

## 2. The product

A system that **removes manual checking** and keeps an **up-to-date feed**:

* a site whose *first* element is a one-click, pre-validated submission GeoTIFF,
  with the exact name and note to paste into the DrivenData form;
* a verified fact base with an official link on every line;
* an offline holdout that tells us whether an idea is worth a submission slot
  **before** we spend one;
* machine-readable evidence (`reports/*.json`) behind every claim, so nothing
  has to be taken on trust.

## 3. Core values (from the Arena team — these govern trade-offs)

### Maximize P(Win)
Weigh trade-offs, assess risk, choose the path that maximises the probability
the project succeeds. Set emotions aside. Make the hard call.

*Applied here:* we do not spend submission slots on untested ideas; we do not
keep re-running a family of detectors that already plateaued; and we surface
eligibility/compliance risk immediately, because a disqualification sets
P(Win) to zero regardless of model quality.

### Own the Outcome
Own results end to end, not one slice. When a problem appears and we can act,
act — without waiting for permission. Treat failure and success as signals.

*Applied here:* when the "0.1563 plateau" turned out to be a measurement
artefact rather than a modelling ceiling, the correct response was to fix the
measurement, not to tune the model harder.

## 4. Non-negotiables

1. **No hallucinations. Verify line by line.** Every factual claim carries the
   official URL it came from. Anything unverifiable is marked `UNVERIFIED` in
   `knowledge/02_irregularities.md`, never laundered into the analysis.
2. **Flag irregularities for review** rather than smoothing them over.
3. **Work autonomously.** No step in the pipeline may require manual input.
4. **Official, free, verifiable sources only** for external data, with a
   licence that permits competition use and sharing with the sponsor.
5. **Holdout gate.** Nothing gets a weekly submission slot until it beats the
   current best on the hide-and-recover holdout, under *multiple* withholding
   rules.
6. **Three submissions per week, one account.**
   ([Official Rules §3.2](https://docs.nlr.gov/docs/fy26osti/96647.pdf))
7. **Disclose generative-AI use** in the narrative — required by
   [Official Rules §3.2](https://docs.nlr.gov/docs/fy26osti/96647.pdf).
8. **Finalists must ship reproducible code.** Keep the pipeline runnable
   end-to-end from a clean checkout.

## 5. How we decide what to build (the scoring facts, settled numerically)

The metric is a **distance-weighted F2 score**; see
`knowledge/01_verified_facts.md §2.1` for the proofs and
`reports/metric_audit.json` for the machine output.

* Add a block of predictions **iff** its marginal weighted precision exceeds
  `0.2 × DTI`. Today that is ~3 %. **Be far more inclusive than a 0.5 cutoff.**
* The optimum is **binary**; graded values only rank pixels.
* **Recall outweighs precision** whenever `P > 0.25·R`.
* `TP_w` maxes over the 300 m neighbourhood → **redundant nearby predictions
  cost FP mass and earn nothing.** Decimate lines; don't thicken them.

Settle "precision versus coverage" **numerically on the holdout**, never by
assertion.

## 6. Validation doctrine

**Hide-and-recover is the main check.** Withhold whole fault segments/systems
with a buffer; derive every catalogue-based feature only from what stays
visible; mask the visible faults pixel-exactly as the organizers do; score DTI
on the withheld pixels alone, under several withholding rules (random, short,
isolated, strike class, dense). **Flag any idea that wins under only one rule
as fragile.**

**Geographic block CV is a stress test, not the main check.** The submission
shares the training features' bounds and the test sets are chunks of the same
region, so the real distribution shift is *unmapped faults among mapped ones*,
not new geography.

## 7. Standing to-do at the start of each session

1. Re-read this charter.
2. Re-check the leaderboard — the target moves.
3. Re-check `knowledge/02_irregularities.md`: are the 🔴 items resolved?
4. Run `scripts/audit_metric.py` (fast) to confirm nothing regressed.
5. Only then: new hypotheses → holdout → (if it wins) submission.

---

## Appendix A — The originating brief

Kept verbatim so intent is never lost in paraphrase.

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
