#!/usr/bin/env python3
"""Null-model baselines on the SAME hold-out protocol as R10-R13.

Question answered: how much of the local DTI of `topo_05_sp3` / `greedy_r11` is
information about faults, and how much is just *how many pixels are predicted and how
they are spread*?  Two content-free maps are scored on the 18 folds:

  null_random_05_sp3  uniform-random scores, top 5 % of the eval mask, spacing-3
                      decimation (same budget and same decimation as the reference);
  null_lattice_sK     every K-th row x every K-th column, K in 2..8 (no fault
                      information whatsoever; K=4 is 6.25 % of pixels);
  null_all_ones       predict 1.0 everywhere in the eval mask (the "blanket" map).

Interpretation guard: this is a LOCAL proxy on known faults (I-16).  The leaderboard
truth set is different (faults NOT in the catalogue), so the numbers bound what
"content-free coverage" earns locally; they do not predict the public score.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gems import detectors as D                                   # noqa: E402
from gems.fastscore import FoldScorer, verify_against_reference    # noqa: E402
from gems.holdout import build_folds                              # noqa: E402
from gems.rio import load_footprint                               # noqa: E402
import validate_r10_holdout as R10                                # noqa: E402
import validate_r10b_holdout as R10B                              # noqa: E402

OUT = ROOT / "reports" / "null_baseline_2026-10-01.json"
SEEDS = (11, 12, 13)
LATTICE_K = (2, 3, 4, 5, 6, 8)


def main() -> int:
    t0 = time.time()
    if not verify_against_reference(trials=15)["pass"]:
        raise RuntimeError("fast scorer disagrees with reference")
    valid, known = load_footprint(R10.RAW / "existing_faults.tif")
    n_valid = int(valid.sum())
    folds = (build_folds(known, valid, n_folds=R10.N_FOLDS, hide_frac=R10.HIDE_FRAC,
                         seed=20260930, link_px=R10.LINK_PX, buffer_px=R10.BUFFER_PX)
             + R10.segment_folds(known, valid, n_folds=R10.N_FOLDS))
    H, W = valid.shape
    lattices = {}
    for k in LATTICE_K:
        lat = np.zeros((H, W), bool)
        lat[::k, ::k] = True
        lattices[f"null_lattice_s{k}"] = lat
    rnd = [np.random.default_rng(s).random((H, W), dtype=np.float32) for s in SEEDS]
    rankers = [R10.Ranker(r) for r in rnd]
    rows = []
    for f in folds:
        ev = f.eval_mask
        sc = FoldScorer.build(f.hidden, ev)
        res = {}
        for i, rk in enumerate(rankers):
            m, _ = rk.topk(ev, int(R10.BASE_COVERAGE * n_valid))
            m = D.decimate_grid(m, rk.score, R10.SPACING) & ev
            res[f"null_random_05_sp3_s{SEEDS[i]}"] = (m, sc.score(m.astype(np.float32)))
        for k, lat in lattices.items():
            m = lat & ev
            res[k] = (m, sc.score(m.astype(np.float32)))
        res["null_all_ones"] = (ev.copy(), sc.score(ev.astype(np.float32)))
        for k, (m, r) in res.items():
            rows.append({"config": k, "fold": f.name, "rule": f.rule,
                         "n_predicted_eval_pixels": int(m.sum()),
                         **{q: round(float(r[q]), 7) for q in
                            ("dti", "tp_w", "fp_w", "precision_w", "recall_w")},
                         "selection_diagnostics": {"x": {"tie_fraction": 0.0,
                                                          "n_selected_at_zero_score": 0}}})
        print(f"[{time.time()-t0:.0f}s] {f.name}", flush=True)
    s = R10B.summarize(rows)
    # reference numbers from the R12 in-run reference (same folds)
    r12 = json.loads((ROOT / "reports" / "holdout_r12_2026-09-30.json").read_text())
    ref = {k: {"dti_mean_all_18": float(np.mean([r["dti"] for r in r12["results"]
                                                if r["config"] == k]))}
           for k in ("topo_05_sp3", "greedy_r11")}
    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "status": "LOCAL_PROXY_HOLDOUT_ONLY_NOT_PRIVATE_TEST_PERFORMANCE",
           "summary": {k: {"dti_mean": v["dti_mean"],
                           "dti_worst_rule_mean": v["dti_worst_rule_mean"],
                           "precision_w_mean": v["precision_w_mean"],
                           "recall_w_mean": v["recall_w_mean"],
                           "predicted_eval_px_mean": v["predicted_eval_px_mean"]}
                       for k, v in s.items()},
           "reference_from_r12_report": ref, "results": rows}
    OUT.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    for k, v in out["summary"].items():
        print(f"{k:28s} dti_mean={v['dti_mean']:.5f} worst_rule={v['dti_worst_rule_mean']:.5f} "
              f"P={v['precision_w_mean']:.4f} R={v['recall_w_mean']:.4f} "
              f"px={v['predicted_eval_px_mean']:.0f}")
    print(ref)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
