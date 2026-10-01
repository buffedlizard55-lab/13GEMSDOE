#!/usr/bin/env python3
"""R14 -- the coverage-budget curve, and which information source deserves it.

WHY THIS EXPERIMENT EXISTS
--------------------------
Two verified facts changed the plan for this repository.

1.  DrivenData staff (forum topic 11516, post 2, 2026-09-16, user `chrisk-dd`,
    flair `drivendata-staff`): *"Pixels corresponding to known USGS/INGENIOUS
    faults are masked / excluded from evaluation, so they do not count towards
    penalty terms"* and *"for scoring purposes it should not matter whether
    these known faults are included with predictions or not."*
    -> Mass placed exactly on the catalogue is score-neutral.  Mass placed
       NEAR the catalogue is not neutral: it is charged as FP unless a NEW
       fault is within 300 m.

2.  The official metric with alpha=0.2, beta=0.8 reduces to
        DTI = 1 / (0.2/P_w + 0.8/R_w)
    (proved in src/gems/metric.py).  So DTI is a *weighted F2*: recall is
    worth four times precision.  That makes the number of pixels predicted,
    and how they are spread, a first-order design variable -- not a detail.

Every submission this group has a public score for sits far from that optimum:
`gems7_halo15` predicted 1,828,699 px (35.4 % of the footprint) and scored
0.1461; `gemsdoe1_ens12` predicted 172,974 px (3.3 %) and scored 0.1563.
One is recall-rich and precision-poor, the other the reverse.  This script
measures the whole curve instead of two points.

WHAT IT MEASURES
----------------
On the repository's spatially-blocked hide-and-recover folds (visible catalogue
masked pixel-exactly, per fact 1), for a grid of predicted-pixel budgets K:

  lattice_sK          fault-blind square lattice, stride K (points, not lines)
  random_topK         fault-blind uniform random, K px
  halo_topK           rank by Euclidean distance to the VISIBLE catalogue,
                      ascending -- "new faults are continuations, stepovers and
                      parallel strands of mapped ones"
  topo_slope_topK     detrended-elevation slope (band 19), descending
  tmi_hgrad_topK      TMI horizontal gradient (band 3), descending
  grav_slope_topK     isostatic gravity anomaly slope (band 5), descending
  strain2_topK        geodetic second invariant of strain rate (band 4), desc.
  curvature_topK      max absolute second directional derivative of detrended
                      elevation over 8 directions (scarp/crest detector)

Each fold is also run with buffer_px = 5 (the repository default, which removes
visible catalogue within 500 m of the hidden truth and therefore penalises
near-catalogue strategies) AND buffer_px = 0 (no buffer: the realistic case,
because real new faults abut mapped ones with no gap).  Reporting both is the
robustness rule; a candidate that only wins at one buffer is fragile.

This is a LOCAL PROXY on known faults.  It is not a leaderboard prediction
(irregularities I-10, I-16).

Run:  python scripts/r14_budget_curve.py [--quick]
Out:  reports/r14_budget_curve.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems.fastscore import FoldScorer, verify_against_reference  # noqa: E402
from gems.holdout import build_folds                             # noqa: E402
from gems.metric import ALPHA, BETA                              # noqa: E402
from gems import rio                                              # noqa: E402

RAW = ROOT / "data" / "raw"
OUT = ROOT / "reports" / "r14_budget_curve.json"

# Budget grid as a fraction of the 5,167,373-pixel footprint.
K_FRACS = (0.005, 0.01, 0.02, 0.03, 0.04, 0.05, 0.0625, 0.08, 0.10, 0.125,
           0.15, 0.20, 0.25, 0.35, 0.50, 1.00)
LATTICE_STRIDES = (2, 3, 4, 5, 6, 7, 8, 10, 12)
SEED = 20261001

# band numbers read from the stack's own GDAL tags by scripts/prepare_data.py
B_TMI_HGRAD = 3
B_STRAIN2 = 4
B_GRAV_SLOPE = 5
B_DETREND_ELEV = 12
B_DETREND_SLOPE = 19
SENTINEL = np.float32(-3.4028235e38)


def read_band(path: Path, b: int) -> np.ndarray:
    """One band, float32, sentinel and NaN both mapped to NaN."""
    with rasterio.open(path) as s:
        a = s.read(b).astype(np.float32, copy=False)
    a[a <= SENTINEL] = np.nan
    return a


def max_abs_second_directional(elev: np.ndarray) -> np.ndarray:
    """|d^2 z / d s^2| maximised over 8 directions -- a scarp/crest detector.

    A fault scarp is a break in slope: the second derivative along the
    downslope direction changes sign across it.  Computed on a filled
    elevation surface, then normalised per-direction so that no single
    direction's units dominate the max.
    """
    z = np.where(np.isfinite(elev), elev, np.nan)
    med = float(np.nanmedian(z))
    z = np.where(np.isfinite(z), z, med).astype(np.float32)
    best = np.zeros(z.shape, np.float32)
    dirs = [(0, 1), (1, 0), (1, 1), (1, -1)]
    for dy, dx in dirs:
        c = z
        p1 = np.roll(np.roll(z, dy, axis=0), dx, axis=1)
        m1 = np.roll(np.roll(z, -dy, axis=0), -dx, axis=1)
        d2 = (p1 - 2.0 * c + m1)
        s = float(np.nanstd(d2)) or 1.0
        np.maximum(best, np.abs(d2) / s, out=best)
    return best


def rank_score(x: np.ndarray, higher_is_better: bool = True) -> np.ndarray:
    """Turn a possibly-NaN field into a dense rank score in [0, 1].

    NaN pixels get the worst rank (they carry no information), ties are broken
    deterministically by flat index so two runs give byte-identical output.
    """
    a = np.asarray(x, dtype=np.float64).ravel()
    nan = ~np.isfinite(a)
    if nan.all():
        return np.zeros(a.size, np.float32)
    fill = np.nanmin(a) if not higher_is_better else np.nanmax(a)
    a = np.where(nan, fill, a)
    if not higher_is_better:
        a = -a
    # rankdata would be O(n log n) with big temporaries; argsort of a
    # lexsort key is enough and deterministic
    order = np.argsort(a, kind="stable")
    r = np.empty(a.size, np.float32)
    r[order] = np.arange(a.size, dtype=np.float32)
    return r / np.float32(a.size - 1)


def topk_mask(flat_scores: np.ndarray, idx: np.ndarray, k: int,
              shape: tuple[int, int]) -> np.ndarray:
    """Dense bool mask of the k highest-scoring pixels among `idx`."""
    sub = flat_scores[idx]
    k = int(min(max(k, 0), sub.size))
    if k == 0:
        return np.zeros(shape, bool)
    if k >= sub.size:
        sel = idx
    else:
        part = np.argpartition(-sub, k - 1)[:k]
        sel = idx[part]
    m = np.zeros(shape[0] * shape[1], bool)
    m[sel] = True
    return m.reshape(shape)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="one fold per rule, buffer 5 only, coarser K grid")
    args = ap.parse_args()
    t0 = time.time()

    v = verify_against_reference(trials=10)
    if not v["pass"]:
        raise SystemExit(f"fast scorer disagrees with the reference metric: {v}")
    print(f"fast scorer verified against src/gems/metric.dti: {v}")

    with rasterio.open(rio.resolve_raw("labels", RAW)) as s:
        lab = s.read(1)
    valid = lab >= 0
    known = lab > 0
    shape = valid.shape
    n_valid = int(valid.sum())
    print(f"footprint {n_valid:,} px, catalogue {int(known.sum()):,} px")

    try:
        feats = rio.resolve_raw("features", RAW)
    except FileNotFoundError:
        feats = None
    geo: dict[str, np.ndarray] = {}
    if feats is not None and feats.exists():
        print("reading geophysical ranking layers ...")
        geo["topo_slope_topK"] = rank_score(read_band(feats, B_DETREND_SLOPE))
        geo["tmi_hgrad_topK"] = rank_score(read_band(feats, B_TMI_HGRAD))
        geo["grav_slope_topK"] = rank_score(read_band(feats, B_GRAV_SLOPE))
        geo["strain2_topK"] = rank_score(read_band(feats, B_STRAIN2))
        geo["curvature_topK"] = rank_score(
            max_abs_second_directional(read_band(feats, B_DETREND_ELEV)))
        for k in list(geo):
            print(f"  {k}: {geo[k].shape} float32")
    else:
        print("training_features.tif absent -- geophysical rankings skipped "
              "(run bash scripts/download_competition_data.sh)")

    k_fracs = (0.01, 0.02, 0.04, 0.0625, 0.10, 0.20, 0.35, 1.00) if args.quick else K_FRACS
    n_folds = 1 if args.quick else 3
    buffers = (5,) if args.quick else (5, 0)

    lattices = {}
    for s_ in LATTICE_STRIDES:
        m = np.zeros(shape, bool)
        m[::s_, ::s_] = True
        lattices[f"lattice_s{s_}"] = m
    rng = np.random.default_rng(SEED)
    rand_rank = rank_score(rng.random(shape, dtype=np.float32))

    rows: list[dict] = []
    for buffer_px in buffers:
        folds = build_folds(known, valid, n_folds=n_folds, hide_frac=0.25,
                            seed=SEED, link_px=8, buffer_px=buffer_px)
        print(f"\n== buffer_px={buffer_px}: {len(folds)} folds ==")
        for f in folds:
            ts = time.time()
            scorer = FoldScorer.build(f.hidden, f.eval_mask)
            idx = np.flatnonzero(f.eval_mask.ravel())
            n_eval = idx.size
            entries = []
            # one distance field per fold, reused for every budget
            halo_rank = rank_score(
                ndi.distance_transform_edt(~f.visible), higher_is_better=False)

            def record(name, pred, extra=None):
                sc = scorer.score(pred.astype(np.float32))
                sc.update({"map": name, "fold": f.name, "rule": f.rule,
                           "buffer_px": buffer_px,
                           "n_predicted_px": int((pred > 0).sum()),
                           "pct_of_footprint": round(100.0 * int((pred > 0).sum()) / n_valid, 4)})
                if extra:
                    sc.update(extra)
                entries.append(sc)

            for name, m in lattices.items():
                record(name, m & f.eval_mask,
                       {"family": "lattice", "budget_px": int((m & f.eval_mask).sum())})
            for frac in k_fracs:
                k = int(round(frac * n_valid))
                record(f"random_topK@{frac:g}", topk_mask(rand_rank, idx, k, shape),
                       {"family": "random", "budget_frac": frac, "budget_px": k})
                record(f"halo_topK@{frac:g}", topk_mask(halo_rank, idx, k, shape),
                       {"family": "halo", "budget_frac": frac, "budget_px": k})
                for gname, g in geo.items():
                    record(f"{gname}@{frac:g}", topk_mask(g, idx, k, shape),
                           {"family": gname, "budget_frac": frac, "budget_px": k})
            rows.extend(entries)
            print(f"  {f.name:22s} truth={f.n_hidden:6d} eval={n_eval:9,d} "
                  f"{len(entries)} maps in {time.time()-ts:.1f}s")
            del scorer, idx, entries

    # ---- aggregate -------------------------------------------------------
    fam_of = lambda n: n.split("@")[0]  # noqa: E731
    agg: dict[str, dict] = {}
    for r in rows:
        key = f"{r['map']}|buf{r['buffer_px']}"
        d = agg.setdefault(key, {"map": r["map"], "buffer_px": r["buffer_px"],
                                 "family": fam_of(r["map"]), "by_rule": {}, "folds": []})
        d["by_rule"].setdefault(r["rule"], []).append(r["dti"])
        d["folds"].append({"fold": r["fold"], "rule": r["rule"], "dti": r["dti"],
                           "precision_w": r["precision_w"], "recall_w": r["recall_w"],
                           "n_predicted_px": r["n_predicted_px"],
                           "pct_of_footprint": r["pct_of_footprint"]})
    for d in agg.values():
        d["dti_mean_all_folds"] = float(np.mean([f["dti"] for f in d["folds"]]))
        d["rule_means"] = {k: float(np.mean(v)) for k, v in sorted(d["by_rule"].items())}
        d["worst_rule_mean"] = float(min(d["rule_means"].values()))
        d["n_folds"] = len(d["folds"])
        d.pop("by_rule")

    # family budget curves: DTI vs pct_of_footprint, averaged over folds
    curves: dict[str, list] = {}
    for d in agg.values():
        fam = d["family"]
        curves.setdefault(fam, []).append({
            "map": d["map"], "buffer_px": d["buffer_px"],
            "pct_of_footprint_mean": float(np.mean([f["pct_of_footprint"] for f in d["folds"]])),
            "dti_mean": d["dti_mean_all_folds"], "worst_rule_mean": d["worst_rule_mean"],
            "precision_w_mean": float(np.mean([f["precision_w"] for f in d["folds"]])),
            "recall_w_mean": float(np.mean([f["recall_w"] for f in d["folds"]])),
        })
    for fam in curves:
        curves[fam].sort(key=lambda r: r["pct_of_footprint_mean"])

    best = max(agg.values(), key=lambda d: d["worst_rule_mean"])
    best_mean = max(agg.values(), key=lambda d: d["dti_mean_all_folds"])

    report = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "script": "scripts/r14_budget_curve.py",
        "quick": args.quick,
        "runtime_s": round(time.time() - t0, 1),
        "scorer_verification": v,
        "metric_identity": "DTI = 1/(alpha/P_w + beta/R_w), alpha=%.2f beta=%.2f" % (ALPHA, BETA),
        "grid": {"footprint_px": n_valid, "catalogue_px": int(known.sum()),
                 "shape": list(shape), "k_fracs": list(k_fracs),
                 "lattice_strides": list(LATTICE_STRIDES),
                 "buffer_px_variants": list(buffers), "n_folds_per_rule": n_folds},
        "verified_organiser_statement": {
            "quote": ("Pixels corresponding to known USGS/INGENIOUS faults are masked / "
                      "excluded from evaluation, so they do not count towards penalty terms."),
            "who": "chrisk-dd (DrivenData Staff)",
            "where": "https://community.drivendata.org/t/scoring-clarification-are-known-"
                     "usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-"
                     "round-label-set/11516/2",
            "when": "2026-09-16",
        },
        "best_by_worst_rule_mean": {k: best[k] for k in
                                    ("map", "buffer_px", "worst_rule_mean",
                                     "dti_mean_all_folds", "n_folds")},
        "best_by_fold_mean": {k: best_mean[k] for k in
                              ("map", "buffer_px", "worst_rule_mean",
                               "dti_mean_all_folds", "n_folds")},
        "curves": curves,
        "maps": {k: d for k, d in sorted(agg.items())},
        "proxy_caveat": ("Hide-and-recover on KNOWN faults. The leaderboard truth is faults "
                         "NOT in the catalogue, so the optimal budget measured here can only "
                         "be a guide (I-10, I-16). No number in this file is a leaderboard "
                         "prediction."),
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n")

    print("\n=== budget curves (worst-rule-mean DTI) ===")
    for fam, rs in sorted(curves.items()):
        print(f"\n{fam}")
        for r in rs:
            print(f"   buf{r['buffer_px']} {r['map']:28s} "
                  f"cov={r['pct_of_footprint_mean']:6.2f}%  "
                  f"P_w={r['precision_w_mean']:.4f} R_w={r['recall_w_mean']:.4f}  "
                  f"DTImean={r['dti_mean']:.5f}  worstRule={r['worst_rule_mean']:.5f}")
    print(f"\nBEST worst-rule-mean : {best['map']} (buf{best['buffer_px']}) "
          f"{best['worst_rule_mean']:.5f}")
    print(f"BEST fold-mean       : {best_mean['map']} (buf{best_mean['buffer_px']}) "
          f"{best_mean['dti_mean_all_folds']:.5f}")
    print(f"\nwrote {OUT.relative_to(ROOT)} in {report['runtime_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
