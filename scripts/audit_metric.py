#!/usr/bin/env python3
"""
SCORE AUDIT -- run before touching a model.

Verifies, numerically and against the official worked example, that:
  0. our raster implementation of DTI is correct;
  1. FN_w == |G| - TP_w, so DTI reduces to TP/(0.2TP + 0.2FP + 0.8|G|);
  2. DTI is the weighted harmonic mean of weighted precision (0.2) and
     weighted recall (0.8) -- i.e. a distance-weighted F2 score;
  3. a block of predictions helps iff marginal weighted precision > 0.2*DTI;
  4. scaling all predictions up toward 1 strictly increases DTI;
  5. recall elasticity beats precision elasticity iff P > 0.25*R.

Official source for every quoted number:
  https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/

Writes reports/metric_audit.json.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems.metric import (  # noqa: E402
    ALPHA, BETA, R_PIX, dti, dti_reduced, dti_from_pr, elasticities,
    kernel_offsets, marginal_precision_threshold, recall_dominates_precision,
)

OUT = Path(__file__).resolve().parents[1] / "reports" / "metric_audit.json"
rng = np.random.default_rng(20260928)
report: dict = {
    "official_source":
        "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
    "official_constants": {"alpha": ALPHA, "beta": BETA,
                           "R_m": 300.0, "pixel_m": 100.0, "R_pix": R_PIX},
    "checks": {},
}
FAIL = []


def check(name: str, ok: bool, detail) -> None:
    report["checks"][name] = {"pass": bool(ok), "detail": detail}
    if not ok:
        FAIL.append(name)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


# ---------------------------------------------------------------- 0. kernel
offs = kernel_offsets()
check("kernel_offsets_count", len(offs) == 25,
      {"n_offsets_with_positive_weight": len(offs),
       "note": "d<=3px, k=1-d/3; the four d==3 offsets have k=0 and are dropped",
       "weights_sorted": sorted({round(k, 6) for _, _, k in offs}, reverse=True)})

# ------------------------------------------- 1. official worked example (algebra)
TPw, FPw, FNw = 3.00, 1.89, 2.00
G_official = TPw + FNw
direct = TPw / (TPw + ALPHA * FPw + BETA * FNw)
reduced = dti_reduced(TPw, FPw, G_official, eps=0.0)
check("worked_example_direct_formula", abs(round(direct, 2) - 0.60) < 1e-12,
      {"TP_w": TPw, "FP_w": FPw, "FN_w": FNw, "DTI": round(direct, 6),
       "rounded_2dp": round(direct, 2), "official_states": 0.60})
check("worked_example_FN_equals_G_minus_TP", abs(G_official - 5.0) < 1e-12,
      {"|G| = TP_w + FN_w": G_official,
       "consistent_with": "ground truth is a single vertical line of 5 pixels"})
check("worked_example_reduced_formula_matches", abs(direct - reduced) < 1e-12,
      {"direct": direct, "reduced TP/(0.2TP+0.2FP+0.8|G|)": reduced})
P_off, R_off = TPw / (TPw + FPw), TPw / G_official
check("worked_example_is_weighted_harmonic_mean",
      abs(dti_from_pr(P_off, R_off) - direct) < 1e-12,
      {"precision_w": round(P_off, 6), "recall_w": round(R_off, 6),
       "1/(0.2/P + 0.8/R)": round(dti_from_pr(P_off, R_off), 6),
       "equals_F_beta_with_beta_squared": BETA / ALPHA,
       "i.e._distance_weighted_F2": True})

# --------------------- 1b. brute-force reconstruction of the worked-example raster
# The schematic is published only as a PNG, so we search for a binary
# prediction pattern on a vertical 5-pixel ground truth that reproduces the
# published triple exactly. Finding one validates the raster implementation
# end-to-end against the organizers' own numbers.
H, W = 9, 11
truth = np.zeros((H, W), bool)
truth[2:7, 5] = True                      # single vertical line, |G| = 5
cand = [(y, x) for y in range(H) for x in range(W)]
found = None
for size in range(3, 7):
    if found:
        break
    for combo in itertools.combinations(cand, size):
        p = np.zeros((H, W))
        for y, x in combo:
            p[y, x] = 1.0
        r = dti(p, truth)
        if (abs(r.tp_w - 3.00) < 5e-3 and abs(r.fp_w - 1.89) < 5e-3
                and abs(r.fn_w - 2.00) < 5e-3):
            found = (combo, r)
            break
check("worked_example_raster_reconstructed", found is not None,
      {"searched": "all binary patterns of 3-6 pixels on a 9x11 grid, "
                   "ground truth = vertical line of 5",
       "match": None if not found else {
           "pred_pixels_(row,col)": [list(c) for c in found[0]],
           "TP_w": round(found[1].tp_w, 4),
           "FP_w": round(found[1].fp_w, 4),
           "FN_w": round(found[1].fn_w, 4),
           "DTI": round(found[1].dti, 4),
           "official": {"TP_w": 3.00, "FP_w": 1.89, "FN_w": 2.00, "DTI": 0.60}}})

# ------------------------------------------- 2. identities on random rasters
ident_max = {"fn": 0.0, "reduced": 0.0, "harmonic": 0.0}
for _ in range(60):
    h, w = int(rng.integers(24, 56)), int(rng.integers(24, 56))
    t = rng.random((h, w)) < rng.uniform(0.003, 0.05)
    if not t.any():
        continue
    p = np.clip(rng.random((h, w)) * (rng.random((h, w)) < rng.uniform(0.02, 0.5)), 0, 1)
    r = dti(p, t)
    ident_max["fn"] = max(ident_max["fn"], abs(r.fn_w - (r.n_truth - r.tp_w)))
    ident_max["reduced"] = max(ident_max["reduced"],
                               abs(r.dti - dti_reduced(r.tp_w, r.fp_w, r.n_truth)))
    if r.tp_w > 0:
        ident_max["harmonic"] = max(ident_max["harmonic"],
                                    abs(r.dti - dti_from_pr(r.precision_w, r.recall_w)))
check("identity_FN_w_equals_G_minus_TP_w", ident_max["fn"] < 1e-9,
      {"max_abs_error_over_60_random_rasters": ident_max["fn"]})
check("identity_reduced_formula", ident_max["reduced"] < 1e-9,
      {"max_abs_error": ident_max["reduced"],
       "formula": "TP_w / (0.2*TP_w + 0.2*FP_w + 0.8*|G|)"})
check("identity_weighted_harmonic_mean", ident_max["harmonic"] < 1e-8,
      {"max_abs_error": ident_max["harmonic"],
       "formula": "1 / (0.2/precision_w + 0.8/recall_w)"})

# ---------------------------- 3. consequence A: marginal precision threshold
h = w = 90
truth3 = np.zeros((h, w), bool)
truth3[20:70, 30] = True
truth3[45, 30:75] = True
base = np.zeros((h, w))
base[20:70, 30] = 1.0
r0 = dti(base, truth3)
thr = marginal_precision_threshold(r0.dti)
rows = []
for frac_good in [0.0, 0.01, 0.02, 0.03, 0.05, 0.08, 0.15, 0.4, 1.0]:
    blk = base.copy()
    # a block of NEW pixels: `frac_good` of them land on uncovered truth,
    # the rest land far from any truth (pure false-positive mass).
    tgt = np.argwhere(truth3 & (base == 0))
    n_block = 400
    n_good = int(round(frac_good * n_block))
    for yy, xx in tgt[:n_good]:
        blk[yy, xx] = 1.0
    far = [(y, x) for y in range(2, 18) for x in range(2, 60)][: n_block - n_good]
    for yy, xx in far:
        blk[yy, xx] = 1.0
    r1 = dti(blk, truth3)
    d_tp, d_fp = r1.tp_w - r0.tp_w, r1.fp_w - r0.fp_w
    mp = d_tp / (d_tp + d_fp) if (d_tp + d_fp) > 0 else 0.0
    rows.append({"block_marginal_precision": round(mp, 5),
                 "threshold_0.2xDTI": round(thr, 5),
                 "predicted_helps": mp > thr,
                 "observed_helps": r1.dti > r0.dti,
                 "dti_before": round(r0.dti, 6), "dti_after": round(r1.dti, 6)})
check("consequenceA_marginal_precision_rule",
      all(x["predicted_helps"] == x["observed_helps"] for x in rows),
      {"rule": "a block raises DTI iff dTP/(dTP+dFP) > alpha*DTI = 0.2*DTI",
       "base_DTI": round(r0.dti, 6), "threshold": round(thr, 6),
       "interpretation": (f"at DTI={r0.dti:.4f} any block with weighted precision "
                          f"above {thr*100:.2f}% is accretive"),
       "trials": rows})

# ------------------------------------- 4. consequence B: scaling up always helps
scale_rows, mono_ok = [], True
prev = None
for c in [0.05, 0.1, 0.2, 0.35, 0.5, 0.7, 0.85, 1.0]:
    rr = dti(base * c, truth3)
    scale_rows.append({"scale": c, "dti": round(rr.dti, 6)})
    if prev is not None and not (rr.dti > prev - 1e-15):
        mono_ok = False
    prev = rr.dti
# per-pixel bang-bang: a pixel exactly on truth has zero FP cost
onpix = np.zeros((h, w)); onpix[45, 30] = 1.0
r_on = dti(onpix, truth3)
check("consequenceB_uniform_scaling_monotone", mono_ok,
      {"rule": "DTI(c*p) = TP/(0.2TP + 0.2FP + 0.8|G|/c) is strictly increasing in c",
       "curve": scale_rows,
       "implication": "never submit a globally down-scaled map; renormalise so max=1",
       "on_truth_pixel_FP_cost": round(r_on.fp_w, 9),
       "bang_bang": "k(0)=1 so a pixel on truth costs 0 FP mass -> push to 1; "
                    "DTI is linear in each p(x) for fixed argmax, so the "
                    "optimum is binary. Graded values only encode ranking."})

# ------------------------------- 5. consequence C: recall vs precision crossover
cross = []
for R_ in [0.10, 0.20, 0.30, 0.50, 0.80]:
    for P_ in [0.02, 0.05, 0.1, 0.2, 0.25, 0.3, 0.5, 0.9]:
        eP, eR = elasticities(P_, R_)
        # empirical: 1% relative bump to each
        d_from_R = dti_from_pr(P_, min(R_ * 1.01, 1.0)) - dti_from_pr(P_, R_)
        d_from_P = dti_from_pr(min(P_ * 1.01, 1.0), R_) - dti_from_pr(P_, R_)
        pred = recall_dominates_precision(P_, R_)
        obs = d_from_R > d_from_P
        cross.append({"P": P_, "R": R_, "P_over_R": round(P_ / R_, 4),
                      "elasticity_P": round(eP, 4), "elasticity_R": round(eR, 4),
                      "recall_wins_predicted": pred, "recall_wins_observed": obs,
                      "agree": pred == obs})
check("consequenceC_recall_beats_precision_iff_P_gt_quarter_R",
      all(c["agree"] for c in cross),
      {"rule": "d log DTI/d log R > d log DTI/d log P  <=>  P > (alpha/beta)*R = 0.25*R",
       "note": "elasticities always sum to 1",
       "grid": cross})

# ------------------------------------------ 6. what DTI can a saturated map reach?
sat = []
for name, pm in [("truth_only", truth3.astype(float)),
                 ("truth_dilated_1px", None), ("all_ones", np.ones((h, w)))]:
    if pm is None:
        from gems.metric import kernel_field_of_truth
        pm = (kernel_field_of_truth(truth3) >= 0.66).astype(float)
    rr = dti(pm, truth3)
    sat.append({"map": name, "dti": round(rr.dti, 6), "TP_w": round(rr.tp_w, 2),
                "FP_w": round(rr.fp_w, 2), "precision_w": round(rr.precision_w, 4),
                "recall_w": round(rr.recall_w, 4)})
report["saturation_reference"] = sat
print("\nsaturation reference:", json.dumps(sat, indent=2))

report["verdict"] = "ALL CHECKS PASSED" if not FAIL else f"FAILED: {FAIL}"
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2))
print(f"\n{report['verdict']}\nwrote {OUT}")
sys.exit(1 if FAIL else 0)
