#!/usr/bin/env python3
"""R12: predeclared validation of R12-1 (hysteresis crest continuation),
R12-2 (finer-step greedy over a widened pool) and R12-3 (basin-floor magnetics
retested at its true support). Register: knowledge/08_r12_hypotheses.md,
written and committed BEFORE any fold was scored.

Protocol identical to scripts/validate_r11_holdout.py (same folds, seeds,
buffer, FoldScorer, tune/confirm split, spacing-3 decimation); the in-run
reference row must reproduce the archived per-fold DTI within the relative
tolerance (I-15 amendment) and all verdicts are paired IN-RUN.

New gate for R12: the best challenger must beat BOTH in-run references
(topo_05_sp3 AND greedy_r11) on tune and confirmation worst-rule-mean DTI,
win >= 4/6 confirmation rule means, and its paired confirmation mean gain must
exceed 10x the largest observed reference drift. Otherwise nothing ships and
greedy_r11 (all-finite encoding) stays the artifact.

Local catalogue hide-and-recover proxy only - NOT leaderboard performance.
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
from gems import detectors as D                                   # noqa: E402
from gems.fastscore import FoldScorer, verify_against_reference    # noqa: E402
from gems.holdout import build_folds                              # noqa: E402
from gems.rio import load_footprint                               # noqa: E402
import validate_r10_holdout as R10                                # noqa: E402
import validate_r10b_holdout as R10B                              # noqa: E402
import validate_r11_holdout as R11V                               # noqa: E402

OUT_PATH = ROOT / "reports" / "holdout_r12_2026-09-30.json"

# ---- predeclared constants (knowledge/08_r12_hypotheses.md) ---------------
# R12-2: widened pool (R11's 9 + R7_hinge_curv + R8_openness + R8_isocoherence),
# capped at 12 stems by the 3 GB sandbox (irregularity I-17)
POOL = ["R11_basin_mag", "HA_worms_rtp", "HB_tdr_rtp", "R7_crossgrad",
        "R7_hinge_curv", "R8_openness", "R8_isocoherence", "R8_tpi", "R8_flow",
        "R10_vent", "R10_alter_field", "R10_dzt_field"]
BLOCK_COVS = [0.001, 0.0025]        # finer than R11's {0.0025, 0.005, 0.01}
MAX_STEPS = 6                       # R11 used 4
EXCLUDE_PX = R11V.EXCLUDE_PX        # 3 px = 300 m, the metric kernel radius
SPACING = R10.SPACING
BASE_COVERAGE = R10.BASE_COVERAGE
# R12-1: hysteresis link radius and added-mass budgets
HYST_LINK_PX = 10                   # 8-connected growth limit from strong chains
HYST_ADD_COVS = [0.005, 0.010, 0.020]
# R12-3: basin magnetics at/below its 7,610-px support (0.147 % of valid)
BASIN_COVS = [0.001, 0.0014]
GREEDY_R11_RECIPE = [("R10_vent", 0.0025), ("R8_tpi", 0.0025),
                     ("R10_dzt_field", 0.0025)]


def far_from(mask: np.ndarray) -> np.ndarray:
    return ~ndi.binary_dilation(
        mask, structure=np.ones((2 * EXCLUDE_PX + 1,) * 2, bool))


def hysteresis_block(strong: np.ndarray, eval_mask: np.ndarray,
                     ranker: R10.Ranker, add_cov: float, n_valid: int,
                     diag_sink: list, label: str) -> np.ndarray:
    """R12-1: Canny-style two-threshold linking on the ridge-strength field.

    strong   = the reference top-5 % crest block for this fold (identical
               construction to topo_05_sp3).
    zone     = pixels within HYST_LINK_PX (8-connected) of a strong chain,
               still unclaimed, inside the fold's evaluation mask.
    The zone is grid-3 decimated (same geometry rule as the reference), then
    the highest-ranked `add_cov * n_valid` zone pixels are added.
    """
    zone = ndi.binary_dilation(strong, structure=np.ones((3, 3), bool),
                               iterations=HYST_LINK_PX)
    zone = zone & eval_mask & ~strong
    n_zone = int(zone.sum())
    if zone.any():
        zone = D.decimate_grid(zone, ranker.score, SPACING)
        add, dg = ranker.topk(zone, int(add_cov * n_valid))
    else:
        add = np.zeros_like(strong)
        dg = {"k_requested": 0, "k_selected": 0, "n_selected_at_zero_score": 0,
              "selection_threshold": 0.0, "n_allowed_pixels_at_threshold": 0,
              "tie_fraction": 0.0}
    diag_sink.append((f"{label}:zone", {"k_requested": n_zone,
                                        "k_selected": n_zone,
                                        "n_selected_at_zero_score": 0,
                                        "selection_threshold": 0.0,
                                        "n_allowed_pixels_at_threshold": n_zone,
                                        "tie_fraction": 0.0}))
    diag_sink.append((f"{label}:add", dg))
    return strong | add


def main() -> int:
    t0 = time.time()
    verify = verify_against_reference(trials=15)
    if not verify["pass"]:
        raise RuntimeError(f"fast scorer disagrees with reference: {verify}")
    valid, known = load_footprint(RAW := R10.RAW / "existing_faults.tif")
    n_valid = int(valid.sum())
    basin_info = R11V.build_basin_mag(valid)
    print("[R12-3] basin_mag", basin_info, flush=True)

    # archived R11 recipe must match the register's hardcoded copy
    r11 = json.loads((ROOT / "reports" / "holdout_r11_2026-09-30.json").read_text())
    archived = [(s[0], s[1]) for s in r11["greedy_recipe"]]
    if len(archived) != len(GREEDY_R11_RECIPE) or any(
            m != m2 or abs(c - c2) > 1e-12
            for (m, c), (m2, c2) in zip(archived, GREEDY_R11_RECIPE)):
        raise SystemExit(f"archived greedy_r11 recipe {archived} != register "
                         f"{GREEDY_R11_RECIPE} - update the register first")

    stems = ["BASE_topo_ridge"] + POOL
    map_stats, rankers = {}, {}
    for stem in stems:
        a = np.load(R10.DER / f"{stem}.npy").astype(np.float32, copy=False)
        map_stats[stem] = R10.full_domain_stats(a, known, valid)
        rankers[stem] = R10.Ranker(a)
        del a
        print(f"[map] {stem:16s} AUC={map_stats[stem]['auc_full_catalogue']:.4f}",
              flush=True)

    folds = (build_folds(known, valid, n_folds=R10.N_FOLDS, hide_frac=R10.HIDE_FRAC,
                         seed=20260930, link_px=R10.LINK_PX, buffer_px=R10.BUFFER_PX)
             + R10.segment_folds(known, valid, n_folds=R10.N_FOLDS))

    diag_sink: list = []

    def block(stem, cov, allowed):
        m, dg = rankers[stem].topk(allowed, int(cov * n_valid))
        diag_sink.append((f"{stem}@{cov}", dg))
        if SPACING > 1:
            m = D.decimate_grid(m, rankers[stem].score, SPACING)
        return m & allowed

    state = {f.name: {"fold": f, "scorer": None} for f in folds}

    def ensure(fname):
        st = state[fname]
        if st["scorer"] is None:
            f = st["fold"]
            st["scorer"] = FoldScorer.build(f.hidden, f.eval_mask)
            st["ref"] = block("BASE_topo_ridge", BASE_COVERAGE, f.eval_mask)
        return st

    def release(fname):
        state[fname]["scorer"] = None
        state[fname].pop("ref", None)

    print(f"[{time.time()-t0:.0f}s] folds ready", flush=True)

    def score(fname, m):
        r = state[fname]["scorer"].score(
            (m & state[fname]["fold"].eval_mask).astype(np.float32))
        return {k: float(r[k]) for k in ("dti", "tp_w", "fp_w", "precision_w",
                                         "recall_w")}

    def worst_rule_mean(res: dict) -> float:
        by = {}
        for fn, r in res.items():
            by.setdefault(state[fn]["fold"].rule, []).append(r["dti"])
        return min(float(np.mean(v)) for v in by.values())

    tune = [n for n in state if n in R10B.TUNE_FOLDS]
    for n in tune:
        ensure(n)

    # ---- R12-2 finer-step greedy on tune folds (same audited rule as R11-4)
    assembly = {n: state[n]["ref"].copy() for n in tune}
    cur = {n: score(n, assembly[n]) for n in tune}
    recipe, path = [], []
    for step in range(MAX_STEPS):
        cur_mean = float(np.mean([cur[n]["dti"] for n in tune]))
        cur_worst = worst_rule_mean(cur)
        bar = 0.2 * cur_mean
        allowed = {n: state[n]["fold"].eval_mask & far_from(assembly[n])
                   for n in tune}
        tested = []
        for stem in POOL:
            for cov in BLOCK_COVS:
                new = {}
                for n in tune:
                    new[n] = score(n, assembly[n] | block(stem, cov, allowed[n]))
                dtp = sum(new[n]["tp_w"] - cur[n]["tp_w"] for n in tune)
                dfp = sum(new[n]["fp_w"] - cur[n]["fp_w"] for n in tune)
                mp = dtp / (dtp + dfp) if (dtp + dfp) > 0 else 0.0
                tested.append({"map": stem, "cov": cov,
                               "marginal_precision": round(mp, 5),
                               "tune_mean": round(float(np.mean(
                                   [new[n]["dti"] for n in tune])), 6),
                               "tune_worst": round(worst_rule_mean(new), 6)})
        tested.sort(key=lambda t: -t["marginal_precision"])
        best = tested[0]
        accept = best["marginal_precision"] > bar and best["tune_worst"] > cur_worst
        path.append({"step": step + 1, "bar_0.2xDTI": round(bar, 5),
                     "tune_mean_before": round(cur_mean, 6),
                     "tune_worst_before": round(cur_worst, 6),
                     "best": best, "accepted": bool(accept),
                     "all_tested": tested})
        print(f"step {step+1}: bar={bar:.4f} best={best} -> "
              f"{'ACCEPT' if accept else 'STOP'}", flush=True)
        if not accept:
            break
        recipe.append((best["map"], best["cov"]))
        for n in tune:
            assembly[n] = assembly[n] | block(best["map"], best["cov"],
                                              allowed[n])
            cur[n] = score(n, assembly[n])
    del assembly
    for n in tune:
        release(n)

    # ---- apply all configs to all 18 folds --------------------------------
    configs = {"topo_05_sp3": [],
               "greedy_r11": [("far", s, c) for s, c in GREEDY_R11_RECIPE]}
    for add in HYST_ADD_COVS:
        configs[f"hyst_add{int(add*1000):03d}"] = [("hyst", None, add)]
    for cov in BASIN_COVS:
        configs[f"topo05_plus_basinmag{int(cov*1000):04d}_sp3"] = [
            ("union", "R11_basin_mag", cov)]
    if recipe:
        configs["greedy_r12"] = [("far", s, c) for s, c in recipe]

    rows = []
    ref_diag = None
    for n in list(state):
        st = ensure(n)
        f = st["fold"]
        if ref_diag is None:
            # every config starts from the same reference block, so its
            # top-k tie diagnostics belong on every row (summarize() takes a
            # max over them; an empty dict would crash it)
            _, ref_diag = rankers["BASE_topo_ridge"].topk(
                f.eval_mask, int(BASE_COVERAGE * n_valid))
        for cname, steps in configs.items():
            m = st["ref"].copy()
            diag_sink.clear()
            diag_sink.append((f"BASE_topo_ridge@{BASE_COVERAGE}", ref_diag))
            for kind, stem, cov in steps:
                if kind == "hyst":
                    m = hysteresis_block(m, f.eval_mask, rankers["BASE_topo_ridge"],
                                         cov, n_valid, diag_sink, cname)
                else:
                    allowed = (f.eval_mask if kind == "union"
                               else (f.eval_mask & far_from(m)))
                    m = m | block(stem, cov, allowed)
            r = score(n, m)
            rows.append({"config": cname, "fold": n, "rule": f.rule,
                         "n_predicted_eval_pixels": int((m & f.eval_mask).sum()),
                         **{k: round(v, 7) for k, v in r.items()},
                         "selection_diagnostics": dict(diag_sink)})
        release(n)
        print(f"[{time.time()-t0:.0f}s] scored {n}", flush=True)

    # ---- protocol regression check (I-15 amendment) -----------------------
    hist = {r["fold"]: r["dti"] for r in
            json.loads(R10.HISTORICAL.read_text())["results"]
            if r["config"] == "topo_05_sp3"}
    TOL_REL = 0.01
    diffs = [[r["fold"], r["dti"], hist[r["fold"]],
              round(r["dti"] - hist[r["fold"]], 7)]
             for r in rows if r["config"] == "topo_05_sp3" and r["fold"] in hist]
    mism = [d for d in diffs if abs(d[3]) > 1e-6]
    maxdev = max((abs(d[3]) for d in diffs), default=float("inf"))
    maxrel = max((abs(d[3]) / max(abs(d[2]), 1e-12) for d in diffs),
                 default=float("inf"))
    import hashlib
    pcheck = {"n_compared": len(hist), "n_exact_mismatch_gt_1e-6": len(mism),
              "max_abs_deviation": maxdev, "max_rel_deviation": maxrel,
              "tolerance_rel": TOL_REL, "per_fold": diffs,
              "exact": not mism, "pass": bool(hist) and maxrel <= TOL_REL,
              "environment": {"numpy": np.__version__,
                              "scipy": __import__("scipy").__version__},
              "BASE_topo_ridge_sha256": hashlib.sha256(
                  (R10.DER / "BASE_topo_ridge.npy").read_bytes()).hexdigest()}
    print("protocol regression check:",
          ("PASS (exact)" if pcheck["exact"]
           else f"PASS within tol, max dev {maxdev:.2e}")
          if pcheck["pass"] else f"FAIL max dev {maxdev:.2e}")
    if not pcheck["pass"]:
        raise SystemExit("protocol regression check failed - run invalid")

    ts = R10B.summarize([r for r in rows if r["fold"] in R10B.TUNE_FOLDS])
    cs = R10B.summarize([r for r in rows if r["fold"] not in R10B.TUNE_FOLDS])
    refs = ["topo_05_sp3", "greedy_r11"]
    cands = [c for c in configs if c not in refs]
    selected = max(cands, key=lambda c: (ts[c]["dti_worst_rule_mean"],
                                         ts[c]["dti_mean"]))
    rt, rc = ts["topo_05_sp3"], cs["topo_05_sp3"]
    gt, gc = ts["greedy_r11"], cs["greedy_r11"]
    st_, sc_ = ts[selected], cs[selected]
    rules_won = sum(1 for k, v in sc_["dti_mean_by_rule"].items()
                    if v >= gc["dti_mean_by_rule"][k] - 1e-9)
    beats = (sc_["dti_worst_rule_mean"] > gc["dti_worst_rule_mean"]
             and st_["dti_worst_rule_mean"] > gt["dti_worst_rule_mean"]
             and sc_["dti_worst_rule_mean"] > rc["dti_worst_rule_mean"]
             and st_["dti_worst_rule_mean"] > rt["dti_worst_rule_mean"])
    paired_gain = sc_["dti_mean"] - gc["dti_mean"]
    above_drift = paired_gain > 10 * maxdev
    # paired per-fold record vs greedy_r11 (audit)
    per = {}
    for r in rows:
        per.setdefault(r["fold"], {})[r["config"]] = r["dti"]
    paired = {"n_folds": len(per),
              "selected_beats_greedy_r11": sum(
                  1 for v in per.values()
                  if v.get(selected, -1) > v.get("greedy_r11", -1)),
              "ties": sum(1 for v in per.values()
                          if v.get(selected, -1) == v.get("greedy_r11", -1))}
    verdict = ("WINS" if beats and rules_won >= 4 and above_drift
               else ("FRAGILE" if beats else "LOSES"))
    print(f"REFERENCE tune worst={rt['dti_worst_rule_mean']:.5f} "
          f"confirm={rc['dti_worst_rule_mean']:.5f} | "
          f"greedy_r11 tune worst={gt['dti_worst_rule_mean']:.5f} "
          f"confirm={gc['dti_worst_rule_mean']:.5f}")
    for c in cands:
        print(f"{c:34s} tune worst={ts[c]['dti_worst_rule_mean']:.5f} "
              f"mean={ts[c]['dti_mean']:.5f} "
              f"px={ts[c]['predicted_eval_px_mean']:.0f}")
    print(f"SELECTED {selected}: confirm worst={sc_['dti_worst_rule_mean']:.5f} "
          f"rules won {rules_won}/6, paired folds won "
          f"{paired['selected_beats_greedy_r11']}/{paired['n_folds']} "
          f"vs greedy_r11 -> {verdict}")

    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "status": "LOCAL_PROXY_HOLDOUT_ONLY_NOT_PRIVATE_TEST_PERFORMANCE",
           "hypothesis_register": "knowledge/08_r12_hypotheses.md",
           "predeclared_before_run": True,
           "references": refs,
           "pool": POOL, "block_coverages": BLOCK_COVS, "max_steps": MAX_STEPS,
           "hyst_link_px": HYST_LINK_PX, "hyst_add_covs": HYST_ADD_COVS,
           "basin_covs": BASIN_COVS, "exclude_px": EXCLUDE_PX,
           "basin_mag": basin_info,
           "map_statistics_full_catalogue": map_stats,
           "scorer_verification": verify,
           "protocol_regression_check": pcheck,
           "greedy_path_tune_only": path, "greedy_r12_recipe": recipe,
           "greedy_r11_recipe_inrun": GREEDY_R11_RECIPE,
           "configurations": configs, "tune_summary": ts,
           "selected_on_tune": selected,
           "confirmation_summary": {k: cs[k] for k in configs},
           "paired_vs_greedy_r11": paired,
           "paired_confirmation_mean_gain_vs_greedy_r11": paired_gain,
           "gain_exceeds_10x_rebuild_drift": bool(above_drift),
           "verdict_predeclared": {
               selected: f"{verdict} (confirmation rule-means won: {rules_won}/6)"},
           "results": rows, "runtime_s": round(time.time() - t0, 1)}
    OUT_PATH.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print("wrote", OUT_PATH.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
