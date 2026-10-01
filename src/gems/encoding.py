"""Local template-compatible GeoTIFF policy, NOT proof of platform acceptance.

The official template has NaN outside the footprint and NoData=nan. We follow
that convention and require finite [0,1] float32 values inside. A zero-fill twin
is a diagnostic alternative, not a second geological prediction.

The archived range rejection is user-reported, not a captured platform receipt.
Three available TIFF readers decode the rejected file correctly. Ignoring its
Predictor=2 *in a simulation* can produce out-of-range numbers; there is no
evidence that DrivenData actually does so. Neither a predictor root cause nor
NaN handling nor a changed validator has been established. Historical filename
scores/team records also do not prove acceptance of those exact bytes.

`accepted_pattern` and its report keys retain their historical API names for
compatibility; they mean 'matches local template policy', NOT 'accepted remotely'.
See knowledge/13_audit_corrections_2026-10-01.md and form_responses.json.
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
PREDICTOR_HORIZONTAL = 2      # avoided for float interoperability; not a proven rejection cause
PREDICTOR_FLOATINGPOINT = 3   # the float predictor defined by Technical Note 3
COMPRESSION_NAMES = {1: "NONE", 5: "LZW", 8: "ADOBE_DEFLATE", 32946: "DEFLATE"}

#: The writing profile used for every file this module publishes.  It is the
#: layout of the measured official template: LZW, one-row strips, no predictor.
#: A compatible layout is a local fact, not a remote acceptance receipt.
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
    simulated rather than attributed to DrivenData. This is not a server trace.
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
        "evidence_class": "hypothetical_reader_simulation_not_server_observation",
        "verdict": ("hypothetically produces values outside [0, 1]; no evidence "
                    "the platform uses this decoding path"
                    if not ((naive >= 0) & (naive <= 1)).all() else
                    "stays inside [0, 1]; predictor mishandling would NOT "
                    "explain a range error for this array"),
    }


# ---------------------------------------------------------------------------
#: Local template-policy rule; historical API name is retained.
def accepted_pattern(report: dict[str, Any]) -> tuple[bool, list[str]]:
    """Match the measured template/grid and our conservative encoding policy.

    Returns local compliance only. No platform acceptance is inferred.
    """
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
        dev.append(f"nodata {p['nodata']!r} != 'nan' (the measured official template declares nan)")
    if pl["n_nan_inside_footprint"] != 0:
        dev.append(f"{pl['n_nan_inside_footprint']} NaN inside the footprint "
                   "violates finite-footprint policy")
    if pl["n_finite_outside_footprint"] != 0:
        dev.append(f"{pl['n_finite_outside_footprint']} finite cells outside the "
                   "footprint where the official template is NaN")
    if pl["n_nan_outside_footprint"] != OUTSIDE_PIXELS:
        dev.append(f"{pl['n_nan_outside_footprint']} NaN outside != {OUTSIDE_PIXELS}")
    if pl["finite_min"] is None or pl["finite_min"] < 0.0 or pl["finite_max"] > 1.0:
        dev.append(f"finite range [{pl['finite_min']}, {pl['finite_max']}] not inside [0, 1]")
    if l["predictor"] == PREDICTOR_HORIZONTAL:
        dev.append("Predictor=2 (horizontal differencing) on IEEE-float samples; "
                   "excluded by our interoperability policy, not a diagnosed server cause")
    if report.get("range_checks", {}).get("n_inf", 0):
        dev.append("infinite samples violate the submission policy")
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
    out["matches_template_policy"] = ok
    out["deviations_from_template_policy"] = dev
    out["matches_accepted_pattern"] = ok  # deprecated alias, not an acceptance receipt
    out["deviations_from_accepted_pattern"] = dev
    out["platform_acceptance_established"] = False
    if out["layout"]["predictor"] == PREDICTOR_HORIZONTAL:
        out["predictor2_simulation"] = simulate_ignored_predictor2(arr)
    return out
