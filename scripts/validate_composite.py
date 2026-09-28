#!/usr/bin/env python3
"""Validate the composite submission recipe on BOTH holdout regimes.

The two holdouts measure different things and disagree, which is the point:

  isolated-systems holdout  ->  "find a completely unmapped fault system"
                                nothing beats chance (best 1.06x)
  tip-extension holdout     ->  "recover missing geometry of a mapped system"
                                directional tip rays reach 14-16x chance

The real label set is a mixture of the two, in unknown proportion. The metric
tells us exactly how to hedge: a block of predictions raises DTI iff its
marginal weighted precision exceeds 0.2 x DTI (~3%). Tip rays measured 37%
weighted precision, so they are always worth including; broad coverage buys the
chance-level bulk. So the composite is

    max(tip rays, broad fill at coverage c, known catalogue)

and this script sweeps c on both holdouts at once.
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
from chance_baseline import dti_chance       # noqa: E402
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
                lifts = []
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
                    ch = dti_chance(mass, sc.n_truth, n_valid)
                    lift = s["dti"] / ch if ch > 0 else 0.0
                    lifts.append(lift)
                    rec["per_regime"][name] = {
                        "dti": round(s["dti"], 5), "chance": round(ch, 5),
                        "lift": round(lift, 3),
                        "precision_w": round(s["precision_w"], 5),
                        "recall_w": round(s["recall_w"], 5),
                        "mass": int(mass)}
                rec["worst_lift"] = round(min(lifts), 4)
                rec["mean_lift"] = round(float(np.mean(lifts)), 4)
                rec["geo_mean_lift"] = round(
                    float(np.exp(np.mean(np.log(np.maximum(lifts, 1e-6))))), 4)
                out.append(rec)

    out.sort(key=lambda z: -z["geo_mean_lift"])
    hdr = (f"{'reach':>6s} {'sp':>3s} {'fill':>6s} {'mass':>9s} "
           f"{'tip20':>7s} {'tip30':>7s} {'iso1':>7s} {'iso2':>7s} "
           f"{'geo':>6s} {'worst':>6s}")
    print("\n=== COMPOSITE: lift over chance in BOTH regimes ===")
    print(hdr); print("-" * len(hdr))
    for r in out[:20]:
        pr = r["per_regime"]
        print(f"{r['reach']:6d} {r['spacing']:3d} {r['fill_cov']:6.3f} "
              f"{pr['tip20']['mass']:9,d} "
              f"{pr['tip20']['lift']:7.2f} {pr['tip30']['lift']:7.2f} "
              f"{pr['isolated_random']['lift']:7.2f} "
              f"{pr['isolated_random2']['lift']:7.2f} "
              f"{r['geo_mean_lift']:6.2f} {r['worst_lift']:6.2f}")

    (REP / "composite_validation.json").write_text(json.dumps(
        {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "regimes": {k: {"n_hidden": int(v[3].n_truth)} for k, v in regimes.items()},
         "note": ("geo_mean_lift is the geometric mean of lift over chance "
                  "across both regimes; it is the hedging objective because we "
                  "do not know the mixture proportion in the real label set."),
         "sweep": out}, indent=2))
    b = out[0]
    print(f"\nBEST HEDGE: reach={b['reach']} spacing={b['spacing']} "
          f"fill_coverage={b['fill_cov']}  geo-mean lift {b['geo_mean_lift']:.2f}x")
    print(f"wrote {REP/'composite_validation.json'} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
