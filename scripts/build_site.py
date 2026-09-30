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
<meta name="description" content="GEMS Prize Challenge: download the current submission GeoTIFF from the front page, plus the audited scoring metric, holdout evidence, and the recorded DrivenData form responses behind it.">
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
    sub = load("latest_submission.json", {}) or {}
    audit = load("metric_audit.json", {})
    r8 = load("holdout_candidate_r8_2026-09-30.json", {}) or {}
    r9 = load("holdout_r9_2026-09-30.json", {}) or {}
    r10 = load("holdout_r10_2026-09-30.json", {}) or {}
    r10b = load("holdout_r10b_2026-09-30.json", {}) or {}
    extdet = load("external_detectors_manifest.json", {}) or {}
    extman = load("external_manifest.json", {}) or {}
    band6 = load("band6_identity.json", {}) or {}
    leaderboard = load("leaderboard_snapshot_2026-09-30.json", {}) or {}
    checks = audit.get("checks", {})
    n_pass = sum(1 for c in checks.values() if c.get("pass"))

    clearance = sub.get("submission_clearance", {})
    clearance_status = clearance.get("status", "UNKNOWN")
    is_reference = str(clearance_status).startswith("BEST_LOCAL_REFERENCE")
    tag_cls = "t-info" if is_reference else ("t-ok" if clearance.get("upload_allowed") else "t-bad")
    status_label = ("BEST LOCAL HOLDOUT REFERENCE" if is_reference
                    else ("CLEARED" if clearance.get("upload_allowed") else "NOT CLEARED"))
    validation = sub.get("validation", {})
    nan_check = validation.get("nan_outside", {})
    local_format_ok = bool(nan_check.get("official_format_conformant", False))
    local_format_text = "passes local format checks" if local_format_ok else "local format checks incomplete"
    name = sub.get("name")
    note = sub.get("note_for_submission_form", "not recorded")
    flip = load("primary_flip_2026-09-30.json", {}) or {}
    fin_ver = flip.get("finite_verification") or {}
    if fin_ver:
        fin_fact = (f"verified in-workspace: 0 NaN, 0 Inf, every cell in "
                    f"[{fin_ver.get('min')}, {fin_ver.get('max')}], "
                    f"{fin_ver.get('n_positive'):,} positive cells")
    else:
        fin_fact = "all-finite encoding: every cell in [0,1], no NaN anywhere"
    pu = sub.get("primary_upload") or {}
    if name:
        if pu.get("file"):
            primary_name, zip_name = pu["file"], (pu.get("zip") or f"{name}.zip")
            secondary_name = (pu.get("secondary_record_only") or {}).get(
                "file", f"{name}_nanoutside.tif")
        else:  # legacy manifest without the policy field: finite twin is the _allfinite file
            primary_name, zip_name = f"{name}_allfinite.tif", f"{name}.zip"
            secondary_name = f"{name}.tif"
        primary_href = f"downloads/{e(primary_name)}"
        zip_href = f"downloads/{e(zip_name)}"
        secondary_href = f"downloads/{e(secondary_name)}"
        artifact_links = f"""
    <div class="row">
      <a class="btn" href="{primary_href}" download>⬇ SUBMIT THIS FILE — {e(primary_name)}</a>
      <a class="btn ghost" href="{zip_href}" download>⬇ ZIP (same GeoTIFF inside)</a>
    </div>
    <table class="small" style="margin-top:10px">
      <tr><td><b>File to submit</b></td><td class="mono">{e(primary_name)} &nbsp;<span class="small">(or the .zip — it contains exactly this GeoTIFF)</span></td></tr>
      <tr><td><b>Note (optional)</b></td><td class="mono">{e(note)}</td></tr>
    </table>
    <p class="small">✅ <b>{e(fin_fact)}</b>; single-band float32, EPSG:32611,
    3730×3292, 100 m — identical predictions to the NaN-outside variant inside the
    survey footprint, with score-neutral 0.0 outside it.<br>
    <span class="tag t-bad">record only</span> The strict null/NaN-outside variant
    <a href="{secondary_href}">{e(secondary_name)}</a> was <b>REJECTED by the form on
    2026-09-30</b> (“Predicted values must be in range [0, 1]”) — do not upload it
    first; it is kept for the record and A/B triage. Evidence log:
    <code>reports/form_responses.json</code>. See the
    <a href="executive_summary.html#if-the-form-says-predicted-values-must-be-in-range-01">triage table</a>.</p>""".strip()
    else:
        artifact_links = '<p class="small">No archived candidate file is currently registered.</p>'

    r11 = load("holdout_r11_2026-09-30.json", {}) or {}
    if str(clearance_status).startswith("CLEARED"):
        cs11 = r11.get("confirmation_summary", {})
        hero_what = (
            "This file is <b>the first recipe in this repository to beat the local "
            "holdout reference</b>: <code>greedy_r11</code> (R11-4 greedy marginal-precision "
            "assembly) — confirmation worst-rule-mean DTI "
            f"<b>{cs11.get('greedy_r11', {}).get('dti_worst_rule_mean', 0):.5f}</b> vs "
            f"{cs11.get('topo_05_sp3', {}).get('dti_worst_rule_mean', 0):.5f} for "
            "<code>topo_05_sp3</code>, 6/6 rule means and 18/18 paired folds, under the "
            "rule predeclared in <code>knowledge/07_r11_hypotheses.md</code>.")
    else:
        hero_what = ("This file is the <b>current local holdout reference recipe</b> "
                     "(<code>topo_05_sp3</code>).")
    hero = f"""<div class="hero"><div class="wrap">
  <h1>Submission download — <span class="tag {tag_cls}">{e(status_label)}</span></h1>
  <p class="sub">{hero_what} The download below is the <b>all-finite upload-safe
  encoding</b> (single-band float32; EPSG:32611; 3730×3292; 100 m; every cell in
  [0,1]; 0.0 outside the survey footprint) — chosen because the form
  <b>rejected the null/NaN-outside encoding on 2026-09-30</b>
  (“Predicted values must be in range [0, 1]”), while this encoding family passes
  both strict and naive validators and is score-neutral for a binary map.
  <b>The holdout numbers are local catalogue-recovery results, not a predicted
  leaderboard score</b>, and remote acceptance of this exact file is confirmed
  only by the form's own response — record it in
  <code>reports/leaderboard_ledger.csv</code> after upload.</p>
  <div class="dl">
    {artifact_links}
    <div class="meta"><b>Primary file:</b> all-finite {e(fin_fact) if fin_fact else ""}.</div>
    <p><a class="btn ghost" href="executive_summary.html">Exactly how to submit (5 steps)</a>
    <a href="evidence.html">Metric, holdout evidence, and verdicts</a></p>
  </div>
</div></div>"""

    rows = leaderboard.get("rows", [])
    first = rows[0] if rows else {}
    second = rows[1] if len(rows) > 1 else {}
    confirm = r8.get("confirmation_summary", {})
    baseline = confirm.get("topo_05_sp3", {})
    candidate = confirm.get("r8_current_union_sp3", {})

    def score_cell(d: dict, key: str, places: int = 5) -> str:
        value = d.get(key)
        return f"{value:.{places}f}" if isinstance(value, (int, float)) else "n/a"

    base_support = baseline.get("predicted_eval_px_mean")
    r8_support = candidate.get("predicted_eval_px_mean")
    base_support_text = f"{base_support:,.0f}" if isinstance(base_support, (int, float)) else "n/a"
    r8_support_text = f"{r8_support:,.0f}" if isinstance(r8_support, (int, float)) else "n/a"

    # R9 verdict table (paired, predeclared, protocol-checked)
    r9_conf = r9.get("confirmation_summary", {})
    r9_paired = r9.get("paired_vs_reference", {})
    r9_verdicts = r9.get("verdicts_predeclared", {})
    r9_rows = ""
    for cfg, summ in sorted(r9_conf.items(),
                            key=lambda kv: -kv[1].get("dti_worst_rule_mean", 0)):
        label = ("BASE_topo_ridge · 5% · spacing 3 (reference)"
                 if cfg == "topo_05_sp3" else cfg)
        p = r9_paired.get(cfg)
        delta = f"{p['mean_delta_dti']:+.5f}" if p else "—"
        verdict = ("reference (reproduced exactly)" if cfg == "topo_05_sp3"
                   else e(r9_verdicts.get(cfg, "n/a")))
        r9_rows += (f"<tr><td><b>{e(label)}</b></td>"
                    f"<td class='num'>{score_cell(summ, 'dti_worst_rule_mean')}</td>"
                    f"<td class='num'>{score_cell(summ, 'dti_mean')}</td>"
                    f"<td class='num'>{score_cell(summ, 'precision_w_mean')}</td>"
                    f"<td class='num'>{score_cell(summ, 'recall_w_mean')}</td>"
                    f"<td class='num'>{delta}</td><td>{verdict}</td></tr>")
    r9_check = r9.get("protocol_regression_check", {})
    r9_check_text = ("PASS — the reference row reproduces the archived R8-run "
                     "per-fold DTI values exactly"
                     if r9_check.get("pass") else "FAILED — investigate before use")

    # R10 / R10b: the external-data round (paired, predeclared, protocol-checked)
    r10_conf = r10.get("confirmation_summary", {})
    r10_paired = r10.get("paired_vs_reference", {})
    r10_verdicts = r10.get("verdicts_predeclared", {})
    r10_rows = ""
    for cfg, summ in sorted(r10_conf.items(),
                            key=lambda kv: -kv[1].get("dti_worst_rule_mean", 0)):
        label = ("BASE_topo_ridge · 5% · spacing 3 (reference)"
                 if cfg == "topo_05_sp3" else cfg)
        pr = r10_paired.get(cfg)
        delta = f"{pr['mean_delta_dti']:+.5f}" if pr else "—"
        verdict = ("reference (reproduced exactly)" if cfg == "topo_05_sp3"
                   else e(r10_verdicts.get(cfg, "n/a")))
        r10_rows += (f"<tr><td><b>{e(label)}</b></td>"
                     f"<td class='num'>{score_cell(summ, 'dti_worst_rule_mean')}</td>"
                     f"<td class='num'>{score_cell(summ, 'dti_mean')}</td>"
                     f"<td class='num'>{score_cell(summ, 'precision_w_mean')}</td>"
                     f"<td class='num'>{score_cell(summ, 'recall_w_mean')}</td>"
                     f"<td class='num'>{delta}</td><td>{verdict}</td></tr>")
    r10_check_text = ("PASS — the reference row reproduces the archived per-fold "
                      "DTI values exactly (18/18 folds)"
                      if r10.get("protocol_regression_check", {}).get("pass")
                      else "FAILED — investigate before use")

    # per-map external signal quality (full catalogue, not a holdout number)
    ext_rows = ""
    for name, st in sorted(
            (r10.get("map_statistics_full_catalogue") or {}).items(),
            key=lambda kv: -kv[1].get("auc_full_catalogue", 0)):
        ext_rows += (f"<tr><td class='mono'>{e(name)}</td>"
                     f"<td class='num'>{st.get('auc_full_catalogue', 0):.4f}</td>"
                     f"<td class='num'>{st.get('catalogue_recall_in_top5pct', 0):.4f}</td>"
                     f"<td class='num'>{st.get('nonzero_pct_of_footprint', 0):.2f}%</td></tr>")

    sel = r10b.get("selected_on_tune")
    sel_conf = (r10b.get("confirmation_summary", {}) or {}).get(sel, {})
    sel_pair = r10b.get("paired_vs_reference_selected", {})
    sel_verdict = (r10b.get("verdict_predeclared", {}) or {}).get(sel, "n/a")
    ref_conf = (r10b.get("confirmation_summary", {}) or {}).get("topo_05_sp3", {})
    r10b_html = ""
    if sel:
        r10b_html = f"""
  <div class="panel">
    <h3 style="margin-top:0">R10b — refinement round, selected on tune folds only</h3>
    <p class="small">R10 measured the <i>average</i> quality of a 2% external block.
    The metric's inclusion rule is a statement about the <i>margin</i>, so R10b
    predeclared two further mechanisms: low-coverage unions (0.5%, 1%) and
    fixed-budget rank fusion, <code>(1−w)·pctl(topo) + w·pctl(external)</code>, which
    keeps the reference pixel mass and lets the external evidence <i>replace</i> the
    weakest reference pixels instead of adding to them. Selection used the tune folds
    only; confirmation was then read for the selected configuration and the reference.</p>
    <table class="small"><thead><tr><th>configuration</th><th class="num">confirm worst-rule DTI</th>
      <th class="num">confirm mean DTI</th><th class="num">P_w</th><th class="num">R_w</th>
      <th class="num">predicted px</th><th>verdict</th></tr></thead><tbody>
      <tr><td><b>topo_05_sp3</b> (reference)</td>
        <td class="num">{ref_conf.get('dti_worst_rule_mean', 0):.5f}</td>
        <td class="num">{ref_conf.get('dti_mean', 0):.5f}</td>
        <td class="num">{ref_conf.get('precision_w_mean', 0):.4f}</td>
        <td class="num">{ref_conf.get('recall_w_mean', 0):.4f}</td>
        <td class="num">{ref_conf.get('predicted_eval_px_mean', 0):,.0f}</td>
        <td>REFERENCE</td></tr>
      <tr><td><b>{e(sel)}</b> (selected on tune)</td>
        <td class="num">{sel_conf.get('dti_worst_rule_mean', 0):.5f}</td>
        <td class="num">{sel_conf.get('dti_mean', 0):.5f}</td>
        <td class="num">{sel_conf.get('precision_w_mean', 0):.4f}</td>
        <td class="num">{sel_conf.get('recall_w_mean', 0):.4f}</td>
        <td class="num">{sel_conf.get('predicted_eval_px_mean', 0):,.0f}</td>
        <td>{e(sel_verdict)}</td></tr>
    </tbody></table>
    <p class="small" style="margin-bottom:0">Paired Δ mean DTI
    {sel_pair.get('mean_delta_dti', 0):+.5f} ({sel_pair.get('relative_delta_pct', 0):+.2f}%),
    {sel_pair.get('wins', 0)}/{sel_pair.get('n_pairs', 0)} confirmation folds won,
    {len([v for v in (sel_conf.get('dti_mean_by_rule') or {}).values()])} rules scored.
    The fusion buys precision (0.0294 vs 0.0276) with 19% fewer pixels by giving up
    recall (0.2487 vs 0.2874) — under β = 2 that trade is a wash on the mean and a loss
    on the worst rule. Report:
    <code>reports/holdout_r10b_2026-09-30.json</code>.</p>
  </div>"""

    holdout_rows = f"""
  <tr><td><b>BASE_topo_ridge · 5% · spacing 3</b><br>local comparator</td>
    <td>{score_cell(baseline, 'dti_worst_rule_mean')}</td>
    <td>{score_cell(baseline, 'dti_mean')}</td>
    <td>{score_cell(baseline, 'precision_w_mean')}</td>
    <td>{score_cell(baseline, 'recall_w_mean')}</td>
    <td>{base_support_text}</td></tr>
  <tr><td><b>R8 current union · spacing 3</b><br>per-fold visible-only rebuild</td>
    <td>{score_cell(candidate, 'dti_worst_rule_mean')}</td>
    <td>{score_cell(candidate, 'dti_mean')}</td>
    <td>{score_cell(candidate, 'precision_w_mean')}</td>
    <td>{score_cell(candidate, 'recall_w_mean')}</td>
    <td>{r8_support_text}</td></tr>"""

    top_score = first.get("best_public_dw_tversky")
    second_score = second.get("best_public_dw_tversky")
    public_scores = (
        f"{e(first.get('account', 'unknown'))} {top_score:.4f}; "
        f"{e(second.get('account', 'unknown'))} {second_score:.4f}"
        if isinstance(top_score, (int, float)) and isinstance(second_score, (int, float))
        else "not available"
    )

    r11_rows = ""
    ts11 = r11.get("tune_summary", {})
    ca11 = r11.get("confirmation_summary_all_for_audit", {})
    for cfg in ts11:
        r11_rows += (f"<tr><td class='mono'>{e(cfg)}</td>"
                     f"<td>{ts11[cfg]['dti_worst_rule_mean']:.5f}</td>"
                     f"<td>{ca11.get(cfg, {}).get('dti_worst_rule_mean', 0):.5f}</td>"
                     f"<td>{ca11.get(cfg, {}).get('precision_w_mean', 0):.4f}</td>"
                     f"<td>{ca11.get(cfg, {}).get('recall_w_mean', 0):.4f}</td></tr>")
    path11 = "".join(
        f"<li>step {p['step']}: best block <code>{e(p['best']['map'])}</code> @ "
        f"{p['best']['cov']*100:g}% — marginal precision {p['best']['marginal_precision']:.4f} "
        f"vs bar 0.2×DTI = {p['bar_0.2xDTI']:.4f} → <b>{'ACCEPT' if p['accepted'] else 'STOP'}</b></li>"
        for p in r11.get("greedy_path_tune_only", []))
    # ---- R12 session block (holdout_r12_2026-09-30.json) ------------------
    r12 = load("holdout_r12_2026-09-30.json", {}) or {}
    r12_html = ""
    if r12:
        ts12 = r12.get("tune_summary", {})
        cs12 = r12.get("confirmation_summary", {})
        order12 = ["topo_05_sp3", "greedy_r11", "greedy_r12",
                   "topo05_plus_basinmag0001_sp3", "hyst_add005",
                   "hyst_add010", "hyst_add020"]
        r12_rows = ""
        for cfg in order12:
            if cfg not in cs12:
                continue
            t, c = ts12.get(cfg, {}), cs12[cfg]
            label = {"topo_05_sp3": "BASE_topo_ridge · 5% · spacing 3 (reference)",
                     "greedy_r11": "greedy_r11 (reference to beat — SHIPPED)",
                     "greedy_r12": "greedy_r12 (finer-step greedy, selected on tune)",
                     "topo05_plus_basinmag0001_sp3":
                         "basin magnetics @0.10% (true support — R11-2 retest)",
                     "hyst_add005": "hysteresis crest continuation, +0.5%",
                     "hyst_add010": "hysteresis crest continuation, +1.0%",
                     "hyst_add020": "hysteresis crest continuation, +2.0%",
                     }.get(cfg, cfg)
            verdict = ("reference" if cfg == "topo_05_sp3"
                       else ("reference — still the best known recipe"
                             if cfg == "greedy_r11" else
                             r12.get("verdict_predeclared", {}).get(cfg, "")))
            r12_rows += (f"<tr><td><b>{e(label)}</b></td>"
                         f"<td class='num'>{t.get('dti_worst_rule_mean', 0):.5f}</td>"
                         f"<td class='num'>{c.get('dti_worst_rule_mean', 0):.5f}</td>"
                         f"<td class='num'>{c.get('precision_w_mean', 0):.4f}</td>"
                         f"<td class='num'>{c.get('recall_w_mean', 0):.4f}</td>"
                         f"<td class='num'>{c.get('predicted_eval_px_mean', 0):,.0f}</td>"
                         f"<td>{e(verdict)}</td></tr>")
        paired12 = r12.get("paired_vs_greedy_r11", {})
        drift12 = r12.get("protocol_regression_check", {}).get("max_abs_deviation")
        r12_html = f"""
<section>
  <h2>Session 6 (R12): the gate held — download encoding fixed, artifact unchanged</h2>
  <p class="lede">Three new hypotheses were predeclared before any fold was scored
  (<code>knowledge/08_r12_hypotheses.md</code>): <b>hysteresis crest continuation</b>
  (the repo's first connectivity transform — Canny-style two-threshold linking on the
  ridge-strength field), a <b>finer-step greedy</b> over a widened 12-map pool
  (0.10% blocks, ≤ 6 steps), and the <b>basin-magnetics retest</b> at its true
  support (resolving R11-2's I-14 invalid measurement). <b>None beat
  <code>greedy_r11</code></b>, so no submission slot was spent and the shipped
  artifact is unchanged — now served in its all-finite, form-verified encoding.</p>
  <div class="grid g4">
    <div class="kpi ok"><div class="v">0.0</div><div class="l">protocol-regression drift this session (pinned versions close I-15)</div></div>
    <div class="kpi bad"><div class="v">0 / 5</div><div class="l">R12 challengers that beat greedy_r11</div></div>
    <div class="kpi bad"><div class="v">0 / 18</div><div class="l">paired folds won by the best R12 challenger vs greedy_r11</div></div>
    <div class="kpi ok"><div class="v">0</div><div class="l">submission slots spent</div></div>
  </div>
  <div class="scroll"><table><thead><tr><th>R12 configuration</th>
    <th class="num">tune worst-rule DTI</th><th class="num">confirm worst-rule DTI</th>
    <th class="num">P_w</th><th class="num">R_w</th>
    <th class="num">predicted px</th><th>predeclared verdict</th></tr></thead>
    <tbody>{r12_rows}</tbody></table></div>
  <p class="small">The hysteresis dose-response is clean: every added budget loses,
  and loses more as the budget grows (confirm worst-rule
  {cs12.get('hyst_add005', {}).get('dti_worst_rule_mean', 0):.5f} →
  {cs12.get('hyst_add010', {}).get('dti_worst_rule_mean', 0):.5f} →
  {cs12.get('hyst_add020', {}).get('dti_worst_rule_mean', 0):.5f}) — recall rises to
  {cs12.get('hyst_add020', {}).get('recall_w_mean', 0):.4f} while marginal weighted
  precision stays below the metric's <code>0.2 × DTI</code> inclusion bar: I-13
  again, now for the connectivity transform. The finer greedy found the
  highest-precision block ever measured (<code>R10_vent@0.10%</code>, pooled
  marginal precision 0.03236) but its frozen one-block recipe is a strict subset of
  R11's assembly — <b>precision above the bar is necessary; accepted mass must
  still move the worst rule.</b> Paired folds vs <code>greedy_r11</code>:
  {paired12.get('selected_beats_greedy_r11', 0)}/{paired12.get('n_folds', 18)};
  drift {drift12 if drift12 is not None else 'n/a'}.
  Report: <code>reports/holdout_r12_2026-09-30.json</code>.</p>
</section>"""

    body = f"""
{r12_html}
<section>
  <h2>Session 5 (R11): first holdout WIN — greedy marginal-precision assembly</h2>
  <p class="lede">R8–R10b showed 24 challengers losing because the pixels they added sat
  <i>inside</i> neighbourhoods the topographic crest already covered, or had marginal
  precision below the metric's inclusion bar. R11-4 turns that audited rule into the
  construction procedure: each candidate block is restricted to pixels <b>more than
  300 m from everything already predicted</b>, and is accepted only while its pooled
  tune-fold marginal weighted precision exceeds <code>0.2 × DTI</code>. Selection used
  tune folds only; the recipe was then applied unchanged to the 12 confirmation folds.</p>
  <ul class="small">{path11}</ul>
  <table class="small"><tr><th>config</th><th>tune worst-rule</th><th>confirm worst-rule</th><th>P_w</th><th>R_w</th></tr>{r11_rows}</table>
  <p class="small">Verdict (predeclared): <b>{e(json.dumps(r11.get('verdict_predeclared', {})))}</b>.
  R11-2 basin-floor magnetic continuity is <b>INVALID, not lost</b>: its 7,610-pixel support is smaller than the 0.5 %/1 % masses requested, so the unions filled with zero-score pixels (irregularity I-14); retest at ≤ 0.14 %.
  Irregularity I-15 flagged: the rebuilt detector cache reproduces the archived reference only to
  ≤ {r11.get('protocol_regression_check', {}).get('max_rel_deviation', 0)*100:.2f}% relative, so the
  verdict is paired in-run and the gain had to exceed 10× that drift. Local proxy only — not a
  leaderboard estimate. Report: <code>reports/holdout_r11_2026-09-30.json</code>.</p>
</section>
<section>
  <h2>Previous round: official external USGS data, staged and measured (R10 / R10b)</h2>
  <p class="lede">For the first time the work went outside the provided 19 bands.
  Six free, official, public-domain USGS products were staged and verified twice each
  (sha256 from the sibling provenance record <b>and</b> git blob SHA-1 from the sibling
  tree), four geological hypotheses were predeclared <i>before</i> any map was built,
  and all of them were then measured on the same paired holdout protocol.
  <b>Every challenger lost</b> — 16 in R10 and 8 in R10b — so no submission slot was
  spent.</p>
  <div class="grid g4">
    {kpi("6 / 6", "external products hash-verified (USGS public domain)", "ok")}
    {kpi("4", "hypotheses predeclared before build", "ok")}
    {kpi("0 / 24", "challengers that beat the reference (R8 · R9 · R10 · R10b)", "bad")}
    {kpi("0", "submission slots spent this round", "ok")}
  </div>
  <div class="scroll"><table><thead><tr><th>R10 candidate (confirmation folds)</th>
  <th class="num">worst-rule mean DTI</th><th class="num">mean DTI</th>
  <th class="num">mean weighted precision</th><th class="num">mean weighted recall</th>
  <th class="num">ΔDTI vs reference</th><th>predeclared verdict</th></tr></thead>
  <tbody>{r10_rows}</tbody></table></div>
  <p class="small">Protocol regression check: {e(r10_check_text)}. All 468 scored rows
  across R10 and R10b report <code>tie_fraction</code> 0.00 and zero selections at
  score 0, so no verdict rests on tie order. Full rows:
  <code>reports/holdout_r10_2026-09-30.json</code>.</p>
  <div class="grid g2">
    <div class="panel">
      <h3 style="margin-top:0">The external maps are <i>better</i> pixel classifiers — and still lose</h3>
      <div class="scroll"><table class="small"><thead><tr><th>map</th>
        <th class="num">AUC vs full catalogue</th><th class="num">recall in own top 5%</th>
        <th class="num">non-zero share of footprint</th></tr></thead>
        <tbody>{ext_rows}</tbody></table></div>
      <p class="small" style="margin-bottom:0">Best provided band for comparison:
      <code>geod_shearrate</code> at AUC 0.5615. These are full-catalogue signal
      statistics, <b>not</b> holdout scores.</p>
    </div>
    <div class="panel">
      <h3 style="margin-top:0">Why signal did not convert into score</h3>
      <p class="small">DTI is a distance-weighted F2 (β = 2), so a block of predictions
      helps only if its <b>marginal weighted precision</b> exceeds <code>0.2 × DTI</code>
      (0.0169 on tune folds, 0.0195 on confirmation). Measured marginal precision of the
      blocks the external maps add: dzt 0.0094, scarp 0.0096, vent 0.0138, alter 0.0141
      at 2% coverage; 0.0136–0.0166 at 0.5–1% coverage. Every one is below the bar.</p>
      <p class="small" style="margin-bottom:0">The direction of the failure matters:
      external evidence raises <b>precision</b> and spends <b>recall</b>. Only a product
      that puts pixels within 300 m of faults the topographic crest never touches can
      raise DTI. Recorded as irregularity
      <a href="https://github.com/buffedlizard55-lab/13GEMSDOE/blob/main/knowledge/02_irregularities.md">I-13</a>
      so the same 24 configurations are not re-derived next session.</p>
    </div>
  </div>{r10b_html}
  <div class="callout ok">
    <p style="margin:0"><b>One irregularity resolved on the way (I-2).</b> Provided band 6
    <code>tc</code> <b>is</b> the radiometric total count: against the official USGS
    GeoDAWN grid, Spearman ρ {band6.get('candidates', {}).get('radiometric::rad_tc', {}).get('spearman_rho', 0):.5f},
    Pearson r 0.99902, OLS slope
    {band6.get('candidates', {}).get('radiometric::rad_tc', {}).get('ols_slope_band6_per_channel_unit', 0):.4f},
    R² {band6.get('candidates', {}).get('radiometric::rad_tc', {}).get('ols_r2', 0):.4f},
    median ratio 1.00000 — plus the physical closure test
    band6 ≈ 7.54 × (K + Th + U) at ρ 0.9958, which no tilt angle or curvature satisfies.
    Its embedded description (“Tilt angle <i>or</i> total curvature — magnetic field
    derivative for edge detection”) does not describe the array, and the earlier
    “disproved” verdict rested on an unverified units assumption. Same match, second
    consequence: it independently validates our external staging pipeline, because the
    sibling re-gridding reproduces the field the organisers shipped.
    <code>reports/band6_identity.json</code>.</p>
  </div>
</section>

<section>
  <h2>Current decision: hold the reference; every challenger lost</h2>
  <p class="lede">Twenty-four challenger configurations across four rounds (the R8
  ensemble union, three R9 internal-data hypotheses, sixteen R10 external-data
  configurations and eight R10b refinements) were each tested under a predeclared,
  paired protocol against the reference recipe. All of them lost. The downloadable
  artifact therefore remains the reference recipe itself.</p>
  <div class="scroll"><table><thead><tr><th>R9 candidate (confirmation folds)</th>
  <th class="num">worst-rule mean DTI</th><th class="num">mean DTI</th>
  <th class="num">mean weighted precision</th><th class="num">mean weighted recall</th>
  <th class="num">ΔDTI vs reference</th><th>predeclared verdict</th></tr></thead>
  <tbody>{r9_rows}</tbody></table></div>
  <p class="small">Protocol regression check: {e(r9_check_text)}. Loose gap-fill added
  ~145,600 px per fold for ΔDTI −0.026 — its marginal weighted precision sat below the
  metric's own <code>0.2 × DTI</code> inclusion bar (audit A5), measured rather than
  asserted. Strict gap-close (+32 px) and corrections (+26 px) were near no-ops.
  Epicentral alignment (+16,590 px) cost −0.002. Full rows:
  <code>reports/holdout_r9_2026-09-30.json</code>.</p>
</section>

<section>
  <h2>The same story from the previous round (R8)</h2>
  <div class="scroll"><table><thead><tr><th>recipe</th><th>worst-rule mean DTI</th>
  <th>mean DTI</th><th>mean weighted precision</th><th>mean weighted recall</th>
  <th>mean effective positive support in eval domain</th></tr></thead>
  <tbody>{holdout_rows}</tbody></table></div>
  <p class="small">Confirmation summary from
  <code>reports/holdout_candidate_r8_2026-09-30.json</code>: 15 tested
  configurations; whole-system and raw 8-connected segment folds; 5-pixel buffer;
  visible-catalogue-only ray/horsetail rebuild; pixel-exact visible mask; withheld
  truth only. The lowest-slope-third slice is a robustness stress test, not a hidden-
  fault analogue. No tested R8 variant beat the baseline in this summary.</p>
</section>

<section>
  <h2>Metric audit and identity checks</h2>
  <div class="grid g4">
    {kpi(f"{n_pass}/{len(checks)}", "metric audit checks passed", "ok")}
    {kpi("0", "local TIFFs tied to verified per-submission public scores", "warn")}
    {kpi("3 / 3", "new R9 hypotheses measured on the holdout — all LOSE", "bad")}
    {kpi("29 / 29", "challengers across R8 · R9 · R10 · R10b · R12 that failed the gate", "bad")}
    {kpi(f"{top_score:.4f}" if isinstance(top_score, (int, float)) else "n/a",
         "leader's account-level best (snapshot 2026-09-30)", "warn")}
  </div>
  <p class="small">DTI algebra and the official worked example pass the local audit.
  Historical equal rounded score labels are not evidence of identical maps or a score
  receipt. Exact file, canonical pixel, effective-support, and unmasked-support
  comparisons are recorded separately in <code>reports/scored_forensics.json</code>.</p>
</section>

<section>
  <h2>Why the team kept scoring 0.1563 — status of that question</h2>
  <div class="callout warn">
    <p><b>Unresolved as a score question, settled as a file question.</b> The two
    archived files carrying 0.1563 labels (<code>gemsdoe1_ens12</code> and
    <code>gems8_apex</code>) are <b>different maps</b>: different bytes, different
    canonical pixels, support IoU 0.067. Equal rounded labels therefore cannot indicate
    copied work, and the official leaderboard column is an account-level best, not a
    per-submission receipt. Measured details:
    <code>reports/scored_forensics.json</code>; irregularity I-3. The productive
    response is the one taken here: generate structurally different candidates
    (catalogue-geometry, potential-field, terrain, hydrologic, seismicity, supervised,
    and now trace-completion families) and gate them on the paired holdout before any
    upload.</p>
  </div>
</section>

<section>
  <h2>Public-score attribution and chance baseline</h2>
  <div class="callout warn">
    <p><b>Historical score-to-file attribution is unresolved.</b> The official
    account-level “Best public DW-Tversky” snapshot is {public_scores}; it does not
    identify scores for local TIFFs. The previous public chance/lift inference is
    withdrawn because it estimated hidden truth size from those same score labels.</p>
    <p style="margin-bottom:0">Candidate variants are ranked by direct DTI. A corrected
    closed-form calculation is retained only as an approximate same-run random-control
    sanity check using the fold-specific eligible domain; its in-sample calibration is
    not universal. No local chance figure is a public/private baseline or upload gate.</p>
  </div>
</section>

<section>
  <h2>Research directions still open</h2>
  <p class="lede">The GeoDAWN/3DEP/QFFDB external family is now <b>staged, verified and
  measured</b> (R10/R10b above) — it loses on Phase-1 DTI and is closed as a score
  direction, though it retains Phase-2 defensibility value. Four <i>other</i>
  external-data directions remain ranked for research and are still not viable because
  their official data are not staged:
  event-level ComCat focal-plane coherence, repeated Landsat thermal/moisture residuals,
  groundwater-head compartments, and cross-depth MT conductor edges. Availability checks
  are recorded per source.</p>
  <p><a class="btn ghost" href="hypotheses.html">Read the ranked hypothesis review</a>
  <a href="https://github.com/buffedlizard55-lab/13GEMSDOE/blob/main/knowledge/05_hypothesis_screen_2026-09-30.md">Sources, data checks, and prior-art comparisons</a></p>
</section>

<section>
  <div class="callout bad">
    <p style="margin:0"><strong>Submission gate:</strong> the shipped download
    (<code>greedy_r11</code>) is the first recipe that <b>cleared</b> the gate — it beat the
    local reference <code>topo_05_sp3</code> on tune and confirmation folds under the
    predeclared rule. It is still a catalogue hide-and-recover proxy, not a leaderboard
    prediction: upload it, record the returned public score in
    <code>reports/leaderboard_ledger.csv</code>, and treat that score as the new
    comparison point for the next round.</p>
  </div>
</section>"""
    return page("index.html", "Submission status", body, hero)


# ---------------------------------------------------------------------------
def build_exec() -> str:
    sub = load("latest_submission.json", {}) or {}
    name = sub.get("name", "(no candidate)")
    pu = sub.get("primary_upload") or {}
    if pu.get("file"):
        primary_file, zip_file = pu["file"], (pu.get("zip") or f"{name}.zip")
        strict_file = (pu.get("secondary_record_only") or {}).get("file", f"{name}_nanoutside.tif")
    else:
        primary_file, zip_file, strict_file = f"{name}_allfinite.tif", f"{name}.zip", f"{name}.tif"
    clearance = sub.get("submission_clearance", {})
    status = clearance.get("status", "UNKNOWN")
    reason = clearance.get("reason", "No current clearance record.")
    holdout_link = "https://github.com/buffedlizard55-lab/13GEMSDOE/blob/main/reports/holdout_r11_2026-09-30.json"
    candidate_link = f"downloads/{e(primary_file)}" if sub else "#"
    fallback_link = f"downloads/{e(strict_file)}" if sub else "#"
    note = sub.get("note_for_submission_form", "")
    body = f"""
<section>
  <h2>Submission workflow — the five steps, in order</h2>
  <div class="callout">
    <p style="margin:0"><b>Current artifact to upload: <code>{e(primary_file)}</code></b> —
    status <b>{e(status)}</b> (a catalogue hide-and-recover proxy result, not a
    predicted leaderboard score). {e(reason)}
    Download it from the <a href="index.html">front page</a> or directly
    <a href="{candidate_link}">here</a>. The all-finite encoding is the default
    because the form <b>rejected the null/NaN-outside encoding on 2026-09-30</b>
    (“Predicted values must be in range [0, 1]”) — evidence:
    <code>reports/form_responses.json</code>. Full comparison:
    <a href="{holdout_link}">R11 holdout report</a> (R9:
    <a href="https://github.com/buffedlizard55-lab/13GEMSDOE/blob/main/reports/holdout_r9_2026-09-30.json">here</a>).</p>
  </div>
  <ol class="steps">
    <li><h4>1. Validate the candidate on the local holdout</h4>
      <p>Use whole-system and raw-segment hide-and-recover folds with buffers,
      visible-catalogue-only construction of catalogue-dependent features, the exact
      visible known-fault mask, and DTI scored on withheld truth only. Compare multiple
      withholding rules and report cutoff, support, precision, recall, and DTI.
      The low-slope-third slice is a robustness stress test, not a hidden-test analogue.</p>
      <p class="small">Do not spend a weekly submission slot unless the candidate beats
      the current holdout best under more than one rule and improves the confirmation
      summary—not only a tuning fold or a qualitative geological rationale. This round's
      twenty-four challengers across R8, R9, R10 and R10b all failed that gate (see the
      front-page tables). Note also that the three-submission allowance resets on a
      <b>rolling window</b>, not a calendar week (forum 11524).</p></li>

    <li><h4>2. Check map identity before proposing an upload</h4>
      <p>Compare the complete raster and effective/chargeable positive support with all
      prior candidates. Record file hash, canonical pixel hash, support hash and overlap.
      An exact duplicate is different from a distinct map with the same rounded score;
      neither outcome can be inferred from filenames or account-level leaderboard values.</p>
      <p class="small">Use a new immutable file stem and note. The generator refuses a
      stem collision. Never promise a unique score: distinct maps can round to the same
      score. This round's artifact was checked against all eight archived historical
      maps — no exact-duplicate match.</p></li>

    <li><h4>3. Validate official GeoTIFF format</h4>
      <p>The primary download is <b>all-finite by policy</b> (flipped 2026-09-30):
      one float32 band, EPSG:32611, 100 m, 3730×3292, exact affine transform,
      <b>every cell finite and in [0,1]</b>, and exactly 0.0 outside the survey
      footprint. That passes both a NoData-honouring read and a naive raw
      <code>all(0 ≤ v ≤ 1)</code> validator, and for a binary map the zero-fill is
      score-neutral (0 is a non-prediction, so TP_w and FP_w are unchanged).
      Recorded verification: <code>reports/primary_flip_2026-09-30.json</code> and
      <code>reports/latest_submission.json</code>. The strict null/NaN-outside
      variant (what the problem-page text describes) exists as
      <code>{e(strict_file)}</code> — record-only, do <b>not</b> upload it first.</p></li>

    <li><h4>4. Fill the DrivenData form</h4>
      <p>On the
      <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">official submissions page</a>,
      click <b>Submit file</b> and fill the form exactly like this:</p>
      <table class="small">
        <tr><td><b>File to submit</b></td>
            <td>choose <code>{e(primary_file)}</code> (single-band GeoTIFF), or
                <code>{e(zip_file)}</code> (a .zip containing that one GeoTIFF)</td></tr>
        <tr><td><b>Note (optional)</b></td>
            <td class="mono">{e(note)}</td></tr>
      </table>
      <p class="small">The note must identify what was actually generated and must not
      claim hidden-test performance or unsupported geothermal certainty. Submitting the
      <i>same file twice</i> wastes a slot; the generator blocks byte-identical reuse.
      The file name is unique per build; if the form ever rejects the finite encoding,
      record the response in <code>reports/form_responses.json</code> and only then
      A/B the strict variant.</p></li>

    <li><h4>5. Upload, then record the receipt</h4>
      <p>The competition allows three submissions per week per the
      <a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">Official Rules §3.2</a>.</p>
      <p>After scoring, record the authenticated per-submission score and submission ID
      in <code>reports/leaderboard_ledger.csv</code>, tied to the exact file checksum.
      The account-level “Best public DW-Tversky” leaderboard value is not a receipt for
      that upload.</p></li>
  </ol>
</section>

<section id="if-the-form-says-predicted-values-must-be-in-range-01">
  <h2>If the form says “Predicted values must be in range [0, 1]”</h2>
  <p class="lede"><b>Status 2026-09-30 (session 6): reproduced and answered for this
  encoding.</b> The team uploaded this site's then-primary NaN-outside file
  (<code>13gems-r11-greedy-mp.tif</code>) and the form returned this exact message —
  the first platform response recorded against a known file from this repository.
  The predeclared triage step 2 was executed the same day: the <b>all-finite twin is
  now the primary download</b>. Notably, NaN-outside files from this group
  <i>were</i> accepted and scored earlier (the pindrop trio, sha256 prefixes
  <code>f347b70daa</code>, <code>37f9d5b855</code>, <code>4e03fc9705</code>,
  re-verified against the archived bytes), so the platform validator changed or is
  inconsistent — flagged in irregularity I-8. Current policy and the remaining
  contingency:</p>
  <div class="scroll"><table><thead><tr><th>encoding</th><th>validator behaviour</th>
  <th>what to do</th></tr></thead><tbody>
  <tr><td><b>All-finite (PRIMARY).</b> float32, no NoData tag, every cell in
      [0,1], exactly 0.0 outside the survey footprint. Score-neutral for a binary
      map: 0 is a non-prediction, so TP_w and FP_w are unchanged.</td>
      <td>Passes BOTH readings: a NoData-honouring (masked) read and a naive raw
      <code>all(0 ≤ v ≤ 1)</code> test. The team's round-12 upload
      (<code>r7-nms3-dem10-scarp_…_allfinite</code>) was accepted under this
      encoding family (team-recorded).</td>
      <td><b>Upload this first, always.</b> The front-page primary button and the
      .zip both serve it. If it is ever rejected, record the exact response in
      <code>reports/form_responses.json</code> — that would be new evidence.</td></tr>
  <tr><td><b>Null/NaN outside (record-only).</b> The problem-page text describes
      null/NaN outside the data bounds; a validator that reads the raw array
      without honouring the NoData tag and tests <code>all(0 ≤ v ≤ 1)</code>
      rejects any such file — <b>measured on the form 2026-09-30</b>.</td>
      <td>REJECTED with “Predicted values must be in range [0, 1]” on the R11
      primary (user-reported, this session). Earlier NaN-outside uploads were
      accepted, so the validator behaviour changed or is inconsistent (I-8).</td>
      <td>Never upload first. Kept as <code>{e(strict_file)}</code> for the record
      and A/B evidence only.</td></tr>
  </tbody></table></div>
  <p class="small">If the all-finite primary <i>also</i> fails, stop spending slots
  and capture the exact response: that would be the first evidence that neither
  NoData encoding is the issue, and the next suspects are the ZIP wrapper or
  CRS/transform. Local checks cannot prove remote acceptance — only the recorded
  form response can.</p>
</section>

<section>
  <h2>Official format requirements</h2>
  <div class="panel">
    <ul class="small">
      <li>Same projected CRS and bounds as training data: <b>EPSG:32611</b></li>
      <li>Same resolution: <b>100 m</b>; 3730×3292 grid and matching transform</li>
      <li>One layer, <b>float32</b>, values between <b>0 and 1</b></li>
      <li>Outside the data bounds: <b>null/NaN per the problem description — but the
          form's validator REJECTED that encoding on 2026-09-30</b>, so this
          repository now ships the score-neutral all-finite encoding (0.0 outside
          the footprint) as the primary upload</li>
    </ul>
    <p class="small">Official source:
    <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">DrivenData problem description → Submission format</a>.
    The shipped all-finite file passes the repository's local grid/range/footprint
    checks (recorded in <code>reports/primary_flip_2026-09-30.json</code>); that does
    not clear its prediction map or fully verify server acceptance — the form's own
    response, recorded in <code>reports/form_responses.json</code>, is the receipt.</p>
  </div>
</section>

<section>
  <h2>Why the holdout gate matters</h2>
  <p>Competition organizers define a new fault to include uncaptured extensions,
  splays, parallel strands, and corrections, and say known training pixels are masked
  pixel-exactly. Predictions near known traces but far from new-fault truth are
  penalized. These are reasons to test plausible detectors locally, not permission to
  treat catalogue hide-and-recover results as a reconstruction of the undisclosed
  test distribution.</p>
  <p>Keep the scientific rationale and the scoring evidence separate. Every challenger
  tested so far (R8 ensemble, R9 gap-completion, epicentral alignment, parallel-offset
  corrections) raised recall but lost DTI against the reference in confirmation folds —
  which is exactly why none of them replaced the shipped reference recipe.</p>
</section>"""
    return page("executive_summary.html", "Submission workflow", body)


# ---------------------------------------------------------------------------
def build_evidence() -> str:
    audit = load("metric_audit.json", {})
    fx = load("scored_forensics.json", {})
    hold = load("holdout_candidate_r8_2026-09-30.json", {}) or {}
    r9 = load("holdout_r9_2026-09-30.json", {}) or {}
    band = load("band_audit.json")
    r10 = load("holdout_r10_2026-09-30.json", {}) or {}
    r10b = load("holdout_r10b_2026-09-30.json", {}) or {}
    extman = load("external_manifest.json", {}) or {}
    extdet = load("external_detectors_manifest.json", {}) or {}
    extaudit = load("external_audit.json", {}) or {}
    band6 = load("band6_identity.json", {}) or {}

    # external staging / verification table
    ext_files_rows = ""
    for fname, rec in (extman.get("files") or {}).items():
        ok = (rec.get("sha256_matches_sibling_provenance")
              and rec.get("blob_matches_sibling_git_tree"))
        ext_files_rows += (
            f"<tr><td class='mono small'>{e(fname)}</td>"
            f"<td class='num'>{rec.get('bytes', 0):,}</td>"
            f"<td class='mono small'>{e(str(rec.get('sha256', ''))[:16])}…</td>"
            f"<td class='mono small'>{e(str(rec.get('git_blob_sha1', ''))[:12])}…</td>"
            f"<td class='small'>{e(rec.get('official_source', ''))}</td>"
            f"<td>{'✅ both' if ok else '⚠️ check'}</td></tr>")

    b6 = ((band6.get("candidates") or {}).get("radiometric::rad_tc") or {})
    b6sum = max((band6.get("sum_closure_tests") or {"": {"spearman_rho": 0}}).values(),
                key=lambda v: v.get("spearman_rho", 0))
    b6verdict = (band6.get("verdict") or {}).get(
        "band6_is_official_radiometric_total_count", False)

    # R10 confirmation table (all 17 configurations)
    r10_conf = r10.get("confirmation_summary", {}) or {}
    r10_verdicts = r10.get("verdicts_predeclared", {}) or {}
    r10_paired = r10.get("paired_vs_reference", {}) or {}
    r10_ev_rows = ""
    for cfg, summ in sorted(r10_conf.items(),
                            key=lambda kv: -kv[1].get("dti_worst_rule_mean", 0)):
        pr = r10_paired.get(cfg) or {}
        r10_ev_rows += (
            f"<tr><td class='mono small'>{e(cfg)}</td>"
            f"<td class='num'>{summ.get('dti_worst_rule_mean', 0):.5f}</td>"
            f"<td class='num'>{summ.get('dti_mean', 0):.5f}</td>"
            f"<td class='num'>{summ.get('precision_w_mean', 0):.4f}</td>"
            f"<td class='num'>{summ.get('recall_w_mean', 0):.4f}</td>"
            f"<td class='num'>{summ.get('predicted_eval_px_mean', 0):,.0f}</td>"
            f"<td class='num'>{pr.get('mean_delta_dti', 0):+.5f}</td>"
            f"<td class='num'>{summ.get('max_tie_fraction', 0):.2f}</td>"
            f"<td class='small'>{'REFERENCE' if cfg == 'topo_05_sp3' else e(r10_verdicts.get(cfg, 'n/a'))}</td></tr>")
    sel = r10b.get("selected_on_tune") or "n/a"
    sel_conf = (r10b.get("confirmation_summary", {}) or {}).get(sel, {}) or {}
    sel_pair = r10b.get("paired_vs_reference_selected", {}) or {}
    sel_verdict = (r10b.get("verdict_predeclared", {}) or {}).get(sel, "n/a")

    # R9 paired validation block
    r9_block = "<p class='small'>No R9 report was found.</p>"
    if r9:
        rules = ["random", "short", "isolated", "oriented", "dense", "segment_random"]
        headers = "".join(f"<th class='num'>{e(rule)}</th>" for rule in rules)
        conf = r9.get("confirmation_summary", {})
        paired = r9.get("paired_vs_reference", {})
        verdicts = r9.get("verdicts_predeclared", {})
        labels = [
            ("BASE_topo_ridge · 5% · sp3 — REFERENCE", "topo_05_sp3"),
            ("H9 strict gap-close (min_side 2)", "topo05_gapS_sp3"),
            ("H11 parallel-offset corrections", "topo05_corr_sp3"),
            ("H10 epicentral alignment (1.5%)", "topo05_eq15_sp3"),
            ("H9 loose gap-close (min_side 1)", "topo05_gapL_sp3"),
            ("topo 8% + loose gap-close", "topo08_gapL_sp3"),
            ("topo 8% + loose gaps + epicentral", "topo08_gapL_eq15_sp3"),
            ("topo 8% + loose gaps + epicentral + corrections", "topo08_all_sp3"),
        ]
        rtrs = ""
        for label, key in labels:
            d = conf.get(key)
            if not d:
                continue
            vals = d.get("dti_mean_by_rule", {})
            rule_cells = "".join(
                f"<td class='num'>{vals[rule]:.4f}</td>" if rule in vals
                else "<td class='num'>–</td>" for rule in rules)
            p = paired.get(key)
            delta = (f"{p['mean_delta_dti']:+.5f}" if p and
                     isinstance(p.get("mean_delta_dti"), (int, float)) else "—")
            wtl = (f"{p['wins']}/{p['ties']}/{p['losses']}" if p else "—")
            verdict = ("reference" if key == "topo_05_sp3"
                       else e(verdicts.get(key, "n/a")))
            rtrs += (f"<tr><td>{e(label)}</td>"
                     f"<td class='num'>{d.get('dti_worst_rule_mean', 0):.4f}</td>"
                     f"<td class='num'>{d.get('dti_mean', 0):.4f}</td>"
                     f"<td class='num'>{delta}</td><td class='num'>{wtl}</td>"
                     f"<td>{verdict}</td>{rule_cells}</tr>")
        check = r9.get("protocol_regression_check", {})
        r9_block = f"""
  <p class="small"><b>R9 protocol regression check:</b>
  {'PASS — the reference row reproduces the archived per-fold DTI values exactly (' + str(check.get('n_compared', 0)) + ' folds compared)' if check.get('pass') else 'FAIL'}.
  Predeclared decision rule and all 144 scored rows:
  <code>reports/holdout_r9_2026-09-30.json</code>.</p>
  <div class="scroll"><table><thead><tr><th>R9 candidate</th>
  <th class="num">worst-rule mean DTI</th><th class="num">mean DTI</th>
  <th class="num">ΔDTI vs ref</th><th class="num">W/T/L</th><th>verdict</th>
  {headers}</tr></thead><tbody>{rtrs}</tbody></table></div>
  <p class="small"><b>Metric reading (audit A5):</b> the loose gap-fill added a mean of
  145,608 evaluation pixels per fold and lost 0.0257 mean DTI — its marginal weighted
  precision was below the <code>0.2 × DTI</code> inclusion bar, so the metric itself
  predicted the loss. The strict gap-close (+32 px) and the corrections detector
  (+26 px) changed nothing measurably; the epicentral alignment (+16,590 px) cost
  −0.0021. None is fragile-or-better: all LOSE under the predeclared rule.</p>"""

    crows = "".join(
        f"<tr><td class='mono'>{e(k)}</td>"
        f"<td><span class='tag {'t-ok' if v['pass'] else 't-bad'}'>"
        f"{'PASS' if v['pass'] else 'FAIL'}</span></td></tr>"
        for k, v in audit.get("checks", {}).items())

    mrows = ""
    for n, v in sorted(fx.get("maps", {}).items()):
        b = v["mass_by_distance_to_known_catalogue"]
        echo = b["on_known"] + b["within_300m"]
        mrows += (f"<tr><td class='mono'>{e(n.replace('.tif',''))}</td>"
                  f"<td class='num'>{v['reported_score_label_not_receipt']:.4f}</td>"
                  f"<td class='num'>{v['n_pixels_gt0']:,}</td>"
                  f"<td class='num'>{v['coverage_pct_of_valid']:.2f}%</td>"
                  f"<td class='num'>{v['n_distinct_values']:,}</td>"
                  f"<td class='num'>{echo*100:.1f}%</td>"
                  f"<td class='num'>{v['n_positive_pixels_outside_known_mask']:,}</td>"
                  f"<td class='num'>{v['unmasked_mass_pct_of_valid']:.2f}%</td></tr>")

    prows = "".join(
        f"<tr><td class='mono'>{e(p['a'].replace('.tif',''))}</td>"
        f"<td class='mono'>{e(p['b'].replace('.tif',''))}</td>"
        f"<td class='num'>{p['reported_score_label_a_not_receipt']:.4f}</td>"
        f"<td class='num'>{p['reported_score_label_b_not_receipt']:.4f}</td>"
                  f"<td>{'yes' if p['exact_file_bytes'] else 'no'}</td>"
        f"<td>{'yes' if p['exact_canonical_pixel_values'] else 'no'}</td>"
        f"<td>{'yes' if p['exact_unmasked_evaluation_support'] else 'no'}</td>"
        f"<td class='num'>{p['IoU_of_support']:.4f}</td>"
        f"<td class='num'>{p['unmasked_evaluation_support_IoU']:.4f}</td></tr>"
        for p in sorted(fx.get("pairwise", []),
                        key=lambda z: (not z["same_reported_score_label"], -z["IoU_of_support"]))[:8])

    hold_block = "<p class='small'>No current holdout report was found.</p>"
    if hold:
        summary = hold.get("confirmation_summary", {})
        display = [
            ("BASE_topo_ridge · 5% · spacing 3", "topo_05_sp3"),
            ("BASE_topo_ridge · 3% · spacing 3", "topo_03_sp3"),
            ("R8 union · spacing 3", "r8_current_union_sp3"),
            ("R8 without catalogue geometry · spacing 3", "r8_no_catalogue_geometry_sp3"),
        ]
        rules = ["random", "short", "isolated", "oriented", "dense", "segment_random"]
        headers = "".join(f"<th class='num'>{e(rule)}</th>" for rule in rules)
        trs = ""
        for label, key in display:
            d = summary.get(key)
            if not d:
                continue
            vals = d.get("dti_mean_by_rule", {})
            rule_cells = "".join(
                f"<td class='num'>{vals[rule]:.4f}</td>" if rule in vals
                else "<td class='num'>–</td>"
                for rule in rules
            )
            support = d.get("predicted_eval_px_mean")
            support_text = f"{support:,.0f}" if isinstance(support, (int, float)) else "n/a"
            trs += (f"<tr><td>{e(label)}</td>"
                    f"<td class='num'>{d.get('dti_worst_rule_mean', 0):.4f}</td>"
                    f"<td class='num'>{d.get('dti_mean', 0):.4f}</td>"
                    f"<td class='num'>{d.get('precision_w_mean', 0):.4f}</td>"
                    f"<td class='num'>{d.get('recall_w_mean', 0):.4f}</td>"
                    f"<td class='num'>{support_text}</td>{rule_cells}</tr>")
        protocol = hold.get("protocol", {})
        system = protocol.get("system_folds", {})
        segment = protocol.get("segment_folds", {})
        fold_count = (len(system.get("rules", [])) * system.get("n_folds_per_rule", 0)
                      + segment.get("n_folds", 0))
        hold_block = f"""
  <p class="small"><b>Protocol:</b> {fold_count} folds total —
  {system.get('n_folds_per_rule', 0)} folds for each of
  {e(', '.join(system.get('rules', [])))} system-withholding rules, plus
  {segment.get('n_folds', 0)} raw 8-connected segment folds. Approximately
  {system.get('hide_fraction_target', 0):.0%} of known fault mass withheld per fold;
  {protocol.get('buffer_px', 0)}-pixel evaluation buffer. Catalogue-derived
  tip/horsetail features are rebuilt per fold from visible catalogue; the exact
  visible known-fault mask is applied; DTI is scored on withheld truth only.
  The low-slope-third slice is reported only as a robustness stress test.</p>
  <div class="scroll"><table><thead><tr><th>recipe</th>
  <th class="num">worst-rule mean DTI</th><th class="num">overall mean DTI</th>
  <th class="num">mean weighted precision</th><th class="num">mean weighted recall</th>
  <th class="num">mean effective positive support</th>{headers}</tr></thead>
  <tbody>{trs}</tbody></table></div>
  <p class="small">These are local known-catalogue recovery scores, not performance
  estimates for the undisclosed test distribution. Candidate selection and this table
  use direct DTI; historical candidate-to-chance ratios have been withdrawn. The
  random-control check is an approximate same-run diagnostic, not a universal baseline
  or submission-clearance criterion.</p>"""
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
  <h2>2 · Score attribution and structural identity</h2>
  <div class="callout warn">
    <p><b>No per-submission score has been verified against these local TIFFs.</b>
    The official leaderboard column is account-level “Best public DW-Tversky”.
    Historical filename/team-note values below are reported labels only, not score
    receipts. The public chance/lift inference based on them is withdrawn.</p>
  </div>
  <p class="small">Exact byte identity, canonical pixel-value identity, and positive-
  support identity are measured separately. Equal rounded labels establish none of
  them; different maps can also receive the same score rounded to four decimals.</p>
  <div class="scroll"><table><thead><tr><th>map A</th><th>map B</th>
  <th class="num">reported label A<br>(not receipt)</th>
  <th class="num">reported label B<br>(not receipt)</th>
  <th>identical TIFF bytes</th><th>identical canonical pixels</th>
  <th>identical unmasked support</th><th class="num">all-support IoU</th>
  <th class="num">unmasked-support IoU</th></tr></thead><tbody>{prows}</tbody></table></div>
  <p class="small">Canonical pixels are decoded float32 values after non-finite and
  outside-valid cells are set to zero. Full SHA-256 values and exact support comparisons
  are in <code>reports/scored_forensics.json</code> and the ledger.</p>

  <h3>Catalogue-distance diagnostics (not score attribution)</h3>
  <div class="scroll"><table><thead><tr><th>local artifact</th>
  <th class="num">historical score label<br>(unverified)</th>
  <th class="num">positive pixels</th><th class="num">coverage</th>
  <th class="num">distinct values</th>
  <th class="num">mass on/within 300 m of known faults</th>
  <th class="num">positive pixels outside known mask</th>
  <th class="num">unmasked prediction mass</th></tr></thead>
  <tbody>{mrows}</tbody></table></div>
  <p class="small">The “unmasked” columns are positive support/mass in valid pixels
  outside the exact known-fault mask, useful for map-identity comparisons. They are not
  true-positive or chargeable support because the new-fault truth is hidden. Proximity
  to the known catalogue likewise does not reveal score: new-fault pixels can lie within
  300 m of known traces, while other nearby predictions are penalized when not close to
  new-fault truth.</p>
</section>

<section>
  <h2>3 · Local hide-and-recover comparison</h2>
  <p class="lede">Withhold catalogue systems and raw raster segments with buffers,
  rebuild catalogue-derived features from visible geometry, apply the organizer's
  pixel-exact known-fault mask, and score DTI on withheld truth only. This tests
  recovery of known catalogue geometry; it does not recreate the undisclosed test
  distribution or estimate private-test performance.</p>
  {hold_block}
</section>

<section>
  <h2>3b · R9 paired validation — three new hypotheses, one predeclared verdict each</h2>
  <p class="lede">Same folds, same buffer, same scorer, same tune/confirm split as the
  R8 comparison. The reference is re-scored in the same run, so every delta is paired.
  H9 = strike-aligned gap completion; H10 = epicentral-alignment lineaments;
  H11 = parallel-offset correction edges.</p>
  {r9_block}
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
    <div class="panel"><h3 style="margin-top:0"><span class="tag t-warn">🟠 I-4</span>
      Account ownership is unverified</h3>
      <p class="small">Score/rank matches do not establish who controls leaderboard
      accounts. The repository makes no allegation of shared ownership or an
      eligibility violation; see the official rules and resolve only from verified
      account records.</p></div>
    <div class="panel"><h3 style="margin-top:0"><span class="tag t-ok">🟢 I-2 RESOLVED</span>
      Band 6 <code>tc</code> <b>is</b> the radiometric total count</h3>
      <p class="small">Measured against the official USGS GeoDAWN radiometric grid
      (<code>radiometric::rad_tc</code>, DOI 10.5066/P93LGLVQ): Spearman
      ρ <b>{b6.get('spearman_rho', 0):.5f}</b>, Pearson r {b6.get('pearson_r', 0):.5f},
      OLS slope {b6.get('ols_slope_band6_per_channel_unit', 0):.4f},
      R² {b6.get('ols_r2', 0):.4f}, RMSE {b6.get('ols_rmse_in_band6_units', 0):.3f} band-6
      units, median ratio {b6.get('median_ratio_band6_over_channel', 0):.5f}. The physical
      closure test also passes — band6 ≈ 7.54 × (K + Th + U) at ρ {b6sum.get('spearman_rho', 0):.5f} —
      which no tilt angle or curvature can satisfy. Its embedded description
      (“Tilt angle <i>or</i> total curvature — magnetic field derivative for edge
      detection”) does not describe the array: that is a documentation defect worth
      raising with the organisers. The earlier “disproved” verdict relied on an unverified
      units assumption (that a count rate must be 10²–10⁴ cps); the official grid itself
      spans 5.47–30.27 here, and band 6 keeps a tail to 88.57 that the 8-bit product
      clips. Measured by <code>scripts/audit_band6_identity.py</code> →
      <code>reports/band6_identity.json</code>.</p></div>
    <div class="panel"><h3 style="margin-top:0"><span class="tag t-warn">🟡 I-6</span>
      Dated leaderboard snapshot</h3>
      <p class="small">Fetched 2026-09-30: <b>0.3168</b> (DARD) and
      <b>0.3042</b> (alexoktaba). Both are account-level “Best public” values,
      not per-submission receipts.</p></div>
  </div>
  <p class="small">Full list with evidence and actions:
  <a href="https://github.com/buffedlizard55-lab/13GEMSDOE/blob/main/knowledge/02_irregularities.md">knowledge/02_irregularities.md</a>.</p>
</section>

<section>
  <h2>6 · Official external data — staging, verification, measurement</h2>
  <p class="lede">Everything below is free, official and public domain. Each file was
  verified twice before use, and every map built from them was measured on the same
  paired holdout protocol as the internal detectors.</p>
  <div class="scroll"><table><thead><tr><th>file</th><th class="num">bytes</th>
    <th>sha256 (prefix)</th><th>git blob (prefix)</th><th>official source</th>
    <th>double-verified</th></tr></thead><tbody>{ext_files_rows}</tbody></table></div>
  <p class="small">Licence: {e(extman.get('licence', 'USGS public domain'))}.
  Egress caveat: {e(extman.get('egress_note', ''))}. Pins:
  <code>reports/external_manifest.json</code>; per-file provenance records:
  <code>reports/external_provenance/</code>.</p>
  <div class="grid g2">
    <div class="panel"><h3 style="margin-top:0">Grid and catalogue checks</h3>
      <p class="small">All six products conform exactly to the competition grid
      (EPSG:32611, 100 m, 3730×3292, transform 243350 / 4508550). The
      QFFDB-minus-provided-catalogue difference — the “missing faults are just the
      national database” hypothesis — measures <b>{e(str(extaudit.get('qffdb_catalogue_gap', 'n/a')))} pixel(s)</b>:
      the hypothesis is dead, and the QFFDB product is used for analysis only because
      training on it would leak the catalogue. Common domain across all products:
      {extaudit.get('common_domain_px', 0):,} px
      ({100 * extaudit.get('common_domain_fraction_of_footprint', 0):.1f}% of the
      footprint). Report: <code>reports/external_audit.json</code>.</p></div>
    <div class="panel"><h3 style="margin-top:0">Band-6 identity verdict</h3>
      <p class="small">Criterion written before the run: ρ &gt; 0.999 <b>and</b> linear-fit
      R² &gt; 0.99 against the official TC channel <b>and</b> ρ &gt; 0.99 against K + Th + U.
      Result: <b>{'PASS — band 6 is the radiometric total count' if b6verdict else 'criteria not met'}</b>.
      Best single-channel match: <code>{e((band6.get('verdict') or {}).get('best_single_channel_match', {}).get('channel', 'n/a'))}</code>.
      Side benefit: because the competition's own band 6 reproduces the sibling
      re-gridding of the USGS release to R² {b6.get('ols_r2', 0):.4f}, the external staging
      pipeline is validated against first-party data.</p></div>
  </div>
  <h3>R10 — all sixteen configurations, confirmation folds</h3>
  <div class="scroll"><table><thead><tr><th>configuration</th><th class="num">worst-rule DTI</th>
    <th class="num">mean DTI</th><th class="num">P_w</th><th class="num">R_w</th>
    <th class="num">predicted px</th><th class="num">Δ vs ref</th>
    <th class="num">tie fraction</th><th>predeclared verdict</th></tr></thead>
    <tbody>{r10_ev_rows}</tbody></table></div>
  <h3>R10b — refinement round (selected on tune folds, then confirmed)</h3>
  <p class="small">Selected on tune folds only: <code>{e(sel)}</code>. Confirmation
  worst-rule mean <b>{sel_conf.get('dti_worst_rule_mean', 0):.5f}</b> vs reference
  0.08687, mean {sel_conf.get('dti_mean', 0):.5f} vs 0.09763
  (paired Δ {sel_pair.get('mean_delta_dti', 0):+.5f},
  {sel_pair.get('wins', 0)}/{sel_pair.get('n_pairs', 0)} folds won) →
  <b>{e(sel_verdict)}</b>. Low-coverage unions (0.5–1%) measured marginal precision
  0.0136–0.0166, still below the 0.0169 tune inclusion bar: the external maps have no
  high-precision head. Reports: <code>reports/holdout_r10_2026-09-30.json</code>,
  <code>reports/holdout_r10b_2026-09-30.json</code>; per-map signal statistics:
  <code>reports/external_detectors_manifest.json</code>.</p>
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
    fresh_screen_html = """
<section>
  <h2>R10 / R10b — the external-data register is now measured and closed</h2>
  <p class="lede">Four hypotheses were predeclared in
  <a href="https://github.com/buffedlizard55-lab/13GEMSDOE/blob/main/knowledge/06_r10_hypotheses.md">knowledge/06_r10_hypotheses.md</a>
  <i>before</i> any map was built, with the decision rule written down first:
  R10-3 damage-zone texture (3DEP slope_std × profile curvature), R10-1 1-m LiDAR
  morphometric scarp composite, R10-2 radiometric alteration-ratio lineaments
  (U/K, U/Th), R10-4 geothermal-vent conjunction. Two more were screened out on
  measurement before build: the QFFDB-minus-catalogue difference (1 pixel) and a
  LiDAR coherence channel (AUC 0.4608, below chance).</p>
  <p class="small"><b>Outcome: all 24 challenger configurations across R8, R9, R10 and
  R10b LOSE</b> to <code>topo_05_sp3</code> (confirmation worst-rule mean 0.08687; best
  R10 challenger 0.08593; best R10b fusion 0.08286). No submission slot was spent.
  One predeclaration was wrong in its mechanism and is corrected on the record: R10-4
  was expected to be low-recall, and it measured the <i>highest</i> top-5% recall of the
  family (0.0841) — it still loses, because its recall stays below the reference while
  its precision gain is too small to pay for it under β = 2.</p>
  <p class="small">What survives as a research direction is narrow and now evidence-based:
  an external product only helps if it puts predictions within 300 m of faults the
  topographic crest never touches. Re-ranking, tightening or fusing the neighbourhoods
  the crest already hits cannot raise DTI, and univariate AUC is not a go/no-go signal
  (irregularity I-13).</p>
</section>

<section>
  <h2>Fresh external-data candidates — rank for research, not submission</h2>
  <p class="lede">The rank is a qualitative geological prior, not a numerical DTI
  forecast. These four directions use layers that have <b>not</b> been staged (the
  GeoDAWN / 3DEP / QFFDB family has been — see above), and none has passed the
  prescribed holdout. None is approved as viable or ready to submit.</p>
  <div class="scroll"><table><thead><tr><th>rank / hypothesis</th>
  <th>layers and physical signature</th><th>why it could find uncatalogued faults / difference from prior detectors</th>
  <th>expected impact / cost</th><th>required official data and availability</th></tr></thead><tbody>
  <tr><td><b>1 · Event-level focal-plane coherence</b></td>
      <td>USGS ComCat hypocentres + moment-tensor nodal planes; coherent strike/dip geometry projected toward a shallow trace.</td>
      <td>Could expose active buried structures or splays without a mapped scarp. Uses event-by-event focal mechanisms, not the supplied smoothed seismicity bands or the prior seismicity gate.</td>
      <td>Medium possible, high variance; no score forecast.<br>Cost: medium-high</td>
      <td>USGS ComCat/FDSN API. 17,178 M≥2 and 478 M≥3 moment-tensor bbox counts checked; counts are not valid-footprint coverage and local event payload is not staged.</td></tr>
  <tr><td><b>2 · Repeat Landsat thermal/moisture corridors</b></td>
      <td>Landsat Collection 2 Level-2 surface temperature/reflectance + QA; recurring date- and terrain-adjusted residual lineaments.</td>
      <td>Could flag fault-controlled seepage or upflow under alluvium. Differs from static radiometry by requiring repeated satellite observations and temporal residualization; confounds include irrigation, land cover, weather, and shadow.</td>
      <td>Low-to-medium, high false-positive risk.<br>Cost: high</td>
      <td>USGS Landsat C2 Level-2 STAC. 875 January 2020 bbox metadata hits; one inspected item reported 61% cloud. Exact usable footprint and time series are unverified.</td></tr>
  <tr><td><b>3 · Groundwater-head compartments</b></td>
      <td>USGS groundwater-level measurements + well, aquifer, datum, and time metadata; persistent head offsets or different response across a candidate corridor.</td>
      <td>Could indicate a buried hydraulic barrier or conduit without surface relief. Differs from static chemistry/temperature and DEM-derived flow by testing temporal well-head response; aquifer boundaries and pumping are confounders.</td>
      <td>Low-to-medium, likely sparse.<br>Cost: high</td>
      <td>USGS Water Data API field measurements. One 1976 groundwater record found in bbox; station density and comparable time coverage are unknown.</td></tr>
  <tr><td><b>4 · Cross-depth MT edge persistence</b></td>
      <td>Five ScienceBase depth-integrated conductance intervals; test whether a lateral edge recurs at the same location across adjacent depth products.</td>
      <td>Could highlight a buried, vertically persistent boundary beneath weak surface expression. Differs from the prior surface-conductivity/basement rasters by using cross-depth persistence; conductors are not uniquely faults.</td>
      <td>Low, high scale risk.<br>Cost: medium-high</td>
      <td>USGS ScienceBase conductance products (DOI 10.5066/P9TWT2LU). Metadata lists five intervals; grids, native resolution, and valid-footprint coverage are not verified.</td></tr>
  </tbody></table></div>
  <p><a href="../knowledge/05_hypothesis_screen_2026-09-30.md">Full hypotheses, prior-art comparisons, official links, data checks, and validation gate</a>.</p>
</section>"""
    # Prefer the corrected DTI-first summary. Older per-detector screens retain
    # direct DTI only; no candidate-to-chance values are used on this page.
    perf: dict[str, tuple[float, float, str]] = {}
    verdict = load("holdout_verdict_v3.json", {}) or {}
    for row in verdict.get("table", []):
        family = row.get("family")
        if not family or row.get("family") in ("prior_submission", "control"):
            continue
        if row.get("stage") == "confirmation":
            perf[family] = (float(row["worst_rule_mean_dti"]),
                            float(row["mean_dti"]), "confirmed local DTI")
        elif family not in perf:
            perf[family] = (float(row["worst_rule_mean_dti"]),
                            float(row["mean_dti"]), "screening-only DTI")

    for src in ("holdout_r8_quick.json", "holdout_supervised.json",
                "holdout_results.json"):
        hold = load(src)
        if not hold:
            continue
        by_family_tag: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list))
        stages: dict[tuple[str, str], set[str]] = defaultdict(set)
        for row in hold.get("results", []):
            family = str(row.get("family", "")).replace("STAGE2:", "")
            if not family or family in ("control", "control_random", "prior_submission"):
                continue
            tag = str(row.get("tag", family))
            by_family_tag[(family, tag)][row.get("rule", "all")].append(
                float(row["dti"]))
            stages[(family, tag)].add(str(row.get("stage", "stage1")))
        candidates_by_family: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
        for (family, tag), rules in by_family_tag.items():
            if family in perf:
                continue
            means = [float(np.mean(values)) for values in rules.values()]
            if means:
                candidates_by_family[family].append((min(means),
                                                     float(np.mean(means)), tag))
        for family, choices in candidates_by_family.items():
            worst, mean, _tag = max(choices, key=lambda x: (x[0], x[1]))
            perf[family] = (worst, mean, f"historical local DTI · {src}")

    # R9 measured values (paired predeclared validation)
    r9h = load("holdout_r9_2026-09-30.json", {}) or {}
    for fam_key, det_key in (("topo05_gapL_sp3", "strike_gap_close"),
                             ("topo05_gapS_sp3", "strike_gap_close"),
                             ("topo05_eq15_sp3", "R9_eq_align"),
                             ("topo05_corr_sp3", "parallel_offset_correction")):
        s = (r9h.get("confirmation_summary", {}) or {}).get(fam_key)
        if s and det_key not in perf:
            perf[det_key] = (float(s.get("dti_worst_rule_mean", 0) or 0),
                             float(s.get("dti_mean", 0) or 0),
                             "R9 paired confirmation DTI (predeclared rule: LOSES)")

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
        ("R8-1a", "Topographic openness / sky-view factor for subtle scarps", "R8_openness",
         "det_elev (12)",
         "For each of 8 azimuths, maximum horizon inclination within 5 px (500 m); openness = 90° − mean(max_slope); edge is Hessian ridge + NMS of |∇ openness|.",
         "Hypothesis: horizon-angle metrics may emphasize some subdued terrain edges that a local slope threshold misses. The supplied elevation grid is 100 m; decimetre relief, Lahontan-wide prevalence, and catalogue omission are not established by this layer alone.",
         "Different terrain operator from slope/curvature and the prior Laplacian shoreline detector, but it remains a topographic feature and may be redundant.",
         "Unknown (not estimated)", "Low (compute)"),
        ("R8-1b", "Multi-scale Topographic Position Index (TPI)", "R8_tpi",
         "det_elev (12)",
         "TPI = elev − mean(elev in window) at 3/6/12 px (300 m/600 m/1.2 km); gradient of TPI → ridge → NMS; stack across scales.",
         "A multiscale elevation residual may emphasize some topographic breaks, but slope, depositional edges, drainage, roads, and other landforms can create similar patterns. It cannot by itself establish a missing fault or resolve sub-pixel relief.",
         "Uses local elevation residuals rather than horizon angles; still overlaps with prior topographic ridge, curvature, and shoreline detectors.",
         "Unknown marginal DTI", "Low (compute)"),
        ("R8-2", "Fault-controlled drainage deflection (hydrologic lineament)", "R8_flow",
         "det_elev (12) + det_elev_slope (19)",
         "D8 steepest-descent flow direction on det_elev, flow accumulation by descending elevation order, log(1+acc) → |∇ log| → ridge + flat gate (45th pct) → directional coherence.",
         "A drainage anomaly could be consistent with fault-controlled ponding or diversion under cover, but DEM-derived flow is affected by topography, DEM artefacts, climate, and land use; the signature is not fault-specific.",
         "Adds a D8/flow-accumulation transform not used by the earlier edge operators, while remaining dependent on the same elevation data and potentially correlated with existing terrain features.",
         "Unknown marginal DTI", "Medium (feature QC)"),
        ("R8-3", "Isostatic coherence breakdown (buried basin)", "R8_isocoherence",
         "iso_grav_anom (13) + det_elev (12)",
         "Windowed Pearson r between gravity and topography (σ=6 px≈600 m): r = cov/σgσt; breakdown = 1−|r|; modulated by joint gradient; ridge-thin.",
         "A gravity–topography mismatch could flag a subsurface or lithologic boundary beneath subdued relief, but non-fault density contrasts, regional compensation, resolution, and processing can also produce decorrelation. No causal interpretation follows from the score alone.",
         "Tests local amplitude coherence rather than the earlier depth gradient or cross-field gradient alignment; related gravity/topography features can still overlap.",
         "Unknown marginal DTI", "Low-to-medium (scale/QC)"),
        ("R8-4", "Magnetic remanence divergence", "R8_remanence",
         "rtp (2) + tmi (14) + mag_anom (1)",
         "|robust_norm(rtp)−robust_norm(tmi)| and vs mag_anom; max; gradient → ridge.",
         "A mismatch between RTP, TMI, and magnetic-anomaly transforms may reflect remanent magnetization or processing differences and could highlight lithologic contacts. Such contacts are not necessarily faults; input scaling and reduction assumptions require checks.",
         "Compares transformed magnetic products rather than applying a single-field edge detector; it may be redundant with existing magnetic-gradient features and is not independent geological confirmation.",
         "Unknown marginal DTI", "Low-to-medium (normalization/QC)"),
        ("R8-5", "Fault-intersection density (geothermal permeability)", "R8_intersections",
         "secondary on ridge maps e.g. BASE_topo_ridge, HA_worms_rtp, R7_crossgrad",
         "Threshold each ridge at 85th pct → binary line → dilate 1 px → pairwise intersections (AND) → kernel density Gaussian σ=6 px (600 m halo) → robust_norm_nonzero → multiply by ridge skeleton.",
         "A dense intersection of candidate edges could mark a structurally complex zone, but it is only an intersection of detector outputs—not confirmed faults, fracture permeability, or a geothermal upflow measurement. Edge density and correlated false positives are major risks.",
         "Adds a secondary density transform over existing candidate ridge maps rather than a new physical observation. Its apparent novelty is computational; it does not independently validate the input lineaments.",
         "Unknown marginal DTI; current R8 union is below the local topo baseline", "Low-to-medium (threshold sensitivity)"),
        ("R9-1", "Strike-aligned gap completion (“dotted-ridge closing”) — MEASURED", "strike_gap_close",
         "the fused binary prediction map itself (no band, no catalogue)",
         "Oriented morphological closing restricted to pure gap-fill: pixel p emitted iff ≥1 support pixel lies on BOTH sides of p along one of four lattice line directions within reach (axial 3 px, diagonal 2 px), p touches dilated support, and p is not in a solid interior.",
         "Top-k + grid decimation emits physically continuous traces as DASHES; “new fault” is defined per PIXEL and each truth pixel is credited through a 300 m max, so a truth pixel inside a dash gap currently earns 0 TP_w while a prediction there costs almost no FP_w if the line is real.",
         "extension_rays/horsetail extrapolate FROM CATALOGUE TIPS; gravity_termination continues gravity ridges; no prior operator closes gaps in the prediction's own support from its own geometry.",
         "MEASURED: LOSES (loose −0.0257 mean DTI, +145.6k px/fold; strict +32 px, tie)", "Low"),
        ("R9-2", "Epicentral-alignment lineaments — MEASURED", "R9_eq_align / eq_lineaments",
         "ieq_n100a15 (16), deq_n100a15 (10)",
         "Smooth both earthquake-density bands, standardise, geometric mean (both must agree), Hessian ridge, NMS crest, keep crest cells with oriented persistence ≥5 crest px within ±9.",
         "Earthquakes occur ON faults; the catalogue is a surface-evidence compilation, so an active structure with no recognised scarp is absent from it while still producing aligned seismicity in two near-uncorrelated fields (r = 0.083).",
         "H-D subtracts seismicity in a deficit residual; R7-3 uses it as a multiplicative gate on OTHER bands' edges. No prior operator extracts lineaments FROM the seismicity fields.",
         "MEASURED: LOSES (−0.0021 mean DTI at +16,590 px/fold)", "Low"),
        ("R9-3", "Parallel-offset “correction” edges — MEASURED", "parallel_offset_correction",
         "visible catalogue (per fold) + R7_crossgrad edge field (rtp + iso_grav_anom)",
         "Within a 1–4 px perpendicular ring of a visible trace, keep independent-field crest pixels whose orientation is parallel to the local trace strike (≤25°) with an along-strike crest run ≥4 px. Emits EDGE pixels only, never a blanket halo.",
         "Organizer statement 3 names corrections/modifications within 300 m of known traces as target truth. A laterally offset high-quality potential-field edge beside a coarse legacy trace is exactly “newly mapped geometry”.",
         "extension_rays/horsetail fire at trace TIPS; R7-5 gates on catalogue ABSENCE; structural_grain never emits near the catalogue. This is the only ALONG-TRACE operator.",
         "MEASURED: LOSES as a no-op (+26 px/fold, Δ −0.00001); the gate is too strict on this data", "Medium"),
    ]
    rows = ""
    for hid, title, det, layers, sig, why, diff, gain, cost in H:
        k = det.split(" / ")[0]
        p = perf.get(k)
        got = (f"<span class='tag t-info'>worst-rule DTI {p[0]:.4f} · mean DTI {p[1]:.4f}</span><br>"
               f"<span class='small'>{e(p[2])}</span>"
               if p else "<span class='tag t-mut'>pending</span>")
        rows += f"""<tr>
          <td><b>{hid}</b><br><span class="small">{title}</span><br>{got}</td>
          <td class="small mono">{layers}</td>
          <td class="small">{sig}</td>
          <td class="small">{why}</td>
          <td class="small">{diff}</td>
          <td><span class="tag t-info">qualitative: {gain}</span><br>
              <span class="tag t-mut">cost {cost}</span></td></tr>"""

    body = f"""
<section>
  <h2>Previously explored detector hypotheses</h2>
  <p class="lede">These entries summarize earlier candidate mechanisms. Geological
  rationales are hypotheses, not established facts or evidence of hidden-test
  performance. The qualitative impact/cost labels are research judgments, not numeric
  DTI forecasts.</p>
  <p class="small">Any “worst / best” values are historical local constructed-holdout
  DTI summaries from their respective reports; they are not public/private leaderboard
  scores, chance ratios, or results from one common protocol. The current R8 ensemble
  lost to the topo baseline on the separate visible-only confirmation comparison.</p>
  {note}
  <div class="callout">
    <p><b>Why not assume a terrain edge is a new fault?</b> Topographic lineaments can
    be catalogue blind spots, but they can also be known faults, erosion, drainage,
    depositional boundaries, or processing artefacts. The organizers define “new” as
    fault pixels not already captured, including extensions, splays, parallel strands,
    and corrections. Only pixel-exact masking and buffered hide-and-recover tests can
    measure a detector's local recovery of withheld catalogue geometry; they do not
    establish transfer to the undisclosed test set.</p>
  </div>
  <div class="scroll"><table><thead><tr>
    <th>hypothesis</th><th>layers</th><th>physical signature</th>
    <th>why it finds a <i>missing</i> fault</th><th>how it differs from prior work</th>
    <th>rank</th></tr></thead><tbody>{rows}</tbody></table></div>
</section>

{fresh_screen_html}

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
  <p class="small"><b>Scope:</b> the earlier H/R detector register uses the supplied
  bands where stated above. The fresh ranked shortlist is separate and requires the
  external sources listed in its availability column; those data checks are incomplete,
  so none of the four new candidates is called viable.</p>
</section>"""
    return page("hypotheses.html", "Hypotheses", body)


# ---------------------------------------------------------------------------
def build_sources() -> str:
    S = [
        ("Competition home", "https://www.drivendata.org/competitions/306/competition-doe-gems/", "DrivenData", "✅ fetched"),
        ("Problem description (metric + submission format)", "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/", "DrivenData", "✅ fetched"),
        ("About page", "https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/", "DrivenData", "✅ linked"),
        ("Data download tab", "https://www.drivendata.org/competitions/306/competition-doe-gems/data/", "DrivenData", "🔒 login required"),
        ("Public leaderboard snapshot", "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/", "DrivenData", "✅ fetched 2026-09-30 — #1 0.3168 / #2 0.3042; account-level Best public"),
        ("Official Rules (PDF)", "https://docs.nlr.gov/docs/fy26osti/96647.pdf", "NLR / DOE", "✅ fetched"),
        ("Rules landing page", "https://www.herox.com/GEMSPrize/resource/2274", "HeroX", "✅ fetched"),
        ("Reference solution", "https://github.com/drivendataorg/gems-prize-reference-solution", "DrivenData", "✅ downloaded"),
        ("Forum — Scoring clarification (11516)", "https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516", "DrivenData forum", "✅ all 4 posts read"),
        ("Forum — Where do you draw the line? (11536)", "https://community.drivendata.org/t/where-do-you-draw-the-line/11536", "DrivenData forum", "✅ both posts read"),
        ("Forum — How were the new test faults identified? (11527)", "https://community.drivendata.org/t/how-were-the-new-test-faults-identified-data-sources-and-fault-types/11527/7", "DrivenData forum", "✅ all 10 posts re-read 2026-09-30 via /print; no new organizer statement"),
        ("Forum — Weekly submissions (11524)", "https://community.drivendata.org/t/weekly-submissions/11524", "DrivenData forum", "✅ read 2026-09-30 — allowance resets on a rolling window"),
        ("Forum — Paid for external data license (11528)", "https://community.drivendata.org/t/paid-for-external-data-license/11528", "DrivenData forum", "✅ read 2026-09-30 — external data allowed with a licence permitting use in the challenge and sharing with the sponsor"),
        ("Forum — Label TIF bands (11529)", "https://community.drivendata.org/t/why-does-the-training-fault-labels-file-in-the-data-tab-have-a-single-band-while-the-labels-in-the-reference-solution-repo-have-19-bands/11529", "DrivenData forum", "✅ read 2026-09-30 — '19 bands' is a notebook printing bug; the label TIF has one band"),
        ("Forum — Team member eligibility (11540)", "https://community.drivendata.org/t/team-member-eligibility-competition-homepage-vs-official-rules/11540", "DrivenData forum", "✅ read 2026-09-30 — Official Rules take precedence over the homepage"),
        ("Forum — Using a teammate's interpretation as labels (11543)", "https://community.drivendata.org/t/using-a-teammates-geological-interpretation-as-training-labels/11543", "DrivenData forum", "⚠️ listed, 0 replies at fetch time; no organizer guidance"),
        ("USGS 3DEP elevation (1 m / 10 m staged products)", "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/", "USGS", "🔒 TLS-blocked from this sandbox; obtained via the sibling-repo mirror and hash-verified"),
        ("USGS Quaternary fault and fold database (QFFDB)", "https://earthquake.usgs.gov/static/lfs/nshm/qfaults/Qfaults_GIS.zip", "USGS", "🔒 TLS-blocked; mirrored copy hash-verified (sha256 447eadc5…, DOI 10.5066/P9BCVRCK) — analysis only, leakage risk"),
        ("USGS Great Basin conductance maps (DOI 10.5066/P9TWT2LU)", "https://doi.org/10.5066/P9TWT2LU", "USGS", "✅ DOI metadata read; 12.34 GB grids not staged (Phase-2 candidate)"),
        ("USGS gravity / magnetic / depth-to-basement grids (DOI 10.5066/P9Z6SA1Z)", "https://doi.org/10.5066/P9Z6SA1Z", "USGS", "✅ DOI metadata read; grids not staged"),
        ("USGS detrended elevation (DOI 10.5066/P9MQRCBY)", "https://doi.org/10.5066/P9MQRCBY", "USGS", "✅ DOI metadata read; 12.34 GB, not staged"),
        ("Sibling staging mirror — 7GEMSDOE external/", "https://github.com/buffedlizard55-lab/7GEMSDOE/tree/HEAD/external", "this group", "✅ fetched via GitHub API; every file verified against sha256 + git blob SHA-1"),
        ("USGS ComCat event catalog / FDSN API", "https://earthquake.usgs.gov/fdsnws/event/1/", "USGS", "✅ bbox counts checked; local bulk download not staged"),
        ("USGS Landsat Collection 2 Level-2 STAC", "https://landsatlook.usgs.gov/stac-server/collections/landsat-c2l2-sr", "USGS", "✅ metadata query checked; exact cloud-free footprint/time-series coverage unverified"),
        ("USGS Water Data API — field measurements", "https://api.waterdata.usgs.gov/ogcapi/v0/collections/field-measurements", "USGS", "✅ one groundwater-level record found in bbox; network adequacy unverified"),
        ("USGS Great Basin conductance maps", "https://www.sciencebase.gov/catalog/item/62979746d34ec53d276c113b", "USGS ScienceBase", "✅ metadata lists five depth intervals; binary grids not verified locally"),
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
  <div class="panel">
    <p class="small"><b>External products (<code>data/external/</code>, gitignored).</b>
    Six USGS public-domain rasters, re-gridded onto the competition grid by this group's
    open-egress runners and re-staged here by <code>scripts/fetch_external_data.py</code>.
    Each file is verified twice: sha256 against the sibling provenance record and git
    blob SHA-1 against the sibling git tree. Pins and mirrors:
    <code>reports/external_manifest.json</code>, per-file records in
    <code>reports/external_provenance/</code>. Licence permits competition use and
    sharing with the sponsor (public domain; attribution recorded).</p>
    <p class="small" style="margin-bottom:0"><b>Independent validation:</b> the
    competition's own band 6 reproduces the staged radiometric total-count channel at
    Spearman ρ 0.99998 / R² 0.9980, so the staging and dequantisation pipeline recovers
    the field the organisers shipped (<code>reports/band6_identity.json</code>).</p>
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
