#!/usr/bin/env python3
"""A/B test of the ONE new geometric idea in the `ranked` recipe.

Claim under test
----------------
`TP_w` takes a MAX over the 300 m neighbourhood, so two predicted pixels within
3 px of each other earn one credit and pay two false-positive masses. Every
earlier recipe in this repo (`composite`, `composite_plus`, `r6`) unions several
components and decimates each component SEPARATELY, which leaves pixels from
different components within 3 px of each other. Decimating the UNION once,
globally, removes that waste.

This script builds both maps from the same components on the same folds and
scores both. If global decimation does not win on the holdout, the `ranked`
recipe is not shipped -- that is the standing rule.

Protocol
--------
Same folds as `scripts/run_holdout3.py` (seed 20260928, whole systems withheld
with a 500 m buffer, five withholding rules), same coverage-matched random
control, same closed-form chance DTI at the ACTUAL pixel count, same concealed
subset.
"""
from __future__ import annotations

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
from chance_baseline import dti_chance                 # noqa: E402

DER = ROOT / "data" / "derived"
REP = ROOT / "reports"
FEATS = ROOT / "data" / "raw" / "gems-geodawn-numerical-features.tif"

COVERAGES = [0.01, 0.02, 0.03, 0.05, 0.08]
SPACINGS = [1, 2, 3]
FOLDS5 = ["random_0", "short_0", "isolated_0", "strike_60_120", "dense_0"]
BUDGETS = [0.02, 0.03, 0.05, 0.08]

# components shared by both arms of the test
TOPK_COMPONENTS = ["BASE_topo_ridge", "HB_tdr_rtp", "HC_hinge", "BASE_tmi_hg"]


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


def main() -> None:
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

    folds = build_folds(known, valid, n_folds=2, hide_frac=0.25)
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

    def evaluate(tag, family, build_pred, fold_names):
        for fn in fold_names:
            f = fold_by_name[fn]
            pred = build_pred(f)
            sf, sc = scorers(fn)
            r = sf.score(pred)
            row = {"tag": tag, "family": family, "fold": fn, "rule": f.rule,
                   "n_hidden": f.n_hidden, "n_pred_px": int((pred > 0).sum()),
                   "dti": round(r["dti"], 6),
                   "precision_w": round(r["precision_w"], 6),
                   "recall_w": round(r["recall_w"], 6)}
            if sc is not None:
                b = sc.score(pred)
                row["dti_concealed"] = round(b["dti"], 6)
                row["n_hidden_concealed"] = sc.n_truth
            results.append(row)

    # ---------------- controls ----------------
    rng = np.random.default_rng(12345)
    noise = Ranker(rng.random(valid.shape).astype(np.float32))
    for cov in COVERAGES:
        n = int(cov * n_valid)
        evaluate(f"CTRL_random|cov{cov}", "control_random",
                 lambda f, n=n: noise.topk(f.eval_mask.ravel(), n), FOLDS5)
    chance = defaultdict(list)
    for r in results:
        if r["family"] == "control_random":
            chance[(float(r["tag"].split("|")[1][3:]), r["fold"])].append(r["dti"])
    chance_mean = {k: float(np.mean(v)) for k, v in chance.items()}

    # ---------------- components ----------------
    print(f"--- loading components ({time.time()-t0:.0f}s) ---")
    comp_scores: dict[str, np.ndarray] = {}
    for c in TOPK_COMPONENTS:
        p = DER / f"{c}.npy"
        if p.exists():
            comp_scores[c] = np.load(p)
    print(f"    {sorted(comp_scores)}")

    # ---------------- arm A: per-component decimation (the OLD way) ----------
    print(f"--- arm A: per-component decimation ({time.time()-t0:.0f}s) ---")
    for cov in COVERAGES:
        n = int(cov * n_valid)
        for sp in SPACINGS:
            def build_a(f, n=n, sp=sp):
                allowed = f.eval_mask
                union = np.zeros(valid.shape, dtype=bool)
                for c, s in comp_scores.items():
                    m = Ranker(s).topk(allowed.ravel(), n)
                    union |= (D.decimate_grid(m, s, sp) if sp > 1 else m)
                return union
            evaluate(f"A_percomponent|cov{cov}|sp{sp}", "A_percomponent",
                     build_a, FOLDS5)
        print(f"    cov={cov} ({time.time()-t0:.0f}s)")

    # ---------------- arm B: global priority union (the NEW way) -------------
    print(f"--- arm B: global priority union ({time.time()-t0:.0f}s) ---")
    pri = {"extension_rays": 1.0, "horsetail_splay": 0.9}
    for c in TOPK_COMPONENTS:
        pri[c] = 0.5
    _geo: dict[str, tuple] = {}

    def geo(f):
        """extension_rays / horsetail_splay are fold-only; build them once."""
        if f.name not in _geo:
            _geo[f.name] = (
                D.extension_rays(f.visible, reach_px=20),
                D.horsetail_splay(f.visible, max_gap_px=20, splay_len_px=12))
            gc.collect()
        return _geo[f.name]

    for budget in BUDGETS:
        for sp in SPACINGS:
            def build_b(f, budget=budget, sp=sp):
                allowed = valid & ~f.visible
                rays, horse = geo(f)
                score = np.zeros(valid.shape, dtype=np.float32)
                for name, s in (("extension_rays", rays),
                                ("horsetail_splay", horse)):
                    np.maximum(score,
                               np.where(allowed,
                                        D.robust_norm_nonzero(s) * pri[name],
                                        0.0),
                               out=score)
                for c, s in comp_scores.items():
                    np.maximum(score,
                               np.where(allowed,
                                        D.robust_norm_nonzero(s) * pri[c], 0.0),
                               out=score)
                nb = int(budget * n_valid)
                flat = np.where(allowed, score, -np.inf).ravel()
                nb = min(nb, int(np.isfinite(flat).sum()))
                thr_ = np.partition(flat, -nb)[-nb]
                m = (score >= max(thr_, 0.0)) & allowed
                return D.decimate_grid(m, score, sp) if sp > 1 else m
            evaluate(f"B_globalunion|budget{budget}|sp{sp}", "B_globalunion",
                     build_b, FOLDS5)
        print(f"    budget={budget} ({time.time()-t0:.0f}s)")

    hidden_by_fold = {f.name: f.n_hidden for f in folds}

    def lift(r, key="dti"):
        g = (hidden_by_fold[r["fold"]] if key == "dti"
             else r.get("n_hidden_concealed"))
        if not g:
            return None
        c = dti_chance(r["n_pred_px"], g, n_valid)
        return r[key] / c if c > 0 else None

    agg = defaultdict(lambda: {"lift": [], "lift_c": [], "dti": [], "px": [],
                               "rules": defaultdict(list)})
    for r in results:
        if r["family"] in ("control_random",):
            continue
        L = lift(r)
        if L is None:
            continue
        a = agg[r["tag"]]
        a["lift"].append(L)
        a["dti"].append(r["dti"])
        a["px"].append(r["n_pred_px"])
        a["rules"][r["rule"]].append(L)
        Lc = lift(r, "dti_concealed")
        if Lc is not None:
            a["lift_c"].append(Lc)
        a["family"] = r["family"]

    table = []
    for tag, a in agg.items():
        per_rule = {k: float(np.mean(x)) for k, x in a["rules"].items()}
        table.append({"tag": tag, "family": a["family"],
                      "mean_lift": float(np.mean(a["lift"])),
                      "worst_rule_lift": float(min(per_rule.values())),
                      "mean_lift_concealed": (float(np.mean(a["lift_c"]))
                                              if a["lift_c"] else None),
                      "mean_dti": float(np.mean(a["dti"])),
                      "median_px": int(np.median(a["px"])),
                      "per_rule_lift": {k: round(x, 4) for k, x in per_rule.items()}})
    table.sort(key=lambda z: -z["worst_rule_lift"])

    best_a = max((t for t in table if t["family"] == "A_percomponent"),
                 key=lambda z: z["worst_rule_lift"], default=None)
    best_b = max((t for t in table if t["family"] == "B_globalunion"),
                 key=lambda z: z["worst_rule_lift"], default=None)

    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scorer_verification": v,
        "question": ("does ONE global decimation of the union beat decimating "
                     "each component separately?"),
        "grid": {"valid_px": n_valid, "known_fault_px": int(known.sum())},
        "concealed_zone": {"slope_percentile": 33.0, "threshold": float(thr),
                           "n_px": int(concealed_zone.sum()),
                           "catalogue_px_inside": int((known & concealed_zone).sum())},
        "folds": [{"name": f.name, "rule": f.rule, "n_hidden": f.n_hidden,
                   "n_visible": f.n_visible} for f in folds],
        "budgets": BUDGETS, "coverages": COVERAGES, "spacings": SPACINGS,
        "normalisation_note": (
            "arm B normalises every source with robust_norm_nonzero, NOT "
            "robust_norm. Measured: robust_norm silently returns an all-zero "
            "array for any field more than 99% zeros, which erased "
            "extension_rays (0.1% nonzero) and HC_hinge (0.98% nonzero) from "
            "the first run of this script. That run's numbers are void."),
        "best_A_percomponent": best_a, "best_B_globalunion": best_b,
        "global_wins": bool(best_b and best_a and
                            best_b["worst_rule_lift"] > best_a["worst_rule_lift"]),
        "table": table, "results": results,
        "runtime_s": round(time.time() - t0, 1)}
    (REP / "ranked_ab.json").write_text(json.dumps(out, indent=1))

    print("\n=== best per arm, by WORST-RULE lift over chance ===")
    for lbl, t in (("A per-component (old)", best_a),
                   ("B global union (new)", best_b)):
        if t is None:
            continue
        lc = (f"{t['mean_lift_concealed']:.3f}"
              if t["mean_lift_concealed"] is not None else "-")
        print(f"  {lbl:24s} {t['tag']:34s} lift={t['mean_lift']:.3f} "
              f"worst={t['worst_rule_lift']:.3f} concealed={lc} "
              f"px={t['median_px']:,}")
    print(f"\n  GLOBAL DECIMATION WINS: {out['global_wins']}")
    print(f"wrote {REP/'ranked_ab.json'} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
