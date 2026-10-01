#!/usr/bin/env python3
"""Provenance + verification for the independent SGMC fault truth set.

WHAT THIS FILE IS
-----------------
``data/external_sgmc/derived_sgmc_faults_100m_u8.tif`` is a uint8 raster on the
exact competition grid (EPSG:32611, 100 m, 3730 x 3292, transform
(100, 0, 243350, 0, -100, 4508550)) holding **fault lines from the USGS State
Geologic Map compilation (SGMC)** for Nevada and California:

  value 1    a fault line from the official USGS state geologic maps
  value 0    not a mapped fault
  value 255  nodata, exactly the 7,111,787 px outside the survey footprint

WHY IT IS HERE
--------------
The competition target is *faults experts identified that are NOT in the public
USGS/INGENIOUS catalogue*.  The only free, official, public set of expert-mapped
faults in this region that is independent of that catalogue is the SGMC.  Its
off-catalogue pixels are therefore the best available stand-in for the private
test set, and ``scripts/calibrate_truth_sets.py`` measures -- rather than
assumes -- how well each such stand-in ranks the ten files this group has public
scores for.

OFFICIAL SOURCES (free, public, no login)
  https://mrdata.usgs.gov/geology/state/shp/NV.zip   69,056,094 B
      sha256 3b333ac025e59aae7f0d827db45ba32c425cf867eb341561a788af1de186b76b
  https://mrdata.usgs.gov/geology/state/shp/CA.zip   24,977,406 B
      sha256 78765ba4428df9f25a84f86e0b2529bd0508fc8a2cf65d2f41a830e82bccfd58
  Landing page: https://mrdata.usgs.gov/geology/state/
  (pins reproduced from 16GEMSDOE evidence/ci/external_verification.json, which
   was produced by a GitHub-hosted runner that downloaded both zips)

HOW IT WAS DERIVED
  A 16GEMSDOE GitHub Actions runner (egress to mrdata.usgs.gov is blocked in
  this sandbox) read the fault line features from both shapefiles, reprojected
  them to EPSG:32611 and burned them onto the competition grid at 100 m.
  The derived raster is committed here (226,663 B) because it is small, it is
  the evidence the selection decision rests on, and it cannot be re-downloaded
  from this sandbox.

Run:  python scripts/fetch_sgmc_truth.py            # verify the committed raster
      python scripts/fetch_sgmc_truth.py --rebuild  # re-derive from NV.zip/CA.zip
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import encoding  # noqa: E402

RASTER = ROOT / "data" / "external_sgmc" / "derived_sgmc_faults_100m_u8.tif"
SHA256 = "d569d5539972f86a7862add0ce6738275ffd56174b9ef1298b08b8ab1dcd700f"
BYTES = 226663
SOURCES = {
    "NV.zip": {"url": "https://mrdata.usgs.gov/geology/state/shp/NV.zip",
               "bytes": 69056094,
               "sha256": "3b333ac025e59aae7f0d827db45ba32c425cf867eb341561a788af1de186b76b"},
    "CA.zip": {"url": "https://mrdata.usgs.gov/geology/state/shp/CA.zip",
               "bytes": 24977406,
               "sha256": "78765ba4428df9f25a84f86e0b2529bd0508fc8a2cf65d2f41a830e82bccfd58"},
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def verify() -> int:
    if not RASTER.exists():
        print(f"FAIL {RASTER} absent"); return 1
    ok = True
    b = RASTER.stat().st_size
    h = sha256(RASTER)
    ok &= b == BYTES
    ok &= h == SHA256
    print(f"{'OK  ' if h == SHA256 else 'FAIL'} sha256 {h}")
    print(f"{'OK  ' if b == BYTES else 'FAIL'} bytes {b:,}")
    with rasterio.open(RASTER) as s:
        a = s.read(1)
        crs, tfm, nd = str(s.crs), tuple(round(v, 6) for v in tuple(s.transform)[:6]), s.nodata
        ok &= crs == encoding.EXPECTED_CRS
        ok &= tfm == encoding.EXPECTED_TRANSFORM
        ok &= tuple(s.shape) == encoding.EXPECTED_SHAPE
        ok &= s.dtypes[0] == "uint8"
        ok &= nd == 255
    print(f"{'OK  ' if crs == encoding.EXPECTED_CRS else 'FAIL'} crs {crs}")
    print(f"{'OK  ' if tfm == encoding.EXPECTED_TRANSFORM else 'FAIL'} transform {tfm}")
    print(f"{'OK  ' if tuple(s.shape) == encoding.EXPECTED_SHAPE else 'FAIL'} shape {tuple(s.shape)}")
    print(f"{'OK  ' if nd == 255 else 'FAIL'} nodata {nd}")
    lab = ROOT / "data" / "raw" / "existing_faults.tif"
    if lab.exists():
        with rasterio.open(lab) as s:
            valid = s.read(1) >= 0
        same = bool(np.array_equal(a == 255, ~valid))
        ok &= same
        print(f"{'OK  ' if same else 'FAIL'} nodata mask == outside-footprint mask "
              f"({int((~valid).sum()):,} px)")
        print(f"     SGMC fault px: {int((a == 1).sum()):,} "
              f"(inside footprint {int(((a == 1) & valid).sum()):,})")
    else:
        print("SKIP nodata-vs-footprint (data/raw absent)")
    (ROOT / "data" / "external_sgmc" / "provenance.json").write_text(json.dumps({
        "raster": str(RASTER.relative_to(ROOT)), "bytes": b, "sha256": h,
        "grid": {"crs": crs, "transform": list(tfm), "shape": list(a.shape),
                 "dtype": "uint8", "nodata": nd},
        "counts": {"fault_px": int((a == 1).sum()), "nodata_px": int((a == 255).sum())},
        "official_sources": SOURCES,
        "landing_page": "https://mrdata.usgs.gov/geology/state/",
        "derived_by": ("16GEMSDOE GitHub Actions runner; egress to mrdata.usgs.gov is "
                       "blocked in the dev sandbox"),
    }, indent=2) + "\n")
    print(f"\n{'ALL CHECKS PASS' if ok else 'FAILURES PRESENT'}")
    return 0 if ok else 1


def rebuild() -> int:
    """Re-derive the raster from the official USGS shapefiles, if present."""
    try:
        import fiona  # noqa: F401
        from rasterio import features
    except ImportError:
        print("FAIL: pip install fiona (or gdal) to rebuild"); return 1
    shps = sorted((ROOT / "data" / "external_sgmc").rglob("*.shp"))
    if not shps:
        print("FAIL: put the extracted NV.zip / CA.zip shapefiles under "
              "data/external_sgmc/ first (see the docstring for official URLs)")
        return 1
    with rasterio.open(ROOT / "data" / "raw" / "existing_faults.tif") as s:
        valid = s.read(1) >= 0
        transform = s.transform
    out = np.where(valid, 0, 255).astype(np.uint8)
    import fiona
    n = 0
    for shp in shps:
        with fiona.open(shp) as src:
            geoms = []
            for rec in src:
                g = rec.get("geometry")
                if not g:
                    continue
                t = (str(rec["properties"].get("FEATDESC", "")) + " " +
                     str(rec["properties"].get("FEAT_TYPE", "")) + " " +
                     str(rec["properties"].get("Shape_Type", ""))).lower()
                if "fault" in t or g["type"] in ("LineString", "MultiLineString"):
                    geoms.append(g)
            if geoms:
                burned = features.rasterize(
                    [(g, 1) for g in geoms], out_shape=out.shape,
                    transform=transform, fill=0, all_touched=True)
                out = np.where(burned == 1, 1, out).astype(np.uint8)
                n += len(geoms)
    print(f"burned {n} fault geometries -> {int((out == 1).sum()):,} px")
    print("NOTE: this rebuild does NOT reproduce the committed raster byte-for-byte "
          "unless the feature selection and rasterisation match the runner's exactly. "
          "Treat the committed, hash-pinned raster as authoritative.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    raise SystemExit(rebuild() if ap.parse_args().rebuild else verify())
