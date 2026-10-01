# Current audit corrections — 2026-10-01

**Authoritative correction notice.** This supersedes contradictory causal/slot
advice in sessions6–8, I8/I18/I22 and the archived README. Original evidence and
verbatim user brief are preserved; historical claims are not silently promoted.

## 1. Four independent assertions, never collapse them

| Assertion | Evidence required | Current state |
|---|---|---|
| Local format/pixels | Decode named bytes; compare official grid/footprint/range with independent readers; TIFF/ZIP hashes | PASS, primary and diagnostic twin. |
| Site delivery | Actual HTTP download, hash/size, ZIP content, browser links and raster checks | Local HTTP/browser and GitHub-hosted live checks are separate from on-disk checks. See latest QA report; do not call this remotely verified until a live run passes. |
| DrivenData acceptance | Platform response tied to the exact named file/hash | **Not established for current files.** No authenticated competition session available. |
| New scientific candidate clearance | Predeclared paired improvement against CURRENT best, plus spatial-block stress test | R14 FAILED; R15 thermal FAILED18/18 and4/4. Neither gets a slot. |

## 2. Rejection root cause remains UNRESOLVED

The user reported `Predicted values must be in range [0, 1]` for an earlier download.
The archived rejected raster has locally valid footprint values and Predictor2.
Rasterio/GDAL, tifffile and Pillow decode that raster correctly. The
`simulate_ignored_predictor2` function deliberately omits differencing; its [-4,3]
range is a **hypothetical failure mode**, not a server decoder trace. We have no
basis to say DrivenData ignored the predictor, changed its validator, or treated
NaN incorrectly. Those former causal assertions are withdrawn.

The primary policy still follows the official template: one float32 band,
EPSG32611, rows3730 x cols3292, 100m affine(100,0,243350,0,-100,4508550), NaN
outside and finite [0,1] inside. Use conservative LZW/no-predictor layout. A
zero-fill twin remains a diagnostic; do not automatically spend a second slot on
an encoding change. Local format compliance cannot guarantee remote acceptance.
`accepted_pattern` is a deprecated API alias for **template policy**, not receipt.

## 3. Failed alternate promotion was a real product bug

`build_site.py::alt_html` called EVERY alternate "Second candidate for your next
slot", even R14 whose own report failed its predeclared gate. Earlier README §7
also recommended failed-gate experiment arms. This violated the standing brief.
The new manifest gives all alternates `upload_allowed=false`, the site moves them
to an explicitly research-only archive, and generator/legacy migration commands
cannot silently replace the primary. Research exports go to ignored storage.

R11 is an older geophysics/topography reference, not a current-best winner. A
previous win against topo alone does not clear it against today's lattice.
No experimental slot is recommended after this review.

## 4. Repeated 0.1563: reuse is measurable; score attribution is not

GitHub trees at the pinned commits in `reports/sibling_site_audit_2026-10-01.json`
show exact blob812e61b74050d1350cc2bde1fab0c76ead32e0c4 (570,890B) in GEMSDOE,
5GEMSDOE and GEMSDOE2. Recovered file SHA256 is
7f00890a62878d612fb5eef67a9a364a2df819433dde74b6762ce4fc0fc4fe15.
The fresh16-repository /37-page audit also found that historical blob in
GEMSDOE3, GEMSDOE4 and7GEMSDOE. Archive presence does not establish the current
primary or an upload. That is exact artifact reuse, not just similar model ideas. It does NOT establish
which byte stream was uploaded to an account or which upload received0.1563.

The 8GEMSDOE `apex` raster with the same reported label has different file/pixel/
support hashes; support IoU vs ens12 is0.06703. GEMSDOE2 `dualunion` is distinct
but highly overlapping (IoU0.94191). `reports/scored_forensics.json` and the CSV
ledger define canonicalization precisely. A rounded score can legitimately repeat
for different predictions. Unique names/hashes cannot guarantee unique scores.

## 5. Stale facts and unsupported geological certainty

- The complete official leaderboard review on2026-10-01 shows DARD0.3168;
  Batik Shirt Brothers is#3 at0.2998. The older same-day snapshot claiming joeyfezster
  #3 is archived, not presented as live. SDCF9/smashi34 are#35/#36 at0.1563;
  those are account-best values, not per-file receipts. Ownership remains unverified.
- Independent band6 comparison was rerun after staging the pinned USGS derivatives:
  rho0.999978, R²0.998037 against radiometric total count. Retain this high-confidence
  measured identity; do not revert to an unresolved label merely because a sibling
  wrote a conflicting interpretation. The embedded tilt/curvature label is flagged.
- All19 supplied feature bands contain missing-data sentinels inside the valid
  footprint (3,061 pixels each; band6 3,073). Sanitize inputs, then refuse—not clip—
  non-finite/out-of-range output. This is a pipeline hazard, not the proven cause
  of the archived rejection.
- R14's statement that bands15/17 had never been used is false: `basement_hinge`
  and `conductive_base_step`, among others, already use them. New terminology or
  a new weight is not new geological information.
- Known-catalogue folds, tip folds, SGMC proxies and geographic blocks expose
  different biases. No local score is private truth, a vent discovery, or a prize
  prediction. Claims that the lattice has a universal0.28 ceiling, all buried
  faults are absent from a catalogue, or all magnetic/conductive edges are faults
  are not supported by official source evidence and are not active conclusions.

## 6. Current research and automation boundaries

Four hypotheses were recorded BEFORE R15 implementation in
[11_r15_predeclared.md](11_r15_predeclared.md). Thermal data are actually staged,
licensed, footprint-checked and measured; event-plane and comparable well-network
acquisition remain incomplete. Proposed != viable != winning.

The official competition target is **new surface fault pixels**, not a temperature
map or vent map. DOE/USGS geology supports plausible mechanisms, not our detector's
performance. Shallow heat can be due to diffuse outflow or surface effects.

Automated review monitors approved public open-data/our GitHub endpoints only,
with byte hashes, failures, timestamps and change flags. A single reusable
GitHub-Actions-bot issue exposes current observations to static Pages; the browser
checks author/envelope/schema/approved links and uses text-only DOM rendering. It does not poll DrivenData
or silently certify a changed source. Competition facts/leaderboard remain dated
one-off reviewed snapshots with direct official links. Earlier assertions about a
specific DrivenData Terms prohibition were not independently relocated at the
attempted URLs this session (404); no new legal conclusion is inferred from them.

AI use: generative AI assisted source review, code, documents and hypothesis design;
humans remain responsible for correctness and authorship. Official Rules §3.2
requires disclosure in a final narrative. Preserve that disclosure in the handoff.

## 7. Operational review discoveries

Real-browser testing caught a nested complementary landmark and a320px overflow
on the long research-only identifier; both were corrected. Test polling was changed
from CSP-forbidden string evaluation to locator assertions without weakening CSP.
Preview serving is restricted to public files and blocks symlinks into private
in-repo data, traversal, dot directories and directory listings.

Output masks must be boolean/finite0-1; complex/object probabilities are refused
before writing. Ignored outside sentinels are not cast into overflowing floats.
Uniform probability rescaling is nondecreasing under the metric assumptions,
strict only when TP and truth mass are positive; an all-zero map cannot be scaled
to a nonzero one. The former unconditional “free strict increase” warning was
corrected. These changes do not alter the immutable primary or the frozen R15
scientific code/register.

On2026-10-01 GitHub subsequently returned401Bad credentials mid-session. Local
verification can continue, but hosted runs / PR / merge / deployed verification
require a functioning connection. Dry-run push never established that completion.

The logistic baseline documentation also now distinguishes case-control sigmoid
confidence from calibrated regional probability, clarifies allowed training-domain
vs visible-positive masks, and gives window WIDTHS (3x3=300m;9x9=900m) separately
from sample-centre spans. The organizer's supervised baseline is not the sole
intended method; no claim that every smaller CPU network is impossible is made.
No trained model or detector outputs were changed by this documentation correction.
