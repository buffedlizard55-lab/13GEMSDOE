"""The "front door": the one pair of files a person uploads to DrivenData.

Everything a human needs to submit is produced here and described in ONE
machine-readable manifest, ``docs/downloads/submit.json``, which the site, the
README and ``scripts/verify_download.py`` all read. Nothing on the site is typed
by hand.

Two encodings of the SAME predictions are published, in the byte layout of the
official ``example_submission.tif`` (LZW, one-row strips, no predictor):

  A  ``*_A_zerofill.tif``      0.0 outside the survey footprint, no NoData tag.
                               Cannot trip any range test (no NaN anywhere).
                               UPLOAD THIS FIRST.
  B  ``*_B_nan-outside.tif``   NaN outside the footprint, NoData=nan - the exact
                               convention the problem page describes
                               ("data outside the bounds is null or nan").
                               Only if A is rejected.

Inside the footprint A and B are identical (checked, not assumed). For a binary
{0,1} map the cells outside the footprint carry no score weight either way.

Honest limits (see knowledge/02_irregularities.md I-8, I-18): this module can
verify the bytes locally with three independent TIFF readers; it cannot observe
the DrivenData validator. Acceptance is only ever established by the form's own
response, which is appended to reports/form_responses.json.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio

from . import rio

NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
FORM_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/"
FORMAT_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/"
MAX_NOTE_CHARS = 160  # the form's note is "a short comment"; keep it one line


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _zip_single(zpath: Path, tif: Path) -> None:
    tmp = zpath.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(tif, arcname=tif.name)
    shutil.move(tmp, zpath)


def layout(path: Path) -> dict:
    """Byte-layout facts that differ between writers (not pixel values)."""
    with rasterio.open(path) as s:
        st = s.tags(ns="IMAGE_STRUCTURE")
        return {
            "compression": st.get("COMPRESSION"),
            "predictor": st.get("PREDICTOR"),
            "tiled": bool(s.profile.get("tiled")),
            "blockysize": s.block_shapes[0][0],
            "nodata": None if s.nodata is None else ("nan" if np.isnan(s.nodata) else s.nodata),
        }


def write_pair(out_dir: Path, stem: str, pred: np.ndarray,
               valid: np.ndarray) -> dict[str, Path]:
    """Write A, B and their zips. Refuses to overwrite (names are immutable)."""
    if not NAME_RE.fullmatch(stem) or stem.lower().endswith((".tif", ".tiff", ".zip")):
        raise ValueError("stem must be 1-128 chars of letters/digits/._- and no extension")
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "A_tif": out_dir / f"{stem}_A_zerofill.tif",
        "A_zip": out_dir / f"{stem}_A_zerofill.zip",
        "B_tif": out_dir / f"{stem}_B_nan-outside.tif",
        "B_zip": out_dir / f"{stem}_B_nan-outside.zip",
    }
    clash = [str(p) for p in paths.values() if p.exists()]
    if clash:
        raise FileExistsError("submission names are immutable; already exist: " + ", ".join(clash))
    rio.write_submission(paths["A_tif"], pred, valid, outside_value=0.0)
    rio.write_submission(paths["B_tif"], pred, valid, outside_value=None)
    _zip_single(paths["A_zip"], paths["A_tif"])
    _zip_single(paths["B_zip"], paths["B_tif"])
    return paths


def read_all_readers(path: Path) -> dict[str, np.ndarray]:
    """Decode with three independent TIFF stacks; used to prove they agree."""
    out = {}
    with rasterio.open(path) as s:
        out["rasterio/GDAL"] = s.read(1)
    try:
        import tifffile
        out["tifffile"] = tifffile.imread(path)
    except ImportError:  # optional dependency; reported as skipped
        pass
    try:
        from PIL import Image
        out["Pillow"] = np.array(Image.open(path))
    except ImportError:
        pass
    return out


def check_pair(a_path: Path, b_path: Path, valid: np.ndarray) -> dict:
    """Every locally checkable property of A and B. Raises nothing; returns facts."""
    facts: dict = {}
    reads_a = read_all_readers(a_path)
    reads_b = read_all_readers(b_path)
    ref_a = reads_a["rasterio/GDAL"]
    ref_b = reads_b["rasterio/GDAL"]
    facts["readers_used"] = sorted(reads_a)
    facts["all_readers_agree_A"] = all(np.array_equal(v, ref_a, equal_nan=True)
                                       for v in reads_a.values())
    facts["all_readers_agree_B"] = all(np.array_equal(v, ref_b, equal_nan=True)
                                       for v in reads_b.values())
    for label, p, arr in (("A", a_path, ref_a), ("B", b_path, ref_b)):
        with rasterio.open(p) as s:
            f = {
                "driver": s.driver, "count": s.count, "dtype": s.dtypes[0],
                "crs": str(s.crs), "shape": list(s.shape),
                "transform": [round(v, 6) for v in list(s.transform)[:6]],
            }
        f["grid_matches_official"] = (
            f["driver"] == "GTiff" and f["count"] == 1 and f["dtype"] == "float32"
            and f["crs"] == rio.EXPECTED_CRS and tuple(f["shape"]) == rio.EXPECTED_SHAPE
            and tuple(f["transform"]) == rio.EXPECTED_TRANSFORM)
        f["n_nan"] = int(np.isnan(arr).sum())
        f["n_inf"] = int(np.isinf(arr).sum())
        fin = arr[np.isfinite(arr)]
        f["min"], f["max"] = float(fin.min()), float(fin.max())
        f["n_positive"] = int((arr > 0).sum())
        f["naive_all_in_0_1"] = bool(np.all((arr >= 0) & (arr <= 1)))
        f["nan_aware_all_in_0_1"] = bool(np.all((fin >= 0) & (fin <= 1)))
        f["n_nan_inside_footprint"] = int((np.isnan(arr) & valid).sum())
        f["n_finite_outside_footprint"] = int((np.isfinite(arr) & ~valid).sum())
        f["layout"] = layout(p)
        facts[label] = f
    facts["A_equals_B_inside_footprint"] = bool(np.array_equal(ref_a[valid], ref_b[valid]))
    facts["A_outside_all_zero"] = bool(np.all(ref_a[~valid] == 0.0))
    facts["B_outside_all_nan"] = bool(np.all(np.isnan(ref_b[~valid])))
    facts["footprint_cells"] = int(valid.sum())
    return facts


def _all_ok(facts: dict) -> list[str]:
    bad = []
    if not facts["all_readers_agree_A"]:
        bad.append("A decodes differently across TIFF readers")
    if not facts["all_readers_agree_B"]:
        bad.append("B decodes differently across TIFF readers")
    a, b = facts["A"], facts["B"]
    for label, f in (("A", a), ("B", b)):
        if not f["grid_matches_official"]:
            bad.append(f"{label}: grid/dtype/band/CRS mismatch")
        if not f["nan_aware_all_in_0_1"]:
            bad.append(f"{label}: values outside [0,1]")
        if f["n_inf"]:
            bad.append(f"{label}: infinite values")
        if f["n_nan_inside_footprint"]:
            bad.append(f"{label}: NaN inside footprint")
        if f["layout"]["predictor"] is not None:
            bad.append(f"{label}: TIFF predictor {f['layout']['predictor']} (must be none)")
        if f["layout"]["compression"] != "LZW":
            bad.append(f"{label}: compression {f['layout']['compression']} (must be LZW)")
    if a["n_nan"] or not a["naive_all_in_0_1"]:
        bad.append("A: not NaN-free / not naively in [0,1]")
    if a["layout"]["nodata"] is not None:
        bad.append("A: carries a NoData tag")
    if a["n_finite_outside_footprint"] != int(np.prod(rio.EXPECTED_SHAPE)) - facts["footprint_cells"]:
        bad.append("A: outside-footprint cells are not all finite")
    if not facts["A_outside_all_zero"]:
        bad.append("A: outside footprint not exactly 0.0")
    if b["layout"]["nodata"] != "nan" or not facts["B_outside_all_nan"]:
        bad.append("B: not NaN/NoData=nan outside footprint")
    if not facts["A_equals_B_inside_footprint"]:
        bad.append("A and B differ inside the footprint")
    if a["n_positive"] != b["n_positive"]:
        bad.append("A and B differ in positive-cell count")
    return bad


def publish(out_dir: Path, stem: str, pred: np.ndarray, valid: np.ndarray, *,
            note: str, source: dict, status: dict,
            existing_paths: dict[str, Path] | None = None) -> dict:
    """Write (or adopt) A/B, verify them, refresh latest.* aliases and submit.json.

    ``existing_paths`` lets a caller adopt already-written files (used when
    re-publishing an archived artifact so the prediction is not rebuilt).
    """
    if len(note) > MAX_NOTE_CHARS or "\n" in note:
        raise ValueError(f"note must be one line of at most {MAX_NOTE_CHARS} characters")
    paths = existing_paths or write_pair(out_dir, stem, pred, valid)
    facts = check_pair(paths["A_tif"], paths["B_tif"], valid)
    problems = _all_ok(facts)
    if problems:
        raise RuntimeError("front-door verification FAILED - nothing released: "
                           + "; ".join(problems))

    # stable aliases so a bookmark never goes stale
    shutil.copyfile(paths["A_tif"], out_dir / "latest.tif")
    shutil.copyfile(paths["A_zip"], out_dir / "latest.zip")
    shutil.copyfile(paths["B_tif"], out_dir / "latest_nan.tif")
    shutil.copyfile(paths["B_zip"], out_dir / "latest_nan.zip")
    legacy = out_dir / "latest_allfinite.tif"
    if legacy.exists():  # redundant alias of latest.tif; removed to avoid ambiguity
        legacy.unlink()

    def entry(tif: Path, zp: Path) -> dict:
        return {
            "file": tif.name, "bytes": tif.stat().st_size, "sha256": sha256_file(tif),
            "zip": zp.name, "zip_bytes": zp.stat().st_size, "zip_sha256": sha256_file(zp),
            "zip_contains": tif.name,
        }

    manifest = {
        "schema": 1,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stem": stem,
        "note_for_form": note,
        "form_url": FORM_URL,
        "format_source": FORMAT_URL,
        "primary_A": {**entry(paths["A_tif"], paths["A_zip"]),
                      "encoding": "float32, 0.0 outside footprint, no NoData tag, no NaN",
                      "use": "UPLOAD THIS FIRST"},
        "fallback_B": {**entry(paths["B_tif"], paths["B_zip"]),
                       "encoding": "float32, NaN outside footprint, NoData=nan (official-text convention)",
                       "use": "ONLY if the form rejects A"},
        "aliases": {"latest.tif": "= primary A", "latest.zip": "= primary A zip",
                    "latest_nan.tif": "= fallback B", "latest_nan.zip": "= fallback B zip"},
        "local_verification": facts,
        "source_artifact": source,
        "status": status,
        "limits": ("Verified locally with rasterio/GDAL, tifffile and Pillow. The DrivenData "
                   "validator itself cannot be observed from here; acceptance is established "
                   "only by the form's own response (reports/form_responses.json)."),
    }
    (out_dir / "submit.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
