#!/usr/bin/env python3
"""Historical local comparison of tip-extension and whole-system folds.

The script evaluates direct DTI for four fixed catalogue hide-and-recover
folds (two terminal-tip folds and two whole-system random folds). These folds
represent distinct local questions, not a known mixture of the competition's
undisclosed labels. Do not combine them with chance ratios or treat them as a
submission gate; candidate decisions require the current multi-rule confirmation
protocol and direct DTI.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gems import detectors as D              # noqa: E402
from gems.fastscore import FoldScorer        # noqa: E402
from gems.holdout import build_folds         # noqa: E402
from run_tip_holdout import tip_fold         # noqa: E402

DER = ROOT / "data" / "derived"
REP = ROOT / "reports"
COVS = [0.0, 0.01, 0.02, 0.03, 0.05, 0.08]
REACHES = [10, 20, 30]


def main() -> None:
    t0 = time.time()
    valid = np.load(DER / "_valid.npy")
    known = np.load(DER / "_known.npy")
    topo = np.load(DER / "BASE_topo_ridge.npy")
    n_valid = int(valid.sum())

    regimes = {}
    for frac, both, seed in [(0.20, True, 1), (0.30, True, 2)]:
        h, vis, em = tip_fold(known, valid, frac, both, seed)
        regimes[f"tip{int(frac*100)}"] = (h, vis, em, FoldScorer.build(h, em))
    for f in build_folds(known, valid, n_folds=1, hide_frac=0.25)[:1]:
        regimes["isolated_random"] = (f.hidden, f.visible, f.eval_mask,
                                      FoldScorer.build(f.hidden, f.eval_mask))
    for f in build_folds(known, valid, n_folds=1, hide_frac=0.25, seed=99)[:1]:
        regimes["isolated_random2"] = (f.hidden, f.visible, f.eval_mask,
                                       FoldScorer.build(f.hidden, f.eval_mask))
    print(f"regimes: {list(regimes)} ({time.time()-t0:.0f}s)")

    # cache tip rays per regime (they depend only on the visible catalogue)
    rays = {}
    for name, (h, vis, em, sc) in regimes.items():
        for reach in REACHES:
            rays[(name, reach)] = D.extension_rays(vis, reach_px=reach)
    print(f"rays built ({time.time()-t0:.0f}s)")

    def topk(score, em, n):
        flat = np.where(em, score, -np.inf).ravel()
        n = min(n, int(np.isfinite(flat).sum()))
        if n <= 0:
            return np.zeros(score.shape, bool)
        idx = np.argpartition(flat, -n)[-n:]
        m = np.zeros(flat.size, bool); m[idx] = True
        return m.reshape(score.shape)

    out = []
    for reach in REACHES:
        for sp in (1, 3):
            for cov in COVS:
                rec = {"reach": reach, "spacing": sp, "fill_cov": cov,
                       "per_regime": {}}
                dti_values = []
                for name, (h, vis, em, sc) in regimes.items():
                    r = rays[(name, reach)]
                    m = (r > 0) & em
                    if sp > 1:
                        m = D.decimate_grid(m, r, sp)
                    if cov > 0:
                        m = m | topk(topo, em, int(cov * n_valid))
                    p = m.astype(np.float32)
                    s = sc.score(p)
                    mass = float(p.sum())
                    dti_values.append(float(s["dti"]))
                    rec["per_regime"][name] = {
                        "dti": round(s["dti"], 6),
                        "precision_w": round(s["precision_w"], 6),
                        "recall_w": round(s["recall_w"], 6),
                        "mass": int(mass), "n_truth": int(sc.n_truth),
                        "n_eval_px": int(em.sum())}
                rec["mean_dti_four_folds"] = round(float(np.mean(dti_values)), 6)
                rec["minimum_single_fold_dti"] = round(min(dti_values), 6)
                out.append(rec)

    # The four folds are intentionally heterogeneous; this is a descriptive
    # direct-DTI sort, not a mixture estimate or submission selection.
    out.sort(key=lambda z: (-z["minimum_single_fold_dti"],
                            -z["mean_dti_four_folds"]))
    hdr = (f"{'reach':>6s} {'sp':>3s} {'fill':>6s} {'mass':>9s} "
           f"{'tip20':>7s} {'tip30':>7s} {'iso1':>7s} {'iso2':>7s} "
           f"{'mean':>7s} {'min':>7s}")
    print("\n=== EXPLORATORY COMPOSITE: direct DTI on four fixed folds ===")
    print(hdr); print("-" * len(hdr))
    for r in out[:20]:
        pr = r["per_regime"]
        print(f"{r['reach']:6d} {r['spacing']:3d} {r['fill_cov']:6.3f} "
              f"{pr['tip20']['mass']:9,d} "
              f"{pr['tip20']['dti']:7.4f} {pr['tip30']['dti']:7.4f} "
              f"{pr['isolated_random']['dti']:7.4f} "
              f"{pr['isolated_random2']['dti']:7.4f} "
              f"{r['mean_dti_four_folds']:7.4f} "
              f"{r['minimum_single_fold_dti']:7.4f}")

    (REP / "composite_validation.json").write_text(json.dumps(
        {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "scope": "LOCAL_PROXY_FOUR_FIXED_FOLDS_NOT_PRIVATE_TEST_PERFORMANCE",
         "selection": "descriptive direct-DTI ordering only; no chance ratio or submission gate",
         "regimes": {k: {"n_hidden": int(v[3].n_truth),
                         "n_eval_px": int(v[2].sum())}
                     for k, v in regimes.items()},
         "note": ("Tip-continuation folds and whole-system folds answer distinct "
                  "local questions. Their mixture in the undisclosed test is unknown; "
                  "the unweighted mean is a descriptive summary only."),
         "sweep": out}, indent=2))
    b = out[0]
    print(f"\nTop descriptive configuration: reach={b['reach']} "
          f"spacing={b['spacing']} fill_coverage={b['fill_cov']} "
          f"mean DTI={b['mean_dti_four_folds']:.4f}; "
          f"minimum single-fold DTI={b['minimum_single_fold_dti']:.4f} "
          "(not submission clearance).")
    print(f"wrote {REP/'composite_validation.json'} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
