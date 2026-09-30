#!/usr/bin/env python3
"""Hide-and-recover holdout, v3 -- adds the R7 hypotheses and closes two leaks.

What changed and why
--------------------
1. **Catalogue-dependent detectors are rebuilt per fold.** In v1/v2 the
   catalogue-derived maps (`HD_strain_raw`'s fault-density term, `R6_horse_full`)
   were cached globally and `R6_horse_full` was swept as if it were a physical
   detector. `R6_horse_full` is built from the FULL catalogue, including the
   segments a fold withholds, so sweeping it leaks the answer. v3 keeps a
   per-fold build hook (`CATALOGUE_DETECTORS`) and only ever evaluates a
   catalogue-dependent map built from that fold's VISIBLE catalogue.
   `R7_grain_full` is likewise submission-only and is never swept.

2. **Lift is measured at the ACTUAL predicted pixel count.** Decimation can cut
   a map's mass by up to 9x, so comparing a decimated map against a
   full-coverage random control is not a comparison. Chance is evaluated at
   `n_pred_px` for every row (closed form, validated against the empirical
   random controls in the same run).

3. **Every candidate is reported on the CONCEALED subset too** -- the withheld
   pixels with the weakest topographic expression, which is the closest
   available analogue to the genuinely unmapped population (see
   knowledge/02_irregularities.md I-10).

4. **Worst-rule, not mean.** A candidate that wins under one withholding rule
   is fragile and is reported as such.

Scoring mirrors the organizers exactly: the VISIBLE catalogue is masked
pixel-exactly (forum 11516 post 4), everything else inside the footprint can
accrue FP_w, and DTI is computed on the withheld pixels alone.
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import gc
from collections import OrderedDict

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gems import detectors as D                        # noqa: E402
from gems.fastscore import FoldScorer, verify_against_reference  # noqa: E402
from gems.holdout import build_folds                   # noqa: E402
from chance_baseline import dti_chance                 # noqa: E402

DER = ROOT / "data" / "derived"
SCORED = ROOT / "data" / "scored"
REP = ROOT / "reports"
FEATS = ROOT / "data" / "raw" / "gems-geodawn-numerical-features.tif"

COVERAGES = [0.005, 0.01, 0.02, 0.03, 0.05, 0.08]
SPACINGS = [1, 2, 3]
FOLDS5 = ["random_0", "short_0", "isolated_0", "strike_60_120", "dense_0"]

# Detectors that read the catalogue. These are NEVER swept from cache; each is
# rebuilt for every fold from that fold's visible catalogue.
CATALOGUE_DETECTORS = {
    "HD_strain": "geodetic strain residual, visible-catalogue term per fold",
    "R7_grain": "R7-5 structural grain, visible-catalogue blindness per fold",
}


class Ranker:
    """Precomputed global ranking of a score map -> fast masked top-k."""

    def __init__(self, score: np.ndarray):
        self.shape = score.shape
        # int32: 12.3M cells fit comfortably and it halves the footprint versus
        # numpy's default int64 index array.
        self.order = np.argsort(-np.asarray(score).ravel(),
                                kind="stable").astype(np.int32)

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

    with rasterio.open(FEATS) as src:
        desc = list(src.descriptions)
        bidx = [i for i, d in enumerate(desc, 1)
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
    del slope
    gc.collect()

    folds = build_folds(known, valid, n_folds=2, hide_frac=0.25)
    fold_by_name = {f.name: f for f in folds}
    print(f"{len(folds)} folds built ({time.time()-t0:.0f}s)")

    # bands needed by the per-fold catalogue detectors
    with rasterio.open(FEATS) as src:
        geod2 = src.read(4).astype(np.float32)
        ieq = src.read(16).astype(np.float32)
        rtp = src.read(2).astype(np.float32)

    # FoldScorer caches a full-grid float32 FP-weight map (~49 MB) per fold, and
    # there are two of them per fold. On a 3 GB box an unbounded cache is an OOM
    # kill (it killed this script once), so scorers are held in a small LRU and
    # rebuilt on demand -- a rebuild is ~25 array shifts, well under a second.
    _SC_CACHE: "OrderedDict[str, tuple]" = OrderedDict()
    _SC_MAX = 3

    def scorers(fn):
        if fn in _SC_CACHE:
            _SC_CACHE.move_to_end(fn)
            return _SC_CACHE[fn]
        f = fold_by_name[fn]
        sf = FoldScorer.build(f.hidden, f.eval_mask)
        hc = f.hidden & concealed_zone
        sc = (FoldScorer.build(hc, f.eval_mask) if hc.sum() > 50 else None)
        _SC_CACHE[fn] = (sf, sc)
        while len(_SC_CACHE) > _SC_MAX:
            _SC_CACHE.popitem(last=False)
        gc.collect()
        return sf, sc

    results: list[dict] = []

    def evaluate(tag, family, build_pred, fold_names, stage="stage1"):
        for fn in fold_names:
            f = fold_by_name[fn]
            pred = build_pred(f)
            sf, sc = scorers(fn)
            a = sf.score(pred)
            row = {"tag": tag, "family": family, "fold": fn, "rule": f.rule,
                   "n_hidden": f.n_hidden, "n_pred_px": int((pred > 0).sum()),
                   "dti": round(a["dti"], 6),
                   "precision_w": round(a["precision_w"], 6),
                   "recall_w": round(a["recall_w"], 6), "stage": stage}
            if sc is not None:
                b = sc.score(pred)
                row["dti_concealed"] = round(b["dti"], 6)
                row["recall_concealed"] = round(b["recall_w"], 6)
                row["n_hidden_concealed"] = sc.n_truth
            results.append(row)

    def catalogue_map(f, name: str) -> np.ndarray:
        """Build a catalogue-dependent map from the VISIBLE catalogue only.

        Not cached across folds: each map is a full float32 grid (~49 MB) and
        its Ranker another ~98 MB of int64 indices, so holding one per fold per
        detector is ~1.5 GB. Callers hold exactly one at a time instead.
        """
        if name == "HD_strain":
            kd = ndi.gaussian_filter(f.visible.astype(np.float32), 6.0)
            return D.strain_residual(geod2, ieq, kd)
        if name == "R7_grain":
            return D.structural_grain(rtp, f.visible)
        raise KeyError(name)

    # ---------------- coverage-matched random controls -------------------
    print("--- coverage-matched random controls ---")
    rng = np.random.default_rng(12345)
    noise_rankers = [Ranker(rng.random(valid.shape).astype(np.float32))]
    for cov in COVERAGES:
        n = int(cov * n_valid)
        for i, rk in enumerate(noise_rankers):
            evaluate(f"CTRL_random|cov{cov}|rep{i}", "control_random",
                     lambda f, rk=rk, n=n: rk.topk(f.eval_mask.ravel(), n),
                     FOLDS5)
    chance = defaultdict(list)
    for r in results:
        if r["family"] == "control_random":
            chance[(float(r["tag"].split("|")[1][3:]), r["fold"])].append(r["dti"])
    chance_mean = {k: float(np.mean(v)) for k, v in chance.items()}
    for cov in COVERAGES:
        vals = [v for (c, _), v in chance_mean.items() if c == cov]
        print(f"      cov={cov:<6} chance DTI={np.mean(vals):.4f}")

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
    cached = sorted(p.stem for p in DER.glob("*.npy")
                    if not p.stem.startswith("_")
                    and p.stem != "HD_strain_raw"
                    and not p.stem.endswith("_full"))   # submission-only maps
    for name in cached:
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
        gc.collect()
        print(f"    {name} ({time.time()-t0:.0f}s)")

    # ---------------- per-fold catalogue-dependent detectors ---------------
    # One fold at a time: the map and its Ranker are ~150 MB together.
    for cname, desc in CATALOGUE_DETECTORS.items():
        print(f"    {cname} (per-fold, visible catalogue only) "
              f"({time.time()-t0:.0f}s)")
        for fn in FOLDS5:
            f = fold_by_name[fn]
            s = catalogue_map(f, cname)
            rk = Ranker(s)
            for cov in COVERAGES:
                n = int(cov * n_valid)
                for sp in SPACINGS:
                    def build(f=f, rk=rk, n=n, sp=sp, s=s):
                        m = rk.topk(f.eval_mask.ravel(), n)
                        return D.decimate_grid(m, s, sp) if sp > 1 else m
                    evaluate(f"{cname}|cov{cov}|sp{sp}", cname, build, [fn])
            del s, rk
            gc.collect()

    # ---------------- lift over chance, then confirm on all folds ---------
    hidden_by_fold = {f.name: f.n_hidden for f in folds}

    def lift(r, key="dti"):
        g = (hidden_by_fold[r["fold"]] if key == "dti"
             else r.get("n_hidden_concealed"))
        if not g:
            return None
        c = dti_chance(r["n_pred_px"], g, n_valid)
        return r[key] / c if c > 0 else None

    agg = defaultdict(list)
    for r in results:
        if r["family"] in ("control", "control_random", "prior_submission"):
            continue
        L = lift(r)
        if L is not None:
            agg[r["tag"]].append(L)
    ranked = sorted(((float(np.mean(v)), t) for t, v in agg.items()), reverse=True)
    survivors = [t for _, t in ranked[:10]]
    print(f"--- stage 2: {survivors} ({time.time()-t0:.0f}s)")

    allf = [f.name for f in folds]
    for tag in survivors:
        fam, covs, sps = tag.split("|")
        cov, sp = float(covs[3:]), int(sps[2:])
        n = int(cov * n_valid)
        if fam in CATALOGUE_DETECTORS:
            for fn in allf:
                f = fold_by_name[fn]
                s = catalogue_map(f, fam)
                rk = Ranker(s)

                def build(f=f, rk=rk, n=n, sp=sp, s=s):
                    m = rk.topk(f.eval_mask.ravel(), n)
                    return D.decimate_grid(m, s, sp) if sp > 1 else m
                evaluate(tag, f"STAGE2:{fam}", build, [fn], stage="stage2")
                del s, rk
                gc.collect()
            evaluate(f"CTRL_random|cov{cov}|rep0", "STAGE2:control_random",
                     lambda f, n=n: noise_rankers[0].topk(f.eval_mask.ravel(), n),
                     allf, stage="stage2")
            continue
        else:
            s = np.load(DER / f"{fam}.npy")
            rk = Ranker(s)

            def build(f, rk=rk, n=n, sp=sp, s=s):
                m = rk.topk(f.eval_mask.ravel(), n)
                return D.decimate_grid(m, s, sp) if sp > 1 else m
            evaluate(tag, f"STAGE2:{fam}", build, allf, stage="stage2")
            del s, rk
            gc.collect()
        evaluate(f"CTRL_random|cov{cov}|rep0", "STAGE2:control_random",
                 lambda f, n=n: noise_rankers[0].topk(f.eval_mask.ravel(), n),
                 allf, stage="stage2")
        evaluate(f"CTRL_random|cov{cov}|rep0", "STAGE2:control_random",
                 lambda f, n=n: noise_rankers[0].topk(f.eval_mask.ravel(), n),
                 allf, stage="stage2")

    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scorer_verification": v,
        "grid": {"valid_px": n_valid, "known_fault_px": int(known.sum())},
        "concealed_zone": {
            "slope_percentile": 33.0, "threshold": float(thr),
            "n_px": int(concealed_zone.sum()),
            "catalogue_px_inside": int((known & concealed_zone).sum())},
        "folds": [{"name": f.name, "rule": f.rule, "n_hidden": f.n_hidden,
                   "n_visible": f.n_visible, **f.meta} for f in folds],
        "coverages": COVERAGES, "spacings": SPACINGS,
        "catalogue_detectors_rebuilt_per_fold": CATALOGUE_DETECTORS,
        "chance_dti_by_cov_fold": {f"{k[0]}|{k[1]}": round(v2, 6)
                                   for k, v2 in chance_mean.items()},
        "results": results, "runtime_s": round(time.time() - t0, 1)}
    (REP / "holdout_v3.json").write_text(json.dumps(out, indent=2))
    print(f"wrote {REP/'holdout_v3.json'} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
