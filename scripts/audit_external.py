#!/usr/bin/env python3
"""Audit the external official products now staged in data/external/.

Four questions are answered by measurement, not assertion:

  1. GRID      Do the external rasters share the competition grid exactly
               (CRS, affine transform, shape)? A mismatch would invalidate
               every downstream fusion.
  2. GAP       Independent reproduction of the USGS QFFDB "catalogue-gap"
               test: how many Quaternary-fault trace pixels inside the
               competition footprint have NO provided training label within
               the metric's own R = 300 m (3 px)?  This decides whether a
               "predict the difference between two official catalogues"
               strategy has any mass at all.
  3. IDENTITY  Which provided band corresponds to which official GeoDAWN
               channel? In particular irregularity I-2: is band 6 (`tc`) the
               radiometric total count, a tilt angle, or something else?
               Spearman rho against the official K/Th/U/TC and ratio grids.
  4. NOVELTY   How much NEW information does each external channel carry
               about faults, beyond the 19 provided bands? Reported as
               (a) univariate AUC against the provided catalogue,
               (b) catalogue recall inside the channel's own top-5 % of the
                   sampled domain (the same selection mass the submission
                   recipe uses), and
               (c) Spearman redundancy against the best-correlated provided
                   band (low |rho| together with high AUC = new signal).

Memory: the sandbox has ~3.9 GB RAM, so bands are streamed one at a time and
all statistics are computed on a fixed deterministic sample of the common
domain (`--sample`, default 300,000 pixels). Everything is written to
reports/external_audit.json.
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
from scipy.stats import rankdata, spearmanr

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
EXT = ROOT / "data" / "external"
REPORTS = ROOT / "reports"

EXPECTED_CRS_EPSG = 32611
EXPECTED_TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
EXPECTED_SHAPE = (3730, 3292)
R_PX = 3  # 300 m at 100 m pixels -- the metric's own neighbourhood radius
FEATURE_NODATA = -3.4028234663852886e38

EXTERNAL_FILES = [
    "geodawn_rad_u8.tif", "geodawn_extensions_u8.tif", "lidar_scarp_features_u8.tif",
    "radiometric_u8.tif", "topo_u8.tif", "qfaults_prior_u8.tif",
]
# channels used as data (the QFFDB product is a catalogue, handled separately)
DATA_FILES = ["geodawn_rad_u8.tif", "geodawn_extensions_u8.tif",
              "lidar_scarp_features_u8.tif", "radiometric_u8.tif", "topo_u8.tif"]


def channel_key(fname: str, ch: str) -> str:
    return f"{fname.split('_u8')[0]}::{ch}"


def auc_from_ranks(values: np.ndarray, positive: np.ndarray) -> float:
    """Rank-statistic AUC of `values` for discriminating `positive`."""
    n_pos = int(positive.sum())
    n_neg = int((~positive).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    r = rankdata(values)
    return float((r[positive].mean() - (n_pos + 1) / 2.0) / n_neg)


def read_channel(fname: str, index: int) -> np.ndarray:
    with rasterio.open(EXT / fname) as ds:
        return ds.read(index)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=300_000)
    args = ap.parse_args(argv)

    t0 = time.time()
    out: dict = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "purpose": "measurement audit of externally sourced official products",
        "expected_grid": {"crs": f"EPSG:{EXPECTED_CRS_EPSG}",
                          "transform": EXPECTED_TRANSFORM,
                          "shape_rows_cols": list(EXPECTED_SHAPE)},
        "sample_pixels": args.sample,
    }

    with rasterio.open(RAW / "existing_faults.tif") as src:
        lab = src.read(1)
    valid = lab >= 0
    known = lab > 0
    out["competition_labels"] = {"valid_px": int(valid.sum()),
                                 "known_fault_px": int(known.sum())}
    del lab

    # ---------------------------------------------------------------- 1. GRID
    grid: dict[str, dict] = {}
    band_index: dict[str, dict[str, int]] = {}
    for name in EXTERNAL_FILES:
        with rasterio.open(EXT / name) as ds:
            shape_ok = (ds.height, ds.width) == EXPECTED_SHAPE
            crs_ok = ds.crs is not None and ds.crs.to_epsg() == EXPECTED_CRS_EPSG
            tf = tuple(ds.transform)[:6]
            tf_ok = all(abs(a - b) < 1e-9 for a, b in zip(tf, EXPECTED_TRANSFORM))
            grid[name] = {"shape_ok": bool(shape_ok), "crs_ok": bool(crs_ok),
                          "transform_ok": bool(tf_ok), "bands": list(ds.descriptions),
                          "dtype": ds.dtypes[0], "nodata": ds.nodata,
                          "all_ok": bool(shape_ok and crs_ok and tf_ok)}
            band_index[name] = {d: i + 1 for i, d in enumerate(ds.descriptions)}
        print(f"[grid] {name}: {'OK' if grid[name]['all_ok'] else 'MISMATCH'} "
              f"({len(grid[name]['bands'])} bands)", flush=True)
    out["grid_conformance"] = grid
    if not all(g["all_ok"] for g in grid.values()):
        print("GRID MISMATCH - refusing to continue", file=sys.stderr)
        REPORTS.joinpath("external_audit.json").write_text(json.dumps(out, indent=2))
        return 2

    # ----------------------------------------------------------------- 2. GAP
    dist_to_label = ndi.distance_transform_edt(~known)   # float32, 49 MB
    qf = "qfaults_prior_u8.tif"
    q_names = grid[qf]["bands"]
    q_masks = {}
    for ch in q_names:
        q_masks[ch] = read_channel(qf, band_index[qf][ch]) > 0
    q_union = np.zeros(valid.shape, dtype=bool)
    for m in q_masks.values():
        q_union |= m
    gap: dict = {
        "source": "USGS Quaternary fault and fold database (QFFDB), "
                  "https://earthquake.usgs.gov/static/lfs/nshm/qfaults/Qfaults_GIS.zip, "
                  "https://doi.org/10.5066/P9BCVRCK, re-gridded onto the competition "
                  "grid by buffedlizard55-lab/7GEMSDOE (sha256-pinned)",
        "R_px": R_PX, "R_m": R_PX * 100,
        "definition": "a QFFDB trace pixel with no PROVIDED training label within "
                      "R px (Euclidean distance transform)",
    }
    for ch in q_names:
        m = q_masks[ch]
        in_fp = m & valid
        gap[ch] = {
            "px_total": int(m.sum()),
            "px_inside_footprint": int(in_fp.sum()),
            "px_outside_footprint": int((m & ~valid).sum()),
            "px_inside_footprint_with_no_label_within_R":
                int((in_fp & (dist_to_label > R_PX)).sum()),
        }
    in_fp = q_union & valid
    gap_px = in_fp & (dist_to_label > R_PX)
    gap["union_all_bands"] = {
        "px_total": int(q_union.sum()),
        "px_inside_footprint": int(in_fp.sum()),
        "px_outside_footprint": int((q_union & ~valid).sum()),
        "px_inside_footprint_with_no_label_within_R": int(gap_px.sum()),
        "fraction_of_in_footprint_traces_already_covered_within_R": round(
            float(1.0 - gap_px.sum() / max(int(in_fp.sum()), 1)), 8),
    }
    if int(gap_px.sum()):
        d = dist_to_label[gap_px]
        gap["gap_distance_to_nearest_label_px"] = {
            "n": int(d.size), "min": float(d.min()),
            "p50": float(np.percentile(d, 50)), "p90": float(np.percentile(d, 90)),
            "max": float(d.max())}
        comps, n_comps = ndi.label(gap_px, structure=np.ones((3, 3), int))
        sizes = np.bincount(comps.ravel())[1:]
        gap["gap_components"] = {"n": int(n_comps), "largest_px": int(sizes.max()),
                                 "median_px": float(np.median(sizes)),
                                 "total_px": int(sizes.sum())}
    out["qffdb_catalogue_gap"] = gap
    print(f"[gap] QFFDB trace px inside footprint: "
          f"{gap['union_all_bands']['px_inside_footprint']:,}; with no provided label "
          f"within 300 m: {gap['union_all_bands']['px_inside_footprint_with_no_label_within_R']:,}",
          flush=True)
    del q_masks, q_union, gap_px, in_fp

    # ------------------------------------------- 3/4. common domain + sampling
    common = valid.copy()
    coverage: dict[str, int] = {}
    for name in DATA_FILES:
        for ch in grid[name]["bands"]:
            arr = read_channel(name, band_index[name][ch])
            m = arr > 0
            coverage[channel_key(name, ch)] = int((m & valid).sum())
            common &= m
            del arr, m
    out["channel_coverage_inside_footprint_px"] = coverage
    out["common_domain_px"] = int(common.sum())
    out["common_domain_fraction_of_footprint"] = round(
        float(common.sum()) / float(valid.sum()), 6)
    print(f"[domain] common domain (all external channels defined): "
          f"{int(common.sum()):,} px = "
          f"{100*common.sum()/valid.sum():.1f}% of footprint", flush=True)

    flat_common = np.flatnonzero(common.ravel())
    rng = np.random.default_rng(11)
    n_s = min(args.sample, flat_common.size)
    idx = np.sort(rng.choice(flat_common, n_s, replace=False))
    del flat_common, common
    pos = known.ravel()[idx]
    out["sample"] = {"n": int(idx.size), "known_fault_px_in_sample": int(pos.sum())}

    # provided bands, sampled
    provided_names: list[str] = []
    prov_s: dict[str, np.ndarray] = {}
    with rasterio.open(RAW / "gems-geodawn-numerical-features.tif") as src:
        provided_names = [(d or f"b{i+1}").split(" - ")[0].strip()
                          for i, d in enumerate(src.descriptions)]
        for i, b_name in enumerate(provided_names, start=1):
            a = src.read(i).astype(np.float32).ravel()
            a = np.where(a <= FEATURE_NODATA + abs(FEATURE_NODATA) * 1e-6, np.nan, a)
            prov_s[b_name] = a[idx]
            del a
    # external channels, sampled
    ext_s: dict[str, np.ndarray] = {}
    for name in DATA_FILES:
        for ch in grid[name]["bands"]:
            a = read_channel(name, band_index[name][ch]).astype(np.float32).ravel()
            ext_s[channel_key(name, ch)] = a[idx]
            del a
    print(f"[sample] {n_s:,} px; provided bands {len(prov_s)}; external channels {len(ext_s)}",
          flush=True)

    # ------------------------------------------------------------- 3. IDENTITY
    ident = {}
    for b_name in provided_names:
        pv = prov_s[b_name]
        fin = np.isfinite(pv)
        rows = []
        for k, ev in ext_s.items():
            ok = fin & (ev > 0)
            if ok.sum() < 1000:
                continue
            rho = float(spearmanr(pv[ok], ev[ok]).statistic)
            rows.append((abs(rho), rho, k))
        rows.sort(reverse=True)
        ident[b_name] = {"best_matches": [{"channel": k, "spearman_rho": round(r, 5)}
                                          for _, r, k in rows[:4]]}
        print("[identity] " + f"{b_name:20s} " +
              ", ".join(f"{k.split('::')[-1]}@{k.split('::')[0]}={r:+.3f}"
                        for _, r, k in rows[:3]), flush=True)
    out["band_identity_vs_official_channels"] = ident

    # -------------------------------------------------------------- 4. NOVELTY
    prov_auc = {}
    for b_name, pv in prov_s.items():
        fin = np.isfinite(pv)
        if fin.sum() < 0.5 * pv.size:
            continue
        v = np.where(fin, pv, float(np.nanmin(pv[fin])))
        prov_auc[b_name] = round(auc_from_ranks(v, pos), 5)
    out["provided_band_auc_vs_catalogue"] = dict(
        sorted(prov_auc.items(), key=lambda kv: -abs(kv[1] - 0.5)))
    best_prov = max(prov_auc.items(), key=lambda kv: abs(kv[1] - 0.5))
    out["best_provided_band_univariate"] = {"band": best_prov[0], "auc": best_prov[1]}

    top5_n = int(0.05 * idx.size)
    novelty = {}
    for k, v in ext_s.items():
        auc = auc_from_ranks(v, pos)
        order = np.argsort(-v, kind="stable")[:top5_n]
        top5 = np.zeros(v.size, dtype=bool)
        top5[order] = True
        recall_top5 = float((top5 & pos).sum() / max(int(pos.sum()), 1))
        prec_top5 = float((top5 & pos).sum() / top5_n)
        best_rho, best_band = 0.0, None
        for b_name, pv in prov_s.items():
            fin = np.isfinite(pv)
            r = float(spearmanr(v[fin], pv[fin]).statistic)
            if abs(r) > abs(best_rho):
                best_rho, best_band = r, b_name
        novelty[k] = {"auc_vs_provided_catalogue": round(float(auc), 5),
                      "catalogue_recall_in_own_top5pct": round(recall_top5, 5),
                      "catalogue_precision_in_own_top5pct": round(prec_top5, 5),
                      "coverage_inside_footprint_px": coverage[k],
                      "max_abs_spearman_vs_provided_bands": round(best_rho, 5),
                      "most_redundant_with": best_band}
        print(f"[novelty] {k:42s} AUC={auc:.4f} top5%recall={recall_top5:.4f} "
              f"prec={prec_top5:.4f} max|rho|={best_rho:+.3f} ({best_band})", flush=True)
    out["external_channel_novelty"] = novelty

    out["runtime_s"] = round(time.time() - t0, 1)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "external_audit.json").write_text(
        json.dumps(out, indent=2, allow_nan=False) + "\n")
    print(f"\nwrote reports/external_audit.json ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
