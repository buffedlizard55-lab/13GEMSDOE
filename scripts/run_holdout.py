#!/usr/bin/env python3
"""Hide-and-recover holdout evaluation + geometry optimisation.

Stage 1  coarse sweep: every detector x coverage x line-spacing, on one fold
         per withholding rule.
Stage 2  confirmation: the surviving candidates on EVERY fold, so that a
         candidate winning under only one rule is visibly flagged as fragile.

Also scores, on the same folds:
  * the catalogue-dilation family this team has been submitting;
  * a uniform-random control at matched coverage;
  * our eight previously-leaderboard-scored submissions (with a leak caveat).

Writes reports/holdout_results.json and reports/holdout_summary.md.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import detectors as D            # noqa: E402
from gems.fastscore import FoldScorer, verify_against_reference  # noqa: E402
from gems.holdout import build_folds       # noqa: E402
from gems.metric import marginal_precision_threshold  # noqa: E402

DER = ROOT / "data" / "derived"
SCORED = ROOT / "data" / "scored"
REP = ROOT / "reports"
REP.mkdir(exist_ok=True)

COVERAGES = [0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12]
SPACINGS = [1, 2, 3, 4]
STAGE1_FOLDS = ["random_0", "short_0", "isolated_0", "strike_60_120", "dense_0"]


def topk_mask(score: np.ndarray, allowed: np.ndarray, n: int) -> np.ndarray:
    """Highest-scoring `n` pixels among `allowed`."""
    flat = np.where(allowed, score, -np.inf).ravel()
    n = min(n, int(np.isfinite(flat).sum()))
    if n <= 0:
        return np.zeros(score.shape, dtype=bool)
    idx = np.argpartition(flat, -n)[-n:]
    out = np.zeros(flat.size, dtype=bool)
    out[idx] = True
    return out.reshape(score.shape)


def main() -> None:
    t0 = time.time()
    v = verify_against_reference(trials=15)
    assert v["pass"], v
    print(f"fast scorer verified against reference metric: {v['max_err']}")

    valid = np.load(DER / "_valid.npy")
    known = np.load(DER / "_known.npy")
    n_valid = int(valid.sum())
    print(f"grid: {valid.shape}  valid={n_valid:,}  known faults={int(known.sum()):,}")

    dets = {p.stem: p for p in sorted(DER.glob("*.npy"))
            if not p.stem.startswith("_")}
    print(f"detectors: {list(dets)}")

    # orientation field for strike-aware decimation (from the topo baseline)
    print("computing orientation field for strike-aware decimation ...")
    _, ORI = D.ridge_strength(np.load(DER / "BASE_topo_ridge.npy"), 1.5)

    print("building folds ...")
    folds = build_folds(known, valid, n_folds=2, hide_frac=0.25)
    fold_by_name = {f.name: f for f in folds}
    print(f"  {len(folds)} folds: " + ", ".join(
        f"{f.name}({f.n_hidden:,}px)" for f in folds))

    scorers: dict[str, FoldScorer] = {}

    def scorer(fname: str) -> FoldScorer:
        if fname not in scorers:
            f = fold_by_name[fname]
            scorers[fname] = FoldScorer.build(f.hidden, f.eval_mask)
        return scorers[fname]

    results: list[dict] = []

    def evaluate(tag: str, family: str, build_pred, fold_names) -> None:
        for fn in fold_names:
            f = fold_by_name[fn]
            pred = build_pred(f)
            s = scorer(fn).score(pred)
            results.append({"tag": tag, "family": family, "fold": fn,
                            "rule": f.rule, "n_hidden": f.n_hidden,
                            **{k: (round(vv, 6) if isinstance(vv, float) else vv)
                               for k, vv in s.items()},
                            "n_pred_px": int(pred.sum()) if pred.dtype == bool
                            else int((pred > 0).sum())})

    # ------------------------------------------------------------------
    # CONTROLS
    # ------------------------------------------------------------------
    print("\n--- controls ---")
    st = ndi.generate_binary_structure(2, 2)
    for k in (1, 2, 3):
        evaluate(f"CTRL_catalogue_dilate_{k}px", "control",
                 lambda f, k=k: (ndi.binary_dilation(f.visible, st, iterations=k)
                                 & ~f.visible & f.eval_mask).astype(np.float32),
                 STAGE1_FOLDS)
    rng = np.random.default_rng(0)
    for cov in (0.01, 0.03):
        noise = rng.random(valid.shape).astype(np.float32)
        evaluate(f"CTRL_random_cov{cov}", "control",
                 lambda f, c=cov, nz=noise: topk_mask(
                     nz, f.eval_mask, int(c * n_valid)).astype(np.float32),
                 STAGE1_FOLDS)
    evaluate("CTRL_all_ones", "control",
             lambda f: f.eval_mask.astype(np.float32), STAGE1_FOLDS)

    # previously scored submissions (leak caveat: built with FULL catalogue)
    print("--- previously leaderboard-scored submissions ---")
    for p in sorted(SCORED.glob("*.tif")):
        with rasterio.open(p) as src:
            a = np.nan_to_num(src.read(1).astype(np.float32), nan=0.0)
        a = np.clip(np.where(valid, a, 0.0), 0, 1)
        evaluate(f"PRIOR_{p.stem}", "prior_submission",
                 lambda f, arr=a: arr, STAGE1_FOLDS)

    # ------------------------------------------------------------------
    # STAGE 1 : coarse sweep
    # ------------------------------------------------------------------
    print(f"\n--- stage 1 sweep ({time.time()-t0:.0f}s) ---")
    for name, path in dets.items():
        s = np.load(path)
        if name == "HD_strain_raw":
            continue  # needs per-fold catalogue term; handled below
        for cov in COVERAGES:
            n = int(cov * n_valid)
            for sp in SPACINGS:
                def build(f, s=s, n=n, sp=sp):
                    m = topk_mask(s, f.eval_mask, n)
                    if sp > 1:
                        m = D.decimate_along_strike(m, ORI, sp)
                    return m.astype(np.float32)
                evaluate(f"{name}|cov{cov}|sp{sp}", name, build, STAGE1_FOLDS)
        del s
        print(f"    {name} done ({time.time()-t0:.0f}s)")

    # H-D needs the visible catalogue density per fold
    hd = np.load(DER / "HD_strain_raw.npy")
    for cov in COVERAGES:
        n = int(cov * n_valid)
        for sp in SPACINGS:
            def build(f, n=n, sp=sp, hd=hd):
                kd = D.robust_norm(ndi.gaussian_filter(
                    f.visible.astype(np.float32), 6.0))
                s = np.clip(hd - 0.5 * kd, 0, 1)
                m = topk_mask(s, f.eval_mask, n)
                if sp > 1:
                    m = D.decimate_along_strike(m, ORI, sp)
                return m.astype(np.float32)
            evaluate(f"HD_strain|cov{cov}|sp{sp}", "HD_strain", build,
                     STAGE1_FOLDS)
    print(f"    HD_strain done ({time.time()-t0:.0f}s)")

    # ------------------------------------------------------------------
    # FUSION of the best per-family detectors (rank mean)
    # ------------------------------------------------------------------
    print(f"\n--- fusion ({time.time()-t0:.0f}s) ---")
    by_family: dict[str, float] = {}
    for r in results:
        if r["family"] in ("control", "prior_submission"):
            continue
        by_family[r["family"]] = max(by_family.get(r["family"], 0.0), r["dti"])
    top_families = [f for f, _ in sorted(by_family.items(),
                                         key=lambda kv: -kv[1])[:4]]
    print(f"    top families: {top_families}")

    def rankmap(a: np.ndarray, m: np.ndarray) -> np.ndarray:
        out = np.zeros(a.shape, dtype=np.float32)
        vals = a[m]
        order = np.argsort(np.argsort(vals)).astype(np.float32)
        out[m] = order / max(len(vals) - 1, 1)
        return out

    fus_parts = [np.load(DER / f"{f}.npy") for f in top_families
                 if (DER / f"{f}.npy").exists()]
    if len(fus_parts) >= 2:
        fused = np.mean([rankmap(a, valid) for a in fus_parts], axis=0)
        np.save(DER / "FUSION_rankmean.npy", fused.astype(np.float32))
        for cov in COVERAGES:
            n = int(cov * n_valid)
            for sp in SPACINGS:
                def build(f, s=fused, n=n, sp=sp):
                    m = topk_mask(s, f.eval_mask, n)
                    if sp > 1:
                        m = D.decimate_along_strike(m, ORI, sp)
                    return m.astype(np.float32)
                evaluate(f"FUSION_rankmean|cov{cov}|sp{sp}", "FUSION_rankmean",
                         build, STAGE1_FOLDS)
        del fus_parts, fused

    # ------------------------------------------------------------------
    # STAGE 2 : confirm survivors on EVERY fold
    # ------------------------------------------------------------------
    print(f"\n--- stage 2 confirmation ({time.time()-t0:.0f}s) ---")
    mean_by_tag: dict[str, list[float]] = {}
    for r in results:
        if r["family"] in ("control", "prior_submission"):
            continue
        mean_by_tag.setdefault(r["tag"], []).append(r["dti"])
    ranked = sorted(mean_by_tag.items(), key=lambda kv: -float(np.mean(kv[1])))
    survivors = [t for t, _ in ranked[:6]]
    print(f"    survivors: {survivors}")

    all_folds = [f.name for f in folds]
    stage2: list[dict] = []
    for tag in survivors:
        fam, covs, sps = tag.split("|")
        cov = float(covs[3:]); sp = int(sps[2:])
        n = int(cov * n_valid)
        src = (DER / f"{fam}.npy")
        if fam == "HD_strain":
            hdm = np.load(DER / "HD_strain_raw.npy")

            def build(f, n=n, sp=sp, hdm=hdm):
                kd = D.robust_norm(ndi.gaussian_filter(
                    f.visible.astype(np.float32), 6.0))
                m = topk_mask(np.clip(hdm - 0.5 * kd, 0, 1), f.eval_mask, n)
                return (D.decimate_along_strike(m, ORI, sp) if sp > 1
                        else m).astype(np.float32)
        else:
            s = np.load(src)

            def build(f, s=s, n=n, sp=sp):
                m = topk_mask(s, f.eval_mask, n)
                return (D.decimate_along_strike(m, ORI, sp) if sp > 1
                        else m).astype(np.float32)
        before = len(results)
        evaluate(tag, f"STAGE2:{fam}", build, all_folds)
        stage2.extend(results[before:])

    # also run the strongest control on every fold for a fair comparison
    evaluate("CTRL_catalogue_dilate_2px", "STAGE2:control",
             lambda f: (ndi.binary_dilation(f.visible, st, iterations=2)
                        & ~f.visible & f.eval_mask).astype(np.float32),
             all_folds)

    # ------------------------------------------------------------------
    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fast_scorer_verification": v,
        "grid": {"valid_px": n_valid, "known_fault_px": int(known.sum())},
        "folds": [{"name": f.name, "rule": f.rule, "n_hidden": f.n_hidden,
                   "n_visible": f.n_visible, **f.meta} for f in folds],
        "coverages": COVERAGES, "spacings": SPACINGS,
        "results": results,
        "runtime_s": round(time.time() - t0, 1),
    }
    (REP / "holdout_results.json").write_text(json.dumps(out, indent=2))
    print(f"\nwrote {REP/'holdout_results.json'}  ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
