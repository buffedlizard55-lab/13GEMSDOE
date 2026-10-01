#!/usr/bin/env python3
"""Predeclared R13 hold-out validation (knowledge/09_r13_hypotheses.md).

Candidates (decision rule frozen in the register BEFORE this script was run):

  R13-1  local-contrast crest normalisation  (4 variants)
  R13-2  scale-persistent crest              (1 variant)
  R13-3  tile-quota regional budget          (2 variants)
  R13-4  paleo-geothermal feature halos      (3 block sizes; INGENIOUS GDR 1391)

Protocol is IDENTICAL to validate_r10/r11/r12_holdout.py (same folds, buffer, scorer,
tune/confirm split, spacing-3 decimation). None of the candidate maps reads the fault
catalogue, so no fold can leak.

Results are local hide-and-recover proxy measurements on KNOWN faults; they are not
leaderboard estimates (irregularity I-16).
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform as warp_transform
from scipy import ndimage as ndi
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gems import detectors as D                                   # noqa: E402
from gems.fastscore import FoldScorer, verify_against_reference    # noqa: E402
from gems.holdout import build_folds                              # noqa: E402
from gems.rio import load_footprint                               # noqa: E402
import validate_r10_holdout as R10                                # noqa: E402
import validate_r10b_holdout as R10B                              # noqa: E402

OUT_PATH = ROOT / "reports" / "holdout_r13_2026-10-01.json"
FEATS = ROOT / "data" / "raw" / "gems-geodawn-numerical-features.tif"
PALEO_CSV = (ROOT / "data" / "external_gdr1391" / "paleo_geothermal_regional"
             / "Paleo_geothermal_final.csv")

# ---- frozen constants (knowledge/09_r13_hypotheses.md) ----------------------
SPACING = R10.SPACING
BASE_COVERAGE = R10.BASE_COVERAGE
EXCLUDE_PX = 3                                # 300 m = metric kernel radius
GREEDY_R11_RECIPE = [("R10_vent", 0.0025), ("R8_tpi", 0.0025),
                     ("R10_dzt_field", 0.0025)]
LOC_ALPHAS = (0.5, 1.0)
LOC_SIGMAS = (10, 30)                         # px
LOC_EPS_FRAC = 0.05
PERSIST_SIGMAS = (1.0, 1.5, 2.5)
TILE_PX = 64
QUOTA_LAMBDAS = (0.5, 1.0)
PALEO_SIGMA_PX = 15                           # 1.5 km
PALEO_CUT_PX = 30                             # 3 km
PALEO_COVS = (0.001, 0.0025, 0.005)
PAIRED_MIN_WINS = 14
ARCHIVE_TOL_REL = 0.01


def far_from(mask: np.ndarray) -> np.ndarray:
    return ~ndi.binary_dilation(
        mask, structure=np.ones((2 * EXCLUDE_PX + 1,) * 2, bool))


def read_band(code: str) -> np.ndarray:
    with rasterio.open(FEATS) as src:
        idx = None
        for i, d in enumerate(src.descriptions, 1):
            if (d or f"b{i}").split(" - ")[0].strip() == code:
                idx = i
        if idx is None:
            raise SystemExit(f"band {code!r} not found in {FEATS.name}")
        a = src.read(idx).astype(np.float32)
        nd = src.nodatavals[idx - 1]
    if nd is not None:
        a = np.where(a <= nd + abs(nd) * 1e-6, np.nan, a)
    return np.where(np.isfinite(a), a, np.nan)


def finish(strength: np.ndarray, orient: np.ndarray,
           valid: np.ndarray) -> np.ndarray:
    """Same tail as build_detectors.BASE_topo_ridge: NMS thin -> robust_norm
    -> footprint mask."""
    arr = D.robust_norm(D.nms_thin(strength, orient))
    return np.where(valid, np.nan_to_num(arr, nan=0.0), 0.0).astype(np.float32)


def local_contrast(s: np.ndarray, valid: np.ndarray, sigma: float,
                   alpha: float) -> np.ndarray:
    v = valid.astype(np.float32)
    num = ndi.gaussian_filter(s * v, sigma, mode="constant")
    den = np.maximum(ndi.gaussian_filter(v, sigma, mode="constant"), 1e-6)
    local = num / den
    eps = LOC_EPS_FRAC * float(s[valid].mean())
    return (s / np.power(local + eps, alpha)).astype(np.float32)


def tile_quota(ref: np.ndarray, valid: np.ndarray, lam: float) -> np.ndarray:
    out = np.zeros(ref.shape, dtype=np.float32)
    gv = ref[valid]
    gp = np.zeros(ref.shape, dtype=np.float32)
    gp[valid] = (rankdata(gv) / gv.size).astype(np.float32)
    H, W = ref.shape
    for y0 in range(0, H, TILE_PX):
        for x0 in range(0, W, TILE_PX):
            sl = (slice(y0, y0 + TILE_PX), slice(x0, x0 + TILE_PX))
            m = valid[sl]
            if not m.any():
                continue
            t = np.zeros(m.shape, dtype=np.float32)
            vals = ref[sl][m]
            t[m] = (rankdata(vals) / vals.size).astype(np.float32)
            out[sl] = np.where(m, (1 - lam) * gp[sl] + lam * t, 0.0)
    return out


def paleo_halo(valid: np.ndarray, shape: tuple) -> tuple[np.ndarray, dict]:
    rows = list(csv.DictReader(open(PALEO_CSV, encoding="latin-1")))
    lon = np.array([float(r["Long_deg_NAD83"]) for r in rows])
    lat = np.array([float(r["Lat_deg_NAD83"]) for r in rows])
    x, y = warp_transform("EPSG:4269", "EPSG:32611", lon, lat)
    x, y = np.asarray(x), np.asarray(y)
    # grid constants from src/gems/rio.py (100 m, origin 243350 / 4508550)
    col = np.floor((x - 243350.0) / 100.0).astype(int)
    row = np.floor((4508550.0 - y) / 100.0).astype(int)
    ins = (row >= 0) & (row < shape[0]) & (col >= 0) & (col < shape[1])
    pts = np.zeros(shape, dtype=bool)
    pts[row[ins], col[ins]] = True
    d = ndi.distance_transform_edt(~pts)
    halo = np.where(d <= PALEO_CUT_PX,
                    np.exp(-(d ** 2) / (2.0 * PALEO_SIGMA_PX ** 2)), 0.0)
    info = {"n_rows_csv": len(rows), "n_on_grid": int(ins.sum()),
            "n_on_valid_pixels": int(valid[row[ins], col[ins]].sum()),
            "csv_sha256": hashlib.sha256(PALEO_CSV.read_bytes()).hexdigest()}
    return halo.astype(np.float32), info


def main() -> int:
    t0 = time.time()
    verify = verify_against_reference(trials=15)
    if not verify["pass"]:
        raise RuntimeError(f"fast scorer disagrees with reference: {verify}")
    valid, known = load_footprint(R10.RAW / "existing_faults.tif")
    n_valid = int(valid.sum())

    # archived recipe must equal the frozen copy
    r11 = json.loads((ROOT / "reports" / "holdout_r11_2026-09-30.json").read_text())
    archived = [(s[0], s[1]) for s in r11["greedy_recipe"]]
    if archived != GREEDY_R11_RECIPE:
        raise SystemExit(f"archived recipe {archived} != frozen {GREEDY_R11_RECIPE}")

    # ---- rebuild the reference crest map from band 19 and check the cache ----
    slope = D.robust_norm(read_band("det_elev_slope"))
    s15, o15 = D.ridge_strength(slope, 1.5)
    cached_ref = np.load(R10.DER / "BASE_topo_ridge.npy").astype(np.float32)
    rebuilt = finish(s15, o15, valid)
    ref_equal = bool(np.allclose(rebuilt, cached_ref, atol=1e-5))
    print(f"[{time.time()-t0:.0f}s] rebuilt reference == cached BASE_topo_ridge: {ref_equal}",
          flush=True)
    if not ref_equal:
        raise SystemExit("rebuilt BASE_topo_ridge differs from the cache - invalid run")
    del rebuilt
    s15v = np.where(valid, np.nan_to_num(s15, nan=0.0), 0.0).astype(np.float32)

    maps: dict[str, np.ndarray] = {"BASE_topo_ridge": cached_ref}
    meta: dict[str, dict] = {}
    for a in LOC_ALPHAS:
        for sg in LOC_SIGMAS:
            name = f"loc_a{int(a*10):02d}_s{sg}"
            maps[name] = finish(local_contrast(s15v, valid, sg, a), o15, valid)
            meta[name] = {"alpha": a, "sigma_px": sg}
    gms = []
    for sg in PERSIST_SIGMAS:
        s, _ = (s15, None) if sg == 1.5 else D.ridge_strength(slope, sg)
        sv = np.where(valid, np.nan_to_num(s, nan=0.0), 0.0).astype(np.float32)
        gms.append(np.maximum(sv / float(sv[valid].mean()), 1e-6))
    maps["persist_gm"] = finish(np.cbrt(gms[0] * gms[1] * gms[2]), o15, valid)
    meta["persist_gm"] = {"sigmas_px": list(PERSIST_SIGMAS)}
    del gms
    for lam in QUOTA_LAMBDAS:
        name = f"quota_l{int(lam*10):02d}_t{TILE_PX}"
        maps[name] = tile_quota(cached_ref, valid, lam)
        meta[name] = {"lambda": lam, "tile_px": TILE_PX}
    halo, paleo_info = paleo_halo(valid, valid.shape)
    s_cont = D.robust_norm(s15v)
    maps["R13_paleo"] = np.where(valid, halo * s_cont, 0.0).astype(np.float32)
    paleo_info["nonzero_px"] = int((maps["R13_paleo"] > 0).sum())
    del halo, s_cont, s15, s15v, o15, slope
    for stem in sorted({s for s, _ in GREEDY_R11_RECIPE}):
        maps[stem] = np.load(R10.DER / f"{stem}.npy").astype(np.float32, copy=False)
    print(f"[{time.time()-t0:.0f}s] maps built: {list(maps)}  paleo={paleo_info}",
          flush=True)

    map_stats, rankers = {}, {}
    for name, arr in maps.items():
        map_stats[name] = R10.full_domain_stats(arr, known, valid)
        rankers[name] = R10.Ranker(arr)
        print(f"[map] {name:18s} AUC={map_stats[name]['auc_full_catalogue']:.4f} "
              f"top5%recall={map_stats[name]['catalogue_recall_in_top5pct']:.4f} "
              f"nz={map_stats[name]['nonzero_pct_of_footprint']:.2f}%", flush=True)
    del maps

    cand_names = [n for n in rankers if n.startswith(("loc_", "persist", "quota"))]
    folds = (build_folds(known, valid, n_folds=R10.N_FOLDS, hide_frac=R10.HIDE_FRAC,
                         seed=20260930, link_px=R10.LINK_PX, buffer_px=R10.BUFFER_PX)
             + R10.segment_folds(known, valid, n_folds=R10.N_FOLDS))

    def block(diag, stem, cov, allowed):
        m, dg = rankers[stem].topk(allowed, int(cov * n_valid))
        diag[f"{stem}@{cov}#{len(diag)}"] = dg
        if SPACING > 1:
            m = D.decimate_grid(m, rankers[stem].score, SPACING)
        return m & allowed

    def chain(diag, base, ev):
        m = base.copy()
        for stem, cov in GREEDY_R11_RECIPE:
            m = m | block(diag, stem, cov, ev & far_from(m))
        return m

    rows: list[dict] = []
    for fi, f in enumerate(folds, 1):
        ev = f.eval_mask
        scorer = FoldScorer.build(f.hidden, ev)

        def emit(cfg, m, diag):
            r = scorer.score((m & ev).astype(np.float32))
            rows.append({"config": cfg, "fold": f.name, "rule": f.rule,
                         "n_predicted_eval_pixels": int((m & ev).sum()),
                         **{k: round(float(r[k]), 7) for k in
                            ("dti", "tp_w", "fp_w", "precision_w", "recall_w")},
                         "selection_diagnostics": dict(diag)})

        d0: dict = {}
        ref_base = block(d0, "BASE_topo_ridge", BASE_COVERAGE, ev)
        emit("topo_05_sp3", ref_base, d0)
        dg: dict = dict(d0)
        g11 = chain(dg, ref_base, ev)
        emit("greedy_r11", g11, dg)
        for cov in PALEO_COVS:
            dp = dict(dg)
            m = g11 | block(dp, "R13_paleo", cov, ev & far_from(g11))
            emit(f"greedy_r11_paleo{int(cov*10000):04d}", m, dp)
        for c in cand_names:
            dc: dict = {}
            b = block(dc, c, BASE_COVERAGE, ev)
            emit(f"{c}_05_sp3", b, dc)
            emit(f"{c}_greedy", chain(dc, b, ev), dc)
        del scorer
        print(f"[{time.time()-t0:.0f}s] fold {fi}/{len(folds)} {f.name} done", flush=True)

    # ---- protocol regression check vs the archive ------------------------
    hist = {r["fold"]: r["dti"] for r in
            json.loads(R10.HISTORICAL.read_text())["results"]
            if r["config"] == "topo_05_sp3"}
    diffs = [[r["fold"], r["dti"], hist[r["fold"]], round(r["dti"] - hist[r["fold"]], 7)]
             for r in rows if r["config"] == "topo_05_sp3" and r["fold"] in hist]
    maxdev = max((abs(d[3]) for d in diffs), default=float("inf"))
    maxrel = max((abs(d[3]) / max(abs(d[2]), 1e-12) for d in diffs),
                 default=float("inf"))
    pcheck = {"n_compared": len(diffs), "max_abs_deviation": maxdev,
              "max_rel_deviation": maxrel, "tolerance_rel": ARCHIVE_TOL_REL,
              "pass": bool(diffs) and maxrel <= ARCHIVE_TOL_REL,
              "rebuilt_reference_equals_cache": ref_equal,
              "numpy": np.__version__, "scipy": __import__("scipy").__version__}
    print("protocol regression check:", "PASS" if pcheck["pass"] else "FAIL",
          f"max dev {maxdev:.2e}", flush=True)
    if not pcheck["pass"]:
        raise SystemExit("protocol regression check failed - run invalid")

    # ---- verdict (frozen rule) -------------------------------------------
    ts = R10B.summarize([r for r in rows if r["fold"] in R10B.TUNE_FOLDS])
    cs = R10B.summarize([r for r in rows if r["fold"] not in R10B.TUNE_FOLDS])
    refs = ["topo_05_sp3", "greedy_r11"]
    challengers = ([f"{c}_greedy" for c in cand_names]
                   + [f"greedy_r11_paleo{int(c*10000):04d}" for c in PALEO_COVS])
    selected = max(challengers, key=lambda c: (ts[c]["dti_worst_rule_mean"],
                                               ts[c]["dti_mean"]))
    rt, rc = ts["topo_05_sp3"], cs["topo_05_sp3"]
    gt, gc = ts["greedy_r11"], cs["greedy_r11"]
    st, sc = ts[selected], cs[selected]
    rules_won = sum(1 for k, v in sc["dti_mean_by_rule"].items()
                    if v >= gc["dti_mean_by_rule"][k] - 1e-9)
    beats = (sc["dti_worst_rule_mean"] > gc["dti_worst_rule_mean"]
             and st["dti_worst_rule_mean"] > gt["dti_worst_rule_mean"]
             and sc["dti_worst_rule_mean"] > rc["dti_worst_rule_mean"]
             and st["dti_worst_rule_mean"] > rt["dti_worst_rule_mean"])
    paired_gain = sc["dti_mean"] - gc["dti_mean"]
    above_drift = paired_gain > 10 * maxdev
    per: dict = {}
    for r in rows:
        per.setdefault(r["fold"], {})[r["config"]] = r["dti"]

    def paired(c):
        return {"wins": sum(1 for v in per.values() if v[c] > v["greedy_r11"]),
                "ties": sum(1 for v in per.values() if v[c] == v["greedy_r11"]),
                "losses": sum(1 for v in per.values() if v[c] < v["greedy_r11"]),
                "n_folds": len(per)}
    pw = paired(selected)
    verdict = ("WINS" if beats and rules_won >= 4 and above_drift
               and pw["wins"] >= PAIRED_MIN_WINS
               else ("FRAGILE" if beats else "LOSES"))
    print(f"REFERENCES tune worst: topo {rt['dti_worst_rule_mean']:.5f} "
          f"greedy {gt['dti_worst_rule_mean']:.5f} | confirm worst: topo "
          f"{rc['dti_worst_rule_mean']:.5f} greedy {gc['dti_worst_rule_mean']:.5f}")
    for c in challengers + [f"{n}_05_sp3" for n in cand_names]:
        print(f"{c:30s} tune worst={ts[c]['dti_worst_rule_mean']:.5f} "
              f"confirm worst={cs[c]['dti_worst_rule_mean']:.5f} "
              f"confirm mean={cs[c]['dti_mean']:.5f}")
    print(f"SELECTED {selected}: confirm worst={sc['dti_worst_rule_mean']:.5f}, "
          f"rules won {rules_won}/6, paired {pw} -> {verdict}")

    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "status": "LOCAL_PROXY_HOLDOUT_ONLY_NOT_PRIVATE_TEST_PERFORMANCE",
           "hypothesis_register": "knowledge/09_r13_hypotheses.md",
           "predeclared_before_run": True,
           "references": refs, "challengers": challengers,
           "candidate_meta": meta, "paleo": paleo_info,
           "frozen": {"greedy_r11_recipe": GREEDY_R11_RECIPE,
                      "paleo_covs": list(PALEO_COVS),
                      "paired_min_wins": PAIRED_MIN_WINS},
           "map_statistics_full_catalogue": map_stats,
           "scorer_verification": verify,
           "protocol_regression_check": pcheck,
           "tune_summary": ts, "confirmation_summary": cs,
           "selected_on_tune": selected,
           "paired_vs_greedy_r11": {c: paired(c) for c in challengers},
           "paired_confirmation_mean_gain_vs_greedy_r11": paired_gain,
           "gain_exceeds_10x_rebuild_drift": bool(above_drift),
           "verdict_predeclared": {selected: f"{verdict} (rules won {rules_won}/6)"},
           "results": rows, "runtime_s": round(time.time() - t0, 1)}
    OUT_PATH.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print("wrote", OUT_PATH.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
