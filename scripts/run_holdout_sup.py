#!/usr/bin/env python3
"""Holdout for H-S, the first SUPERVISED detector in this repository.

Protocol is identical to `scripts/run_holdout3.py` so the numbers are directly
comparable:

  * whole fault SYSTEMS withheld with a 500 m buffer, five withholding rules
    (random, short, isolated, strike-class, dense);
  * the visible catalogue masked pixel-exactly, as the organizers do;
  * DTI computed on the withheld pixels alone, with same-run random-map DTI
    reported as a limited local control (not a universal chance calibration);
  * the lowest-slope-third subset is reported as a catalogue robustness stress
    test, not as an analogue of hidden-test truth (irregularity I-11);
  * the classifier is trained ONLY on the visible catalogue of that fold.

Usage:  python scripts/run_holdout_sup.py [--epochs 40] [--l2 1e-3]
"""
from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from collections import OrderedDict, defaultdict
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gems import detectors as D                        # noqa: E402
from gems.fastscore import FoldScorer, verify_against_reference  # noqa: E402
from gems.holdout import build_folds                   # noqa: E402
from gems.supervised import fit_labelled               # noqa: E402

DER = ROOT / "data" / "derived"
REP = ROOT / "reports"
FEATS = ROOT / "data" / "raw" / "gems-geodawn-numerical-features.tif"
NODATA = -3.4028234663852886e+38

COVERAGES = [0.005, 0.01, 0.02, 0.03, 0.05, 0.08]
SPACINGS = [1, 2, 3]
FOLDS5 = ["random_0", "short_0", "isolated_0", "strike_0_60", "dense_0"]


class Ranker:
    def __init__(self, score: np.ndarray):
        self.shape = score.shape
        self.order = np.argsort(-np.asarray(score).ravel(),
                                kind="stable").astype(np.int32)

    def topk(self, allowed_flat: np.ndarray, n: int) -> np.ndarray:
        sel = self.order[allowed_flat[self.order]][:n]
        m = np.zeros(allowed_flat.size, dtype=bool)
        m[sel] = True
        return m.reshape(self.shape)


def load_bands() -> list[np.ndarray]:
    """All 19 official bands, nodata -> NaN, as float32."""
    with rasterio.open(FEATS) as src:
        out = []
        for i in range(1, 20):
            a = src.read(i).astype(np.float32)
            out.append(np.where((a > NODATA + abs(NODATA) * 1e-6)
                                & np.isfinite(a), a, np.nan))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--l2", type=float, default=1e-3)
    ap.add_argument("--max-neg", type=int, default=400_000)
    ap.add_argument("--skip-stage2", action="store_true")
    a = ap.parse_args()

    t0 = time.time()
    v = verify_against_reference(trials=12)
    assert v["pass"], v
    print(f"scorer verified: {v['max_err']}")

    valid = np.load(DER / "_valid.npy")
    known = np.load(DER / "_known.npy")
    n_valid = int(valid.sum())

    with rasterio.open(FEATS) as src:
        desc = list(src.descriptions)
        bidx = [i for i, d in enumerate(desc, 1)
                if (d or "").startswith("det_elev_slope")][0]
        slope = src.read(bidx).astype(np.float32)
    slope = np.where(valid & np.isfinite(slope), slope, np.nan)
    thr = np.nanpercentile(slope, 33.0)
    concealed_zone = valid & np.isfinite(slope) & (slope <= thr)
    del slope
    gc.collect()
    print(f"concealed zone: {int(concealed_zone.sum()):,} px; "
          f"catalogue inside: {int((known & concealed_zone).sum()):,}")

    folds = build_folds(known, valid, n_folds=1, hide_frac=0.25)
    fold_by_name = {f.name: f for f in folds}
    print(f"{len(folds)} folds built ({time.time()-t0:.0f}s)")

    _SC: "OrderedDict[str, tuple]" = OrderedDict()

    def scorers(fn):
        if fn in _SC:
            _SC.move_to_end(fn)
            return _SC[fn]
        f = fold_by_name[fn]
        sf = FoldScorer.build(f.hidden, f.eval_mask)
        hc = f.hidden & concealed_zone
        sc = (FoldScorer.build(hc, f.eval_mask) if hc.sum() > 50 else None)
        _SC[fn] = (sf, sc)
        while len(_SC) > 3:
            _SC.popitem(last=False)
        gc.collect()
        return sf, sc

    results: list[dict] = []

    def evaluate(tag, family, build_pred, fold_names, stage="stage1"):
        for fn in fold_names:
            f = fold_by_name[fn]
            pred = build_pred(f)
            sf, sc = scorers(fn)
            r = sf.score(pred)
            row = {"tag": tag, "family": family, "fold": fn, "rule": f.rule,
                   "n_hidden": f.n_hidden, "n_pred_px": int((pred > 0).sum()),
                   "dti": round(r["dti"], 6),
                   "precision_w": round(r["precision_w"], 6),
                   "recall_w": round(r["recall_w"], 6), "stage": stage}
            if sc is not None:
                b = sc.score(pred)
                row["dti_concealed"] = round(b["dti"], 6)
                row["recall_concealed"] = round(b["recall_w"], 6)
                row["n_hidden_concealed"] = sc.n_truth
            results.append(row)

    # ---------------- controls ----------------
    print("--- controls ---")
    rng = np.random.default_rng(12345)
    noise = Ranker(rng.random(valid.shape).astype(np.float32))
    for cov in COVERAGES:
        n = int(cov * n_valid)
        evaluate(f"CTRL_random|cov{cov}|rep0", "control_random",
                 lambda f, n=n: noise.topk(f.eval_mask.ravel(), n), FOLDS5)
    control_scores = defaultdict(list)
    for r in results:
        if r["family"] == "control_random":
            control_scores[(float(r["tag"].split("|")[1][3:]),
                            r["fold"])].append(r["dti"])
    random_control_dti_by_cov_fold = {
        k: float(np.mean(v)) for k, v in control_scores.items()
    }
    for cov in COVERAGES:
        vals = [v for (c, _), v in random_control_dti_by_cov_fold.items()
                if c == cov]
        print(f"      cov={cov:<6} local random-control DTI={np.mean(vals):.4f}")

    st = ndi.generate_binary_structure(2, 2)
    for k in (1, 2):
        evaluate(f"CTRL_catalogue_dilate_{k}px", "control",
                 lambda f, k=k: (ndi.binary_dilation(f.visible, st, iterations=k)
                                 & f.eval_mask), FOLDS5)

    # the analytic baselines, for a same-run comparison
    for base in ("BASE_topo_ridge", "BASE_tmi_hg", "R7_crossgrad",
                 "R7_consensus3", "HB_tdr_rtp"):
        p = DER / f"{base}.npy"
        if not p.exists():
            continue
        s = np.load(p)
        rk = Ranker(s)
        for cov in COVERAGES:
            n = int(cov * n_valid)
            for sp in SPACINGS:
                def build(f, rk=rk, n=n, sp=sp, s=s):
                    m = rk.topk(f.eval_mask.ravel(), n)
                    return D.decimate_grid(m, s, sp) if sp > 1 else m
                evaluate(f"{base}|cov{cov}|sp{sp}", base, build, FOLDS5)
        del s, rk
        gc.collect()
        print(f"    baseline {base} ({time.time()-t0:.0f}s)")

    # ---------------- the supervised detector ----------------
    print(f"--- H-S supervised ({time.time()-t0:.0f}s) ---")
    bands = load_bands()
    print(f"    19 bands loaded ({time.time()-t0:.0f}s)")

    sup_models: dict[str, object] = {}
    for fn in FOLDS5:
        f = fold_by_name[fn]
        # TRAIN ONLY ON WHAT IS VISIBLE. `eval_mask` in `gems.holdout` is
        # `valid & ~visible`, which INCLUDES the withheld pixels -- so we must
        # subtract `hidden` (and a 5-px dilation of it, so no withheld geometry
        # leaks through a 9x9 context mean) explicitly. Using eval_mask as-is
        # would train the withheld faults as NEGATIVES, i.e. leak the answer.
        allowed = (valid & ~f.hidden
                   & ~ndi.binary_dilation(f.hidden, structure=st, iterations=5))
        model = fit_labelled(bands, f.visible, allowed, l2=a.l2,
                             epochs=a.epochs, max_neg=a.max_neg, seed=7)
        sup_models[fn] = model
        print(f"    trained on {fn}: {model.n_train_pos:,} pos / "
              f"{model.n_train_neg:,} neg ({time.time()-t0:.0f}s)")

    for fn in FOLDS5:
        s = sup_models[fn].predict(bands)
        rk = Ranker(s)
        for cov in COVERAGES:
            n = int(cov * n_valid)
            for sp in SPACINGS:
                def build(f, rk=rk, n=n, sp=sp, s=s):
                    m = rk.topk(f.eval_mask.ravel(), n)
                    return D.decimate_grid(m, s, sp) if sp > 1 else m
                evaluate(f"HS_supervised|cov{cov}|sp{sp}", "HS_supervised",
                         build, [fn])
        del s, rk
        gc.collect()
        print(f"    HS evaluated on {fn} ({time.time()-t0:.0f}s)")

    # feature weights: which bands carry the signal
    m0 = sup_models[FOLDS5[0]]
    order = np.argsort(-np.abs(m0.w))
    codes = [d.split(" - ")[0] for d in desc]
    top = []
    for rank, j in enumerate(order[:20]):
        blk = ("value" if j < 19 else ("3x3 mean" if j < 38 else "9x9 mean"))
        top.append({"rank": rank + 1, "feature_index": int(j),
                    "band": codes[j % 19], "scale": blk,
                    "weight": round(float(m0.w[j]), 5)})
    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scorer_verification": v,
        "grid": {"valid_px": n_valid, "known_fault_px": int(known.sum())},
        "concealed_zone": {"slope_percentile": 33.0, "threshold": float(thr),
                           "n_px": int(concealed_zone.sum()),
                           "catalogue_px_inside": int((known & concealed_zone).sum())},
        "folds": [{"name": f.name, "rule": f.rule, "n_hidden": f.n_hidden,
                   "n_visible": f.n_visible,
                   "n_eval_px": int(f.eval_mask.sum()), **f.meta}
                  for f in folds],
        "coverages": COVERAGES, "spacings": SPACINGS,
        "train_config": {"l2": a.l2, "epochs": a.epochs,
                         "max_neg": a.max_neg, "seed": 7,
                         "pos_weight": "inverse class frequency",
                         "trained_on": "visible catalogue of that fold only",
                         "context_scales": ["1 px", "3x3 mean (150 m)",
                                            "9x9 mean (450 m)"]},
        "top_feature_weights_fold_random_0": top,
        "random_control_dti_by_cov_fold": {
            f"{k[0]}|{k[1]}": round(v2, 6)
            for k, v2 in random_control_dti_by_cov_fold.items()
        },
        "results": results, "runtime_s": round(time.time() - t0, 1)}
    (REP / "holdout_supervised.json").write_text(json.dumps(out, indent=1))
    print(f"wrote {REP/'holdout_supervised.json'} ({time.time()-t0:.0f}s)")
    print("\ntop feature weights (fold random_0):")
    for r in top[:12]:
        print(f"  {r['rank']:2d}. {r['band']:20s} {r['scale']:14s} "
              f"w={r['weight']:+.4f}")


if __name__ == "__main__":
    main()
