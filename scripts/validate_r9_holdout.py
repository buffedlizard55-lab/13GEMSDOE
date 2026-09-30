#!/usr/bin/env python3
"""Predeclared validation of the three R9 hypotheses on the local holdout.

H9  strike_gap_close            - close sub-kernel dash gaps along a predicted
                                  line's own strike (no catalogue input).
H10 eq_lineaments               - epicentral-alignment lineaments from the two
                                  supplied seismicity bands (no catalogue).
H11 parallel_offset_correction  - independent-physics edges running parallel
                                  to, but offset from, each fold's VISIBLE
                                  catalogue traces (per-fold rebuild).

Protocol is identical to scripts/validate_ensemble_holdout.py (same fold
builder, seeds, buffer, scorer and tune/confirm split), so `topo_05_sp3`
here must reproduce that report's per-fold numbers -- that reproduction is
asserted as a protocol regression check.

PREDECLARED DECISION RULE (written before any fold was scored):
  primary metric .......... confirmation worst-rule-mean DTI (6 rules)
  a candidate WINS ........ beats the paired reference `topo_05_sp3` on BOTH
                            tune and confirmation worst-rule-mean DTI and is
                            not worse on >= 4 of the 6 confirmation rule means
  a candidate is FRAGILE .. beats the reference overall but wins < 4 of 6
                            confirmation rule means
  anything else ........... LOSES; the idea does not get a submission slot.

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
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gems import detectors as D  # noqa: E402
from gems.fastscore import FoldScorer, verify_against_reference  # noqa: E402
from gems.holdout import build_folds, label_segments, make_fold  # noqa: E402
from gems.rio import load_footprint, read_band  # noqa: E402

RAW = ROOT / "data" / "raw"
DER = ROOT / "data" / "derived"
REPORTS = ROOT / "reports"
N_FOLDS = 3
HIDE_FRAC = 0.25
BUFFER_PX = 5
LINK_PX = 8
SPACING = 3
BASE_COVERAGE = 0.05
EQ_COVERAGE = 0.015
HISTORICAL = REPORTS / "holdout_candidate_r8_2026-09-30.json"


class Ranker:
    """Stable score ranking, matching validate_ensemble_holdout.py."""

    def __init__(self, score: np.ndarray):
        self.score = np.asarray(score, dtype=np.float32)
        self.order = np.argsort(-self.score.ravel(), kind="stable").astype(np.int32)

    def topk(self, allowed: np.ndarray, n: int) -> np.ndarray:
        flat_allowed = np.asarray(allowed, dtype=bool).ravel()
        selected = self.order[flat_allowed[self.order]][:n]
        out = np.zeros(flat_allowed.size, dtype=bool)
        out[selected] = True
        return out.reshape(allowed.shape)


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
    return [
        {"name": "topo_05_sp3", "kind": "ref"},
        {"name": "topo05_gapL_sp3", "kind": "gap", "min_side": 1},
        {"name": "topo05_gapS_sp3", "kind": "gap", "min_side": 2},
        {"name": "topo08_gapL_sp3", "kind": "gap", "coverage": 0.08, "min_side": 1},
        {"name": "topo05_eq15_sp3", "kind": "eq", "cov": EQ_COVERAGE},
        {"name": "topo08_gapL_eq15_sp3", "kind": "gap_eq", "coverage": 0.08,
         "cov": EQ_COVERAGE, "min_side": 1},
        {"name": "topo05_corr_sp3", "kind": "corr"},
        {"name": "topo08_all_sp3", "kind": "gap_eq_corr", "coverage": 0.08,
         "cov": EQ_COVERAGE, "min_side": 1},
    ]


def main() -> None:
    t0 = time.time()
    verify = verify_against_reference(trials=15)
    if not verify["pass"]:
        raise RuntimeError(f"Fast scorer disagrees with the reference: {verify}")

    valid, known = load_footprint(RAW / "existing_faults.tif")
    n_valid = int(valid.sum())
    n_known = int(known.sum())

    # fold-independent detector maps (input-derived, no catalogue content)
    topo = np.load(DER / "BASE_topo_ridge.npy").astype(np.float32, copy=False)
    topo_ranker = Ranker(topo)
    crossgrad = np.load(DER / "R7_crossgrad.npy").astype(np.float32, copy=False)

    # H10 map: compute once, cache like the other input-derived detectors
    eq_path = DER / "R9_eq_align.npy"
    if eq_path.exists():
        eq = np.load(eq_path).astype(np.float32, copy=False)
        print("loaded cached R9_eq_align.npy")
    else:
        print("computing R9_eq_align (H10 epicentral alignment)...")
        ieq = read_band(RAW / "gems-geodawn-numerical-features.tif",
                        band=BANDS["ieq_n100a15"])
        deq = read_band(RAW / "gems-geodawn-numerical-features.tif",
                        band=BANDS["deq_n100a15"])
        eq = D.eq_lineaments(ieq, deq)
        eq = np.where(valid, np.nan_to_num(eq, nan=0.0), 0.0).astype(np.float32)
        np.save(eq_path, eq)
        del ieq, deq
    eq_ranker = Ranker(eq)

    configs = build_configs()

    slope = read_band(RAW / "gems-geodawn-numerical-features.tif", band=19)
    slope_ok = valid & np.isfinite(slope)
    slope_threshold = float(np.nanpercentile(slope[slope_ok], 33.0))
    concealed_zone = slope_ok & (slope <= slope_threshold)
    del slope

    system_folds = build_folds(known, valid, n_folds=N_FOLDS,
                               hide_frac=HIDE_FRAC, seed=20260930,
                               link_px=LINK_PX, buffer_px=BUFFER_PX)
    seg_folds = segment_folds(known, valid, n_folds=N_FOLDS)
    folds = system_folds + seg_folds

    rows: list[dict] = []
    for fold_i, fold in enumerate(folds, start=1):
        print(f"[{fold_i:02d}/{len(folds)}] {fold.name} ({fold.rule}), "
              f"hidden={fold.n_hidden:,}, eval={int(fold.eval_mask.sum()):,}",
              flush=True)
        eval_mask = fold.eval_mask
        cache: dict[tuple[str, float, int], np.ndarray] = {}

        def static_component(name: str, ranker: Ranker, coverage: float) -> np.ndarray:
            key = (name, float(coverage), SPACING)
            if key not in cache:
                n = int(coverage * n_valid)
                m = ranker.topk(eval_mask, n)
                if SPACING > 1:
                    m = D.decimate_grid(m, ranker.score, SPACING)
                cache[key] = m
            return cache[key]

        # H11 is catalogue-derived: rebuild from this fold's VISIBLE traces only
        corr = D.parallel_offset_correction(fold.visible, crossgrad)
        corr = (corr > 0) & eval_mask

        fold_scorer = FoldScorer.build(fold.hidden, eval_mask)
        hidden_concealed = fold.hidden & concealed_zone
        concealed_scorer = (FoldScorer.build(hidden_concealed, eval_mask)
                            if int(hidden_concealed.sum()) > 50 else None)

        for cfg in configs:
            kind = cfg["kind"]
            base = static_component("topo", topo_ranker, BASE_COVERAGE)
            parts: list[np.ndarray] = []
            if kind == "ref":
                candidate = base.copy()
            elif kind in ("gap", "gap_eq", "gap_eq_corr"):
                coverage = float(cfg.get("coverage", BASE_COVERAGE))
                if coverage != BASE_COVERAGE:
                    base = static_component("topo", topo_ranker, coverage)
                gap = D.strike_gap_close(base, min_side=int(cfg["min_side"]))
                candidate = base | gap
                parts.append(("gap", int(gap.sum())))
            else:
                candidate = base.copy()
            if kind in ("eq", "gap_eq", "gap_eq_corr"):
                eqm = static_component("eq", eq_ranker, float(cfg["cov"]))
                candidate = candidate | eqm
                parts.append(("eq", int(eqm.sum())))
            if kind in ("corr", "gap_eq_corr"):
                candidate = candidate | corr
                parts.append(("corr", int(corr.sum())))
            candidate &= eval_mask

            n_eff = int(candidate.sum())
            result = fold_scorer.score(candidate)
            row = {
                "config": cfg["name"], "hypothesis": kind,
                "fold": fold.name, "rule": fold.rule,
                "n_truth": fold_scorer.n_truth,
                "n_eval_pixels": int(eval_mask.sum()),
                "n_predicted_eval_pixels": n_eff,
                "coverage_of_eval_pct": round(100.0 * n_eff / eval_mask.sum(), 5),
                "dti": round(float(result["dti"]), 7),
                "precision_w": round(float(result["precision_w"]), 7),
                "recall_w": round(float(result["recall_w"]), 7),
                "added_px": {k: v for k, v in parts},
                "dti_concealed": None, "n_truth_concealed": 0,
            }
            if concealed_scorer is not None:
                hr = concealed_scorer.score(candidate)
                row["dti_concealed"] = round(float(hr["dti"]), 7)
                row["n_truth_concealed"] = concealed_scorer.n_truth
            rows.append(row)
            del candidate
        del corr, fold_scorer, concealed_scorer, cache

    # ---- protocol regression check: topo_05_sp3 must equal the archived run
    hist_rows = {}
    if HISTORICAL.exists():
        for r in json.loads(HISTORICAL.read_text())["results"]:
            if r["config"] == "topo_05_sp3":
                hist_rows[r["fold"]] = r["dti"]
    mismatches = []
    for r in rows:
        if r["config"] == "topo_05_sp3" and r["fold"] in hist_rows:
            if abs(r["dti"] - hist_rows[r["fold"]]) > 1e-6:
                mismatches.append((r["fold"], r["dti"], hist_rows[r["fold"]]))
    protocol_check = {
        "compared_to": HISTORICAL.name,
        "n_compared": len(hist_rows),
        "n_mismatch": len(mismatches),
        "mismatches": mismatches[:10],
        "pass": not mismatches,
    }

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
                "dti_concealed_mean_by_rule": {
                    rule: float(np.mean([x["dti_concealed"] for x in v
                                         if x["dti_concealed"] is not None]))
                    for rule, v in rules.items()
                    if any(x["dti_concealed"] is not None for x in v)},
                "precision_w_mean": float(np.mean(
                    [x["precision_w"] for x in selected if x["config"] == cfg])),
                "recall_w_mean": float(np.mean(
                    [x["recall_w"] for x in selected if x["config"] == cfg])),
                "predicted_eval_px_mean": float(np.mean(
                    [x["n_predicted_eval_pixels"] for x in selected
                     if x["config"] == cfg])),
            }
        return out

    tune_summary = summarize(tune_rows)
    confirm_summary = summarize(confirm_rows)

    # paired per-fold deltas vs the reference
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
            "mean_delta_dti": float(np.mean(deltas)),
            "wins": wins, "ties": ties, "losses": len(deltas) - wins - ties,
            "rule_means_delta": {
                rule: float(np.mean([
                    r["dti"] - ref[(r["fold"], r["rule"])]
                    for r in confirm_rows if r["config"] == cfg]))
                for rule in confirm_summary["topo_05_sp3"]["dti_mean_by_rule"]},
        }

    # predeclared verdicts
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
            verdicts[cfg] = "LOSES"
        elif rules_won >= 4:
            verdicts[cfg] = "WINS"
        else:
            verdicts[cfg] = "FRAGILE"
        verdicts[cfg] += f" (confirmation rule-means won: {rules_won}/6)"

    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "LOCAL_PROXY_HOLDOUT_ONLY_NOT_PRIVATE_TEST_PERFORMANCE",
        "purpose": ("Predeclared validation of R9 gap-completion (H9), "
                    "epicentral alignment (H10) and parallel-offset "
                    "corrections (H11) against the paired topo_05_sp3 "
                    "reference on the identical fold set."),
        "grid": {"valid_pixels": n_valid, "known_fault_pixels": n_known},
        "protocol": {
            "identical_to": "scripts/validate_ensemble_holdout.py",
            "system_folds": {"rules": ["random", "short", "isolated",
                                       "oriented", "dense"],
                             "n_folds_per_rule": N_FOLDS,
                             "hide_fraction_target": HIDE_FRAC},
            "segment_folds": {"n_folds": N_FOLDS,
                              "hide_fraction_target": HIDE_FRAC},
            "buffer_px": BUFFER_PX, "buffer_m": BUFFER_PX * 100,
            "spacing_px": SPACING, "base_coverage": BASE_COVERAGE,
            "eq_coverage": EQ_COVERAGE,
            "visible_catalogue_only": True,
            "catalogue_dependent_features_rebuilt_per_fold":
                ["parallel_offset_correction"],
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
    out_path = REPORTS / "holdout_r9_2026-09-30.json"
    out_path.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print(f"wrote {out_path} ({len(rows)} rows, {time.time()-t0:.0f}s)")
    print("protocol regression check:", "PASS" if protocol_check["pass"]
          else f"FAIL {protocol_check['mismatches']}")
    for cfg, summ in sorted(confirm_summary.items(),
                            key=lambda kv: -kv[1]["dti_worst_rule_mean"]):
        v = verdicts.get(cfg, "reference")
        print(f"{cfg:24s} confirm worst={summ['dti_worst_rule_mean']:.5f} "
              f"mean={summ['dti_mean']:.5f} prec={summ['precision_w_mean']:.4f} "
              f"rec={summ['recall_w_mean']:.4f}  {v}")


BANDS = {"ieq_n100a15": 16, "deq_n100a15": 10}

if __name__ == "__main__":
    main()
