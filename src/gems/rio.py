"""Raster I/O plus strict local checks for the competition GeoTIFF format.

A historical remote rejection reported `Predicted values must be in range
[0, 1]`, but the exact file and cause are not established. This validator
checks the stated grid, dtype, band count, value range, and (when supplied) the
valid-footprint NoData convention. It does not reproduce DrivenData's remote
validator or establish score/performance equivalence.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio

# Grid constants read from the official example_submission.tif / existing_faults.tif
EXPECTED_SHAPE = (3730, 3292)
EXPECTED_CRS = "EPSG:32611"
EXPECTED_TRANSFORM = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)


def read_band(path: str | Path, band: int = 1) -> np.ndarray:
    with rasterio.open(path) as src:
        a = src.read(band).astype(np.float32)
        nd = src.nodatavals[band - 1]
    if nd is not None and not (isinstance(nd, float) and np.isnan(nd)):
        a = np.where(a == nd, np.nan, a)
    return a


def read_profile(path: str | Path) -> dict:
    with rasterio.open(path) as src:
        return dict(src.profile)


def load_footprint(labels_path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Return (valid_mask, known_fault_mask) from the official label raster."""
    with rasterio.open(labels_path) as src:
        a = src.read(1)
    return (a >= 0), (a > 0)


# ---------------------------------------------------------------------------


@dataclass
class ValidationReport:
    ok: bool
    errors: list[str]
    warnings: list[str]
    stats: dict

    def render(self) -> str:
        lines = [f"submission validation: {'PASS' if self.ok else 'FAIL'}"]
        for e in self.errors:
            lines.append(f"  ERROR   {e}")
        for w in self.warnings:
            lines.append(f"  WARNING {w}")
        for k, v in self.stats.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)


def validate_submission(path: str | Path,
                        allow_nan: bool = True,
                        valid_mask: np.ndarray | None = None,
                        require_nodata_outside: bool = False) -> ValidationReport:
    """Check a GeoTIFF against every stated submission requirement.

    Official requirements (problem description → Submission format):
      * same projected CRS as the training data (EPSG:32611)
      * same resolution (100 m)
      * same bounds; data outside the bounds null or nan
      * a single float32 band with values between 0 and 1

    `allow_nan=False` requires every stored value to be finite. When a
    `valid_mask` is supplied, the validator also checks that predictions inside
    the footprint are finite. `require_nodata_outside=True` requires NaN outside
    that footprint, following the official submission-format text; finite zero
    fill can be checked separately as a diagnostic but is not treated as
    equivalent to NoData.
    """
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict = {}

    with rasterio.open(path) as src:
        stats["driver"] = src.driver
        stats["shape"] = list(src.shape)
        if src.driver != "GTiff":
            errors.append(f"must be a GeoTIFF; got driver {src.driver}")
        stats["count"] = src.count
        stats["dtype"] = src.dtypes[0]
        stats["crs"] = str(src.crs)
        stats["nodata"] = (None if src.nodata is None
                           else ("nan" if np.isnan(src.nodata) else src.nodata))
        stats["transform"] = [round(v, 6) for v in list(src.transform)[:6]]

        if src.count != 1:
            errors.append(f"must be single-band; got {src.count}")
        if src.dtypes[0] != "float32":
            errors.append(f"datatype must be float32; got {src.dtypes[0]}")
        if src.crs is None or src.crs.to_string() != EXPECTED_CRS:
            errors.append(f"CRS must be {EXPECTED_CRS}; got {src.crs}")
        if tuple(src.shape) != EXPECTED_SHAPE:
            errors.append(f"shape must be {EXPECTED_SHAPE}; got {tuple(src.shape)}")
        t = tuple(round(v, 6) for v in list(src.transform)[:6])
        if t != EXPECTED_TRANSFORM:
            errors.append(f"geotransform must be {EXPECTED_TRANSFORM}; got {t}")

        a = src.read(1)

    finite = np.isfinite(a)
    nan_mask = np.isnan(a)
    n_nan = int(nan_mask.sum())
    n_inf = int(np.isinf(a).sum())
    stats["n_finite"] = int(finite.sum())
    stats["n_nan"] = n_nan
    stats["n_inf"] = n_inf

    if valid_mask is not None:
        valid_mask = np.asarray(valid_mask, dtype=bool)
        if valid_mask.shape != a.shape:
            errors.append(
                f"valid-mask shape must match raster {a.shape}; got {valid_mask.shape}"
            )
        else:
            n_inside = int(valid_mask.sum())
            n_outside = int(valid_mask.size - n_inside)
            n_nan_inside = int((nan_mask & valid_mask).sum())
            n_finite_outside = int((finite & ~valid_mask).sum())
            n_nan_outside = int((nan_mask & ~valid_mask).sum())
            stats["n_valid_footprint"] = n_inside
            stats["n_nan_inside_footprint"] = n_nan_inside
            stats["n_finite_outside_footprint"] = n_finite_outside
            stats["n_nan_outside_footprint"] = n_nan_outside
            stats["outside_nodata_ok"] = (n_finite_outside == 0)
            if n_nan_inside:
                errors.append(
                    f"{n_nan_inside} NaN values inside the valid footprint"
                )
            if n_finite_outside:
                message = (
                    f"{n_finite_outside} finite values outside the valid footprint; "
                    "official format requires null/NaN outside bounds"
                )
                if require_nodata_outside:
                    errors.append(message)
                else:
                    warnings.append(message + "; zero-fill is diagnostic only")
            if n_outside == 0:
                stats["outside_nodata_ok"] = True

    if n_inf:
        errors.append(f"{n_inf} infinite values present; must be finite or nan")
    if not allow_nan and n_nan:
        errors.append(f"{n_nan} NaN values present but allow_nan=False")
    if allow_nan and n_nan:
        warnings.append(
            f"{n_nan} NaN cells. The official format requires null/NaN outside "
            "the data bounds; verify their location against the supplied footprint "
            "and record the official form's response before upload.")

    if finite.any():
        lo, hi = float(a[finite].min()), float(a[finite].max())
        stats["min"] = lo
        stats["max"] = hi
        stats["sum"] = float(a[finite].sum())
        stats["n_gt0"] = int((a[finite] > 0).sum())
        if lo < 0.0:
            errors.append(f"minimum {lo} < 0 — DrivenData rejects with "
                          "'Predicted values must be in range [0, 1]'")
        if hi > 1.0:
            errors.append(f"maximum {hi} > 1 — DrivenData rejects with "
                          "'Predicted values must be in range [0, 1]'")
        if hi < 1.0 - 1e-6:
            warnings.append(
                f"maximum is {hi:.6f} < 1.0. DTI(c·p) is strictly increasing in "
                "c (metric audit A6): rescaling so the maximum is exactly 1.0 "
                "is a free score increase.")
    else:
        errors.append("no finite values at all")

    return ValidationReport(not errors, errors, warnings, stats)


def write_submission(path: str | Path, values: np.ndarray,
                     valid_mask: np.ndarray,
                     outside_value: float | None = None) -> Path:
    """Write a compliant single-band float32 GeoTIFF.

    Fail closed rather than clipping invalid probabilities: silently clipping
    would change the submitted map and could hide the source of the remote
    ``Predicted values must be in range [0, 1]`` rejection. Predictions must be
    finite and in [0, 1] throughout the scored footprint. NaN outside the
    footprint is written when ``outside_value=None`` (the official template
    convention); ``outside_value=0.0`` is a diagnostic all-finite variant.
    """
    path = Path(path)
    values = np.asarray(values)
    valid = np.asarray(valid_mask, dtype=bool)
    if values.ndim != 2 or values.shape != EXPECTED_SHAPE:
        raise ValueError(
            f"prediction shape must be {EXPECTED_SHAPE}; got {values.shape}"
        )
    if valid.shape != EXPECTED_SHAPE:
        raise ValueError(
            f"valid-mask shape must be {EXPECTED_SHAPE}; got {valid.shape}"
        )
    if not valid.any():
        raise ValueError("valid footprint is empty")
    if outside_value is not None and (
        not np.isfinite(outside_value) or outside_value < 0 or outside_value > 1
    ):
        raise ValueError("outside_value must be None or a finite value in [0, 1]")

    scored = np.asarray(values[valid], dtype=np.float64)
    if not np.isfinite(scored).all():
        raise ValueError("predictions inside the valid footprint must all be finite")
    lo, hi = float(scored.min()), float(scored.max())
    if lo < 0.0 or hi > 1.0:
        raise ValueError(
            f"predictions inside the valid footprint must lie in [0, 1]; got [{lo}, {hi}]"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    out = np.asarray(values, dtype=np.float32)
    fill = np.float32(np.nan) if outside_value is None else np.float32(outside_value)
    out = np.where(valid, out, fill).astype(np.float32)

    profile = {
        "driver": "GTiff", "height": EXPECTED_SHAPE[0], "width": EXPECTED_SHAPE[1],
        "count": 1, "dtype": "float32",
        "crs": rasterio.crs.CRS.from_string(EXPECTED_CRS),
        "transform": rasterio.transform.Affine(*EXPECTED_TRANSFORM),
        "nodata": float("nan") if outside_value is None else None,
        "compress": "deflate", "predictor": 2, "zlevel": 9,
        "tiled": True, "blockxsize": 256, "blockysize": 256,
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(out, 1)
        dst.set_band_description(1, "fault probability")
    return path
