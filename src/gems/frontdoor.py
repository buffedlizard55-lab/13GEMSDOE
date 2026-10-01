"""The "front door": the one pair of files a person uploads to DrivenData.

Everything a human needs to submit is produced here and described in ONE
machine-readable manifest, ``docs/downloads/submit.json``, which the site, the
README and ``scripts/verify_download.py`` all read.  Nothing on the site is
typed by hand.

WHICH ENCODING IS PRIMARY, AND WHY (settled by measurement, 2026-10-01)
----------------------------------------------------------------------
Two encodings of the SAME predictions are published:

  PRIMARY  ``*_nan-outside.tif``   NaN outside the survey footprint and
                                   ``GDAL_NODATA = nan``.  This is the encoding
                                   of the official ``sample_submission.tif``
                                   template AND of every one of the nine files
                                   this group has a public DrivenData score
                                   for.  It is the only encoding in this
                                   project's history with an acceptance
                                   receipt.  UPLOAD THIS.

  HEDGE    ``*_zerofill.tif``      0.0 outside the footprint, no NoData tag,
                                   no NaN anywhere.  Satisfies a naive
                                   whole-array ``[0, 1]`` test.  It is NOT the
                                   official template's encoding, though one
                                   all-finite file IS team-recorded as accepted
                                   (12GEMSDOE ``..._allfinite``, account SDCF9,
                                   score 0.1294 -- the same score as its
                                   NaN-outside twin, as expected since encoding
                                   does not change footprint pixels).  That is a
                                   team record, not a platform receipt, and it
                                   cannot be told apart from one upload recorded
                                   twice.  Use only if the form rejects the
                                   primary.

This is the reverse of the ordering sessions 6-7 shipped.  Those sessions
guessed that the NaN cells caused the form's
``Predicted values must be in range [0, 1]`` rejection.  That guess is
falsified: the official template itself carries 7,111,787 NaN cells, and so do
all nine scored files.  ``reports/platform_encoding_evidence.json`` has the
byte-level audit; ``src/gems/encoding.py`` has the rule and the reproducible
demonstration that the one rejected file's distinguishing feature --
``Predictor = 2`` (integer horizontal differencing) on IEEE-float samples --
decodes to the range [-4.0, 3.0] in any reader that does not run the
accumulator.  Every file this module writes therefore forbids a predictor.

Inside the footprint PRIMARY and HEDGE are identical (checked, not assumed).

Honest limits (see knowledge/02_irregularities.md I-8, I-18, I-22): this module
can verify the bytes locally with three independent TIFF readers; it cannot
observe the DrivenData validator.  Acceptance is only ever established by the
form's own response, which is appended to ``reports/form_responses.json``.
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

from . import encoding, rio

NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
FORM_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/"
FORMAT_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/"
EVIDENCE_URL = ("https://github.com/buffedlizard55-lab/13GEMSDOE/blob/main/"
                "reports/platform_encoding_evidence.json")
MAX_NOTE_CHARS = 160  # the form's note is "a short comment"; keep it one line

PRIMARY_SUFFIX = "_nan-outside"
HEDGE_SUFFIX = "_zerofill"

PRIMARY_ENCODING_TEXT = (
    "float32, NaN outside the survey footprint, GDAL_NODATA=nan, every footprint "
    "value finite and in [0, 1], LZW, no predictor -- the byte encoding of the "
    "official sample_submission.tif and of all 9 platform-scored group files")
HEDGE_ENCODING_TEXT = (
    "float32, 0.0 outside the footprint, no NoData tag, no NaN anywhere -- a "
    "hedge for a naive whole-array [0, 1] test; NOT the template's encoding")

#: aliases that must exist after every publish
ALIASES = {"latest.tif": "primary", "latest.zip": "primary_zip",
           "latest_zerofill.tif": "hedge", "latest_zerofill.zip": "hedge_zip"}
#: aliases that must NOT exist (they inverted the primary/hedge roles)
RETIRED_ALIASES = ("latest_nan.tif", "latest_nan.zip", "latest_allfinite.tif")


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
            "nodata": None if s.nodata is None else (
                "nan" if np.isnan(s.nodata) else s.nodata),
        }


def write_pair(out_dir: Path, stem: str, pred: np.ndarray,
               valid: np.ndarray) -> dict[str, Path]:
    """Write PRIMARY, HEDGE and their zips.  Refuses to overwrite."""
    if not NAME_RE.fullmatch(stem) or stem.lower().endswith((".tif", ".tiff", ".zip")):
        raise ValueError("stem must be 1-128 chars of letters/digits/._- and no extension")
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "primary": out_dir / f"{stem}{PRIMARY_SUFFIX}.tif",
        "primary_zip": out_dir / f"{stem}{PRIMARY_SUFFIX}.zip",
        "hedge": out_dir / f"{stem}{HEDGE_SUFFIX}.tif",
        "hedge_zip": out_dir / f"{stem}{HEDGE_SUFFIX}.zip",
    }
    clash = [str(p) for p in paths.values() if p.exists()]
    if clash:
        raise FileExistsError(
            "submission names are immutable; already exist: " + ", ".join(clash))
    # outside_value=None -> NaN outside + nodata=nan (the proven encoding)
    rio.write_submission(paths["primary"], pred, valid, outside_value=None)
    rio.write_submission(paths["hedge"], pred, valid, outside_value=0.0)
    _zip_single(paths["primary_zip"], paths["primary"])
    _zip_single(paths["hedge_zip"], paths["hedge"])
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


def _one_file_facts(label: str, path: Path, arr: np.ndarray,
                    valid: np.ndarray) -> dict:
    with rasterio.open(path) as s:
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
    f["min"] = float(fin.min()) if fin.size else None
    f["max"] = float(fin.max()) if fin.size else None
    f["n_positive"] = int(np.nansum(arr > 0))
    f["naive_all_in_0_1"] = bool(np.all((arr >= 0) & (arr <= 1)))
    f["nan_aware_all_in_0_1"] = bool(fin.size and np.all((fin >= 0) & (fin <= 1)))
    f["n_nan_inside_footprint"] = int((np.isnan(arr) & valid).sum())
    f["n_finite_outside_footprint"] = int((np.isfinite(arr) & ~valid).sum())
    f["n_nan_outside_footprint"] = int((np.isnan(arr) & ~valid).sum())
    f["layout"] = layout(path)
    # The empirical platform gate only applies to a real-size file: the pattern
    # it checks is defined on the official 3730x3292 grid, and the unit tests
    # publish 40x50 synthetic rasters.
    official_size = tuple(f["shape"]) == encoding.EXPECTED_SHAPE
    f["official_size"] = official_size
    if official_size:
        audit = encoding.audit_file(path, valid)
        f["matches_accepted_pattern"] = audit["matches_accepted_pattern"]
        f["deviations_from_accepted_pattern"] = audit["deviations_from_accepted_pattern"]
    else:
        f["matches_accepted_pattern"] = None
        f["deviations_from_accepted_pattern"] = ["synthetic size; accepted-pattern gate skipped"]
    f["sha256"] = sha256_file(path)
    f["label"] = label
    return f


def check_pair(primary_path: Path, hedge_path: Path, valid: np.ndarray) -> dict:
    """Every locally checkable property of PRIMARY and HEDGE.  Returns facts."""
    reads_p = read_all_readers(primary_path)
    reads_h = read_all_readers(hedge_path)
    ref_p = reads_p["rasterio/GDAL"]
    ref_h = reads_h["rasterio/GDAL"]
    facts: dict = {
        "readers_used": sorted(reads_p),
        "all_readers_agree_primary": all(np.array_equal(v, ref_p, equal_nan=True)
                                         for v in reads_p.values()),
        "all_readers_agree_hedge": all(np.array_equal(v, ref_h, equal_nan=True)
                                       for v in reads_h.values()),
    }
    facts["primary"] = _one_file_facts("primary", primary_path, ref_p, valid)
    facts["hedge"] = _one_file_facts("hedge", hedge_path, ref_h, valid)
    facts["primary_equals_hedge_inside_footprint"] = bool(
        np.array_equal(ref_p[valid], ref_h[valid]))
    facts["hedge_outside_all_zero"] = bool(np.all(ref_h[~valid] == 0.0))
    facts["primary_outside_all_nan"] = bool(np.all(np.isnan(ref_p[~valid])))
    facts["footprint_cells"] = int(valid.sum())
    facts["outside_cells"] = int((~valid).sum())
    return facts


def _all_ok(facts: dict) -> list[str]:
    """Hard gate: if this returns anything, nothing is released."""
    bad: list[str] = []
    if not facts["all_readers_agree_primary"]:
        bad.append("PRIMARY decodes differently across TIFF readers")
    if not facts["all_readers_agree_hedge"]:
        bad.append("HEDGE decodes differently across TIFF readers")
    p, h = facts["primary"], facts["hedge"]
    for label, f in (("PRIMARY", p), ("HEDGE", h)):
        if not f["grid_matches_official"]:
            bad.append(f"{label}: grid/dtype/band/CRS mismatch")
        if not f["nan_aware_all_in_0_1"]:
            bad.append(f"{label}: finite values outside [0,1]")
        if f["n_inf"]:
            bad.append(f"{label}: infinite values")
        if f["n_nan_inside_footprint"]:
            bad.append(f"{label}: {f['n_nan_inside_footprint']} NaN INSIDE the "
                       "footprint -- the exact condition behind the platform's "
                       "'Predicted values must be in range [0, 1]'")
        pred = f["layout"]["predictor"]
        if pred not in (None, "1", 1, "NONE"):
            bad.append(f"{label}: TIFF predictor {pred!r}; only 'none' is allowed "
                       "(Predictor=2 is the sole deviation of the one file the "
                       "form rejected)")
        if f["layout"]["compression"] != "LZW":
            bad.append(f"{label}: compression {f['layout']['compression']} "
                       "(must be LZW, the official template's)")
    # PRIMARY must be the encoding the platform has actually accepted
    if p["layout"]["nodata"] != "nan" or not facts["primary_outside_all_nan"]:
        bad.append("PRIMARY: not NaN with NoData=nan outside the footprint")
    if p["n_finite_outside_footprint"]:
        bad.append(f"PRIMARY: {p['n_finite_outside_footprint']} finite cells outside "
                   "the footprint (the official template is NaN there)")
    if p["official_size"]:
        if not p["matches_accepted_pattern"]:
            bad.append("PRIMARY deviates from the empirically ACCEPTED platform "
                       "encoding: " + "; ".join(p["deviations_from_accepted_pattern"]))
        if p["n_nan_outside_footprint"] != encoding.OUTSIDE_PIXELS:
            bad.append(f"PRIMARY: {p['n_nan_outside_footprint']:,} NaN outside != "
                       f"{encoding.OUTSIDE_PIXELS:,}")
    # HEDGE must be NaN-free (that is the whole point of the hedge)
    if h["n_nan"] or not h["naive_all_in_0_1"]:
        bad.append("HEDGE: not NaN-free / not naively in [0,1]")
    if h["layout"]["nodata"] is not None:
        bad.append("HEDGE: carries a NoData tag (must not)")
    if not facts["hedge_outside_all_zero"]:
        bad.append("HEDGE: outside footprint not exactly 0.0")
    if not facts["primary_equals_hedge_inside_footprint"]:
        bad.append("PRIMARY and HEDGE differ inside the footprint")
    if p["n_positive"] != h["n_positive"]:
        bad.append("PRIMARY and HEDGE differ in positive-cell count")
    return bad


def publish(out_dir: Path, stem: str, pred: np.ndarray, valid: np.ndarray, *,
            note: str, source: dict, status: dict,
            existing_paths: dict[str, Path] | None = None) -> dict:
    """Write (or adopt) PRIMARY/HEDGE, verify, refresh aliases + submit.json.

    ``existing_paths`` lets a caller adopt already-written files (used when
    re-publishing an artifact so the prediction is not rebuilt).

    Raises RuntimeError -- and therefore releases nothing -- if any hard check
    in ``_all_ok`` fails.
    """
    if len(note) > MAX_NOTE_CHARS or "\n" in note:
        raise ValueError(f"note must be one line of at most {MAX_NOTE_CHARS} characters")
    paths = existing_paths or write_pair(out_dir, stem, pred, valid)
    facts = check_pair(paths["primary"], paths["hedge"], valid)
    problems = _all_ok(facts)
    if problems:
        raise RuntimeError("front-door verification FAILED - nothing released: "
                           + "; ".join(problems))

    for alias, key in ALIASES.items():
        shutil.copyfile(paths[key], out_dir / alias)
    for dead in RETIRED_ALIASES:
        p = out_dir / dead
        if p.exists():
            p.unlink()

    def entry(tif: Path, zp: Path, text: str, use: str) -> dict:
        return {
            "file": tif.name, "bytes": tif.stat().st_size, "sha256": sha256_file(tif),
            "zip": zp.name, "zip_bytes": zp.stat().st_size, "zip_sha256": sha256_file(zp),
            "zip_contains": tif.name, "encoding": text, "use": use,
        }

    manifest = {
        "schema": 2,
        "schema_note": ("schema 2 (2026-10-01) renames primary_A -> primary and "
                        "fallback_B -> hedge and SWAPS which encoding each holds: "
                        "the primary is now the NaN-outside file, because that is "
                        "the encoding of the official template and of all 9 "
                        "platform-scored group files. See "
                        "reports/platform_encoding_evidence.json."),
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stem": stem,
        "note_for_form": note,
        "form_url": FORM_URL,
        "format_source": FORMAT_URL,
        "encoding_evidence": EVIDENCE_URL,
        "primary": entry(paths["primary"], paths["primary_zip"],
                         PRIMARY_ENCODING_TEXT, "UPLOAD THIS"),
        "hedge": entry(paths["hedge"], paths["hedge_zip"],
                       HEDGE_ENCODING_TEXT,
                       "ONLY if the form rejects the primary"),
        "aliases": {a: f"= {k}" for a, k in ALIASES.items()},
        "local_verification": facts,
        "source_artifact": source,
        "status": status,
        "limits": ("Verified locally with rasterio/GDAL, tifffile and Pillow against the "
                   "official sample_submission.tif and the nine platform-scored group "
                   "files. The DrivenData validator itself cannot be observed from here; "
                   "acceptance is established only by the form's own response "
                   "(reports/form_responses.json)."),
    }
    (out_dir / "submit.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
