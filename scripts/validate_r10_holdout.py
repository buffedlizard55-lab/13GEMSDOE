#!/usr/bin/env python3
"""Predeclared validation of the R10 external-data hypotheses on the holdout.

Candidates (all built from OFFICIAL external products + at most two provided
bands; NONE of them reads the fault catalogue, so no fold can leak):

  R10-3 `dzt`     damage-zone texture  (3DEP slope_std x profile curvature)
  R10-1 `scarp`   1-m LiDAR morphometric scarp composite
  R10-2 `alter`   radiometric alteration-ratio lineaments (U/K, U/Th)
  R10-4 `vent`    vent conjunction: scarp x alteration x conductivity x
                  shallow conductive base (and a `ventdzt` variant that swaps
                  the LiDAR composite for damage-zone texture, giving 100 %
                  footprint coverage instead of 62 %)

Protocol is IDENTICAL to scripts/validate_r9_holdout.py /
validate_ensemble_holdout.py (same fold builder, seeds, 5-px buffer,
FoldScorer, tune/confirm split, spacing-3 grid decimation), so `topo_05_sp3`
here must reproduce the archived per-fold DTI values; that reproduction is
asserted as a protocol regression check before any verdict is read.

PREDECLARED DECISION RULE (copied verbatim from
knowledge/06_r10_hypotheses.md, written before any fold was scored):
  primary metric .......... confirmation worst-rule-mean DTI (6 rules)
  a candidate WINS ........ beats the paired reference `topo_05_sp3` on BOTH
                            tune and confirmation worst-rule-mean DTI and is
                            not worse on >= 4 of the 6 confirmation rule means
  a candidate is FRAGILE .. beats the reference overall but wins < 4 of 6
                            confirmation rule means
  anything else ........... LOSES; the idea does not get a submission slot.

Tie diagnostic: a top-k selection over a SPARSE crest map can select more
pixels than the map has non-zero values, and the surplus is chosen by
`argsort(kind="stable")` -- i.e. by row-major position, which is a spatial
bias, not evidence. Each row therefore records `n_selected_at_zero_score` and
`tie_fraction`. Configs with a large tie fraction are flagged, not trusted.

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
from gems.holdout import build_folds, label_segments, make_fold    # noqa: E402
from gems.rio import load_footprint                                # noqa: E402

RAW = ROOT / "data" / "raw"
DER = ROOT / "data" / "derived"
REPORTS = ROOT / "reports"

N_FOLDS = 3
HIDE_FRAC = 0.25
BUFFER_PX = 5
LINK_PX = 8
SPACING = 3
BASE_COVERAGE = 0.05
HISTORICAL = REPORTS / "holdout_candidate_r8_2026-09-30.json"
OUT_PATH = REPORTS / "holdout_r10_2026-09-30.json"

# map name -> cached npy stem
MAPS = {
    "topo": "BASE_topo_ridge",
    "dzt": "R10_dzt_field",
    "scarp": "R10_scarp_field",
    "alter": "R10_alter_field",
    "vent": "R10_vent",
    "ventdzt": "R10_vent_dzt",
    "dztC": "R10_dzt",
    "scarpC": "R10_scarp",
    "alterC": "R10_alter",
}


class Ranker:
    """Stable score ranking, identical to validate_ensemble_holdout.py."""

    def __init__(self, score: np.ndarray):
        self.score = np.asarray(score, dtype=np.float32)
        self.order = np.argsort(-self.score.ravel(), kind="stable").astype(np.int32)

    def topk(self, allowed: np.ndarray, n: int) -> tuple[np.ndarray, dict]:
        flat_allowed = np.asarray(allowed, dtype=bool).ravel()
        flat_score = self.score.ravel()
        selected = self.order[flat_allowed[self.order]][:n]
        out = np.zeros(flat_allowed.size, dtype=bool)
        out[selected] = True
        sel_scores = flat_score[selected]
        n_zero = int((sel_scores <= 0).sum())
        thr = float(sel_scores[-1]) if selected.size else 0.0
        n_at_thr = int((flat_score[flat_allowed] == thr).sum()) if selected.size else 0
        diag = {"k_requested": int(n), "k_selected": int(selected.size),
                "n_selected_at_zero_score": n_zero,
                "selection_threshold": thr,
                "n_allowed_pixels_at_threshold": n_at_thr,
                "tie_fraction": round(n_at_thr / max(int(selected.size), 1), 4)}
        return out.reshape(allowed.shape), diag


def segment_folds(known: np.ndarray, valid: np.ndarray,
                  n_folds: int = N_FOLDS) -> list:
    seg, n_segments = label_segments(known)
    sizes = np.bincount(seg.ravel(), minlength=n_segments + 1)[1:].astype(np.int64)
    target = HIDE_FRAC * int(known.sum())
    rng = np.random.default_rng(20260930)
    folds = []
    ids = np.arange(1, n_segments + 1, dtype=np.int32)
    for i in range(n_folds):
        order = rng.permutation(n_segments)
        cumulative = np.cumsum(sizes[order])
        k = int(np.searchsorted(cumulative, target, side="left")) + 1
        hidden_ids = ids[order[:k]]
        fold = make_fold(known, valid, hidden_ids, seg,
                         f"segment_random_{i}", "segment_random", BUFFER_PX)
        fold.meta.update({"segmentation": "raw 8-connected raster components",
                          "n_catalogue_components": int(n_segments)})
        folds.append(fold)
    return folds


def build_configs() -> list[dict]:
    """Each config: which map ranks the mass, at what coverage, and what it is
    unioned with. `ref` is the archived reference recipe and must reproduce."""
    return [
        {"name": "topo_05_sp3", "primary": ("topo", 0.05)},
        {"name": "dzt_05_sp3", "primary": ("dzt", 0.05)},
        {"name": "dzt_08_sp3", "primary": ("dzt", 0.08)},
        {"name": "scarp_05_sp3", "primary": ("scarp", 0.05)},
        {"name": "scarp_08_sp3", "primary": ("scarp", 0.08)},
        {"name": "alter_05_sp3", "primary": ("alter", 0.05)},
        {"name": "vent_05_sp3", "primary": ("vent", 0.05)},
        {"name": "vent_08_sp3", "primary": ("vent", 0.08)},
        {"name": "ventdzt_05_sp3", "primary": ("ventdzt", 0.05)},
        {"name": "ventdzt_08_sp3", "primary": ("ventdzt", 0.08)},
        # union partners: the reference plus a small block of new physics.
        # The audited A5 inclusion rule says such a block helps only if its
        # marginal weighted precision exceeds 0.2 x DTI; this measures it.
        {"name": "topo05_plus_vent02_sp3", "primary": ("topo", 0.05),
         "extra": [("vent", 0.02)]},
        {"name": "topo05_plus_alter02_sp3", "primary": ("topo", 0.05),
         "extra": [("alter", 0.02)]},
        {"name": "topo05_plus_scarp02_sp3", "primary": ("topo", 0.05),
         "extra": [("scarp", 0.02)]},
        {"name": "topo05_plus_dzt02_sp3", "primary": ("topo", 0.05),
         "extra": [("dzt", 0.02)]},
        # thinned crest maps at mass <= their own support (avoids zero ties)
        {"name": "scarpC_015_sp3", "primary": ("scarpC", 0.015)},
        {"name": "dztC_02_sp3", "primary": ("dztC", 0.02)},
        {"name": "alterC_015_sp3", "primary": ("alterC", 0.015)},
    ]


def full_domain_stats(score: np.ndarray, known: np.ndarray, valid: np.ndarray,
                      top_frac: float = 0.05) -> dict:
    v = valid.ravel()
    s = np.where(np.isfinite(score.ravel()), score.ravel(), np.nan)
    pos = (known & valid).ravel()
    sv, pv = s[v], pos[v]
    fin = np.isfinite(sv)
    lo = float(sv[fin].min()) if fin.any() else 0.0
    sv = np.where(fin, sv, lo)
    n_pos, n_neg = int(pv.sum()), int((~pv).sum())
    r = rankdata(sv)
    auc = float((r[pv].mean() - (n_pos + 1) / 2.0) / n_neg)
    k = int(top_frac * v.sum())
    idx = np.argpartition(-sv, k)[:k]
    tm = np.zeros(sv.size, dtype=bool)
    tm[idx] = True
    return {"auc_full_catalogue": round(auc, 5),
            "catalogue_recall_in_top5pct": round(float((tm & pv).sum()) / n_pos, 5),
            "nonzero_px": int(((score > 0) & valid).sum()),
            "nonzero_pct_of_footprint": round(
                100.0 * float(((score > 0) & valid).sum()) / float(valid.sum()), 4)}


def main() -> int:
    t0 = time.time()
    verify = verify_against_reference(trials=15)
    if not verify["pass"]:
        raise RuntimeError(f"Fast scorer disagrees with the reference: {verify}")

    missing = [m for m in MAPS.values() if not (DER / f"{m}.npy").exists()]
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
    for key, stem in MAPS.items():
        a = np.load(DER / f"{stem}.npy").astype(np.float32, copy=False)
        scores[key] = a
        map_stats[key] = {"cached_map": f"{stem}.npy", **full_domain_stats(a, known, valid)}
        print(f"[map] {key:8s} <- {stem:18s} AUC={map_stats[key]['auc_full_catalogue']:.4f} "
              f"top5%recall={map_stats[key]['catalogue_recall_in_top5pct']:.4f} "
              f"nz={map_stats[key]['nonzero_pct_of_footprint']:.2f}% of footprint")
    rankers = {k: Ranker(v) for k, v in scores.items()}
    del scores

    configs = build_configs()

    system_folds = build_folds(known, valid, n_folds=N_FOLDS, hide_frac=HIDE_FRAC,
                               seed=20260930, link_px=LINK_PX, buffer_px=BUFFER_PX)
    seg_folds = segment_folds(known, valid, n_folds=N_FOLDS)
    folds = system_folds + seg_folds

    rows: list[dict] = []
    for fold_i, fold in enumerate(folds, start=1):
        print(f"[{fold_i:02d}/{len(folds)}] {fold.name} ({fold.rule}), "
              f"hidden={fold.n_hidden:,}, eval={int(fold.eval_mask.sum()):,}", flush=True)
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
        print(f"     [{time.time()-t0:6.1f}s] done", flush=True)

    # ---- protocol regression check -----------------------------------------
    hist_rows = {}
    if HISTORICAL.exists():
        for r in json.loads(HISTORICAL.read_text())["results"]:
            if r["config"] == "topo_05_sp3":
                hist_rows[r["fold"]] = r["dti"]
    mismatches = []
    for r in rows:
        if r["config"] == "topo_05_sp3" and r["fold"] in hist_rows:
            if abs(r["dti"] - hist_rows[r["fold"]]) > 1e-6:
                mismatches.append([r["fold"], r["dti"], hist_rows[r["fold"]]])
    protocol_check = {"compared_to": HISTORICAL.name, "n_compared": len(hist_rows),
                      "n_mismatch": len(mismatches), "mismatches": mismatches[:10],
                      "pass": bool(hist_rows) and not mismatches}
    print("protocol regression check:",
          "PASS" if protocol_check["pass"] else f"FAIL {mismatches[:3]}")
    if not protocol_check["pass"]:
        raise SystemExit("protocol regression check failed - run is invalid")

    tune_folds = {"random_0", "short_0", "isolated_0", "strike_60_120",
                  "dense_0", "segment_random_0"}
    tune_rows = [r for r in rows if r["fold"] in tune_folds]
    confirm_rows = [r for r in rows if r["fold"] not in tune_folds]

    def summarize(selected: list[dict]) -> dict[str, dict]:
        by: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        for r in selected:
            by[r["config"]][r["rule"]].append(r)
        out = {}
        for cfg, rules in by.items():
            rule_means = {rule: float(np.mean([x["dti"] for x in v]))
                          for rule, v in rules.items()}
            out[cfg] = {
                "n_rows": sum(len(v) for v in rules.values()),
                "dti_mean": float(np.mean([x["dti"] for x in selected
                                           if x["config"] == cfg])),
                "dti_worst_rule_mean": min(rule_means.values()),
                "dti_mean_by_rule": rule_means,
                "precision_w_mean": float(np.mean(
                    [x["precision_w"] for x in selected if x["config"] == cfg])),
                "recall_w_mean": float(np.mean(
                    [x["recall_w"] for x in selected if x["config"] == cfg])),
                "predicted_eval_px_mean": float(np.mean(
                    [x["n_predicted_eval_pixels"] for x in selected
                     if x["config"] == cfg])),
                "max_tie_fraction": max(
                    d["tie_fraction"]
                    for x in selected if x["config"] == cfg
                    for d in x["selection_diagnostics"].values()),
                "max_zero_score_selections": max(
                    d["n_selected_at_zero_score"]
                    for x in selected if x["config"] == cfg
                    for d in x["selection_diagnostics"].values()),
            }
        return out

    tune_summary = summarize(tune_rows)
    confirm_summary = summarize(confirm_rows)

    ref = {(r["fold"], r["rule"]): r["dti"] for r in rows
           if r["config"] == "topo_05_sp3"}
    paired = {}
    for cfg in confirm_summary:
        if cfg == "topo_05_sp3":
            continue
        deltas = [r["dti"] - ref[(r["fold"], r["rule"])]
                  for r in confirm_rows if r["config"] == cfg]
        wins = int(sum(1 for d in deltas if d > 1e-9))
        ties = int(sum(1 for d in deltas if abs(d) <= 1e-9))
        paired[cfg] = {
            "n_pairs": len(deltas),
            "mean_delta_dti": round(float(np.mean(deltas)), 7),
            "relative_delta_pct": round(
                100.0 * float(np.mean(deltas)) / max(abs(np.mean(
                    [ref[(r["fold"], r["rule"])] for r in confirm_rows])), 1e-12), 2),
            "wins": wins, "ties": ties, "losses": len(deltas) - wins - ties,
            "rule_means_delta": {
                rule: round(float(np.mean([
                    r["dti"] - ref[(r["fold"], r["rule"])]
                    for r in confirm_rows if r["config"] == cfg])), 7)
                for rule in confirm_summary["topo_05_sp3"]["dti_mean_by_rule"]},
        }

    ref_conf = confirm_summary["topo_05_sp3"]
    ref_tune = tune_summary["topo_05_sp3"]
    ref_rules = ref_conf["dti_mean_by_rule"]
    verdicts = {}
    for cfg, summ in confirm_summary.items():
        if cfg == "topo_05_sp3":
            continue
        beats = (summ["dti_worst_rule_mean"] > ref_conf["dti_worst_rule_mean"]
                 and tune_summary[cfg]["dti_worst_rule_mean"]
                 > ref_tune["dti_worst_rule_mean"])
        rules_won = sum(1 for rule, v in summ["dti_mean_by_rule"].items()
                        if v >= ref_rules[rule] - 1e-9)
        if not beats:
            verdict = "LOSES"
        elif rules_won >= 4:
            verdict = "WINS"
        else:
            verdict = "FRAGILE"
        verdicts[cfg] = f"{verdict} (confirmation rule-means won: {rules_won}/6)"

    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "LOCAL_PROXY_HOLDOUT_ONLY_NOT_PRIVATE_TEST_PERFORMANCE",
        "purpose": ("Predeclared validation of the four R10 external-data "
                    "hypotheses (LiDAR morphometric scarp, damage-zone texture, "
                    "radiometric alteration ratios, vent conjunction) against the "
                    "paired topo_05_sp3 reference on the identical fold set."),
        "hypothesis_register": "knowledge/06_r10_hypotheses.md",
        "external_provenance": "reports/external_manifest.json",
        "grid": {"valid_pixels": n_valid, "known_fault_pixels": n_known},
        "map_statistics_full_catalogue": map_stats,
        "protocol": {
            "identical_to": "scripts/validate_r9_holdout.py",
            "system_folds": {"rules": ["random", "short", "isolated", "oriented",
                                       "dense"], "n_folds_per_rule": N_FOLDS,
                             "hide_fraction_target": HIDE_FRAC},
            "segment_folds": {"n_folds": N_FOLDS, "hide_fraction_target": HIDE_FRAC},
            "buffer_px": BUFFER_PX, "buffer_m": BUFFER_PX * 100,
            "spacing_px": SPACING, "base_coverage": BASE_COVERAGE,
            "catalogue_input_used_by_candidates": False,
            "scorer_verification": verify,
            "decision_rule": "see module docstring; predeclared",
        },
        "protocol_regression_check": protocol_check,
        "configurations": configs,
        "tune_summary": tune_summary,
        "confirmation_summary": confirm_summary,
        "paired_vs_reference": paired,
        "verdicts_predeclared": verdicts,
        "results": rows,
        "runtime_s": round(time.time() - t0, 1),
    }
    OUT_PATH.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print(f"\nwrote {OUT_PATH} ({len(rows)} rows, {time.time()-t0:.0f}s)")
    for cfg, summ in sorted(confirm_summary.items(),
                            key=lambda kv: -kv[1]["dti_worst_rule_mean"]):
        v = verdicts.get(cfg, "REFERENCE")
        p = paired.get(cfg, {})
        print(f"{cfg:26s} confirm worst={summ['dti_worst_rule_mean']:.5f} "
              f"mean={summ['dti_mean']:.5f} d={p.get('mean_delta_dti', 0.0):+.5f} "
              f"prec={summ['precision_w_mean']:.4f} rec={summ['recall_w_mean']:.4f} "
              f"px={summ['predicted_eval_px_mean']:.0f} tie={summ['max_tie_fraction']:.2f} "
              f"{v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
