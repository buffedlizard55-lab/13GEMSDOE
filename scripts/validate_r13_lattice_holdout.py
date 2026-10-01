#!/usr/bin/env python3
"""R13-6 coverage-geometry lattices (knowledge/09_r13_hypotheses.md, addendum A).

Rule, folds, scorer, tune/confirm split: identical to validate_r13_holdout.py.
Local hide-and-recover proxy on KNOWN faults only (I-10, I-16).
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

OUT_PATH = ROOT / "reports" / "holdout_r13_lattice_2026-10-01.json"
RECIPE = [("R10_vent", 0.0025), ("R8_tpi", 0.0025), ("R10_dzt_field", 0.0025)]
KS = (5, 6)
PAIRED_MIN_WINS = 14
EXCLUDE_PX = 3


def square_lattice(shape, k: int) -> np.ndarray:
    m = np.zeros(shape, bool)
    m[::k, ::k] = True
    return m


def hex_lattice(shape, k: int) -> np.ndarray:
    """Triangular lattice with the same density as a square lattice of stride k."""
    a = k * np.sqrt(2.0 / np.sqrt(3.0))
    pitch = a * np.sqrt(3.0) / 2.0
    m = np.zeros(shape, bool)
    i = 0
    while True:
        r = int(round(i * pitch))
        if r >= shape[0]:
            break
        shift = (a / 2.0) if i % 2 else 0.0
        cols = np.round(np.arange(shift, shape[1], a)).astype(int)
        cols = cols[cols < shape[1]]
        m[r, cols] = True
        i += 1
    return m


def far_from(mask):
    return ~ndi.binary_dilation(mask, structure=np.ones((2 * EXCLUDE_PX + 1,) * 2, bool))


def main() -> int:
    t0 = time.time()
    if not verify_against_reference(trials=15)["pass"]:
        raise RuntimeError("fast scorer disagrees with reference")
    valid, known = load_footprint(R10.RAW / "existing_faults.tif")
    n_valid = int(valid.sum())
    lat = {}
    for k in KS:
        lat[f"sq{k}"] = square_lattice(valid.shape, k)
        lat[f"hex{k}"] = hex_lattice(valid.shape, k)
    dens = {n: round(float(m.sum()) / m.size, 5) for n, m in lat.items()}
    print("lattice density (fraction of grid):", dens, flush=True)
    rankers = {}
    for stem in ["BASE_topo_ridge"] + [s for s, _ in RECIPE]:
        rankers[stem] = R10.Ranker(np.load(R10.DER / f"{stem}.npy").astype(np.float32))
    folds = (build_folds(known, valid, n_folds=R10.N_FOLDS, hide_frac=R10.HIDE_FRAC,
                         seed=20260930, link_px=R10.LINK_PX, buffer_px=R10.BUFFER_PX)
             + R10.segment_folds(known, valid, n_folds=R10.N_FOLDS))

    def block(stem, cov, allowed):
        m, _ = rankers[stem].topk(allowed, int(cov * n_valid))
        m = D.decimate_grid(m, rankers[stem].score, R10.SPACING)
        return m & allowed

    rows = []
    for f in folds:
        ev = f.eval_mask
        sc = FoldScorer.build(f.hidden, ev)
        base = block("BASE_topo_ridge", R10.BASE_COVERAGE, ev)
        g = base.copy()
        for stem, cov in RECIPE:
            g = g | block(stem, cov, ev & far_from(g))
        cfgs = {"topo_05_sp3": base, "greedy_r11": g}
        for n, m in lat.items():
            cfgs[n] = m & ev
            cfgs[f"hyb_{n}"] = (m & ev) | g
        for name, m in cfgs.items():
            r = sc.score((m & ev).astype(np.float32))
            rows.append({"config": name, "fold": f.name, "rule": f.rule,
                         "n_predicted_eval_pixels": int((m & ev).sum()),
                         **{q: round(float(r[q]), 7) for q in
                            ("dti", "tp_w", "fp_w", "precision_w", "recall_w")},
                         "selection_diagnostics": {"x": {"tie_fraction": 0.0,
                                                          "n_selected_at_zero_score": 0}}})
        print(f"[{time.time()-t0:.0f}s] {f.name}", flush=True)

    ts = R10B.summarize([r for r in rows if r["fold"] in R10B.TUNE_FOLDS])
    cs = R10B.summarize([r for r in rows if r["fold"] not in R10B.TUNE_FOLDS])
    # reference drift: in-run topo vs archive (same check as R13/R12)
    hist = {r["fold"]: r["dti"] for r in
            json.loads(R10.HISTORICAL.read_text())["results"]
            if r["config"] == "topo_05_sp3"}
    dev = [abs(r["dti"] - hist[r["fold"]]) for r in rows
           if r["config"] == "topo_05_sp3" and r["fold"] in hist]
    maxdev = max(dev) if dev else float("inf")
    if not dev or max(abs(r["dti"] - hist[r["fold"]]) / hist[r["fold"]] for r in rows
                  if r["config"] == "topo_05_sp3" and r["fold"] in hist) > 0.01:
        raise SystemExit("protocol regression check failed - run invalid")
    challengers = [n for n in cs if n not in ("topo_05_sp3", "greedy_r11")]
    sel = max(challengers, key=lambda c: (ts[c]["dti_worst_rule_mean"], ts[c]["dti_mean"]))
    rt, rc, gt, gc = ts["topo_05_sp3"], cs["topo_05_sp3"], ts["greedy_r11"], cs["greedy_r11"]
    st, sc_ = ts[sel], cs[sel]
    rules_won = sum(1 for k, v in sc_["dti_mean_by_rule"].items()
                    if v >= gc["dti_mean_by_rule"][k] - 1e-9)
    beats = (sc_["dti_worst_rule_mean"] > gc["dti_worst_rule_mean"]
             and st["dti_worst_rule_mean"] > gt["dti_worst_rule_mean"]
             and sc_["dti_worst_rule_mean"] > rc["dti_worst_rule_mean"]
             and st["dti_worst_rule_mean"] > rt["dti_worst_rule_mean"])
    gain = sc_["dti_mean"] - gc["dti_mean"]
    per = {}
    for r in rows:
        per.setdefault(r["fold"], {})[r["config"]] = r["dti"]

    def paired(c):
        return {"wins": sum(v[c] > v["greedy_r11"] for v in per.values()),
                "losses": sum(v[c] < v["greedy_r11"] for v in per.values()),
                "n_folds": len(per)}
    pw = paired(sel)
    verdict = ("WINS" if beats and rules_won >= 4 and gain > 10 * maxdev
               and pw["wins"] >= PAIRED_MIN_WINS else ("FRAGILE" if beats else "LOSES"))
    print(f"REF tune worst topo {rt['dti_worst_rule_mean']:.5f} greedy {gt['dti_worst_rule_mean']:.5f}"
          f" | confirm worst topo {rc['dti_worst_rule_mean']:.5f} greedy {gc['dti_worst_rule_mean']:.5f}")
    for c in challengers + ["greedy_r11", "topo_05_sp3"]:
        print(f"{c:12s} tune worst={ts[c]['dti_worst_rule_mean']:.5f} mean={ts[c]['dti_mean']:.5f} | "
              f"confirm worst={cs[c]['dti_worst_rule_mean']:.5f} mean={cs[c]['dti_mean']:.5f} "
              f"P={cs[c]['precision_w_mean']:.4f} R={cs[c]['recall_w_mean']:.4f} "
              f"px={cs[c]['predicted_eval_px_mean']:.0f}")
    print(f"SELECTED {sel}: rules won {rules_won}/6, paired {pw}, gain {gain:.5f} -> {verdict}")
    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "status": "LOCAL_PROXY_HOLDOUT_ONLY_NOT_PRIVATE_TEST_PERFORMANCE",
           "hypothesis_register": "knowledge/09_r13_hypotheses.md (addendum A)",
           "origin_note": "post-hoc in origin (null baseline seen first); frozen rule applied unchanged",
           "lattice_density": dens, "references": ["topo_05_sp3", "greedy_r11"],
           "challengers": challengers, "tune_summary": ts, "confirmation_summary": cs,
           "selected_on_tune": sel, "paired_vs_greedy_r11": {c: paired(c) for c in challengers},
           "paired_confirmation_mean_gain_vs_greedy_r11": gain, "reference_max_abs_drift": maxdev,
           "verdict_predeclared": {sel: f"{verdict} (rules won {rules_won}/6)"},
           "results": rows, "runtime_s": round(time.time() - t0, 1)}
    OUT_PATH.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print("wrote", OUT_PATH.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
