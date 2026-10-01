"""The empirically-proven DrivenData GeoTIFF encoding for this competition.

WHY THIS MODULE EXISTS
----------------------
On 2026-09-30 the DrivenData submission form rejected this project's file with
the single sentence ``Predicted values must be in range [0, 1]``.  Every finite
value in that file was 0.0 or 1.0, so the message could not be explained by the
pixel values alone.  Sessions 6-7 guessed that the *NaN cells* were the cause
and flipped the shipped primary to an all-finite zero-filled encoding.

That guess is now falsified by direct measurement (2026-10-01, this module):

1.  The official ``sample_submission.tif`` that DrivenData itself publishes as
    the format template (sha256 2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4
    0454d35cbc, pin reproduced in two independent group repos) contains
    **7,111,787 NaN cells** and declares ``GDAL_NODATA = nan``.  A validator
    that rejected NaN as "out of range" would reject its own template.

2.  **Nine** files this group uploaded were accepted and scored by the platform
    (public scores 0.0286 ... 0.1563, and 0.1294 twice).  All nine -- without
    exception -- are ``float32``, ``EPSG:32611``, ``3730 x 3292``,
    transform ``(100, 0, 243350, 0, -100, 4508550)``, ``nodata = nan``, with
    **exactly** 7,111,787 NaN cells, **zero** NaN inside the 5,167,373-pixel
    footprint and **zero** finite cells outside it.  Their compression
    (DEFLATE and LZW), tiling (tiled and striped) and predictor (1 and 3) all
    differ, so none of those is the discriminator.

3.  The one rejected file differs from all nine in exactly one structural
    respect: ``Predictor = 2`` (TIFF horizontal differencing) on ``SampleFormat
    = 3`` (IEEE float) ``BitsPerSample = 32``.  Horizontal differencing is
    defined by TIFF 6.0 for integer samples; the floating-point predictor is
    ``Predictor = 3`` (TIFF Technical Note 3).  A reader that does not apply
    the accumulator to that stream returns the raw differences reinterpreted as
    float32, which for this file spans **[-4.0, 3.0]** -- i.e. it produces
    exactly the reported error while the value range of the real pixels is
    [0, 1].  ``simulate_ignored_predictor2`` reproduces that arithmetic.

CONSEQUENCE (the policy this module enforces)
---------------------------------------------
The primary upload encoding is **NaN outside the footprint, ``nodata=nan``,
finite values in [0, 1] inside, and never ``Predictor=2``**.  That is the
encoding of the official template *and* of all nine accepted files.  The
all-finite zero-filled variant is kept as a labelled hedge only; no all-finite
file in this group's history has an acceptance receipt independent of its
NaN-outside twin.

Honest limits: this module measures bytes.  It cannot observe DrivenData's
validator; only the form's own response can confirm acceptance, and that
response is logged in ``reports/form_responses.json``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Grid constants, measured from the official rasters (not copied from prose).
#   sample_submission.tif  sha256 2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc
#   labels.tif             sha256 7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093
# ---------------------------------------------------------------------------
EXPECTED_SHAPE = (3730, 3292)
EXPECTED_CRS = "EPSG:32611"
EXPECTED_TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
FOOTPRINT_PIXELS = 5_167_373
OUTSIDE_PIXELS = 7_111_787
SAMPLE_SUBMISSION_SHA256 = (
    "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc")
LABELS_SHA256 = (
    "7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093")

# TIFF tag values (TIFF 6.0 s.14; TIFF Technical Note 3 for PREDICTOR=3).
PREDICTOR_NONE = 1
PREDICTOR_HORIZONTAL = 2      # integer samples only -- INVALID for IEEE float
PREDICTOR_FLOATINGPOINT = 3   # the float predictor defined by Technical Note 3
COMPRESSION_NAMES = {1: "NONE", 5: "LZW", 8: "ADOBE_DEFLATE", 32946: "DEFLATE"}

#: The writing profile used for every file this module publishes.  It is the
#: byte layout of the official ``sample_submission.tif``: LZW, one-row strips,
#: no predictor.  ``sc_gems6_hgb88_LB0.0286.tif`` (accepted, scored 0.0286)
#: has exactly this layout.
SAFE_PROFILE: dict[str, Any] = {
    "driver": "GTiff",
    "dtype": "float32",
    "count": 1,
    "compress": "lzw",
    "tiled": False,
    "blockysize": 1,
    "predictor": PREDICTOR_NONE,
}


# ---------------------------------------------------------------------------
def read_layout(path: str | Path) -> dict[str, Any]:
    """TIFF structural tags + GDAL profile facts for one file."""
    import rasterio
    import tifffile

    with rasterio.open(path) as s:
        arr = s.read(1)
        prof = {
            "driver": s.driver,
            "count": s.count,
            "dtype": s.dtypes[0],
            "crs": str(s.crs),
            "shape": list(s.shape),
            "transform": [float(v) for v in tuple(s.transform)[:6]],
            "nodata": (None if s.nodata is None
                       else ("nan" if np.isnan(s.nodata) else float(s.nodata))),
        }
    with tifffile.TiffFile(path) as t:
        pg = t.pages[0]
        comp = pg.tags.get("Compression")
        pred = pg.tags.get("Predictor")
        sf = pg.tags.get("SampleFormat")
        bps = pg.tags.get("BitsPerSample")
        comp = int(comp.value) if comp is not None else None
        layout = {
            "compression_code": comp,
            "compression": COMPRESSION_NAMES.get(comp, str(comp)),
            "predictor": int(pred.value) if pred is not None else None,
            "sample_format": int(sf.value) if sf is not None else None,
            "bits_per_sample": (int(bps.value[0]) if bps is not None
                                and isinstance(bps.value, tuple) else
                                (int(bps.value) if bps is not None else None)),
            "tiled": bool(pg.is_tiled),
            "rows_per_strip": (int(pg.tags["RowsPerStrip"].value)
                               if "RowsPerStrip" in pg.tags else None),
            "tile_width": (int(pg.tags["TileWidth"].value)
                           if "TileWidth" in pg.tags else None),
        }
    return {"profile": prof, "layout": layout, "array_shape": list(arr.shape)}


def placement(arr: np.ndarray, footprint: np.ndarray) -> dict[str, Any]:
    """Where the NaNs are, relative to the official valid footprint."""
    arr = np.asarray(arr)
    nan = np.isnan(arr)
    finite = np.isfinite(arr)
    fin = arr[finite]
    return {
        "n_nan_total": int(nan.sum()),
        "n_nan_inside_footprint": int((nan & footprint).sum()),
        "n_finite_outside_footprint": int((finite & ~footprint).sum()),
        "n_nan_outside_footprint": int((nan & ~footprint).sum()),
        "finite_min": float(fin.min()) if fin.size else None,
        "finite_max": float(fin.max()) if fin.size else None,
        "n_positive": int((fin > 0).sum()) if fin.size else 0,
    }


def range_checks(arr: np.ndarray) -> dict[str, Any]:
    """Every plausible way a platform could test "values in range [0, 1]"."""
    a = np.asarray(arr, dtype=np.float32)
    fin = a[np.isfinite(a)]
    naive = bool(((a >= 0) & (a <= 1)).all())
    return {
        "naive_all_in_0_1": naive,
        "nan_aware_all_in_0_1": bool(fin.size and fin.min() >= 0 and fin.max() <= 1),
        "has_nan": bool(np.isnan(a).any()),
        "n_nan": int(np.isnan(a).sum()),
        "n_inf": int(np.isinf(a).sum()),
    }


def simulate_ignored_predictor2(arr: np.ndarray) -> dict[str, Any]:
    """What a reader that ignores ``Predictor=2`` would decode.

    libtiff stores horizontal-differenced rows; the first sample of each row is
    raw and each later sample is ``u[i] - u[i-1]`` on the *bit pattern* viewed
    as an unsigned integer of the sample width.  A reader that decompresses but
    never runs the accumulator hands those differences to the caller as if they
    were float32.  This function computes that stream, so the failure mode is
    demonstrated rather than asserted.
    """
    a = np.asarray(arr, dtype=np.float32)
    u = a.view(np.uint32)
    stored = u.copy()
    stored[:, 1:] = u[:, 1:] - u[:, :-1]
    naive = stored.view(np.float32)
    fin = naive[np.isfinite(naive)]
    return {
        "decoded_min": float(fin.min()) if fin.size else None,
        "decoded_max": float(fin.max()) if fin.size else None,
        "all_in_0_1": bool(((naive >= 0) & (naive <= 1)).all()),
        "fraction_in_0_1": float(((naive >= 0) & (naive <= 1)).mean()),
        "verdict": ("produces values outside [0, 1] -> the exact form error "
                    "'Predicted values must be in range [0, 1]'"
                    if not ((naive >= 0) & (naive <= 1)).all() else
                    "stays inside [0, 1]; predictor mishandling would NOT "
                    "explain a range error for this array"),
    }


# ---------------------------------------------------------------------------
#: The accepted-pattern rule, stated once and used by every gate.
def accepted_pattern(report: dict[str, Any]) -> tuple[bool, list[str]]:
    """Does `report` (from `audit_file`) match the pattern of all nine
    platform-accepted files?  Returns (matches, list_of_deviations)."""
    dev: list[str] = []
    p, l, pl = report["profile"], report["layout"], report["placement"]
    if p["dtype"] != "float32":
        dev.append(f"dtype {p['dtype']} != float32")
    if p["count"] != 1:
        dev.append(f"count {p['count']} != 1")
    if p["crs"] != EXPECTED_CRS:
        dev.append(f"crs {p['crs']} != {EXPECTED_CRS}")
    if tuple(p["shape"]) != EXPECTED_SHAPE:
        dev.append(f"shape {tuple(p['shape'])} != {EXPECTED_SHAPE}")
    if tuple(p["transform"]) != EXPECTED_TRANSFORM:
        dev.append(f"transform {tuple(p['transform'])} != {EXPECTED_TRANSFORM}")
    if p["nodata"] != "nan":
        dev.append(f"nodata {p['nodata']!r} != 'nan' (all nine accepted files declare nan)")
    if pl["n_nan_inside_footprint"] != 0:
        dev.append(f"{pl['n_nan_inside_footprint']} NaN inside the footprint "
                   "-> 'Predicted values must be in range [0, 1]'")
    if pl["n_finite_outside_footprint"] != 0:
        dev.append(f"{pl['n_finite_outside_footprint']} finite cells outside the "
                   "footprint where the official template is NaN")
    if pl["n_nan_outside_footprint"] != OUTSIDE_PIXELS:
        dev.append(f"{pl['n_nan_outside_footprint']} NaN outside != {OUTSIDE_PIXELS}")
    if pl["finite_min"] is None or pl["finite_min"] < 0.0 or pl["finite_max"] > 1.0:
        dev.append(f"finite range [{pl['finite_min']}, {pl['finite_max']}] not inside [0, 1]")
    if l["predictor"] == PREDICTOR_HORIZONTAL:
        dev.append("Predictor=2 (horizontal differencing) on IEEE-float samples; "
                   "no platform-accepted file in this group's history uses it")
    if l["sample_format"] != 3 or l["bits_per_sample"] != 32:
        dev.append(f"SampleFormat/BitsPerSample {l['sample_format']}/{l['bits_per_sample']} != 3/32")
    return (not dev, dev)


def audit_file(path: str | Path, footprint: np.ndarray) -> dict[str, Any]:
    """Full structural + placement audit of one GeoTIFF."""
    import rasterio

    path = Path(path)
    with rasterio.open(path) as s:
        arr = s.read(1)
    facts = read_layout(path)
    out = {
        "file": path.name,
        "bytes": path.stat().st_size,
        "profile": facts["profile"],
        "layout": facts["layout"],
        "placement": placement(arr, footprint),
        "range_checks": range_checks(arr),
    }
    ok, dev = accepted_pattern(out)
    out["matches_accepted_pattern"] = ok
    out["deviations_from_accepted_pattern"] = dev
    if out["layout"]["predictor"] == PREDICTOR_HORIZONTAL:
        out["predictor2_simulation"] = simulate_ignored_predictor2(arr)
    return out
