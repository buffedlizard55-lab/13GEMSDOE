#!/usr/bin/env python3
"""R14/R15 validation of knowledge/10_r14_hypotheses.md under its OWN rule.

Implements §3 exactly:

  folds      9 new `tip` folds (gems.holdout.tip_folds) + the 15 pre-existing
             hide-and-recover folds (gems.holdout.build_folds, unchanged)
             + one external SGMC truth set (USGS State Geologic Map faults
             >= 16 px from the catalogue)
  scoring    gems.metric.dti via gems.fastscore.FoldScorer, verified against
             the reference implementation before the run
  masks      footprint & ~visible_catalogue in every fold (organiser rule, F1)
  decision   D1 worst-rule mean on the tip folds beats the shipped reference
             D2 >= 7 of 9 tip folds individually (paired)
             D3 does not lose by > 0.002 on the worst rule of the 15 old folds
             D4 the DEPLOYMENT map (tips grown from the FULL catalogue) is
                >= 95 % off-catalogue

Run:  python scripts/validate_r14_hypotheses.py
Out:  reports/holdout_r14_2026-10-01.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import propagation as P                          # noqa: E402
from gems.encoding import FOOTPRINT_PIXELS                 # noqa: E402
from gems.fastscore import FoldScorer, verify_against_reference  # noqa: E402
from gems.holdout import build_folds, tip_folds            # noqa: E402

RAW = ROOT / "data" / "raw"
EXT = ROOT / "data" / "external_sgmc" / "derived_sgmc_faults_100m_u8.tif"
OUT = ROOT / "reports" / "holdout_r14_2026-10-01.json"

TIP_LENS = (5, 10, 20)
BUDGET_FRACS = (0.01, 0.02, 0.04)
# prioritised unions: tips at this budget, then a stride-7 lattice fills the
# rest of a 4 % total budget (a coverage floor under the geological prior)
UNION_SPECS = [("union_tipsL20_1pct+lat7_4pct", 20, 0.01, 7, 0.04),
               ("union_tipsL20_2pct+lat7_4pct", 20, 0.02, 7, 0.04),
               ("union_tipsL10_1pct+lat6_4pct", 10, 0.01, 6, 0.04)]
REFERENCE = "lattice_s5"
D2_MIN_PAIRED_WINS = 7
D3_MAX_LOSS = 0.002
D4_MIN_OFFCATALOGUE = 0.95



def union_pred(spec, tips_field, eval_mask, budgets_, lattices_, jitter_):
    _, L, tip_frac, stride, total_frac = spec
    tf = tips_field[L]
    prim = P.budget_from_intensity(tf, eval_mask, budgets_[tip_frac], jitter=jitter_) > 0
    return P.prioritised_union(prim, lattices_[stride], eval_mask,
                               budgets_[total_frac], jitter=jitter_)

def main() -> int:
    t0 = time.time()
    v = verify_against_reference(trials=10)
    if not v["pass"]:
        raise SystemExit(f"fast scorer disagrees with the reference metric: {v}")
    print(f"scorer verified: {v['max_err']}")

    with rasterio.open(RAW / "existing_faults.tif") as s:
        lab = s.read(1)
    valid = lab >= 0
    known = lab > 0
    assert int(valid.sum()) == FOOTPRINT_PIXELS
    n_valid = int(valid.sum())
    budgets = {f: int(round(f * n_valid)) for f in BUDGET_FRACS}
    print(f"footprint {n_valid:,} px, catalogue {int(known.sum()):,} px, "
          f"budgets {budgets}")

    ref_lattice = P.square_lattice(valid.shape, 5)
    # fixed, seeded, spatially uniform tie-break field (I-14: without it a
    # top-K over a massively tied field silently selects by row-major position)
    jitter = P.make_jitter(valid.shape)

    tip = tip_folds(known, valid, tip_lens=(8, 16, 32), seeds=(1, 2, 3))
    old = build_folds(known, valid, n_folds=3, hide_frac=0.25,
                      seed=20260930, link_px=8, buffer_px=5)
    print(f"{len(tip)} tip folds, {len(old)} pre-existing folds")

    sgmc_truth = None
    if EXT.exists():
        with rasterio.open(EXT) as s:
            sg = s.read(1)
        sgmc_truth = (sg == 1) & valid & ~ndi.binary_dilation(known, iterations=16)
        print(f"SGMC external truth: {int(sgmc_truth.sum()):,} px")
    else:
        print("SGMC external truth absent (python scripts/fetch_sgmc_truth.py)")

    # candidate names, fixed before scoring
    names = [REFERENCE]
    for f in BUDGET_FRACS:
        names.append(f"halo@{f:g}")
        for L in TIP_LENS:
            names.append(f"tips_L{L}@{f:g}")
    names += [u[0] for u in UNION_SPECS]
    lattices = {st: P.square_lattice(valid.shape, st) for _, _, _, st, _ in UNION_SPECS}

    rows: list[dict] = []
    families = [("tip", tip), ("old", old)]
    for fam, folds in families:
        for f in folds:
            ts = time.time()
            scorer = FoldScorer.build(f.hidden, f.eval_mask)
            idx = np.flatnonzero(f.eval_mask.ravel())
            # per-fold intensity fields
            halo = P.isotropic_halo(f.visible)
            tips = {L: P.along_strike_tips(f.visible, length_px=L) for L in TIP_LENS}
            for name in names:
                if name == REFERENCE:
                    pred = (ref_lattice & f.eval_mask).astype(np.float32)
                elif name.startswith("halo@"):
                    fr = float(name.split("@")[1])
                    pred = P.budget_from_intensity(halo, f.eval_mask, budgets[fr],
                                                   jitter=jitter)
                elif name.startswith("union_"):
                    spec = next(u for u in UNION_SPECS if u[0] == name)
                    pred = union_pred(spec, tips, f.eval_mask, budgets, lattices, jitter)
                else:
                    _, Ls = name.split("_L")
                    L, fr = Ls.split("@")
                    pred = P.budget_from_intensity(tips[int(L)], f.eval_mask,
                                                   budgets[float(fr)], jitter=jitter)
                sc = scorer.score(pred)
                rows.append({"family": fam, "fold": f.name, "rule": f.rule,
                             "map": name, "n_truth": f.n_hidden,
                             "n_predicted": int((pred > 0).sum()), **sc})
            # the external truth set, scored once per candidate on the FULL
            # catalogue as visible (that is the deployment situation)
            print(f"  [{fam}] {f.name:16s} truth={f.n_hidden:6d} "
                  f"{len(names)} maps in {time.time()-ts:.1f}s")
            del scorer, idx, halo, tips

    if sgmc_truth is not None:
        ts = time.time()
        em = valid & ~known
        scorer = FoldScorer.build(sgmc_truth, em)
        halo = P.isotropic_halo(known)
        tips = {L: P.along_strike_tips(known, length_px=L) for L in TIP_LENS}
        for name in names:
            if name == REFERENCE:
                pred = (ref_lattice & em).astype(np.float32)
            elif name.startswith("halo@"):
                pred = P.budget_from_intensity(halo, em, budgets[float(name.split("@")[1])],
                                               jitter=jitter)
            elif name.startswith("union_"):
                spec = next(u for u in UNION_SPECS if u[0] == name)
                pred = union_pred(spec, tips, em, budgets, lattices, jitter)
            else:
                _, Ls = name.split("_L"); L, fr = Ls.split("@")
                pred = P.budget_from_intensity(tips[int(L)], em, budgets[float(fr)],
                                               jitter=jitter)
            sc = scorer.score(pred)
            rows.append({"family": "sgmc", "fold": "sgmc_offcat_r16",
                         "rule": "sgmc_offcat_r16", "map": name,
                         "n_truth": int(sgmc_truth.sum()),
                         "n_predicted": int((pred > 0).sum()), **sc})
        print(f"  [sgmc] scored {len(names)} maps in {time.time()-ts:.1f}s")

    # ---- aggregate -------------------------------------------------------
    def agg(family: str, rule: str | None = None) -> dict:
        out = {}
        for name in names:
            rs = [r for r in rows if r["family"] == family and r["map"] == name
                  and (rule is None or r["rule"] == rule)]
            if not rs:
                continue
            out[name] = {
                "dti_mean": float(np.mean([r["dti"] for r in rs])),
                "dti_min": float(np.min([r["dti"] for r in rs])),
                "precision_w_mean": float(np.mean([r["precision_w"] for r in rs])),
                "recall_w_mean": float(np.mean([r["recall_w"] for r in rs])),
                "n_predicted_mean": float(np.mean([r["n_predicted"] for r in rs])),
                "n_folds": len(rs),
            }
        return out

    tip_by_rule = {r: agg("tip", r) for r in sorted({x["rule"] for x in rows
                                                     if x["family"] == "tip"})}
    tip_all = agg("tip")
    old_by_rule = {r: agg("old", r) for r in sorted({x["rule"] for x in rows
                                                     if x["family"] == "old"})}
    old_all = agg("old")
    sgmc_all = agg("sgmc")

    def worst_rule(by_rule: dict, name: str) -> float:
        vals = [d[name]["dti_mean"] for d in by_rule.values() if name in d]
        return float(min(vals)) if vals else float("nan")

    # paired fold comparison on the tip folds
    paired = {}
    for name in names:
        if name == REFERENCE:
            continue
        wins = 0
        tot = 0
        for f in tip:
            a = [r for r in rows if r["family"] == "tip" and r["fold"] == f.name
                 and r["map"] == name]
            b = [r for r in rows if r["family"] == "tip" and r["fold"] == f.name
                 and r["map"] == REFERENCE]
            if a and b:
                tot += 1
                wins += int(a[0]["dti"] > b[0]["dti"])
        paired[name] = {"wins": wins, "folds": tot}

    # D4: the DEPLOYMENT map, tips grown from the FULL catalogue
    d4 = {}
    em_full = valid & ~known
    halo_full = P.isotropic_halo(known)
    for L in TIP_LENS:
        tf = P.along_strike_tips(known, length_px=L)
        for f in BUDGET_FRACS:
            pred = P.budget_from_intensity(tf, em_full, budgets[f], jitter=jitter)
            sel = pred > 0
            d4[f"tips_L{L}@{f:g}"] = {
                "n_selected": int(sel.sum()),
                "frac_off_catalogue": float((sel & ~known).sum() / max(int(sel.sum()), 1)),
                "frac_off_catalogue_and_off_valid": float(
                    (sel & ~known & valid).sum() / max(int(sel.sum()), 1)),
            }
        del tf
    for spec in UNION_SPECS:
        _, L, tip_frac, stride, total_frac = spec
        tf = P.along_strike_tips(known, length_px=L)
        prim = P.budget_from_intensity(tf, em_full, budgets[tip_frac], jitter=jitter) > 0
        up = P.prioritised_union(prim, lattices[stride], em_full,
                                 budgets[total_frac], jitter=jitter) > 0
        d4[spec[0]] = {"n_selected": int(up.sum()),
                       "frac_off_catalogue": float((up & ~known).sum() / max(int(up.sum()), 1))}
        del tf
    sel = P.budget_from_intensity(halo_full, em_full, budgets[0.04], jitter=jitter) > 0
    d4["halo@0.04"] = {"n_selected": int(sel.sum()),
                       "frac_off_catalogue": float((sel & ~known).sum() / max(int(sel.sum()), 1))}

    ties = {"halo_full_catalogue": P.tie_fraction(halo_full, em_full)}
    for L in TIP_LENS:
        ties[f"tips_L{L}_full_catalogue"] = P.tie_fraction(
            P.along_strike_tips(known, length_px=L), em_full)

    verdicts = {}
    for name in names:
        if name == REFERENCE:
            verdicts[name] = {"verdict": "REFERENCE"}
            continue
        d1 = worst_rule(tip_by_rule, name) > worst_rule(tip_by_rule, REFERENCE)
        d2 = paired[name]["wins"] >= D2_MIN_PAIRED_WINS
        d3 = (worst_rule(old_by_rule, name)
              >= worst_rule(old_by_rule, REFERENCE) - D3_MAX_LOSS)
        d4ok = d4.get(name, {}).get("frac_off_catalogue", 0.0) >= D4_MIN_OFFCATALOGUE
        allpass = d1 and d2 and d3 and d4ok
        verdicts[name] = {
            "D1_tip_worst_rule_beats_reference": bool(d1),
            "D1_values": {"candidate": worst_rule(tip_by_rule, name),
                          "reference": worst_rule(tip_by_rule, REFERENCE)},
            "D2_paired_tip_fold_wins": paired[name],
            "D2_threshold": D2_MIN_PAIRED_WINS,
            "D3_old_fold_worst_rule_not_worse_by_more_than": {
                "candidate": worst_rule(old_by_rule, name),
                "reference": worst_rule(old_by_rule, REFERENCE),
                "max_loss": D3_MAX_LOSS, "pass": bool(d3)},
            "D4_deployment_off_catalogue": d4.get(name),
            "D4_threshold": D4_MIN_OFFCATALOGUE,
            "PASSES_ALL": bool(allpass),
            "verdict": ("PASSES the predeclared gate" if allpass else
                        "does NOT pass the predeclared gate"),
        }

    winners = [n for n, d in verdicts.items() if d.get("PASSES_ALL")]
    report = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "script": "scripts/validate_r14_hypotheses.py",
        "register": "knowledge/10_r14_hypotheses.md",
        "runtime_s": round(time.time() - t0, 1),
        "scorer_verification": v,
        "config": {"reference": REFERENCE, "tip_lens": list(TIP_LENS),
                   "budget_fracs": list(BUDGET_FRACS), "budgets_px": budgets,
                   "n_tip_folds": len(tip), "n_old_folds": len(old),
                   "thresholds": {"D2": D2_MIN_PAIRED_WINS, "D3": D3_MAX_LOSS,
                                  "D4": D4_MIN_OFFCATALOGUE}},
        "tip_fold_inventory": [{"name": f.name, "rule": f.rule,
                                "n_hidden": f.n_hidden, "n_visible": f.n_visible,
                                "eval_mask_px": int(f.eval_mask.sum()),
                                **f.meta} for f in tip],
        "sgmc_truth_px": int(sgmc_truth.sum()) if sgmc_truth is not None else None,
        "results_tip_by_rule": tip_by_rule,
        "results_tip_all": tip_all,
        "results_old_by_rule": old_by_rule,
        "results_old_all": old_all,
        "results_sgmc_offcat_r16": sgmc_all,
        "paired_tip_wins": paired,
        "deployment_off_catalogue": d4,
        "tie_fractions_largest_tie_over_allowed": ties,
        "tie_break_policy": ("fixed seeded spatially uniform jitter "
                             "(gems.propagation.make_jitter, seed 20261001), "
                             "scaled to 1e-7 of each field's own range; without "
                             "it argpartition breaks ties by flat index and "
                             "silently selects the northernmost slice (I-14)"),
        "verdicts_predeclared": verdicts,
        "winners": winners,
        "predeclared_predictions_checked": {
            "P1_halo_beats_lattice_on_tip_folds": bool(
                any(n.startswith("halo@") and verdicts[n]["D1_tip_worst_rule_beats_reference"]
                    for n in names)),
            "P2_tips_beat_halo_at_equal_budget": {
                f"@{f:g}": {f"tips_L{L}": worst_rule(tip_by_rule, f"tips_L{L}@{f:g}"),
                            "halo": worst_rule(tip_by_rule, f"halo@{f:g}")}
                for f in BUDGET_FRACS for L in TIP_LENS},
        },
        "proxy_caveat": ("Per F6 (reports/truthset_calibration.json) no local truth set "
                         "demonstrably predicts the recorded public scores, so nothing "
                         "here is a leaderboard prediction. A PASS means 'clears the "
                         "predeclared local gate', nothing more."),
        "rows": rows,
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n")

    print("\n=== tip folds: worst-rule mean DTI ===")
    for name in names:
        print(f"  {name:18s} tip_worst={worst_rule(tip_by_rule, name):.5f} "
              f"tip_mean={tip_all.get(name, {}).get('dti_mean', float('nan')):.5f} "
              f"old_worst={worst_rule(old_by_rule, name):.5f} "
              f"sgmc={sgmc_all.get(name, {}).get('dti_mean', float('nan')):.5f} "
              f"paired={paired.get(name, {}).get('wins', '-')}/9")
    print("\n=== verdicts ===")
    for name, d in verdicts.items():
        print(f"  {name:18s} {d['verdict']}")
    print(f"\nWINNERS: {winners or 'none'}")
    print(f"wrote {OUT.relative_to(ROOT)} in {report['runtime_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
