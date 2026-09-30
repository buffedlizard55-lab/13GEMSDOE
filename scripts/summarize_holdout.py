#!/usr/bin/env python3
"""Turn reports/holdout_v2.json into a verdict.

The only number that matters is LIFT OVER CHANCE at the map's ACTUAL predicted
pixel count -- not at its nominal coverage target, because decimation can cut
the pixel count by up to 9x and comparing a decimated map to a full-size random
map is not a comparison at all.

Chance is computed from the closed form in scripts/chance_baseline.py and is
validated here against the empirical coverage-matched random controls that the
sweep actually ran.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from chance_baseline import dti_chance  # noqa: E402

REP = ROOT / "reports"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default="holdout_v2.json")
    ap.add_argument("--output", default="holdout_verdict.json")
    a = ap.parse_args()
    d = json.loads((REP / a.input).read_text())
    res = d["results"]
    n_valid = d["grid"]["valid_px"]
    hidden_by_fold = {f["name"]: f["n_hidden"] for f in d["folds"]}

    # ---- validate the closed form against the empirical random controls ----
    errs = []
    for r in res:
        if r["family"] != "control_random":
            continue
        pred = dti_chance(r["n_pred_px"], hidden_by_fold[r["fold"]], n_valid)
        errs.append(abs(pred - r["dti"]) / max(r["dti"], 1e-9))
    calib = {"n_controls": len(errs), "median_rel_err": float(np.median(errs)),
             "p90_rel_err": float(np.percentile(errs, 90))}
    print(f"closed-form chance vs {len(errs)} measured random controls: "
          f"median rel. error {calib['median_rel_err']*100:.1f}%, "
          f"p90 {calib['p90_rel_err']*100:.1f}%\n")

    def lift(r, key="dti"):
        g = hidden_by_fold[r["fold"]]
        if key == "dti_concealed":
            g = r.get("n_hidden_concealed")
            if not g:
                return None
        c = dti_chance(r["n_pred_px"], g, n_valid)
        return r[key] / c if c > 0 else None

    rows = defaultdict(lambda: {"lift": [], "lift_c": [], "dti": [],
                                "px": [], "rules": defaultdict(list)})
    for r in res:
        if r["family"] in ("control_random", "STAGE2:control_random"):
            continue
        k = r["tag"]
        L = lift(r)
        if L is None:
            continue
        rows[k]["lift"].append(L)
        rows[k]["dti"].append(r["dti"])
        rows[k]["px"].append(r["n_pred_px"])
        rows[k]["rules"][r["rule"]].append(L)
        Lc = lift(r, "dti_concealed")
        if Lc is not None:
            rows[k]["lift_c"].append(Lc)
        rows[k]["family"] = r["family"].replace("STAGE2:", "")

    table = []
    for tag, v in rows.items():
        per_rule = {k: float(np.mean(x)) for k, x in v["rules"].items()}
        table.append({
            "tag": tag, "family": v["family"],
            "mean_lift": float(np.mean(v["lift"])),
            "worst_rule_lift": float(min(per_rule.values())),
            "n_rules": len(per_rule),
            "mean_lift_concealed": (float(np.mean(v["lift_c"]))
                                    if v["lift_c"] else None),
            "mean_dti": float(np.mean(v["dti"])),
            "median_px": int(np.median(v["px"])),
            "per_rule_lift": {k: round(x, 4) for k, x in per_rule.items()},
        })
    table.sort(key=lambda z: -z["worst_rule_lift"])
    # Prior submissions were BUILT using the full catalogue, including the
    # segments this holdout hides, so their lift is inflated by leakage and
    # they are excluded from the verdict. Their presence at the top is itself
    # the evidence that the leak is real: an honest detector cannot reach
    # weighted recall 0.95 on faults it has never seen.
    honest = [t for t in table if t["family"] not in ("prior_submission", "control")]

    hdr = (f"{'candidate':42s} {'px':>9s} {'DTI':>7s} {'lift':>6s} "
           f"{'worst':>6s} {'conceal':>8s}")
    print("=== ALL CANDIDATES, ranked by WORST-RULE lift over chance ===")
    print(hdr); print("-" * len(hdr))
    for t in table[:26]:
        lc = (f"{t['mean_lift_concealed']:8.2f}"
              if t["mean_lift_concealed"] is not None else "       –")
        print(f"{t['tag'][:42]:42s} {t['median_px']:9,d} {t['mean_dti']:7.4f} "
              f"{t['mean_lift']:6.2f} {t['worst_rule_lift']:6.2f} {lc}")

    print("\n=== BEST CONFIG PER FAMILY (by worst-rule lift) ===")
    best = {}
    for t in table:
        if t["family"] not in best:
            best[t["family"]] = t
    for f, t in sorted(best.items(), key=lambda kv: -kv[1]["worst_rule_lift"]):
        lc = (f"{t['mean_lift_concealed']:.2f}"
              if t["mean_lift_concealed"] is not None else "–")
        cfg = t['tag'].split('|', 1)[1] if '|' in t['tag'] else '-'
        print(f"  {f:22s} {cfg:14s} "
              f"lift={t['mean_lift']:.2f} worst={t['worst_rule_lift']:.2f} "
              f"concealed={lc}  px={t['median_px']:,}")

    # The concealed subset is the honest tie-breaker: catalogue faults are
    # 1.7x over-represented on slopes (irregularity I-11), so a detector that
    # only wins on the full withheld set is winning on the catalogue's own bias.
    n_concealed = sum(1 for r in res if "dti_concealed" in r)
    verdict = {
        "input": a.input,
        "calibration_of_closed_form_chance": calib,
        "best_honest_candidate": honest[0]["tag"] if honest else None,
        "best_worst_rule_lift": (round(honest[0]["worst_rule_lift"], 4)
                                 if honest else None),
        "any_honest_candidate_beats_chance_by_20pct":
            bool(honest and honest[0]["worst_rule_lift"] >= 1.2),
        "concealed_subset_rows": n_concealed,
        "leaked_priors_excluded_from_verdict": [
            {"tag": t["tag"], "lift": round(t["mean_lift"], 2),
             "reason": "built using the full catalogue incl. withheld segments"}
            for t in table if t["family"] == "prior_submission"][:3],
        "table": table,
    }
    (REP / a.output).write_text(json.dumps(verdict, indent=2))

    print("\n=== VERDICT (leaked prior submissions excluded) ===")
    b = honest[0]
    if b["worst_rule_lift"] < 1.05:
        print("  NO candidate is meaningfully better than a random map of the "
              "same size under every withholding rule.")
    elif b["worst_rule_lift"] < 1.2:
        print("  Best candidate is only marginally above chance "
              f"({b['worst_rule_lift']:.2f}x worst-rule).")
    else:
        print(f"  {b['tag']} beats chance by {b['worst_rule_lift']:.2f}x "
              "under EVERY withholding rule.")
    print(f"  wrote {REP/a.output}")


if __name__ == "__main__":
    main()
