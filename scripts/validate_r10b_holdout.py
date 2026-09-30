#!/usr/bin/env python3
"""R10b: predeclared refinement round for the R10 external-data hypotheses.

R10 (reports/holdout_r10_2026-09-30.json) measured ALL 16 candidates below the
paired reference `topo_05_sp3` (confirmation worst-rule-mean DTI 0.08687). The
loss mechanism is documented: every 2 %-coverage union added pixels whose
marginal weighted precision (0.0094-0.0141 on tune folds) sits BELOW the audited
inclusion threshold 0.2 x DTI (0.0169 tune / 0.0195 confirmation), so the F2
optimum stops before them.

Two mechanisms were left untested and are predeclared here (see
knowledge/06_r10_hypotheses.md, section "R10b", written before any fold was
scored):

  A. low-coverage union - the audited rule is a statement about the MARGIN, so
     the very top of an external map (0.5 %, 1 %) may clear the threshold even
     though its 0-2 % band does not.
  B. fixed-budget rank fusion - keep the reference pixel mass (top 5 % of the
     fused ranking, spacing-3 decimation) and let the external evidence REPLACE
     the weakest reference pixels instead of adding to them:
         fused = (1 - w) * pctl(topo) + w * pctl(external)
     with `pctl` the tie-corrected (average-rank) percentile over the valid
     footprint only. Small w re-orders the topographic crest; large w admits
     external-only peaks at fixed mass, bounding the precision loss.

Protocol is IDENTICAL to scripts/validate_r10_holdout.py (same fold builder,
seeds, 5-px buffer, FoldScorer, tune/confirm split, spacing-3 decimation), and
the reference row must reproduce the archived per-fold DTI values; that
reproduction is asserted as a protocol regression check before any verdict.

PREDECLARED SELECTION AND DECISION RULE
  selection ....... the single configuration with the highest TUNE
                    worst-rule-mean DTI (tie-break: tune mean DTI) is carried
                    forward. Confirmation numbers for non-selected
                    configurations are stored for audit but are NOT inspected
                    before the selection is made.
  a candidate WINS  beats `topo_05_sp3` on BOTH tune and confirmation
                    worst-rule-mean DTI and is not worse on >= 4 of the 6
                    confirmation rule means.
  FRAGILE ......... beats overall but wins < 4 of 6 confirmation rule means.
  anything else ... LOSES.
  No weekly submission slot is spent unless a candidate WINS.

Results are local catalogue hide-and-recover proxy measurements. They are NOT
public/private leaderboard performance estimates.
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gems import detectors as D                                   # noqa: E402
from gems.fastscore import FoldScorer, verify_against_reference    # noqa: E402
from gems.holdout import build_folds                              # noqa: E402
from gems.rio import load_footprint                               # noqa: E402
import validate_r10_holdout as R10                                # noqa: E402

RAW = ROOT / "data" / "raw"
DER = ROOT / "data" / "derived"
REPORTS = ROOT / "reports"

N_FOLDS = R10.N_FOLDS
HIDE_FRAC = R10.HIDE_FRAC
BUFFER_PX = R10.BUFFER_PX
LINK_PX = R10.LINK_PX
SPACING = R10.SPACING
BASE_COVERAGE = R10.BASE_COVERAGE
REFERENCE = "topo_05_sp3"
REF_CONFIRM_WORST = 0.08687          # archived paired reference value
HISTORICAL = R10.HISTORICAL          # holdout_candidate_r8_2026-09-30.json
OUT_PATH = REPORTS / "holdout_r10b_2026-09-30.json"

TUNE_FOLDS = {"random_0", "short_0", "isolated_0", "strike_60_120",
              "dense_0", "segment_random_0"}

# fusion weights, predeclared
FUSIONS = [("vent", 0.15), ("vent", 0.30), ("vent", 0.50), ("alter", 0.30)]
# low-coverage union blocks, predeclared
UNION_EXTRAS = [("vent", 0.005), ("vent", 0.01), ("alter", 0.005), ("alter", 0.01)]


def percentile_field(score: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Tie-corrected (average-rank) percentile over the valid footprint only.

    Invalid pixels get -1.0 so they can never enter a top-k selection. Using
    average ranks matters: `BASE_topo_ridge` is exactly zero over ~94 % of the
    footprint, and those pixels must share one percentile instead of being
    ordered by row-major position.
    """
    flat = np.asarray(score, dtype=np.float32).ravel()
    v = np.asarray(valid, dtype=bool).ravel()
    out = np.full(flat.size, -1.0, dtype=np.float32)
    idx = np.flatnonzero(v)
    ranks = rankdata(flat[idx], method="average")
    out[idx] = (ranks / idx.size).astype(np.float32)
    del ranks
    return out.reshape(np.shape(score))


def fuse(pctl_a: np.ndarray, pctl_b: np.ndarray, w: float,
         valid: np.ndarray) -> np.ndarray:
    """(1 - w) * pctl_a + w * pctl_b, forced to -1 outside the footprint."""
    out = (1.0 - float(w)) * pctl_a + float(w) * pctl_b
    out[~np.asarray(valid, dtype=bool)] = -1.0
    return out.astype(np.float32)


def build_configs() -> list[dict]:
    cfgs: list[dict] = [{"name": REFERENCE, "primary": ("topo", BASE_COVERAGE)}]
    for name, cov in UNION_EXTRAS:
        cfgs.append({
            "name": f"topo05_plus_{name}{int(round(cov * 1000)):03d}_sp3",
            "primary": ("topo", BASE_COVERAGE), "extra": [(name, cov)]})
    for name, w in FUSIONS:
        cfgs.append({
            "name": f"fuse_{name}_w{int(round(w * 100)):03d}_sp3",
            "primary": (f"fuse_{name}_w{int(round(w * 100)):03d}", BASE_COVERAGE)})
    return cfgs


def summarize(rows: list[dict]) -> dict[str, dict]:
    by: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by[r["config"]][r["rule"]].append(r)
    out = {}
    for cfg, rules in by.items():
        all_rows = [x for v in rules.values() for x in v]
        rule_means = {rule: float(np.mean([x["dti"] for x in v]))
                      for rule, v in rules.items()}
        out[cfg] = {
            "n_rows": len(all_rows),
            "dti_mean": float(np.mean([x["dti"] for x in all_rows])),
            "dti_worst_rule_mean": min(rule_means.values()),
            "dti_mean_by_rule": rule_means,
            "precision_w_mean": float(np.mean([x["precision_w"] for x in all_rows])),
            "recall_w_mean": float(np.mean([x["recall_w"] for x in all_rows])),
            "predicted_eval_px_mean": float(np.mean(
                [x["n_predicted_eval_pixels"] for x in all_rows])),
            "max_tie_fraction": max(
                d["tie_fraction"] for x in all_rows
                for d in x["selection_diagnostics"].values()),
            "max_zero_score_selections": max(
                d["n_selected_at_zero_score"] for x in all_rows
                for d in x["selection_diagnostics"].values()),
        }
    return out


def main() -> int:
    t0 = time.time()
    verify = verify_against_reference(trials=15)
    if not verify["pass"]:
        raise RuntimeError(f"Fast scorer disagrees with the reference: {verify}")

    needed = ["BASE_topo_ridge", "R10_vent", "R10_alter_field"]
    missing = [m for m in needed if not (DER / f"{m}.npy").exists()]
    if missing:
        raise SystemExit(
            f"missing cached detector maps: {missing}\n"
            "run: .venv/bin/python scripts/build_detectors.py && "
            ".venv/bin/python scripts/build_external_detectors.py")

    valid, known = load_footprint(RAW / "existing_faults.tif")
    n_valid = int(valid.sum())
    n_known = int(known.sum())

    scores: dict[str, np.ndarray] = {}
    map_stats: dict[str, dict] = {}
    for key, stem in (("topo", "BASE_topo_ridge"), ("vent", "R10_vent"),
                      ("alter", "R10_alter_field")):
        a = np.load(DER / f"{stem}.npy").astype(np.float32, copy=False)
        scores[key] = a
        map_stats[key] = {"cached_map": f"{stem}.npy",
                          **R10.full_domain_stats(a, known, valid)}
        print(f"[map] {key:6s} <- {stem:18s} "
              f"AUC={map_stats[key]['auc_full_catalogue']:.4f} "
              f"top5%recall={map_stats[key]['catalogue_recall_in_top5pct']:.4f} "
              f"nz={map_stats[key]['nonzero_pct_of_footprint']:.2f}%", flush=True)

    pctl = {k: percentile_field(scores[k], valid) for k in ("topo", "vent", "alter")}
    for name, w in FUSIONS:
        key = f"fuse_{name}_w{int(round(w * 100)):03d}"
        fused = fuse(pctl["topo"], pctl[name], w, valid)
        scores[key] = fused
        map_stats[key] = {"cached_map": f"(1-{w})*pctl(BASE_topo_ridge) + "
                                        f"{w}*pctl({map_stats[name]['cached_map']})",
                          "fusion_weight": w,
                          **R10.full_domain_stats(fused, known, valid)}
        print(f"[fuse] {key:20s} AUC={map_stats[key]['auc_full_catalogue']:.4f} "
              f"top5%recall={map_stats[key]['catalogue_recall_in_top5pct']:.4f} "
              f"nz={map_stats[key]['nonzero_pct_of_footprint']:.2f}%", flush=True)
    del pctl

    rankers = {k: R10.Ranker(v) for k, v in scores.items()}
    del scores

    configs = build_configs()

    system_folds = build_folds(known, valid, n_folds=N_FOLDS, hide_frac=HIDE_FRAC,
                               seed=20260930, link_px=LINK_PX, buffer_px=BUFFER_PX)
    seg_folds = R10.segment_folds(known, valid, n_folds=N_FOLDS)
    folds = system_folds + seg_folds

    rows: list[dict] = []
    for fold_i, fold in enumerate(folds, start=1):
        print(f"[{fold_i:02d}/{len(folds)}] {fold.name} ({fold.rule}), "
              f"hidden={fold.n_hidden:,}, eval={int(fold.eval_mask.sum()):,}",
              flush=True)
        eval_mask = fold.eval_mask
        cache: dict[tuple[str, float], tuple[np.ndarray, dict]] = {}

        def component(name: str, coverage: float) -> tuple[np.ndarray, dict]:
            key = (name, float(coverage))
            if key not in cache:
                n = int(coverage * n_valid)
                m, diag = rankers[name].topk(eval_mask, n)
                if SPACING > 1:
                    m = D.decimate_grid(m, rankers[name].score, SPACING)
                cache[key] = (m, diag)
            return cache[key]

        fold_scorer = FoldScorer.build(fold.hidden, eval_mask)
        for cfg in configs:
            pname, pcov = cfg["primary"]
            cand, diag = component(pname, pcov)
            cand = cand.copy()
            parts = {pname: int(cand.sum())}
            diags = {f"{pname}@{pcov}": diag}
            for ename, ecov in cfg.get("extra", []):
                em, ediag = component(ename, ecov)
                before = int(cand.sum())
                cand |= em
                parts[ename] = int(cand.sum()) - before
                diags[f"{ename}@{ecov}"] = ediag
            cand &= eval_mask
            n_eff = int(cand.sum())
            result = fold_scorer.score(cand.astype(np.float32))
            rows.append({
                "config": cfg["name"], "fold": fold.name, "rule": fold.rule,
                "ranking_map": pname, "coverage": pcov,
                "union_extras": [f"{e}@{c}" for e, c in cfg.get("extra", [])],
                "n_truth": fold_scorer.n_truth,
                "n_eval_pixels": int(eval_mask.sum()),
                "n_predicted_eval_pixels": n_eff,
                "coverage_of_eval_pct": round(100.0 * n_eff / eval_mask.sum(), 5),
                "dti": round(float(result["dti"]), 7),
                "precision_w": round(float(result["precision_w"]), 7),
                "recall_w": round(float(result["recall_w"]), 7),
                "tp_w": round(float(result["tp_w"]), 4),
                "fp_w": round(float(result["fp_w"]), 4),
                "components_px": parts,
                "selection_diagnostics": diags,
            })
            del cand
        del fold_scorer, cache
        print(f"     [{time.time() - t0:6.1f}s] done", flush=True)

    # ---- protocol regression check (must pass before any verdict) ----------
    hist_rows = {}
    if HISTORICAL.exists():
        for r in json.loads(HISTORICAL.read_text())["results"]:
            if r["config"] == REFERENCE:
                hist_rows[r["fold"]] = r["dti"]
    mismatches = []
    for r in rows:
        if r["config"] == REFERENCE and r["fold"] in hist_rows:
            if abs(r["dti"] - hist_rows[r["fold"]]) > 1e-6:
                mismatches.append([r["fold"], r["dti"], hist_rows[r["fold"]]])
    protocol_check = {"compared_to": HISTORICAL.name, "n_compared": len(hist_rows),
                      "n_mismatch": len(mismatches), "mismatches": mismatches[:10],
                      "reference_confirm_worst_archived": REF_CONFIRM_WORST,
                      "pass": bool(hist_rows) and not mismatches}
    print("protocol regression check:",
          "PASS" if protocol_check["pass"] else f"FAIL {mismatches[:3]}")
    if not protocol_check["pass"]:
        raise SystemExit("protocol regression check failed - run is invalid")

    tune_rows = [r for r in rows if r["fold"] in TUNE_FOLDS]
    confirm_rows = [r for r in rows if r["fold"] not in TUNE_FOLDS]
    tune_summary = summarize(tune_rows)
    confirm_summary = summarize(confirm_rows)

    # ---- STEP 1: selection on TUNE folds only (predeclared) ----------------
    print("\n=== TUNE folds (6): selection happens here, confirmation not yet read ===")
    ref_t = tune_summary[REFERENCE]
    print(f"{REFERENCE:28s} tune worst={ref_t['dti_worst_rule_mean']:.5f} "
          f"mean={ref_t['dti_mean']:.5f} P={ref_t['precision_w_mean']:.4f} "
          f"R={ref_t['recall_w_mean']:.4f} px={ref_t['predicted_eval_px_mean']:.0f} "
          f"REFERENCE")
    tune_ranked = sorted(
        ((c, s) for c, s in tune_summary.items() if c != REFERENCE),
        key=lambda kv: (-kv[1]["dti_worst_rule_mean"], -kv[1]["dti_mean"]))
    for cfg, s in tune_ranked:
        # marginal precision of the change vs the reference, on tune folds
        dpx = s["predicted_eval_px_mean"] - ref_t["predicted_eval_px_mean"]
        dhits = (s["precision_w_mean"] * s["predicted_eval_px_mean"]
                 - ref_t["precision_w_mean"] * ref_t["predicted_eval_px_mean"])
        mp = (dhits / dpx) if abs(dpx) > 1 else float("nan")
        print(f"{cfg:28s} tune worst={s['dti_worst_rule_mean']:.5f} "
              f"mean={s['dti_mean']:.5f} d={s['dti_mean'] - ref_t['dti_mean']:+.5f} "
              f"P={s['precision_w_mean']:.4f} R={s['recall_w_mean']:.4f} "
              f"px={s['predicted_eval_px_mean']:.0f} dpx={dpx:+.0f} margP={mp:.4f} "
              f"tie={s['max_tie_fraction']:.2f}")
    selected, sel_tune = tune_ranked[0]
    print(f"\nSELECTED ON TUNE: {selected} "
          f"(tune worst-rule mean {sel_tune['dti_worst_rule_mean']:.5f})")

    # ---- STEP 2: confirmation read for the reference + the selected only ---
    ref_c = confirm_summary[REFERENCE]
    sel_c = confirm_summary[selected]
    ref_by_fold = {(r["fold"], r["rule"]): r["dti"] for r in rows
                   if r["config"] == REFERENCE}
    deltas = [r["dti"] - ref_by_fold[(r["fold"], r["rule"])]
              for r in confirm_rows if r["config"] == selected]
    wins = int(sum(1 for d in deltas if d > 1e-9))
    ties = int(sum(1 for d in deltas if abs(d) <= 1e-9))
    paired = {
        "n_pairs": len(deltas),
        "mean_delta_dti": round(float(np.mean(deltas)), 7),
        "relative_delta_pct": round(100.0 * float(np.mean(deltas))
                                    / max(abs(ref_c["dti_mean"]), 1e-12), 2),
        "wins": wins, "ties": ties, "losses": len(deltas) - wins - ties,
        "rule_means_delta": {
            rule: round(float(np.mean([
                r["dti"] - ref_by_fold[(r["fold"], r["rule"])]
                for r in confirm_rows if r["config"] == selected])), 7)
            for rule in ref_c["dti_mean_by_rule"]},
    }
    rules_won = sum(1 for rule, v in sel_c["dti_mean_by_rule"].items()
                    if v >= ref_c["dti_mean_by_rule"][rule] - 1e-9)
    beats = (sel_c["dti_worst_rule_mean"] > ref_c["dti_worst_rule_mean"]
             and sel_tune["dti_worst_rule_mean"] > ref_t["dti_worst_rule_mean"])
    verdict = "WINS" if (beats and rules_won >= 4) else ("FRAGILE" if beats else "LOSES")

    print("\n=== CONFIRMATION folds (12): reference + selected only ===")
    print(f"{REFERENCE:28s} confirm worst={ref_c['dti_worst_rule_mean']:.5f} "
          f"mean={ref_c['dti_mean']:.5f} P={ref_c['precision_w_mean']:.4f} "
          f"R={ref_c['recall_w_mean']:.4f} px={ref_c['predicted_eval_px_mean']:.0f} "
          f"REFERENCE")
    print(f"{selected:28s} confirm worst={sel_c['dti_worst_rule_mean']:.5f} "
          f"mean={sel_c['dti_mean']:.5f} d={paired['mean_delta_dti']:+.5f} "
          f"P={sel_c['precision_w_mean']:.4f} R={sel_c['recall_w_mean']:.4f} "
          f"px={sel_c['predicted_eval_px_mean']:.0f} "
          f"tie={sel_c['max_tie_fraction']:.2f} "
          f"{verdict} (confirmation rule-means won: {rules_won}/6, "
          f"paired folds won {wins}/{paired['n_pairs']})")

    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "LOCAL_PROXY_HOLDOUT_ONLY_NOT_PRIVATE_TEST_PERFORMANCE",
        "purpose": ("R10b refinement round: low-coverage unions and fixed-budget "
                    "rank fusion of the two best R10 external blocks (vent "
                    "conjunction, alteration-ratio lineaments) against the paired "
                    "reference topo_05_sp3, on the identical fold set."),
        "hypothesis_register": "knowledge/06_r10_hypotheses.md#r10b",
        "predeclared_before_run": True,
        "predecessor_run": "holdout_r10_2026-09-30.json",
        "external_provenance": "reports/external_manifest.json",
        "grid": {"valid_pixels": n_valid, "known_fault_pixels": n_known},
        "map_statistics_full_catalogue": map_stats,
        "protocol": {
            "identical_to": "scripts/validate_r10_holdout.py",
            "system_folds": {"rules": ["random", "short", "isolated", "oriented",
                                       "dense"], "n_folds_per_rule": N_FOLDS,
                             "hide_fraction_target": HIDE_FRAC},
            "segment_folds": {"n_folds": N_FOLDS, "hide_fraction_target": HIDE_FRAC},
            "buffer_px": BUFFER_PX, "buffer_m": BUFFER_PX * 100,
            "spacing_px": SPACING, "base_coverage": BASE_COVERAGE,
            "catalogue_input_used_by_candidates": False,
            "scorer_verification": verify,
            "selection_rule": ("highest TUNE worst-rule-mean DTI (tie-break tune "
                               "mean DTI); confirmation for non-selected configs "
                               "stored for audit but not inspected before selection"),
            "decision_rule": "see module docstring; predeclared",
        },
        "protocol_regression_check": protocol_check,
        "configurations": configs,
        "tune_summary": tune_summary,
        "tune_ranking_for_selection": [
            {"config": c, "tune_worst_rule_mean": s["dti_worst_rule_mean"],
             "tune_mean": s["dti_mean"]} for c, s in tune_ranked],
        "selected_on_tune": selected,
        "confirmation_summary": confirm_summary,
        "confirmation_read_for": [REFERENCE, selected],
        "paired_vs_reference_selected": paired,
        "verdict_predeclared": {
            selected: f"{verdict} (confirmation rule-means won: {rules_won}/6)"},
        "results": rows,
        "runtime_s": round(time.time() - t0, 1),
    }
    OUT_PATH.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print(f"\nwrote {OUT_PATH} ({len(rows)} rows, {time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
