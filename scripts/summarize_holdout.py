#!/usr/bin/env python3
"""Summarize local hide-and-recover reports by direct DTI.

The primary ranking is direct DTI on the reported folds (worst-rule mean, then
overall mean). Public/private chance estimates are not available from these
experiments. An optional closed-form chance calculation is used only as an
in-sample sanity check against random controls in the same local report; it is
not a candidate-ranking metric, submission gate, or hidden-test baseline.
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
    stage2_metric = d.get("stage2_shortlist_metric")
    allow_stage2_confirmation = stage2_metric == "worst_rule_mean_dti"
    n_valid = int(d["grid"]["valid_px"])
    hidden_by_fold = {f["name"]: int(f["n_hidden"]) for f in d["folds"]}
    eval_by_fold = {
        f["name"]: int(f["n_eval_px"] if "n_eval_px" in f
                        else n_valid - f["n_visible"])
        for f in d["folds"]
    }
    if any(n <= 0 for n in eval_by_fold.values()):
        raise ValueError("Each fold must have a positive evaluation-domain size")

    # This is a same-run diagnostic only: the approximation does not encode the
    # spatial arrangement of each fold's mask, so never rank candidates by it.
    errs = []
    for r in res:
        if r["family"] != "control_random":
            continue
        pred = dti_chance(r["n_pred_px"], hidden_by_fold[r["fold"]],
                          eval_by_fold[r["fold"]])
        errs.append(abs(pred - r["dti"]) / max(float(r["dti"]), 1e-9))
    calib = {
        "n_random_controls": len(errs),
        "median_relative_error": float(np.median(errs)) if errs else None,
        "p90_relative_error": float(np.percentile(errs, 90)) if errs else None,
        "scope": (
            "Same-run local sanity check only. The closed-form approximation uses "
            "each fold's eligible pixel count and known hidden-truth size, but does "
            "not model the exact spatial arrangement of the eval mask. It is not a "
            "candidate-ranking metric or a public/private baseline."
        ),
    }
    if errs:
        print(f"approximate local chance vs {len(errs)} same-run random controls: "
              f"median relative error {calib['median_relative_error']*100:.1f}%, "
              f"p90 {calib['p90_relative_error']*100:.1f}%\n")
    else:
        print("No random-control rows available for local chance sanity check.\n")

    grouped = defaultdict(list)
    for r in res:
        if r["family"] in ("control_random", "STAGE2:control_random"):
            continue
        grouped[r["tag"]].append(r)

    has_stage2_rows = any(
        r.get("stage") == "stage2" or str(r["family"]).startswith("STAGE2:")
        for rows_for_tag in grouped.values() for r in rows_for_tag
    )
    table = []
    for tag, candidates in grouped.items():
        stage2_rows = [r for r in candidates
                       if r.get("stage") == "stage2"
                       or str(r["family"]).startswith("STAGE2:")]
        # Historical reports may have selected stage-2 candidates using a
        # chance/lift statistic. Do not call those DTI-confirmed unless the input
        # records that its shortlist itself used direct worst-rule DTI.
        confirmed = stage2_rows if allow_stage2_confirmation else []
        stage1_rows = [r for r in candidates if r not in stage2_rows]
        selected = confirmed if confirmed else (stage1_rows or candidates)
        per_rule: dict[str, list[float]] = defaultdict(list)
        for r in selected:
            per_rule[r["rule"]].append(float(r["dti"]))
        per_rule_dti = {k: float(np.mean(x)) for k, x in per_rule.items()}
        families = {str(r["family"]).replace("STAGE2:", "") for r in selected}
        rows_px = [int(r["n_pred_px"]) for r in selected]
        dti_values = [float(r["dti"]) for r in selected]
        concealed = [float(r["dti_concealed"]) for r in selected
                     if r.get("dti_concealed") is not None]
        table.append({
            "tag": tag,
            "family": sorted(families)[0] if families else "unknown",
            "stage": "confirmation" if confirmed else "screening_only",
            "n_folds": len(selected),
            "mean_dti": float(np.mean(dti_values)),
            "worst_rule_mean_dti": float(min(per_rule_dti.values())),
            "n_rules": len(per_rule_dti),
            "mean_dti_concealed": float(np.mean(concealed)) if concealed else None,
            "median_predicted_px": int(np.median(rows_px)),
            "per_rule_dti": {k: round(x, 6) for k, x in per_rule_dti.items()},
        })
    table.sort(key=lambda z: (-z["worst_rule_mean_dti"], -z["mean_dti"]))

    # Prior submission maps are excluded because their construction may use the
    # very geometry being withheld. This is a local leak-control, not a test claim.
    nonleaked = [t for t in table
                 if t["family"] not in ("prior_submission", "control")]
    confirmed_nonleaked = [t for t in nonleaked if t["stage"] == "confirmation"]
    screen_nonleaked = [t for t in nonleaked if t["stage"] == "screening_only"]
    ranked_nonleaked = confirmed_nonleaked or screen_nonleaked

    hdr = (f"{'candidate':42s} {'px':>9s} {'mean DTI':>9s} "
           f"{'worst DTI':>9s}")
    print("=== LOCAL CANDIDATES, ranked by WORST-RULE DTI ===")
    print(hdr)
    print("-" * len(hdr))
    for t in table[:26]:
        print(f"{t['tag'][:42]:42s} {t['median_predicted_px']:9,d} "
              f"{t['mean_dti']:9.4f} {t['worst_rule_mean_dti']:9.4f}")

    print("\n=== BEST CONFIG PER FAMILY (by worst-rule DTI) ===")
    best = {}
    for t in table:
        if t["family"] not in best:
            best[t["family"]] = t
    for family, t in sorted(best.items(),
                            key=lambda kv: -kv[1]["worst_rule_mean_dti"]):
        cfg = t["tag"].split("|", 1)[1] if "|" in t["tag"] else "-"
        print(f"  {family:22s} {cfg:14s} mean={t['mean_dti']:.4f} "
              f"worst-rule={t['worst_rule_mean_dti']:.4f} "
              f"px={t['median_predicted_px']:,}")

    n_concealed = sum(1 for r in res if "dti_concealed" in r)
    verdict = {
        "input": a.input,
        "scope": "LOCAL_PROXY_HOLDOUT_ONLY_NOT_PRIVATE_TEST_PERFORMANCE",
        "primary_ranking_metric": "worst_rule_mean_dti_then_mean_dti",
        "local_random_control_chance_sanity_check_only": calib,
        "evaluation_domain": (
            "Use each fold's recorded n_eval_px when present; otherwise valid_px "
            "minus n_visible. Predictions are restricted by that fold's eval_mask."
        ),
        "best_confirmed_nonleaked_candidate_by_worst_rule_dti": (
            confirmed_nonleaked[0]["tag"] if confirmed_nonleaked else None),
        "best_confirmed_nonleaked_worst_rule_mean_dti": (
            round(confirmed_nonleaked[0]["worst_rule_mean_dti"], 6)
            if confirmed_nonleaked else None),
        "best_screened_nonleaked_candidate_by_worst_rule_dti": (
            screen_nonleaked[0]["tag"] if screen_nonleaked else None),
        "best_screened_nonleaked_worst_rule_mean_dti": (
            round(screen_nonleaked[0]["worst_rule_mean_dti"], 6)
            if screen_nonleaked else None),
        "stage2_shortlist_metric_in_input": stage2_metric,
        "legacy_stage2_rows_ignored": bool(has_stage2_rows and not allow_stage2_confirmation),
        "selection_note": (
            "Stage-two rows are treated as confirmation only when the input explicitly "
            "records worst-rule mean DTI as its shortlist metric. Legacy stage-two rows "
            "selected by chance/lift are ignored in favor of the stage-one screen. "
            "Screening-only rows do not establish a holdout-best candidate."),
        "concealed_subset_rows": n_concealed,
        "prior_submission_maps_excluded_due_full_catalogue_construction": [
            t["tag"] for t in table if t["family"] == "prior_submission"],
        "table": table,
    }
    out = REP / a.output
    out.write_text(json.dumps(verdict, indent=2) + "\n")

    print("\n=== LOCAL PROXY SUMMARY (full-catalogue priors excluded) ===")
    if confirmed_nonleaked:
        b = confirmed_nonleaked[0]
        print(f"  Best confirmed configuration by worst-rule DTI: {b['tag']} "
              f"({b['worst_rule_mean_dti']:.4f})")
        print("  Local known-catalogue recovery only; not a private-test estimate.")
    elif screen_nonleaked:
        b = screen_nonleaked[0]
        print("  No confirmation rows; best available screen is "
              f"{b['tag']} ({b['worst_rule_mean_dti']:.4f}).")
        print("  Screening-only result; it does not establish the holdout-best candidate.")
    else:
        print("  No non-leaked candidate rows available.")
    print(f"  wrote {out}")


if __name__ == "__main__":
    main()
