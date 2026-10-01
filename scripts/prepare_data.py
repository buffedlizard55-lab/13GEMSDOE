#!/usr/bin/env python3
"""Turn data/raw/ into the derived arrays every model and gate needs.

Writes into data/derived/ (gitignored):
  footprint.npy        bool 3730x3292 -- the officially valid/scored region
  known_faults.npy     bool 3730x3292 -- the USGS/INGENIOUS catalogue raster
  band_index.json      band number -> description / data_category, read from
                       the feature stack's own GDAL band tags (never typed)
  band_stats.json      per-band finite count, sentinel count inside the
                       footprint, min/max/mean over footprint-valid pixels

It also enforces the two data facts that have repeatedly bitten this project:

  * the feature stack stores missing data as the float32 most-negative sentinel
    -3.4028235e+38 (and, in some bands, true NaN).  Both are counted, per band,
    INSIDE the scored footprint, because a model that propagates them writes
    NaN into the submission and the platform answers
    "Predicted values must be in range [0, 1]".
  * the footprint must come from the official sample_submission.tif, not from a
    band of the feature stack.

Run:  python scripts/prepare_data.py [--no-features]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import encoding  # noqa: E402

RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived"
SENTINEL = np.float32(-3.4028235e38)


def resolve(*names: str) -> Path:
    for n in names:
        if (RAW / n).exists():
            return RAW / n
    raise SystemExit(f"missing {names} in {RAW}; run "
                     "bash scripts/download_competition_data.sh")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-features", action="store_true",
                    help="prepare footprint + labels only (fast, no 419 MB read)")
    args = ap.parse_args()

    DERIVED.mkdir(parents=True, exist_ok=True)
    out: dict = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

    tmpl = resolve("sample_submission.tif", "example_submission.tif")
    lab = resolve("labels.tif", "existing_faults.tif")

    with rasterio.open(tmpl) as s:
        t = s.read(1)
        out["template"] = {
            "path": str(tmpl.relative_to(ROOT)), "shape": list(t.shape),
            "crs": str(s.crs), "dtype": s.dtypes[0],
            "nodata": None if s.nodata is None else str(s.nodata),
            "transform": [float(v) for v in tuple(s.transform)[:6]],
        }
    footprint = np.isfinite(t)
    if tuple(t.shape) != encoding.EXPECTED_SHAPE:
        raise SystemExit(f"template shape {t.shape} != {encoding.EXPECTED_SHAPE}")
    if int(footprint.sum()) != encoding.FOOTPRINT_PIXELS:
        raise SystemExit(f"footprint {int(footprint.sum())} != {encoding.FOOTPRINT_PIXELS}")
    del t

    with rasterio.open(lab) as s:
        l = s.read(1)
        out["labels"] = {"path": str(lab.relative_to(ROOT)), "dtype": s.dtypes[0],
                         "nodata": None if s.nodata is None else float(s.nodata),
                         "values": sorted(int(v) for v in np.unique(l))}
    known = l > 0
    out["labels"]["n_positive"] = int(known.sum())
    out["labels"]["footprint_equals_labels_ge_0"] = bool(np.array_equal(footprint, l >= 0))
    out["labels"]["positives_inside_footprint"] = int((known & footprint).sum())
    out["labels"]["positives_outside_footprint"] = int((known & ~footprint).sum())
    del l

    np.save(DERIVED / "footprint.npy", footprint)
    np.save(DERIVED / "known_faults.npy", known)
    print(f"footprint {int(footprint.sum()):,} px -> {DERIVED/'footprint.npy'}")
    print(f"known faults {int(known.sum()):,} px -> {DERIVED/'known_faults.npy'}")
    print(f"  footprint == (labels >= 0): {out['labels']['footprint_equals_labels_ge_0']}")
    print(f"  catalogue pixels inside footprint: {out['labels']['positives_inside_footprint']:,}")

    if args.no_features:
        (DERIVED / "prepare_manifest.json").write_text(json.dumps(out, indent=2) + "\n")
        print("--no-features: band audit skipped")
        return 0

    feats = resolve("training_features.tif", "gems-geodawn-numerical-features.tif")
    bands, stats = {}, {}
    with rasterio.open(feats) as s:
        out["features"] = {
            "path": str(feats.relative_to(ROOT)), "count": s.count,
            "shape": list(s.shape), "crs": str(s.crs), "dtype": s.dtypes[0],
            "nodata": None if s.nodata is None else float(s.nodata),
            "transform": [float(v) for v in tuple(s.transform)[:6]],
        }
        if tuple(s.shape) != encoding.EXPECTED_SHAPE:
            raise SystemExit(f"feature stack shape {s.shape} != {encoding.EXPECTED_SHAPE}")
        for b in range(1, s.count + 1):
            tags = s.tags(b)
            bands[b] = {"description": tags.get("description"),
                        "data_category": tags.get("data_category")}
            # read band by band: 3730*3292*4 B = 49 MB per band, safe in 3 GB
            a = s.read(b).astype(np.float32, copy=False)
            bad_sentinel = a <= SENTINEL
            nan = np.isnan(a)
            good = footprint & ~bad_sentinel & ~nan
            v = a[good]
            stats[b] = {
                "n_sentinel_inside_footprint": int((bad_sentinel & footprint).sum()),
                "n_nan_inside_footprint": int((nan & footprint).sum()),
                "n_valid_outside_footprint": int((~bad_sentinel & ~nan & ~footprint).sum()),
                "n_good_inside_footprint": int(good.sum()),
                "min": float(v.min()) if v.size else None,
                "max": float(v.max()) if v.size else None,
                "mean": float(v.mean()) if v.size else None,
                "p01": float(np.percentile(v, 1)) if v.size else None,
                "p99": float(np.percentile(v, 99)) if v.size else None,
            }
            print(f"  band {b:2d} {str(bands[b]['description'])[:52]:52s} "
                  f"sentinel_in_fp={stats[b]['n_sentinel_inside_footprint']:5d} "
                  f"nan_in_fp={stats[b]['n_nan_inside_footprint']:5d} "
                  f"range=[{stats[b]['min']:.4g}, {stats[b]['max']:.4g}]")
            del a, v
    out["bands"] = bands
    out["band_stats"] = stats
    out["bands_with_invalid_pixels_inside_footprint"] = sorted(
        b for b, st in stats.items()
        if st["n_sentinel_inside_footprint"] or st["n_nan_inside_footprint"])

    (DERIVED / "band_index.json").write_text(json.dumps(bands, indent=2) + "\n")
    (DERIVED / "band_stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    (DERIVED / "prepare_manifest.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nbands with invalid pixels INSIDE the scored footprint: "
          f"{out['bands_with_invalid_pixels_inside_footprint']}")
    print("wrote data/derived/{band_index,band_stats,prepare_manifest}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
