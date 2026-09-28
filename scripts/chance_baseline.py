#!/usr/bin/env python3
"""What would a RANDOM map of the same size have scored?

Nobody in this project has ever asked that, and without it a DTI number means
almost nothing: at these coverages most of the score is bought by area, not by
skill.

Closed form. For a Bernoulli(c) random prediction, the expected TP credit for
one ground-truth pixel is the expected maximum of the kernel weights over the
cells that happen to be switched on. Sorting the 25 kernel weights in
descending order w1 >= w2 >= ... >= w25,

    r(c) = E[max] = sum_j  w_j * c * (1-c)^(j-1)

and with FP_w = M * (1 - mean kernel field over predicted pixels),

    DTI_chance = r / (0.2*r + 0.8 + 0.2 * FP_w / |G|)

which follows from the audited identity DTI = TP/(0.2TP + 0.2FP + 0.8|G|) with
TP = r*|G|. The only unknown is |G|, the number of new-fault pixels in the
public chunk -- so we invert the relation for each of our scored submissions
and report the |G| that would make it exactly chance. A submission whose
implied |G| is far from the others is carrying real signal (or real anti-signal).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems.metric import kernel_offsets  # noqa: E402

N_VALID = 5_167_373
KERNEL_MASS = 5.0     # sum of k over the 25-cell kernel is ~5.0 for line-like G


def r_of_c(c: float) -> float:
    w = sorted((k for _, _, k in kernel_offsets()), reverse=True)
    return float(sum(wj * c * (1 - c) ** j for j, wj in enumerate(w)))


def dti_chance(mass: float, n_truth: float, n_valid: int = N_VALID) -> float:
    c = mass / n_valid
    r = r_of_c(c)
    fp = mass * max(0.0, 1.0 - KERNEL_MASS * n_truth / n_valid)
    return r / (0.2 * r + 0.8 + 0.2 * fp / n_truth)


def implied_truth(mass: float, dti: float) -> float:
    """|G| that makes this (mass, score) pair exactly chance."""
    lo, hi = 50.0, 2.0e6
    for _ in range(200):
        mid = np.sqrt(lo * hi)
        if dti_chance(mass, mid) < dti:
            lo = mid
        else:
            hi = mid
    return float(np.sqrt(lo * hi))


def main() -> None:
    fx = json.loads((ROOT / "reports" / "scored_forensics.json").read_text())
    rows = []
    for name, v in sorted(fx["maps"].items(),
                          key=lambda kv: -kv[1]["public_LB_DW_Tversky"]):
        mass = v["total_mass_sum_p"]
        lb = v["public_LB_DW_Tversky"]
        b = v["mass_by_distance_to_known_catalogue"]
        rows.append({
            "submission": name.replace(".tif", ""),
            "public_LB": lb,
            "predicted_mass": mass,
            "coverage_pct": round(100 * mass / N_VALID, 3),
            "catalogue_echo_pct": round(100 * (b["on_known"] + b["within_300m"]), 1),
            "implied_|G|_if_pure_chance": int(implied_truth(mass, lb)),
        })

    # A consistent |G| should emerge for the chance-like submissions.
    cands = [r["implied_|G|_if_pure_chance"] for r in rows]
    g_med = float(np.median(cands))

    for r in rows:
        r["chance_DTI_at_|G|=median"] = round(dti_chance(r["predicted_mass"], g_med), 4)
        r["lift_over_chance"] = round(r["public_LB"] / r["chance_DTI_at_|G|=median"], 3)

    out = {
        "method": "closed-form chance DTI for a random map of equal mass",
        "n_valid_px": N_VALID,
        "median_implied_|G|": int(g_med),
        "note": ("Each row's implied |G| is the public-chunk new-fault pixel "
                 "count that would make that submission EXACTLY chance. Rows "
                 "clustering on one value are indistinguishable from random; "
                 "a much larger implied |G| means the map beat chance."),
        "rows": rows,
        "chance_curve_at_median_G": {
            f"{c:.3f}": round(dti_chance(c * N_VALID, g_med), 4)
            for c in (0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.20, 0.35, 1.0)},
    }
    (ROOT / "reports" / "chance_baseline.json").write_text(json.dumps(out, indent=2))

    print(f"median implied |G| (public chunk) = {int(g_med):,}\n")
    hdr = (f"{'submission':38s} {'LB':>7s} {'cov%':>6s} {'echo%':>6s} "
           f"{'implied|G|':>11s} {'chance':>7s} {'lift':>6s}")
    print(hdr); print("-" * len(hdr))
    for r in rows:
        print(f"{r['submission'][:38]:38s} {r['public_LB']:7.4f} "
              f"{r['coverage_pct']:6.2f} {r['catalogue_echo_pct']:6.1f} "
              f"{r['implied_|G|_if_pure_chance']:11,d} "
              f"{r['chance_DTI_at_|G|=median']:7.4f} {r['lift_over_chance']:6.2f}x")
    print(f"\nchance DTI curve at |G|={int(g_med):,}:")
    for c, d in out["chance_curve_at_median_G"].items():
        print(f"   coverage {float(c)*100:6.1f}%  ->  DTI {d:.4f}")
    print(f"\nwrote {ROOT/'reports'/'chance_baseline.json'}")


if __name__ == "__main__":
    main()
