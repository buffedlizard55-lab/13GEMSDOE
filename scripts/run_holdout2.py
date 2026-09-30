#!/usr/bin/env python3
"""Hide-and-recover holdout, v2 — corrected and interpretable.

Three changes over v1, each forced by what v1 measured:

1. COVERAGE-MATCHED RANDOM CONTROLS at every coverage. These show the direct
   DTI of same-run random maps on the same folds; they are limited local
   references, not a universal chance calibration. Candidate ranking uses direct
   DTI, not a candidate-to-chance ratio.

2. GRID DECIMATION instead of strike decimation. v1's strike decimation removed
   only 2.5% of mass at spacing=4 because the orientation estimate on an
   already-thinned crest is noise. `decimate_grid` keeps one pixel per
   spacing x spacing tile, which is what the metric's 300 m max actually
   rewards.

3. LOW-SLOPE ROBUSTNESS SLICE. The withheld pixels still come from the known
   catalogue, so this is not the undisclosed new-fault population. We also score
   withheld truth in the lowest one-third of detrended-elevation slope as a
   predeclared stress test. It describes detector behavior on this catalogue
   subset; it is not an analogue or estimate of hidden-test truth.
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
from gems import detectors as D                       # noqa: E402
from gems.fastscore import FoldScorer, verify_against_reference   # noqa: E402
from gems.holdout import build_folds                  # noqa: E402

DER = ROOT / "data" / "derived"
SCORED = ROOT / "data" / "scored"
REP = ROOT / "reports"
FEATS = ROOT / "data" / "raw" / "gems-geodawn-numerical-features.tif"

COVERAGES = [0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12]
SPACINGS = [1, 2, 3]
FOLDS5 = ["random_0", "short_0", "isolated_0", "strike_60_120", "dense_0"]


class Ranker:
    """Precomputed global ranking of a score map -> fast masked top-k."""

    def __init__(self, score: np.ndarray):
        self.shape = score.shape
        self.order = np.argsort(-score.ravel(), kind="stable").astype(np.int64)

    def topk(self, allowed_flat: np.ndarray, n: int) -> np.ndarray:
        sel = self.order[allowed_flat[self.order]][:n]
        m = np.zeros(allowed_flat.size, dtype=bool)
        m[sel] = True
        return m.reshape(self.shape)


def main() -> None:
    t0 = time.time()
    v = verify_against_reference(trials=15)
    assert v["pass"], v
    print(f"scorer verified: {v['max_err']}")

    valid = np.load(DER / "_valid.npy")
    known = np.load(DER / "_known.npy")
    n_valid = int(valid.sum())

    # topographic expression, used to define the "concealed" subset
    with rasterio.open(FEATS) as src:
        bidx = [i for i, d in enumerate(src.descriptions, 1)
                if (d or "").startswith("det_elev_slope")][0]
        slope = src.read(bidx).astype(np.float32)
    slope = np.where(valid & np.isfinite(slope), slope, np.nan)
    thr = np.nanpercentile(slope, 33.0)
    concealed_zone = valid & np.isfinite(slope) & (slope <= thr)
    print(f"concealed zone (slope <= p33 = {thr:.4g}): "
          f"{int(concealed_zone.sum()):,} px "
          f"({100*concealed_zone.sum()/n_valid:.1f}% of valid); "
          f"catalogue pixels inside it: {int((known & concealed_zone).sum()):,} "
          f"({100*(known & concealed_zone).sum()/known.sum():.1f}% of catalogue)")

    folds = build_folds(known, valid, n_folds=2, hide_frac=0.25)
    fold_by_name = {f.name: f for f in folds}
    print(f"{len(folds)} folds built ({time.time()-t0:.0f}s)")

    sc_full: dict[str, FoldScorer] = {}
    sc_conc: dict[str, FoldScorer] = {}

    def scorers(fn):
        if fn not in sc_full:
            f = fold_by_name[fn]
            sc_full[fn] = FoldScorer.build(f.hidden, f.eval_mask)
            hc = f.hidden & concealed_zone
            sc_conc[fn] = FoldScorer.build(hc, f.eval_mask) if hc.sum() > 50 else None
        return sc_full[fn], sc_conc[fn]

    results: list[dict] = []

    def evaluate(tag, family, build_pred, fold_names):
        for fn in fold_names:
            f = fold_by_name[fn]
            pred = build_pred(f)
            sf, sc = scorers(fn)
            a = sf.score(pred)
            row = {"tag": tag, "family": family, "fold": fn, "rule": f.rule,
                   "n_hidden": f.n_hidden, "n_visible": f.n_visible,
                   "n_eval_px": int(f.eval_mask.sum()),
                   "n_pred_px": int((pred > 0).sum()),
                   "dti": round(a["dti"], 6),
                   "precision_w": round(a["precision_w"], 6),
                   "recall_w": round(a["recall_w"], 6)}
            if sc is not None:
                b = sc.score(pred)
                row["dti_concealed"] = round(b["dti"], 6)
                row["recall_concealed"] = round(b["recall_w"], 6)
                row["n_hidden_concealed"] = sc.n_truth
            results.append(row)

    # ---------------- coverage-matched random controls -------------------
    print("--- coverage-matched random controls ---")
    rng = np.random.default_rng(12345)
    noise_rankers = [Ranker(rng.random(valid.shape).astype(np.float32))
                     for _ in range(3)]
    for cov in COVERAGES:
        n = int(cov * n_valid)
        for i, rk in enumerate(noise_rankers):
            evaluate(f"CTRL_random|cov{cov}|rep{i}", "control_random",
                     lambda f, rk=rk, n=n: rk.topk(f.eval_mask.ravel(), n),
                     FOLDS5)
    control_scores = defaultdict(list)
    for r in results:
        if r["family"] == "control_random":
            control_scores[(float(r["tag"].split("|")[1][3:]),
                            r["fold"])].append(r["dti"])
    random_control_dti_by_cov_fold = {
        k: float(np.mean(v)) for k, v in control_scores.items()
    }
    print("    same-run random-control DTI by coverage:")
    for cov in COVERAGES:
        vals = [v for (c, _), v in random_control_dti_by_cov_fold.items()
                if c == cov]
        print(f"      cov={cov:<6} mean control DTI={np.mean(vals):.4f}")

    st = ndi.generate_binary_structure(2, 2)
    for k in (1, 2):
        evaluate(f"CTRL_catalogue_dilate_{k}px", "control",
                 lambda f, k=k: (ndi.binary_dilation(f.visible, st, iterations=k)
                                 & f.eval_mask), FOLDS5)

    for p in sorted(SCORED.glob("*.tif")):
        with rasterio.open(p) as src:
            a = np.nan_to_num(src.read(1).astype(np.float32), nan=0.0)
        evaluate(f"PRIOR_{p.stem}", "prior_submission",
                 lambda f, arr=np.clip(np.where(valid, a, 0), 0, 1): arr, FOLDS5)
        del a

    # ---------------- detector sweep --------------------------------------
    print(f"--- detector sweep ({time.time()-t0:.0f}s) ---")
    names = [p.stem for p in sorted(DER.glob("*.npy"))
             if not p.stem.startswith("_") and p.stem != "HD_strain_raw"]
    for name in names:
        s = np.load(DER / f"{name}.npy")
        rk = Ranker(s)
        for cov in COVERAGES:
            n = int(cov * n_valid)
            for sp in SPACINGS:
                def build(f, rk=rk, n=n, sp=sp, s=s):
                    m = rk.topk(f.eval_mask.ravel(), n)
                    return D.decimate_grid(m, s, sp) if sp > 1 else m
                evaluate(f"{name}|cov{cov}|sp{sp}", name, build, FOLDS5)
        del s, rk
        print(f"    {name} ({time.time()-t0:.0f}s)")

    hd = np.load(DER / "HD_strain_raw.npy")
    for cov in COVERAGES:
        n = int(cov * n_valid)
        for sp in SPACINGS:
            def build(f, n=n, sp=sp, hd=hd):
                kd = D.robust_norm(ndi.gaussian_filter(
                    f.visible.astype(np.float32), 6.0))
                s = np.clip(hd - 0.5 * kd, 0, 1)
                m = Ranker(s).topk(f.eval_mask.ravel(), n)
                return D.decimate_grid(m, s, sp) if sp > 1 else m
            evaluate(f"HD_strain|cov{cov}|sp{sp}", "HD_strain", build, FOLDS5)
    print(f"    HD_strain ({time.time()-t0:.0f}s)")

    # ---------------- direct-DTI screening, then confirmation -------------
    by_tag_rule: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list))
    for r in results:
        if r["family"] in ("control", "control_random", "prior_submission"):
            continue
        by_tag_rule[r["tag"]][r["rule"]].append(float(r["dti"]))

    ranked = []
    for tag, by_rule in by_tag_rule.items():
        per_rule = [float(np.mean(values)) for values in by_rule.values()]
        if per_rule:
            ranked.append((min(per_rule), float(np.mean(per_rule)), tag))
    ranked.sort(key=lambda row: (-row[0], -row[1], row[2]))
    survivors = [tag for _, _, tag in ranked[:8]]
    print(f"--- stage 2, shortlisted by worst-rule DTI: {survivors} "
          f"({time.time()-t0:.0f}s)")

    allf = [f.name for f in folds]
    for tag in survivors:
        fam, covs, sps = tag.split("|")
        cov, sp = float(covs[3:]), int(sps[2:])
        n = int(cov * n_valid)
        if fam == "HD_strain":
            hdm = np.load(DER / "HD_strain_raw.npy")

            def build(f, n=n, sp=sp, hdm=hdm):
                kd = D.robust_norm(ndi.gaussian_filter(
                    f.visible.astype(np.float32), 6.0))
                s = np.clip(hdm - 0.5 * kd, 0, 1)
                m = Ranker(s).topk(f.eval_mask.ravel(), n)
                return D.decimate_grid(m, s, sp) if sp > 1 else m
        else:
            s = np.load(DER / f"{fam}.npy")
            rk = Ranker(s)

            def build(f, rk=rk, n=n, sp=sp, s=s):
                m = rk.topk(f.eval_mask.ravel(), n)
                return D.decimate_grid(m, s, sp) if sp > 1 else m
        evaluate(tag, f"STAGE2:{fam}", build, allf)
        for i, rk2 in enumerate(noise_rankers[:1]):
            evaluate(f"CTRL_random|cov{cov}|rep{i}", "STAGE2:control_random",
                     lambda f, rk2=rk2, n=n: rk2.topk(f.eval_mask.ravel(), n), allf)

    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "scorer_verification": v,
           "grid": {"valid_px": n_valid, "known_fault_px": int(known.sum())},
           "concealed_zone": {
               "slope_percentile": 33.0, "threshold": float(thr),
               "n_px": int(concealed_zone.sum()),
               "catalogue_px_inside": int((known & concealed_zone).sum())},
           "folds": [{"name": f.name, "rule": f.rule, "n_hidden": f.n_hidden,
                      "n_visible": f.n_visible,
                      "n_eval_px": int(f.eval_mask.sum()), **f.meta}
                     for f in folds],
           "coverages": COVERAGES, "spacings": SPACINGS,
           "stage2_shortlist_metric": "worst_rule_mean_dti",
           "random_control_dti_by_cov_fold": {
               f"{k[0]}|{k[1]}": round(v2, 6)
               for k, v2 in random_control_dti_by_cov_fold.items()
           },
           "results": results, "runtime_s": round(time.time() - t0, 1)}
    (REP / "holdout_v2.json").write_text(json.dumps(out, indent=2))
    print(f"wrote {REP/'holdout_v2.json'} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
