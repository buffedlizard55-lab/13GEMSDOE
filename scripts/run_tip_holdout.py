#!/usr/bin/env python3
"""Tip-extension holdout — the regime the organizers actually described.

`run_holdout2.py` withholds WHOLE fault systems plus a 5-px buffer, so every
withheld pixel is >=500 m from anything visible. That measures "find a
completely unmapped, isolated fault system". It is a real part of the task, but
it is the hardest part, and it destroys by construction the single strongest
prior available: proximity to a mapped trace.

The organizers were explicit that the label set is not like that:

  "A new-fault ground truth pixel can indeed lie within 300m of a known fault
   trace. Such pixels would constitute corrections or modifications to existing
   fault traces. Identifying these corrections is one outcome we are aiming for
   as part of this competition."     -- chrisk-dd, forum 11516 post 4

  "'new fault' means 'any fault pixel not already captured by USGS/INGENIOUS'
   and can include newly mapped geometry of an existing fault system."
                                     -- chrisk-dd, forum 11536

So this script builds a complementary local stress test: hide terminal portions
of known mapped segments, keep the rest visible, and measure recovery of the
missing continuation with direct DTI. The result is not an estimate of the
undisclosed test distribution.
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gems import detectors as D                 # noqa: E402
from gems.fastscore import FoldScorer           # noqa: E402

DER = ROOT / "data" / "derived"
REP = ROOT / "reports"


def tip_fold(known: np.ndarray, valid: np.ndarray, frac: float,
             both_ends: bool, seed: int):
    """Hide the terminal `frac` of each segment, along its own strike."""
    lab, n = ndi.label(known, structure=np.ones((3, 3), dtype=int))
    hidden = np.zeros(known.shape, dtype=bool)
    rng = np.random.default_rng(seed)
    for i, sl in enumerate(ndi.find_objects(lab)):
        if sl is None:
            continue
        ys, xs = np.nonzero(lab[sl] == i + 1)
        if ys.size < 8:
            continue
        ys = ys + sl[0].start
        xs = xs + sl[1].start
        cy, cx = ys.mean(), xs.mean()
        dy, dx = ys - cy, xs - cx
        cov = np.array([[np.dot(dx, dx), np.dot(dx, dy)],
                        [np.dot(dx, dy), np.dot(dy, dy)]]) / ys.size
        _, v = np.linalg.eigh(cov)
        ax = v[:, -1]
        t = dx * ax[0] + dy * ax[1]
        ends = (1.0, -1.0) if both_ends else (rng.choice([1.0, -1.0]),)
        for sgn in ends:
            k = max(1, int(round(frac * ys.size / len(ends))))
            idx = np.argsort(-sgn * t)[:k]
            hidden[ys[idx], xs[idx]] = True
    visible = known & ~hidden
    return hidden, visible, valid & ~visible


def main() -> None:
    t0 = time.time()
    valid = np.load(DER / "_valid.npy")
    known = np.load(DER / "_known.npy")
    n_valid = int(valid.sum())

    folds = {}
    for frac, both, seed in [(0.20, True, 1), (0.30, True, 2), (0.25, False, 3)]:
        name = f"tip{int(frac*100)}_{'both' if both else 'one'}"
        h, vis, em = tip_fold(known, valid, frac, both, seed)
        folds[name] = (h, vis, em, FoldScorer.build(h, em))
        print(f"{name}: hidden={int(h.sum()):,}  visible={int(vis.sum()):,} "
              f"({time.time()-t0:.0f}s)")

    topo = np.load(DER / "BASE_topo_ridge.npy")
    hinge = np.load(DER / "HC_hinge.npy")
    tdr = np.load(DER / "HB_tdr_rtp.npy")
    rng = np.random.default_rng(7)
    noise = rng.random(valid.shape).astype(np.float32)

    results = []

    def ev(tag, build):
        for fn, (h, vis, em, sc) in folds.items():
            p = build(vis, em).astype(np.float32)
            p = np.where(em, np.clip(p, 0, 1), 0.0)
            s = sc.score(p)
            mass = float(p.sum())
            results.append({
                "tag": tag, "fold": fn, "dti": round(s["dti"], 6),
                "precision_w": round(s["precision_w"], 6),
                "recall_w": round(s["recall_w"], 6),
                "mass": round(mass, 1), "n_truth": sc.n_truth,
                "n_eval_px": int(em.sum())})

    def topk(score, em, n):
        flat = np.where(em, score, -np.inf).ravel()
        n = min(n, int(np.isfinite(flat).sum()))
        idx = np.argpartition(flat, -n)[-n:]
        m = np.zeros(flat.size, bool); m[idx] = True
        return m.reshape(score.shape)

    print("--- candidates ---")
    st = ndi.generate_binary_structure(2, 2)
    for k in (1, 2, 3, 5, 8):
        ev(f"catalogue_dilate_{k}px",
           lambda vis, em, k=k: ndi.binary_dilation(vis, st, iterations=k) & em)
    for reach in (10, 20, 30, 50):
        for sp in (1, 3):
            def b(vis, em, reach=reach, sp=sp):
                r = D.extension_rays(vis, reach_px=reach)
                m = (r > 0) & em
                return D.decimate_grid(m, r, sp) if sp > 1 else m
            ev(f"H-I_extension_rays_reach{reach}_sp{sp}", b)
    for reach in (20, 30):
        def b(vis, em, reach=reach):
            r = D.extension_rays(vis, reach_px=reach)
            return ((r > 0) & em).astype(np.float32) * D.robust_norm(topo)
        ev(f"H-I_rays{reach}_x_toporidge", b)
    for cov in (0.01, 0.03, 0.05):
        n = int(cov * n_valid)
        ev(f"BASE_topo_ridge_cov{cov}", lambda vis, em, n=n: topk(topo, em, n))
        ev(f"HC_hinge_cov{cov}", lambda vis, em, n=n: topk(hinge, em, n))
        ev(f"HB_tdr_rtp_cov{cov}", lambda vis, em, n=n: topk(tdr, em, n))
        ev(f"CTRL_random_cov{cov}", lambda vis, em, n=n: topk(noise, em, n))

    agg = defaultdict(list)
    for r in results:
        agg[r["tag"]].append(r)
    rows = []
    for tag, v in agg.items():
        fold_dti = [float(x["dti"]) for x in v]
        rows.append({"tag": tag,
                     "mean_dti": float(np.mean(fold_dti)),
                     "minimum_fold_dti": float(min(fold_dti)),
                     "mean_recall": float(np.mean([x["recall_w"] for x in v])),
                     "median_mass": float(np.median([x["mass"] for x in v]))})
    rows.sort(key=lambda z: (-z["minimum_fold_dti"], -z["mean_dti"]))

    hdr = (f"{'candidate':38s} {'mass':>9s} {'mean DTI':>9s} "
           f"{'min-fold DTI':>12s} {'recall':>7s}")
    print("\n=== LOCAL TIP-CONTINUATION HOLDOUT (direct DTI) ===")
    print(hdr); print("-" * len(hdr))
    for r in rows:
        print(f"{r['tag'][:38]:38s} {r['median_mass']:9,.0f} "
              f"{r['mean_dti']:9.4f} {r['minimum_fold_dti']:12.4f} "
              f"{r['mean_recall']:7.4f}")

    (REP / "holdout_tip.json").write_text(json.dumps(
        {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "scope": "LOCAL_KNOWN_CATALOGUE_TIP_CONTINUATION_STRESS_TEST_NOT_PRIVATE_TEST_PERFORMANCE",
         "ranking_metric": "minimum single-fold DTI, then mean DTI; no chance ratio",
         "folds": {k: {"n_hidden": int(v[0].sum()),
                       "n_visible": int(v[1].sum()),
                       "n_eval_px": int(v[2].sum())}
                   for k, v in folds.items()},
         "summary": rows, "results": results}, indent=2))
    print(f"\nwrote {REP/'holdout_tip.json'} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
