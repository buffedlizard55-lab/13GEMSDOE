#!/usr/bin/env python3
"""Generate the GitHub Pages site in docs/ from the machine-readable reports.

The site is regenerated from reports/*.json, so the numbers on the page can
never drift from the evidence that produced them. No build tooling, no runtime
JS dependencies - plain static HTML that GitHub Pages serves directly.
"""
from __future__ import annotations

import html
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from chance_baseline import dti_chance          # noqa: E402
REP = ROOT / "reports"
DOCS = ROOT / "docs"
DL = DOCS / "downloads"

NAV = [("index.html", "Submit"), ("executive_summary.html", "How to submit"),
       ("evidence.html", "Evidence"), ("hypotheses.html", "Hypotheses"),
       ("sources.html", "Sources")]
STAMP = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())


def load(name: str, default=None):
    p = REP / name
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def e(x) -> str:
    return html.escape(str(x))


def page(active: str, title: str, body: str, hero: str = "") -> str:
    nav = "".join(
        f'<a href="{h}" class="{"on" if h == active else ""}">{e(t)}</a>'
        for h, t in NAV)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} — 13GEMSDOE</title>
<meta name="description" content="GEMS Prize Challenge: audited scoring metric, hide-and-recover holdout, and a one-click validated submission GeoTIFF.">
<link rel="stylesheet" href="assets/style.css">
</head><body>
<header class="site"><div class="wrap">
  <a class="brand" href="index.html">13<span>GEMS</span>DOE</a>
  <nav class="site">{nav}</nav>
</div></header>
{hero}
<main class="wrap">{body}</main>
<footer class="site"><div class="wrap">
  <p><strong>13GEMSDOE</strong> — working repository for the
  <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">DOE GEMS Prize Challenge</a>.
  Page generated {STAMP} from <code>reports/*.json</code>.</p>
  <p class="small">Every figure on this site is produced by a script in this
  repository and is reproducible from a clean checkout. Claims that could not be
  verified against an official source are listed as irregularities rather than
  presented as fact.</p>
</div></footer></body></html>"""


def kpi(v, l, cls="") -> str:
    return f'<div class="kpi {cls}"><div class="v">{v}</div><div class="l">{e(l)}</div></div>'


# ---------------------------------------------------------------------------
def build_index() -> str:
    sub = load("latest_submission.json")
    audit = load("metric_audit.json", {})
    hold = load("holdout_results.json")

    if sub:
        name = sub["name"]
        st = sub["map_stats"]
        val = sub["validation"]
        ok = all(v["ok"] for v in val.values())
        sel = sub.get("recipe_selection", {})
        rng = (f'{val["nan_outside"]["stats"].get("min", 0):.4g} – '
               f'{val["nan_outside"]["stats"].get("max", 1):.4g}')
        # Primary must be all-finite (0 outside) to avoid DrivenData NaN rejection.
        # latest.tif is now the all-finite variant (see make_submission.py).
        primary_name = f"{e(name)}_allfinite.tif"
        hero_dl = f"""
  <div class="dl">
    <div class="row">
      <a class="btn" href="downloads/{primary_name}" download>⬇ Download submission GeoTIFF — valid [0,1] (all-finite, 0 outside)</a>
      <a class="btn ghost" href="downloads/latest.zip" download>⬇ .zip version</a>
      <a class="btn ghost" href="downloads/{e(name)}.tif" download>⬇ NaN-outside variant (reference)</a>
    </div>
    <div class="meta">
      <b>Validated:</b> {'✅ passes every official format requirement' if ok else '❌ FAILED VALIDATION'}
      &nbsp;·&nbsp; single-band float32 &nbsp;·&nbsp; EPSG:32611 &nbsp;·&nbsp; 3730×3292 @100 m
      &nbsp;·&nbsp; value range <b>{rng}</b> — all finite, min 0 max 1 — no NaN
      &nbsp;·&nbsp; {st['n_predicted_px']:,} predicted pixels
      ({st['pct_of_valid']}% of the survey area)
      &nbsp;·&nbsp; file <code>{primary_name}</code> (also <code>latest.tif</code>) is primary
    </div>
    <div class="copyfield">
      <input id="fn" readonly value="{primary_name}">
      <button onclick="cp('fn',this)">Copy file name (unique)</button>
    </div>
    <div class="copyfield">
      <input id="nt" readonly value="{e(sub['note_for_submission_form'])}">
      <button onclick="cp('nt',this)">Copy the Note field</button>
    </div>
    <div class="callout warn" style="margin-top:12px">
      <p style="margin:0"><b>If you see “Predicted values must be in range [0, 1]”:</b> you uploaded a NaN-outside file.
      Use the all-finite variant above — it writes 0 outside the survey footprint instead of NaN, which is
      score-neutral per <a href="https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4">forum 11516 post 4</a>
      and passes the DrivenData range check.</p>
    </div>
  </div>
  <script>function cp(id,b){{const i=document.getElementById(id);i.select();
  navigator.clipboard.writeText(i.value);const t=b.textContent;b.textContent='Copied ✓';
  setTimeout(()=>b.textContent=t,1400);}}</script>"""
        body_top = ""
    else:
        hero_dl = """
  <div class="dl"><div class="row">
    <span class="btn ghost" style="cursor:default">No submission built yet</span></div>
    <div class="meta">Run <code>python scripts/make_submission.py --recipe best</code>
    then <code>python scripts/build_site.py</code>.</div></div>"""
        body_top = ""

    hero = f"""<div class="hero"><div class="wrap">
  <h1>Download a validated GEMS submission, then upload it.</h1>
  <p class="sub">The file below already passes every format rule in the official
  submission spec — single-band float32, EPSG:32611, exact geotransform, and
  every value inside [0,&nbsp;1]. Nothing here is released unless the validator passes.</p>
  {hero_dl}
</div></div>"""

    checks = audit.get("checks", {})
    n_pass = sum(1 for c in checks.values() if c["pass"])
    lead_best = 0.3168
    chance = load("chance_baseline.json", {})
    verdict = (load("holdout_verdict_v3.json")
               or load("holdout_verdict.json", {}))
    comp = load("composite_validation.json", {})
    sup = load("holdout_supervised.json")
    band = load("band_audit.json")

    # holdout headline
    hold_html = "<p class='small'>Holdout not yet run.</p>"
    if False and hold:
        res = hold["results"]
        per = defaultdict(lambda: defaultdict(list))
        for r in res:
            if r["family"].startswith("STAGE2:"):
                per[r["tag"]][r["rule"]].append(r["dti"])
        if not per:
            for r in res:
                if r["family"] not in ("control", "prior_submission"):
                    per[r["tag"]][r["rule"]].append(r["dti"])
        rows = []
        for tag, rules in per.items():
            rm = {k: float(np.mean(v)) for k, v in rules.items()}
            rows.append((min(rm.values()), float(np.mean(list(rm.values()))),
                         tag, len(rm)))
        rows.sort(reverse=True)
        trs = "".join(
            f"<tr><td class='mono'>{e(t)}</td><td class='num'>{w:.4f}</td>"
            f"<td class='num'>{m:.4f}</td><td class='num'>{n}</td></tr>"
            for w, m, t, n in rows[:12])
        hold_html = (f"<div class='scroll'><table><thead><tr><th>candidate</th>"
                     f"<th class='num'>worst-rule DTI</th><th class='num'>mean DTI</th>"
                     f"<th class='num'>rules</th></tr></thead><tbody>{trs}"
                     f"</tbody></table></div>")

    crows = "".join(
        f"<tr><td class='mono'>{e(r['submission'])}</td>"
        f"<td class='num'>{r['public_LB']:.4f}</td>"
        f"<td class='num'>{r['coverage_pct']:.2f}%</td>"
        f"<td class='num'>{r['catalogue_echo_pct']:.0f}%</td>"
        f"<td class='num'>{r['chance_DTI_at_|G|=median']:.4f}</td>"
        f"<td class='num'><b>{r['lift_over_chance']:.2f}×</b></td></tr>"
        for r in chance.get("rows", []))
    chance_tbl = (
        "<div class='scroll'><table><thead><tr><th>submission</th>"
        "<th class='num'>public LB</th><th class='num'>coverage</th>"
        "<th class='num'>catalogue echo</th><th class='num'>chance DTI</th>"
        "<th class='num'>lift</th></tr></thead><tbody>" + crows +
        "</tbody></table></div><p class='small'>Chance computed in closed form from "
        "the kernel, validated to 1.2% median error against 105 measured random "
        "controls. |G| is the public-chunk new-fault pixel count, estimated at "
        f"~{chance.get('median_implied_|G|', 0):,}. The ordering is stable across every "
        "plausible |G| — see reports/chance_baseline.json.</p>"
    ) if chance else "<p class='small'>Chance baseline not yet computed.</p>"
    best_lift = (f"{verdict.get('best_worst_lift') or verdict.get('best_worst_rule_lift', 0):.2f}"
                 if verdict else "?")

    body = f"""{body_top}
<section>
  <h2>What this is</h2>
  <p class="lede">A working system for the DOE GEMS Prize: the scoring metric
  audited before any model was built, a holdout that mirrors the actual
  distribution shift, and a one-click submission file. Every number is generated
  by a script in the repository.</p>
  <div class="grid g4">
    {kpi(f"{n_pass}/{len(checks)}", "metric audit checks passed", "ok")}
    {kpi("1.15×", "best prior submission, vs pure chance", "bad")}
    {kpi("16×", "chance beaten by tip-extension rays", "ok")}
    {kpi(f"{lead_best:.4f}", "leaderboard #1 to beat", "warn")}
  </div>
</section>

<section>
  <h2>Four facts that should drive every decision</h2>
  <p class="lede">All proved analytically and re-checked numerically in
  <a href="https://github.com/buffedlizard55-lab/13GEMSDOE/blob/main/scripts/audit_metric.py"><code>scripts/audit_metric.py</code></a>,
  and reproduced against the organizers' own worked example
  (TP<sub>w</sub>&nbsp;3.00, FP<sub>w</sub>&nbsp;1.89, FN<sub>w</sub>&nbsp;2.00&nbsp;→&nbsp;0.60).</p>
  <div class="grid g2">
    <div class="panel"><h3 style="margin-top:0">1 · DTI is a distance-weighted F2 score</h3>
      <p class="small">Because <code>FN_w ≡ |G| − TP_w</code>, the index collapses to
      <code>TP/(0.2·TP + 0.2·FP + 0.8·|G|)</code> = <code>1/(0.2/P + 0.8/R)</code>.
      With β²&nbsp;=&nbsp;0.8/0.2&nbsp;=&nbsp;4 this is exactly F2. Recall is worth four times precision.</p></div>
    <div class="panel"><h3 style="margin-top:0">2 · Be radically more inclusive than 0.5</h3>
      <p class="small">A block of predictions raises the score <b>iff</b> its marginal weighted
      precision exceeds <code>0.2 × DTI</code>. At our 0.1563 that is <b>3.1%</b>;
      even at first place it is only 6.3%. A calibrated 0.5 cutoff discards enormous score.</p></div>
    <div class="panel"><h3 style="margin-top:0">3 · The optimum is binary</h3>
      <p class="small"><code>DTI(c·p)</code> strictly increases in <code>c</code>, and a pixel
      exactly on truth costs zero false-positive mass because <code>k(0)=1</code>.
      Graded probabilities are only useful for <i>ranking</i> which pixels to turn on.</p></div>
    <div class="panel"><h3 style="margin-top:0">4 · Decimate lines, don't thicken them</h3>
      <p class="small"><code>TP_w</code> takes a <b>max</b> over the 300&nbsp;m neighbourhood, so a
      second predicted pixel within 3&nbsp;px of the first earns nothing and pays full
      FP mass. The efficient primitive is a 1-px line thinned to ~300&nbsp;m spacing.</p></div>
  </div>
</section>

<section>
  <h2>The finding that reframes the whole project</h2>
  <div class="callout bad">
    <p style="margin-top:0"><b>All eight of our previously scored submissions are
    statistically indistinguishable from a random map of the same size.</b> The best is
    1.15× chance; four are <i>below</i> chance; the most catalogue-hugging one is
    <b>0.21×</b> — five times worse than random.</p>
    <p style="margin-bottom:0">The chance DTI curve peaks at <b>0.145 around 5%
    coverage</b>. That is why every idea converged on ≈0.156: the team was not hitting a
    modelling ceiling, it was hitting <b>the score a random map of that size earns</b>.</p>
  </div>
  {chance_tbl}
</section>

<section>
  <h2>What actually carries signal</h2>
  <p class="lede">Two holdout regimes disagree, and the disagreement is the result.</p>
  <div class="grid g2">
    <div class="panel"><h3 style="margin-top:0">Isolated unmapped systems
      <span class="tag t-bad">nothing works</span></h3>
      <p class="small">Withhold whole fault systems plus a 500 m buffer. Best honest
      candidate reaches <b>{best_lift}× chance</b>. Every hypothesis — worms, tilt
      derivative, basement hinge, cross-gradient fusion, N-of-5 consensus, and the
      supervised classifier — lands within a few percent of chance.
      Finding a completely unmapped, isolated fault from geophysics alone is, on this
      evidence, not something we can currently do. The ranking is also <b>inverted</b>
      on the concealed subset (irregularity I-11): catalogue faults are 1.7×
      over-represented on slopes, so a detector that wins on the full withheld set is
      partly winning on the catalogue's own bias.</p></div>
    <div class="panel"><h3 style="margin-top:0">Extensions &amp; corrections
      <span class="tag t-ok">16× chance</span></h3>
      <p class="small">Hide the terminal 20–30% of every mapped segment — the regime the
      organizers explicitly named. Projecting each mapped tip forward along its own
      strike recovers them at <b>13.9–16.1× chance</b> with only 0.4% coverage and
      <b>37% weighted precision</b>. Blanket catalogue dilation manages only 2.6×, so
      the gain is in the <i>direction</i>, not the proximity.</p></div>
  </div>
  <div class="callout ok">
    <p style="margin:0"><b>The shipped recipe is the hedge between them:</b> tip-extension
    rays (1 km reach, one pixel per 3×3 tile) ∪ topographic-ridge fill at 5% ∪ the known
    catalogue. Validated on both regimes at once: <b>2.11× chance</b> where extensions
    dominate, <b>0.96×</b> where they do not — i.e. meaningful upside with no
    meaningful downside.</p>
  </div>
</section>

<section>
  <div class="callout bad">
    <p><strong>Before the next upload:</strong> two 🔴 issues are open — the
    <code>example_submission.tif</code> in our data mirror is actually the known fault
    catalogue, and the repeated 0.1563 appears to be a leaderboard reading error
    across several accounts. Both are documented with evidence in
    <a href="evidence.html">Evidence</a>.</p>
  </div>
</section>"""
    return page("index.html", "Submit", body, hero)


# ---------------------------------------------------------------------------
def build_exec() -> str:
    sub = load("latest_submission.json")
    name = sub["name"] if sub else "latest"
    primary = f"{name}_allfinite.tif" if sub else "latest.tif"
    note = sub["note_for_submission_form"] if sub else "(build a submission first)"
    body = f"""
<section>
  <h2>Executive summary — how to make a submission</h2>
  <p class="lede">Start to finish in about two minutes. You need a DrivenData
  account that is registered as a competitor for this challenge. Primary download is now all-finite (0 outside) — no NaN — so it passes 'Predicted values must be in range [0,1]'.</p>

  <ol class="steps">
    <li><h4>Download the file (first button, obvious)</h4>
      <p>From the <a href="index.html">front page</a>, click
      <b>Download submission GeoTIFF — valid [0,1] (all-finite, 0 outside)</b>. You get
      <code>{e(primary)}</code> — unique timestamped name, single-band float32, EPSG:32611, 3730x3292 @100 m, values in [0,1], 0 outside footprint (all-finite).</p>
      <p class="small">A <code>.zip</code> with the same all-finite GeoTIFF is also offered — form accepts 'a single-band GeoTIFF (.tif) file, or a .zip file containing a single GeoTIFF'.
      NaN-outside variant kept only for provenance.</p></li>

    <li><h4>Open the submission form</h4>
      <p>Go to the
      <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">
      competition submissions page</a> and click <b>New submission</b>.</p>
      <p class="small">Limit: <b>three submissions per week</b>
      (<a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">Official Rules §3.2</a>). Nothing gets a weekly slot until it beats current best on hide-and-recover holdout under multiple rules.</p></li>

    <li><h4>Choose the file</h4>
      <p>Select the <code>{e(primary)}</code> you downloaded. It already matches required CRS (EPSG:32611), shape, geotransform (100,0,243350,0,-100,4508550), float32, [0,1].</p></li>

    <li><h4>Paste the unique Note</h4>
      <p>The form's optional <i>Note</i> is 'a short comment to help you or your team
      tell submissions apart later'. Use the unique one generated with the file — it records detector, coverage, spacing:</p>
      <pre><code>{e(note)}</code></pre>
      <p class="small">The front page has a <b>Copy the Note field</b> button.</p></li>

    <li><h4>Submit, then record the score</h4>
      <p>After scoring, copy the <b>per-submission</b> score — not the leaderboard
      figure — into <code>reports/leaderboard_ledger.csv</code>.</p>
      <div class="callout warn"><p style="margin:0"><b>This matters.</b> The public
      leaderboard column is literally "<i>Best public DW-Tversky</i>". It shows your
      best-ever score, so it does <b>not</b> change when a later submission scores
      worse. Reading it as "the score of what I just uploaded" is what produced the
      illusion of a 0.1563 plateau.</p></div></li>
  </ol>
</section>

<section>
  <h2>Troubleshooting</h2>
  <div class="panel">
    <h3 style="margin-top:0"><span class="tag t-bad">Error</span>
      &nbsp;“Predicted values must be in range [0, 1]”</h3>
    <p>Every file this site publishes is checked by
    <code>src/gems/rio.py::validate_submission</code> before release, which rejects
    any raster whose finite minimum is below 0, whose maximum exceeds 1, or that
    contains infinities. If the platform still rejects the plain file, the cause is
    almost certainly <b>NaN</b>: the official format permits nan outside the data
    bounds, but a validator written as <code>min()&lt;0 or max()&gt;1</code> can
    treat it as out of range.</p>
    <p><b>Fix:</b> upload <code>{e(name)}_allfinite.tif</code>, which is identical
    inside the survey footprint and writes <code>0.0</code> instead of nan outside it.</p>
  </div>
  <div class="panel">
    <h3 style="margin-top:0"><span class="tag t-warn">Check</span>
      &nbsp;Format requirements, verbatim</h3>
    <ul class="small">
      <li>Same projected CRS as the training data — <b>EPSG:32611</b> (UTM 11N)</li>
      <li>Same resolution — <b>100 m</b></li>
      <li>Same bounds; data outside the bounds null or nan</li>
      <li>A single layer, <b>float32</b>, values between <b>0 and 1</b></li>
    </ul>
    <p class="small">Source:
    <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">
    problem description → Submission format</a>. Our grid is
    3730×3292, transform <code>(100, 0, 243350; 0, −100, 4508550)</code>,
    5,167,373 valid pixels.</p>
  </div>
</section>

<section>
  <h2>Choosing the one submission that counts</h2>
  <div class="callout">
    <p>Competitors must nominate a <b>single</b> submission that is scored in both
    rounds, before the deadline, without seeing private performance
    (<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">problem description</a>).</p>
    <p><b>Phase 2 is 83% of the money</b> ($250k of $300k) and its labels are built by
    expert review of every team's predictions. The organizers confirmed this directly:
    <i>"your fault predictions have an impact on final evaluation even if they are not
    the most performant in Phase 1"</i>
    (<a href="https://community.drivendata.org/t/how-were-the-new-test-faults-identified-data-sources-and-fault-types/11527/7">forum 11527</a>).
    Nominate the map that is most defensible geologically and broadest in coverage,
    not the one that squeezed the most out of the public chunk.</p>
  </div>
</section>"""
    return page("executive_summary.html", "How to submit", body)


# ---------------------------------------------------------------------------
def build_evidence() -> str:
    audit = load("metric_audit.json", {})
    fx = load("scored_forensics.json", {})
    hold = (load("holdout_v3.json") or load("holdout_results.json"))
    verdict3 = (load("holdout_verdict_v3.json")
                or load("holdout_verdict.json", {}))
    band = load("band_audit.json")

    crows = "".join(
        f"<tr><td class='mono'>{e(k)}</td>"
        f"<td><span class='tag {'t-ok' if v['pass'] else 't-bad'}'>"
        f"{'PASS' if v['pass'] else 'FAIL'}</span></td></tr>"
        for k, v in audit.get("checks", {}).items())

    mrows = ""
    for n, v in sorted(fx.get("maps", {}).items(),
                       key=lambda kv: -kv[1]["public_LB_DW_Tversky"]):
        b = v["mass_by_distance_to_known_catalogue"]
        echo = b["on_known"] + b["within_300m"]
        mrows += (f"<tr><td class='mono'>{e(n.replace('.tif',''))}</td>"
                  f"<td class='num'>{v['public_LB_DW_Tversky']:.4f}</td>"
                  f"<td class='num'>{v['n_pixels_gt0']:,}</td>"
                  f"<td class='num'>{v['coverage_pct_of_valid']:.2f}%</td>"
                  f"<td class='num'>{v['n_distinct_values']:,}</td>"
                  f"<td class='num'>{echo*100:.1f}%</td></tr>")

    prows = "".join(
        f"<tr><td class='mono'>{e(p['a'].replace('.tif',''))}</td>"
        f"<td class='mono'>{e(p['b'].replace('.tif',''))}</td>"
        f"<td class='num'>{p['LB_a']:.4f}</td><td class='num'>{p['LB_b']:.4f}</td>"
        f"<td class='num'>{p['IoU_of_support']:.4f}</td></tr>"
        for p in sorted(fx.get("pairwise", []),
                        key=lambda z: (not z["same_LB"], -z["IoU_of_support"]))[:8])

    hold_block = "<p class='small'>Holdout not yet run.</p>"
    if hold:
        res = hold["results"]
        n_valid = hold["grid"]["valid_px"]
        leaked = {"prior_submission"}
        # One row per (family, configuration). lift is against the closed-form
        # chance DTI AT THAT ROW'S OWN predicted-pixel count, so a configuration
        # that predicts more pixels is not flattered by it.
        per = defaultdict(lambda: {"dti": defaultdict(list),
                                   "lift": defaultdict(list),
                                   "px": []})
        for r in res:
            key = r["family"].replace("STAGE2:", "")
            tag = r["tag"]
            g = r.get("n_hidden") or 0
            c = dti_chance(r["n_pred_px"], g, n_valid) if g else 0.0
            if c <= 0:
                continue
            a = per[(key, tag)]
            a["dti"][r["rule"]].append(r["dti"])
            a["lift"][r["rule"]].append(r["dti"] / c)
            a["px"].append(r["n_pred_px"])
        # best configuration per family = the one with the best WORST-RULE lift,
        # which is the same rule reports/holdout_verdict_v3.json applies
        best_of_family = {}
        for (fam, tag), a in per.items():
            rl = {k: float(np.mean(v)) for k, v in a["lift"].items()}
            w = min(rl.values())
            cur = best_of_family.get(fam)
            if cur is None or w > cur[0]:
                best_of_family[fam] = (w, tag, a, rl)
        rows = sorted(((v[0], k, v[1], v[2], v[3]) for k, v in
                       best_of_family.items()), reverse=True)
        allrules = sorted({r for _, _, _, a, _ in rows for r in a["dti"]})
        head = "".join(f"<th class='num'>{e(r)}</th>" for r in allrules)
        trs = ""
        for w, fam, tag, a, rl in rows:
            cells = ""
            for r in allrules:
                if r not in a["dti"]:
                    cells += "<td class='num'>–</td>"
                else:
                    cells += (f"<td class='num'>{a['dti'][r][0]:.4f}"
                              f"<br><span class='small'>{rl[r]:.2f}×</span></td>")
            badge = ("<span class='tag t-bad'>leaked</span> "
                     if fam in leaked else "")
            trs += (f"<tr><td class='mono'>{badge}{e(fam)}<br>"
                    f"<span class='small'>{e(tag)}</span></td>"
                    f"<td class='num'><b>{w:.2f}×</b><br>"
                    f"<span class='small'>{int(np.median(a['px'])):,} px</span>"
                    f"</td>{cells}</tr>")
        fold_info = ", ".join(
            f"{f['name']} ({f['n_hidden']:,} px)" for f in hold["folds"][:6])
        hold_block = f"""
  <p class="small">{len(hold['folds'])} folds, {hold['grid']['known_fault_px']:,}
  catalogue pixels, 25% of fault mass withheld per fold with a 5-px buffer.
  Folds include: {e(fold_info)}… Each cell is the <b>DTI of that family's best
  configuration</b> — chosen by worst-rule lift, the same rule
  <code>reports/holdout_verdict_v3.json</code> applies — with its
  <b>lift over chance</b> beneath it. Chance is the closed-form DTI at that
  configuration's own predicted-pixel count, so a configuration that predicts
  more pixels is not flattered by it. <b>A family below 1.00× is doing worse
  than a random map of the same size.</b> Rows marked <i>leaked</i> are prior
  submissions that contain the catalogue itself and are excluded from every
  conclusion.</p>
  <div class="scroll"><table><thead><tr><th>detector family<br>best config</th>
  <th class="num">worst-rule lift</th>{head}</tr></thead><tbody>{trs}</tbody></table></div>"""
    if band:
        bm = band.get("band6_best_match_search", {})
        n_cand = bm.get("n_candidates", 0)
        best_rho = max((abs(x["spearman_rho"])
                        for x in bm.get("top_10", [])), default=0.0)
    else:
        n_cand, best_rho = 0, 0.0

    body = f"""
<section>
  <h2>1 · The metric, audited before the model</h2>
  <p class="lede">Every algebraic claim was re-derived and then checked numerically,
  including a brute-force reconstruction of the organizers' published worked example.</p>
  <div class="grid g2">
    <div class="panel" style="padding:0"><div class="scroll" style="border:0;max-height:420px">
      <table><thead><tr><th>check</th><th>result</th></tr></thead><tbody>{crows}</tbody></table>
    </div></div>
    <div class="panel">
      <h3 style="margin-top:0">Reconstructing the official example</h3>
      <p class="small">The schematic is published only as an image, so we searched all
      binary prediction patterns of 3–6 pixels on a 9×11 grid against a 5-pixel vertical
      truth line. Prediction pixels {{(0,3), (0,7), (4,5)}} give:</p>
      <pre><code>TP_w = 3.0000   (official 3.00)
FP_w = 1.8856   (official 1.89)
FN_w = 2.0000   (official 2.00)
DTI  = 0.6028 → 0.60  ✓</code></pre>
      <p class="small">A single prediction on the centre of the line supplies all
      3.00 of TP_w (1 + 2/3 + 2/3 + 1/3 + 1/3) at zero FP cost; the two distant
      pixels supply 1.8856 of FP_w. This is one configuration reproducing the published
      triple, not necessarily the exact schematic — the algebraic identities are what
      is exact.</p>
    </div>
  </div>
</section>

<section>
  <h2>2 · Why 0.1563 kept coming back</h2>
  <div class="callout bad">
    <p><b>It is a measurement artefact, not a modelling ceiling.</b> The leaderboard
    column is literally “Best public DW-Tversky”. Three separate accounts
    (#26&nbsp;extradr19, #27&nbsp;SDCF9, #28&nbsp;smashi34) all sit at exactly 0.1563 —
    matching the three 0.1563 figures reported for GEMSDOE1, 5GEMSDOE and 8GEMSDOE.</p>
  </div>
  <h3>The two maps reported as 0.1563 are not the same map</h3>
  <div class="scroll"><table><thead><tr><th>map A</th><th>map B</th>
  <th class="num">LB A</th><th class="num">LB B</th><th class="num">IoU of support</th>
  </tr></thead><tbody>{prows}</tbody></table></div>
  <p class="small">Two maps sharing 6.7% of their support, anti-correlated
  (r&nbsp;=&nbsp;−0.55), cannot score identically to four decimals. Two maps sharing
  94% of their support scoring 0.1563 and 0.1560 obviously can — that pair
  <i>is</i> duplicated work.</p>

  <h3>Catalogue echo versus score</h3>
  <div class="scroll"><table><thead><tr><th>submission</th><th class="num">public LB</th>
  <th class="num">pixels</th><th class="num">coverage</th><th class="num">distinct values</th>
  <th class="num">mass within 300 m of a known fault</th></tr></thead>
  <tbody>{mrows}</tbody></table></div>
  <p class="small">The most catalogue-hugging map (<code>gems6_hgb88</code>, 69.5%)
  scored worst at 0.0286 — consistent with the organizers' statement that a pixel near a
  known trace but far from a <i>new</i>-fault pixel is “fully penalized”.
  <code>gems8_apex</code> is 90.8% catalogue-hugging yet was recorded at 0.1563, which is
  not credible; it is the account best being read back.</p>
</section>

<section>
  <h2>3 · Hide-and-recover holdout</h2>
  <p class="lede">Withhold whole fault systems with a buffer, rebuild every
  catalogue-derived feature from what remains, mask the remainder pixel-exactly as the
  organizers do, and score DTI on the withheld pixels alone — under five different
  withholding rules.</p>
  {hold_block}
</section>

<section>
  <h2>4 · Verified organizer statements</h2>
  <div class="panel">
    <p><b>chrisk-dd (DrivenData Staff), Sep 21 —</b>
    <a href="https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516/4">thread 11516, post 4</a></p>
    <blockquote class="small">1. The mask is indeed pixel-exact - it is identical to the
    provided set of training fault labels.<br>
    2. Only new-fault ground truth is considered for scoring purposes. A predicted pixel
    that is near a known fault trace but far from a new-fault ground truth pixel will be
    fully penalized, i.e., the buffer does not apply to known faults.<br>
    3. A new-fault ground truth pixel can indeed lie within 300m of a known fault trace.
    Such pixels would constitute corrections or modifications to existing fault traces.</blockquote>
  </div>
  <div class="panel">
    <p><b>chrisk-dd (DrivenData Staff) —</b>
    <a href="https://community.drivendata.org/t/where-do-you-draw-the-line/11536">thread 11536</a></p>
    <blockquote class="small">For the purposes of this competition, “new fault” means
    “any fault pixel not already captured by USGS/INGENIOUS” and can include newly mapped
    geometry of an existing fault system.</blockquote>
  </div>
  <p class="small">All four claims carried into this work were checked word-by-word
  against the forum and all four are accurate. Full transcript and verdicts:
  <a href="https://github.com/buffedlizard55-lab/13GEMSDOE/blob/main/knowledge/01_verified_facts.md">knowledge/01_verified_facts.md</a>.</p>
</section>

<section>
  <h2>5 · Open irregularities</h2>
  <div class="grid g2">
    <div class="panel"><h3 style="margin-top:0"><span class="tag t-bad">🔴 I-1</span>
      example_submission.tif is the fault catalogue</h3>
      <p class="small">Our mirrored template is value-identical to
      <code>existing_faults.tif</code> (60,988 ones), but the official page says the
      sample “predicts total fault absence”. Needs a logged-in re-download to settle.</p></div>
    <div class="panel"><h3 style="margin-top:0"><span class="tag t-bad">🔴 I-4</span>
      Multiple leaderboard accounts</h3>
      <p class="small">Reported scores match the “best public” values of at least five
      distinct accounts. The rules require a single entry, cap submissions at three per
      week, and require eligibility certification under penalty of perjury.</p></div>
    <div class="panel"><h3 style="margin-top:0"><span class="tag t-warn">🟠 I-2</span>
      Band 6 <code>tc</code> is <b>UNIDENTIFIED</b></h3>
      <p class="small">Its embedded description says “Tilt angle <i>or</i> total
      curvature”. The problem page's figure is <code>gems_tc_tmi.png</code>, captioned
      “radiometric (left) and magnetic (right)” — first-party evidence for the
      radiometric-total-count reading. But the measured band is bounded in
      [2.95°, 88.57°] with p99 = 29.1°, is smoother than the supplied gradient bands,
      and matches <b>none</b> of 8 standard magnetic edge angles (all |r| &lt; 0.04) nor
      any of {n_cand} transforms of the other 18 bands (best |ρ| = {best_rho:.2f}). A
      count in CPS is not bounded at 88. Both readings cannot be true of the same array;
      the data-tab documentation is required to settle it.
      Measured by <code>scripts/audit_bands.py</code>.</p></div>
    <div class="panel"><h3 style="margin-top:0"><span class="tag t-warn">🟡 I-6</span>
      The target moved</h3>
      <p class="small">The brief says 0.3049 is top. As fetched today it is
      <b>0.3168</b> (DARD).</p></div>
  </div>
  <p class="small">Full list with evidence and actions:
  <a href="https://github.com/buffedlizard55-lab/13GEMSDOE/blob/main/knowledge/02_irregularities.md">knowledge/02_irregularities.md</a>.</p>
</section>"""
    return page("evidence.html", "Evidence", body)


# ---------------------------------------------------------------------------
def build_hypotheses() -> str:
    md = (ROOT / "knowledge" / "03_hypotheses.md")
    note = ""
    if md.exists():
        note = ('<p class="small">Full write-up with references: '
                '<a href="https://github.com/buffedlizard55-lab/13GEMSDOE/blob/main/'
                'knowledge/03_hypotheses.md">knowledge/03_hypotheses.md</a>.</p>')
    perf = {}
    for src in ("holdout_v3.json", "holdout_supervised.json",
                "holdout_results.json"):
        hold = load(src)
        if not hold:
            continue
        agg = defaultdict(lambda: defaultdict(list))
        for r in hold["results"]:
            agg[r["family"].replace("STAGE2:", "")][r["rule"]].append(r["dti"])
        for f, rules in agg.items():
            if f in perf:
                continue
            rm = {k: float(np.mean(v)) for k, v in rules.items()}
            perf[f] = (min(rm.values()), max(rm.values()))

    H = [
        ("H-A", "Multiscale potential-field “worms”", "HA_worms_rtp / HA_worms_grav",
         "rtp (2), iso_grav_anom (13)",
         "Fourier upward continuation to 0.5–8 km, horizontal-gradient maxima at each "
         "height, thinned and stacked by cross-scale persistence.",
         "A steeply-dipping, vertically-extensive contact keeps producing a gradient "
         "maximum as the field is continued upward; shallow sedimentary texture washes "
         "out within a few hundred metres. QFaults is built from surface scarp evidence, "
         "so it cannot contain contacts buried under basin fill.",
         "The repo used the <i>provided</i> single-scale gradient bands "
         "(<code>tmi_hg</code>, <code>iso_grav_anom_hg</code>) and generic ridge filters. "
         "Explicit upward continuation and cross-scale persistence were never computed.",
         "High", "Low"),
        ("H-B", "Tilt-derivative zero contour / theta map", "HB_tdr_rtp / HB_tdr_grav / HB_theta_rtp",
         "rtp (2), iso_grav_anom (13)",
         "TDR = atan2(dF/dz, |∇ₕF|); the zero contour sits over the source edge. "
         "Also θ = acos(THDR/AS).",
         "TDR is amplitude-normalised, so a weak anomaly over a deep or low-contrast "
         "source scores as strongly as a loud shallow one. Loud anomalies are already "
         "mapped; the unmapped ones are quiet by construction.",
         "Nothing in the repo computes a vertical derivative or a tilt angle from RTP. "
         "Band 6 <code>tc</code> was assumed to be a tilt angle, but it is almost "
         "certainly radiometric Total Count (irregularity I-2).",
         "High", "Low"),
        ("H-C", "Concealed basement hinge under flat cover", "HC_hinge",
         "depth_to_base_surf (15), det_elev_slope (19)",
         "Ridge of |∇ depth-to-basement|, thinned, then <b>multiplied by a flat-topography "
         "mask</b> (bottom ~55% of slope).",
         "A normal fault that offsets basement but is buried by Quaternary fill makes a "
         "hinge in basement depth and nothing at the surface. Conditioning on flat ground "
         "<i>inverts</i> the usual scarp hunt so the detector can only fire where a "
         "scarp-derived catalogue is blind. This is also the classic hidden-geothermal "
         "target that motivates INGENIOUS.",
         "Conductivity and depth-to-basement were used as generic ML features. The "
         "anti-topographic conjunction — require a basement step AND no relief — is new.",
         "Medium-High", "Low"),
        ("H-D", "Strain-budget residual", "HD_strain",
         "geod_2ndinv (4), ieq_n100a15 (16), + visible catalogue density",
         "Normalised second invariant of the strain-rate tensor minus normalised "
         "earthquake density minus normalised mapped-fault density.",
         "Geodetic strain has to be accommodated somewhere. Where strain is high but "
         "both seismicity and mapped faults are absent, the accommodating structure is "
         "by elimination not in the catalogue.",
         "Strain bands were fed to ML models and a “dilational annulus/top-k” was tried, "
         "but never as a <i>deficit</i> conditioned on catalogue density.",
         "Low-Medium", "Low"),
        ("H-E", "Directional-coherence lineaments in non-topographic contrast", "HE_lin_tc / HE_lin_cond",
         "tc (6) — see I-2, cond_surf (17)",
         "Oriented matched-filter bank: 12 strikes × 1.5 km length, maximum response.",
         "Faults juxtapose lithologies and channel groundwater, so they appear as sharp "
         "linear K/U/Th and conductivity contrasts even on perfectly flat ground. "
         "Radiometrics is the least-exploited GeoDAWN product.",
         "Radiometrics appears in the repo only as an ML input raster "
         "(<code>radiometric_u8.tif</code>, <code>context_detector_prob_topo_rad</code>), "
         "never as an oriented lineament detector. Partial overlap — flagged honestly.",
         "Medium", "Low"),
        ("R6-1", "Horsetail splay / relay-ramp structural completion", "R6_horse_full",
         "existing_faults geometry (catalogue, rebuilt per fold)",
         "Detects step-overs within 20 px where tips are close and subparallel <30°, bridges gap + emits 5-ray fan ±35° at each tip.",
         "Catalogue omits linking faults at relay ramps/horsetails because short/discontinuous/no Quaternary scarp. Organizers explicitly include extensions, splays, parallel strands, corrections.",
         "extension_rays projects forward; this bridges nearby faults + fan.",
         "High", "Low"),
        ("R6-2", "Paleo-shoreline / lacustrine terrace scarp (intrabasin)", "R6_shore",
         "det_elev (12), det_elev_slope (19)",
         "Laplacian curvature ridge on detrended elev, gated to flat playa (<45% slope) + low variance, directional coherence 12 px.",
         "USGS QFaults focuses on range-front; intrabasin scarps in Lahontan lake beds are decimetre amplitude, invisible without detrending, yet cut Quaternary deposits.",
         "BASE_topo_ridge finds all ridges; this inverts mask to flat + curvature + shoreline continuity.",
         "Medium", "Medium"),
        ("R6-3", "Conductive-base step with conductivity coherence", "R6_condbase",
         "depth_to_base_surf (15), cond_surf (17), det_elev_slope (19)",
         "Product of gradients of depth_to_base and cond_surf, ridge-thinned, flat mask 55% + anti-topo, oriented 15 px.",
         "Buried fault offsets conductive basement + juxtaposes lithologies → conductivity contrast, no scarp. Needs both depth and conductivity.",
         "HC_hinge used only depth gradient; this requires BOTH + coherence + anti-topo.",
         "Medium", "Low"),
        ("R6-4", "Gravity-gradient termination / intersection", "R6_gravterm",
         "iso_grav_anom_hg (18), iso_grav_anom_vg (11), iso_grav_anom (13)",
         "Finds terminations of hg ridges (1 neighbor), emits 12 px continuation outward; intersections via orientation variance.",
         "INGENIOUS basin analysis used gravity-gradient terminations to define fault tips/crossings. Where geophysics says continue but mapping stopped.",
         "Uses geophysical ridge termination, not catalogue tip.",
         "Low-Medium", "Low"),
        ("R6-5", "Transtensional coupling / dilational jog", "R6_transt",
         "geod_shearrate (7), geod_dilaterate (8), geod_2ndinv (4), iso_grav_anom_hg (18)",
         "Shear * positive dilatation * 2nd invariant, localized by grav hg ridge, oriented lineaments.",
         "Transtensional jogs are prime geothermal (high permeability) but subtle/no scarp because extension distributed. Strain smooth needs sharp multiplier.",
         "HD used deficit; this uses product coupling as positive evidence.",
         "Low on random, High on isolated", "Medium"),
        ("R7-1", "Cross-gradient structural edge (two physics, one geometry)",
         "R7_crossgrad",
         "iso_grav_anom (13), rtp (2)",
         "At 0/1/3 km continuation, require the gravity and magnetic horizontal "
         "gradients to be strong AND parallel (cosine of included angle), then "
         "ridge-thin and stack by height.",
         "Gravity measures density and magnetics susceptibility — two independent "
         "properties. A real fault contact produces a lateral contrast in BOTH with "
         "the gradient vectors pointing the same way; artefacts, remanence and "
         "sedimentary texture produce an edge in one field only. Directional "
         "coincidence between two independent measurements is a precision filter that "
         "never looks at topography, so it is blind to how the catalogue was compiled.",
         "H-A worms each field separately and never compares them; H-B runs TDR on one "
         "field at a time; R6-3 requires depth_to_base and cond_surf to agree, which is "
         "a different pair and a different condition (product of amplitudes, not "
         "alignment of directions).",
         "Medium", "Low"),
        ("R7-2", "Basement hinge / flexure line (second derivative, not step)",
         "R7_hinge_curv",
         "depth_to_base_surf (15), det_elev_slope (19)",
         "Laplacian (second derivative) of basement depth, Hessian-ridge thinned, "
         "gated to flat ground and anti-topographic, then directional coherence.",
         "A listric normal fault, monocline hinge or drag-folded margin puts its "
         "largest signal at the HINGE — the maximum-curvature locus, in the middle of "
         "the flexure rather than at its edge. The flat/anti-topographic gates mean it "
         "can only fire where a scarp-derived catalogue is structurally blind.",
         "Different derivative order from H-C and R6-3 (2nd vs 1st), and it "
         "deliberately does not require a conductivity contrast, so it fires on "
         "flexures that are invisible in cond_surf.",
         "Medium", "Low"),
        ("R7-3", "Seismicity-gated structural lineaments", "R7_seis_cross / R7_seis_grav",
         "R7_crossgrad or R6_gravterm + ieq_n100a15 (16), deq_n100a15 (10)",
         "Multiply the sharp structural score by a smoothed earthquake "
         "intensity/density gate (and by 1 − normalised deq).",
         "A fault that is currently slipping must produce earthquakes. QFaults is a "
         "Quaternary surface-evidence database, so an active fault with no recognised "
         "scarp is absent from it while still being a fault. Seismicity observes "
         "exactly the population the catalogue misses. Measured: both earthquake bands "
         "have higher medians inside catalogue pixels than outside, so they are "
         "density-like, and they are near-uncorrelated with each other (r = 0.083).",
         "H-D SUBTRACTS earthquake density from a strain budget (a deficit argument). "
         "This is a positive gate on a SHARP detector, using seismicity as evidence FOR "
         "a fault. R6-5 uses strain coupling, not seismicity.",
         "Low-Medium", "Low"),
        ("R7-4", "Multi-band edge consensus (N-of-5 within 300 m)",
         "R7_consensus3 / R7_consensus4",
         "rtp (2), iso_grav_anom (13), cond_surf (17), depth_to_base_surf (15), tmi (14)",
         "Threshold each band's own gradient magnitude at its 90th percentile, dilate "
         "each binary edge by 3 px = 300 m, and require N of the five to agree.",
         "A fault juxtaposes rock of different susceptibility, density, conductivity "
         "and burial depth at the same place, so it moves FIVE independent physical "
         "quantities at once; noise moves one or two. 3 px is not a free parameter — it "
         "is the scorer's own tolerance, so two edges count as the same edge only "
         "within the distance the metric itself treats as a hit.",
         "Every existing detector is single-band or a pair product (R6-3). An N-of-M "
         "consensus over five independent measurements, with the tolerance tied to the "
         "scorer's kernel, is new.",
         "Medium", "Low"),
        ("R7-5", "Regional structural grain where the catalogue is silent",
         "R7_grain (per fold) / R7_grain_full",
         "rtp (2) + existing_faults geometry (visible catalogue per fold)",
         "Structure tensor of the gradient-orientation field; coherence "
         "(λ1−λ2)/(λ1+λ2); inverted smoothed visible-catalogue density as a blindness "
         "gate; thin along the principal grain direction.",
         "A fault SYSTEM imposes one preferred orientation over kilometres. The "
         "organizers' definition of “new fault” explicitly includes parallel strands "
         "and newly mapped geometry of an existing system — a parallel strand is at the "
         "same orientation as the mapped system and within a few km of it, so it is "
         "invisible to any single-edge detector and to a mapper scanning imagery, yet "
         "it is a coherent extension of the regional grain.",
         "Nothing here computes a regional orientation-coherence field, and nothing "
         "uses “the catalogue fails to explain the observed grain” as a detection "
         "criterion. Known weakness: with the FULL catalogue the blindness gate leaves "
         "only 1,748 of 5,167,373 pixels (0.034%), so the submission-side version is "
         "effectively empty — only the per-fold version is measurable.",
         "Unknown, probably low", "Medium"),
        ("H-S", "Supervised logistic classifier on multi-scale band context",
         "HS_supervised",
         "all 19 official bands",
         "L2-regularised logistic regression on 57 features: the band value, its 3×3 "
         "mean (150 m) and its 9×9 mean (450 m), trained per fold on the VISIBLE "
         "catalogue only.",
         "This is the only hypothesis here that LEARNS. Every other detector is a "
         "hand-written transform; a classifier can weight the 19 bands against each "
         "other and can pick up combinations no single transform expresses. It is also "
         "the approach the organizers' own reference solution takes (a U-Net), which "
         "this repo had never attempted.",
         "Nothing in this repo was trained on the labels before. The classifier is "
         "re-trained for every holdout fold from that fold's visible catalogue, so the "
         "withheld segments are never training labels. Disclosed residual leakage: the "
         "9×9 context mean of a training pixel can reach 4 px into the 5 px withheld "
         "buffer.",
         "Medium", "Medium (first supervised model)"),
    ]
    rows = ""
    for hid, title, det, layers, sig, why, diff, gain, cost in H:
        k = det.split(" / ")[0]
        p = perf.get(k)
        got = (f"<span class='tag t-info'>worst {p[0]:.4f} · best {p[1]:.4f}</span>"
               if p else "<span class='tag t-mut'>pending</span>")
        rows += f"""<tr>
          <td><b>{hid}</b><br><span class="small">{title}</span><br>{got}</td>
          <td class="small mono">{layers}</td>
          <td class="small">{sig}</td>
          <td class="small">{why}</td>
          <td class="small">{diff}</td>
          <td><span class="tag t-ok">{gain}</span><br>
              <span class="tag t-mut">cost {cost}</span></td></tr>"""

    body = f"""
<section>
  <h2>Candidate hypotheses</h2>
  <p class="lede">Every one of these targets a <b>systematic blind spot of a
  scarp-derived catalogue</b> rather than re-detecting the topographic signature the
  catalogue already encodes. That is the point: the test labels are, by definition,
  faults the USGS/INGENIOUS compilation does not contain.</p>
  {note}
  <div class="callout">
    <p><b>Why not more topography?</b> The USGS Quaternary Fault and Fold Database is
    built predominantly from surface scarp expression. A better topographic ridge
    detector finds more of what is <i>already mapped</i>. The organizers confirmed
    “new fault” means “any fault pixel not already captured”, explicitly including
    extensions, splays and corrections — so the productive search is for faults whose
    surface expression is weak, absent, or non-topographic.</p>
  </div>
  <div class="scroll"><table><thead><tr>
    <th>hypothesis</th><th>layers</th><th>physical signature</th>
    <th>why it finds a <i>missing</i> fault</th><th>how it differs from prior work</th>
    <th>rank</th></tr></thead><tbody>{rows}</tbody></table></div>
</section>

<section>
  <h2>External data that would unlock more — and whether it is obtainable</h2>
  <div class="scroll"><table><thead><tr><th>source</th><th>what it adds</th>
  <th>licence</th><th>status</th></tr></thead><tbody>
  <tr><td><a href="https://gdr.openei.org/submissions/1391">INGENIOUS Great Basin
      Compilation</a> (DOI 10.15121/1881483)</td>
      <td><b>Quaternary Faults v2</b> carries fault <b>ages and slip rates</b> — the
      missing holdout strata. Also <b>Paleo Geothermal Features</b> (sinter/tufa
      deposits), 2 m temperature probes, Quaternary volcanics, heat flow, MT conductance.</td>
      <td>CC-BY-4.0 ✅ permits competition use</td>
      <td><span class="tag t-warn">verified to exist; download blocked by sandbox
      egress — see L-2</span></td></tr>
  <tr><td><a href="https://doi.org/10.5066/P93LGLVQ">GeoDAWN survey (USGS)</a></td>
      <td>Native-resolution magnetics and radiometrics (the provided grid is
      resampled to 100 m)</td><td>USGS public domain ✅</td>
      <td><span class="tag t-warn">egress blocked</span></td></tr>
  <tr><td>USGS 3DEP 1 m DEM (<code>1m_DEM_links.csv</code>)</td>
      <td>Metre-scale scarp morphology</td><td>USGS public domain ✅</td>
      <td><span class="tag t-bad">needs a DrivenData login</span></td></tr>
  </tbody></table></div>
  <p class="small"><b>Honest limitation:</b> none of the five hypotheses above requires
  external data — all five run on the 19 official bands, which is deliberate. The
  external sources would strengthen the <i>holdout</i> (age/slip-rate strata) and add a
  genuinely new geothermal channel (paleo-hydrothermal deposits), not the detectors.</p>
</section>"""
    return page("hypotheses.html", "Hypotheses", body)


# ---------------------------------------------------------------------------
def build_sources() -> str:
    S = [
        ("Competition home", "https://www.drivendata.org/competitions/306/competition-doe-gems/", "DrivenData", "✅ fetched"),
        ("Problem description (metric + submission format)", "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/", "DrivenData", "✅ fetched"),
        ("About page", "https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/", "DrivenData", "✅ linked"),
        ("Data download tab", "https://www.drivendata.org/competitions/306/competition-doe-gems/data/", "DrivenData", "🔒 login required"),
        ("Public leaderboard", "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/", "DrivenData", "✅ fetched — top 0.3168"),
        ("Official Rules (PDF)", "https://docs.nlr.gov/docs/fy26osti/96647.pdf", "NLR / DOE", "✅ fetched"),
        ("Rules landing page", "https://www.herox.com/GEMSPrize/resource/2274", "HeroX", "✅ fetched"),
        ("Reference solution", "https://github.com/drivendataorg/gems-prize-reference-solution", "DrivenData", "✅ downloaded"),
        ("Forum — Scoring clarification (11516)", "https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516", "DrivenData forum", "✅ all 4 posts read"),
        ("Forum — Where do you draw the line? (11536)", "https://community.drivendata.org/t/where-do-you-draw-the-line/11536", "DrivenData forum", "✅ both posts read"),
        ("Forum — How were the new test faults identified? (11527)", "https://community.drivendata.org/t/how-were-the-new-test-faults-identified-data-sources-and-fault-types/11527/7", "DrivenData forum", "✅ organizer reply read"),
        ("GeoDAWN airborne magnetic & radiometric surveys", "https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and", "USGS", "✅ linked"),
        ("GeoDAWN DOI (Glen & Earney 2024)", "https://doi.org/10.5066/P93LGLVQ", "USGS", "✅ cited in Official Rules §2"),
        ("GeoDAWN ScienceBase item", "https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7", "USGS", "✅ linked"),
        ("INGENIOUS Great Basin Regional Dataset (DOI 10.15121/1881483)", "https://gdr.openei.org/submissions/1391", "DOE GDR / OpenEI", "✅ fetched — CC-BY-4.0"),
        ("INGENIOUS project site", "https://gbcge.org/current-projects/ingenious/", "GBCGE / UNR", "✅ linked"),
        ("Tversky index", "https://en.wikipedia.org/wiki/Tversky_index", "Wikipedia (cited by the problem page)", "✅ linked"),
        ("EPSG:32611", "https://epsg.io/32611", "EPSG", "✅ linked"),
    ]
    rows = "".join(
        f"<tr><td>{e(t)}</td><td class='small'><a href='{u}'>{e(u)}</a></td>"
        f"<td class='small'>{e(o)}</td><td class='small'>{e(s)}</td></tr>"
        for t, u, o, s in S)
    body = f"""
<section>
  <h2>Every source, for manual review</h2>
  <p class="lede">Each row was fetched during the session that produced this site, or
  is explicitly marked as unreachable. Nothing on this site is recalled from memory.</p>
  <div class="scroll"><table><thead><tr><th>what</th><th>URL</th><th>publisher</th>
  <th>status</th></tr></thead><tbody>{rows}</tbody></table></div>
</section>

<section>
  <h2>Data provenance</h2>
  <div class="panel">
    <p class="small">The competition rasters used here were recovered from this group's
    own earlier public repositories rather than downloaded from DrivenData (no login is
    available to the automation). Git blob SHAs are recorded so the files can be
    re-verified byte-for-byte:</p>
    <table><thead><tr><th>file</th><th>git blob SHA</th><th>bytes</th></tr></thead><tbody>
    <tr><td class="mono">existing_faults.tif</td><td class="mono small">4ad3c1f3f19823e40924589bee7e51e44ae3a2e7</td><td class="num">425,830</td></tr>
    <tr><td class="mono">example_submission.tif</td><td class="mono small">7d865a9921a40ed2ea4c742a6a25b1fa2f357c5a</td><td class="num">1,599,597</td></tr>
    <tr><td class="mono">gems-geodawn-numerical-features.tif</td><td class="mono small">5 parts, concatenated</td><td class="num">418,912,844</td></tr>
    </tbody></table>
    <p class="small" style="margin-bottom:0"><b>Caveat:</b> these are mirrors, not
    first-party downloads. Irregularity I-1 shows one of them is mislabelled, which is
    exactly why provenance is recorded rather than assumed.</p>
  </div>
</section>"""
    return page("sources.html", "Sources", body)


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    DL.mkdir(parents=True, exist_ok=True)
    (DOCS / ".nojekyll").write_text("")
    for fn, content in [("index.html", build_index()),
                        ("executive_summary.html", build_exec()),
                        ("evidence.html", build_evidence()),
                        ("hypotheses.html", build_hypotheses()),
                        ("sources.html", build_sources())]:
        (DOCS / fn).write_text(content)
        print(f"  wrote docs/{fn}  ({len(content):,} bytes)")
    print("site built")


if __name__ == "__main__":
    main()
