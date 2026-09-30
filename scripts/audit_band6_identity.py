#!/usr/bin/env python3
"""Identify provided band 6 (`tc`) against official USGS radiometric channels.

Background (knowledge/02_irregularities.md, I-2). The feature GeoTIFF's embedded
description for band 6 hedges - `tc - Tilt angle **or** total curvature -
magnetic field derivative for edge detection` - and an earlier session declared
the "radiometric total count" reading **disproved** on two grounds: the band is
bounded in [2.953, 88.567] (a count rate in cps should be 10^2-10^4) and it is
smoother than the supplied magnetic gradient bands.

The R10 external audit then measured Spearman rho = 0.99998 between band 6 and
`radiometric::rad_tc` (and 0.99994 against the independent `geodawn_rad::TC`),
both dequantised from hash-verified USGS releases. Rank correlation is invariant
to units and to monotone rescaling, so it cannot by itself distinguish "same
field, different units" from "same field". This script settles it:

  1. ranges and percentiles of band 6 and of each official channel on the common
     valid mask (does a unit rescale reconcile the [2.95, 88.57] bound?);
  2. Spearman rho AND Pearson r, plus an OLS fit band6 = a*channel + b with R^2
     and RMSE (a pure unit change must be linear with R^2 ~ 1);
  3. distinct-value counts (an 8-bit product has <= 255 levels; band 6 is
     float32 - if it has far more levels it is not the quantised product itself);
  4. the physical closure test: total count must be the sum of the three
     windowed channels, so band 6 is also regressed against K + Th + U from both
     official products. A tilt angle or a curvature has no reason to equal that
     sum.

Nothing here reads the fault catalogue, so nothing can leak into a holdout.

Run:  .venv/bin/python scripts/audit_band6_identity.py
Out:  reports/band6_identity.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import external as X                          # noqa: E402
from gems.rio import load_footprint, read_band          # noqa: E402

RAW = ROOT / "data" / "raw"
FEATURES = RAW / "gems-geodawn-numerical-features.tif"
BAND = 6
OUT = ROOT / "reports" / "band6_identity.json"

# channel candidates, one at a time (3.9 GB RAM box: never hold two full grids
# of float64 at once)
CANDIDATES = [
    ("radiometric_u8.tif", "rad_tc"),
    ("geodawn_rad_u8.tif", "TC"),
    ("radiometric_u8.tif", "rad_th"),
    ("geodawn_rad_u8.tif", "Th"),
    ("radiometric_u8.tif", "rad_k"),
    ("geodawn_rad_u8.tif", "K"),
    ("radiometric_u8.tif", "rad_u"),
    ("geodawn_rad_u8.tif", "U"),
]
TC_KEY = "radiometric::rad_tc"   # the channel the predeclared criterion names
SUM_SETS = [
    ("radiometric_u8.tif", ["rad_k", "rad_th", "rad_u"]),
    ("geodawn_rad_u8.tif", ["K", "Th", "U"]),
]


def pct(a: np.ndarray, qs=(0, 1, 50, 99, 100)) -> dict:
    if a.size == 0:
        return {}
    v = np.percentile(a, qs)
    names = ["min", "p1", "p50", "p99", "max"] if qs == (0, 1, 50, 99, 100) else \
            [f"p{q}" for q in qs]
    return {n: round(float(x), 6) for n, x in zip(names, v)}


def compare(b6: np.ndarray, chan: np.ndarray, mask: np.ndarray) -> dict:
    """All statistics on the common valid mask, one channel at a time."""
    y = b6[mask].astype(np.float64)
    x = chan[mask].astype(np.float64)
    n = int(y.size)
    ry = rankdata(y, method="average")
    rx = rankdata(x, method="average")
    rho = float(np.corrcoef(rx, ry)[0, 1])
    del rx, ry
    r = float(np.corrcoef(x, y)[0, 1])
    # OLS y = a*x + b
    sx, sy = x.sum(), y.sum()
    sxx = float((x * x).sum())
    sxy = float((x * y).sum())
    denom = n * sxx - sx * sx
    a = (n * sxy - sx * sy) / denom if denom else float("nan")
    b = (sy - a * sx) / n
    resid = y - (a * x + b)
    rmse = float(np.sqrt((resid ** 2).mean()))
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float((resid ** 2).sum()) / ss_tot if ss_tot > 0 else float("nan")
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = y / x
        good = np.isfinite(ratio) & (np.abs(x) > 1e-12)
        med_ratio = float(np.median(ratio[good])) if good.any() else float("nan")
        iqr_ratio = (float(np.percentile(ratio[good], 25)),
                     float(np.percentile(ratio[good], 75))) if good.any() else (
                    float("nan"), float("nan"))
    return {
        "n_common_valid_px": n,
        "spearman_rho": round(rho, 6),
        "pearson_r": round(r, 6),
        "ols_slope_band6_per_channel_unit": round(a, 8),
        "ols_intercept": round(b, 6),
        "ols_r2": round(r2, 6),
        "ols_rmse_in_band6_units": round(rmse, 6),
        "median_ratio_band6_over_channel": round(med_ratio, 8),
        "iqr_ratio": [round(iqr_ratio[0], 8), round(iqr_ratio[1], 8)],
        "band6_stats_on_mask": pct(y),
        "channel_stats_on_mask": pct(x),
        "band6_distinct_values": int(np.unique(y).size),
        "channel_distinct_values": int(np.unique(x).size),
    }


def main() -> int:
    t0 = time.time()
    X.require(*[c[0] for c in CANDIDATES])
    valid, known = load_footprint(RAW / "existing_faults.tif")
    b6 = read_band(FEATURES, BAND).astype(np.float32)
    base_mask = valid & np.isfinite(b6)
    out: dict = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "purpose": ("settle I-2: is provided band 6 (`tc`) the official USGS "
                    "radiometric total count, a tilt angle, or a curvature?"),
        "feature_file": FEATURES.name,
        "band_index": BAND,
        "band6_full_footprint_stats": pct(b6[base_mask].astype(np.float64)),
        "band6_distinct_values_full": int(np.unique(b6[base_mask]).size),
        "footprint_px": int(valid.sum()),
        "catalogue_px_not_used_here": int(known.sum()),
        "candidates": {},
        "sum_closure_tests": {},
        "external_provenance": "reports/external_manifest.json",
    }

    for fname, ch in CANDIDATES:
        arr = X.read_channel(fname, ch)
        mask = base_mask & np.isfinite(arr)
        stats = compare(b6, arr, mask)
        out["candidates"][f"{fname.split('_u8')[0]}::{ch}"] = stats
        print(f"[{time.time()-t0:6.1f}s] {fname}::{ch:8s} "
              f"rho={stats['spearman_rho']:.5f} r={stats['pearson_r']:.5f} "
              f"R2={stats['ols_r2']:.5f} slope={stats['ols_slope_band6_per_channel_unit']:.6g} "
              f"ratio={stats['median_ratio_band6_over_channel']:.6g} "
              f"chan_range=[{stats['channel_stats_on_mask']['min']:.4g}, "
              f"{stats['channel_stats_on_mask']['max']:.4g}] "
              f"n_distinct(chan)={stats['channel_distinct_values']}", flush=True)
        del arr, mask

    for fname, chans in SUM_SETS:
        total = None
        for ch in chans:
            arr = X.read_channel(fname, ch)
            total = arr.astype(np.float32) if total is None else total + arr
            del arr
        mask = base_mask & np.isfinite(total)
        stats = compare(b6, total, mask)
        key = f"{fname.split('_u8')[0]}::({' + '.join(chans)})"
        out["sum_closure_tests"][key] = stats
        print(f"[{time.time()-t0:6.1f}s] {key:34s} "
              f"rho={stats['spearman_rho']:.5f} r={stats['pearson_r']:.5f} "
              f"R2={stats['ols_r2']:.5f} slope={stats['ols_slope_band6_per_channel_unit']:.6g}",
              flush=True)
        del total, mask

    # ---- verdict logic, written before the run: what would each answer look like
    best = max(out["candidates"].items(), key=lambda kv: abs(kv[1]["spearman_rho"]))
    tc = out["candidates"].get(TC_KEY)
    if tc is None:
        raise SystemExit(f"criterion channel {TC_KEY!r} was not measured - "
                         "cannot issue a verdict; fix CANDIDATES, do not guess")
    tc_rho = abs(tc["spearman_rho"])
    tc_r2 = tc["ols_r2"]
    if not out["sum_closure_tests"]:
        raise SystemExit("no closure test was measured - cannot issue a verdict")
    sum_rho = max(abs(v["spearman_rho"]) for v in out["sum_closure_tests"].values())
    sum_r2 = max(v["ols_r2"] for v in out["sum_closure_tests"].values())
    ident = bool(tc_rho > 0.999 and tc_r2 > 0.99 and sum_rho > 0.99)
    out["verdict"] = {
        "band6_is_official_radiometric_total_count": bool(ident),
        "criterion_channel": TC_KEY,
        "best_single_channel_match": {"channel": best[0], **{
            k: best[1][k] for k in ("spearman_rho", "pearson_r", "ols_r2",
                                    "ols_slope_band6_per_channel_unit",
                                    "median_ratio_band6_over_channel")}},
        "sum_closure_best_rho": round(sum_rho, 6),
        "sum_closure_best_r2": round(sum_r2, 6),
        "criterion": ("Spearman rho > 0.999 AND linear-fit R^2 > 0.99 against the "
                      "official TC channel AND rho > 0.99 against K+Th+U from the "
                      "same release; a tilt angle or curvature cannot satisfy the "
                      "sum-closure test"),
    }
    OUT.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print(f"\nverdict: band6 == official radiometric total count? "
          f"{out['verdict']['band6_is_official_radiometric_total_count']}")
    print(f"wrote {OUT} ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
