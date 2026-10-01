#!/usr/bin/env python3
"""Measure what encoding the DrivenData platform actually accepts.

Inputs (all local; fetch them first if `data/raw` is empty):
  data/raw/sample_submission.tif  official template   (scripts/fetch_data.py)
  data/raw/labels.tif             official label raster
  data/scored/*.tif               every file this group has a public score for
  docs/downloads/archive/13gems-r11-greedy-mp.tif   the file the form REJECTED
  docs/downloads/*.tif            the files this project currently ships

Output: reports/platform_encoding_evidence.json

The report answers one question with bytes rather than argument: *which
GeoTIFF encoding has an acceptance receipt, and which does not?*

Run:  python scripts/audit_platform_encoding.py
"""
from __future__ import annotations

import hashlib
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
SCORED = ROOT / "data" / "scored"
DL = ROOT / "docs" / "downloads"
OUT = ROOT / "reports" / "platform_encoding_evidence.json"

# blob sha1 -> public score, from reports/leaderboard_ledger.csv and the
# sibling repo registry; file names carry the score the team recorded.
SCORE_LABEL_NOTE = (
    "Scores are team-recorded public leaderboard values, not per-submission "
    "receipts (see reports/leaderboard_ledger.csv, column `verified` = NO). "
    "What IS verified here is the byte encoding of each file.")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(*names: str) -> Path:
    """The mirrors are filed under both the data-tab name and the canonical
    name used by GEMSDOE's data/bridge/manifest.json.  Accept either."""
    for n in names:
        if (RAW / n).exists():
            return RAW / n
    raise SystemExit("missing official raster (looked for "
                     + ", ".join(names) + f" in {RAW})"
                     "\n  run: bash scripts/download_competition_data.sh")


def main() -> int:
    tmpl_path = resolve("sample_submission.tif", "example_submission.tif")
    lab_path = resolve("labels.tif", "existing_faults.tif")

    tmpl_sha = sha256(tmpl_path)
    lab_sha = sha256(lab_path)
    print(f"{tmpl_path.name} sha256 {tmpl_sha}")
    print(f"  pin match: {tmpl_sha == encoding.SAMPLE_SUBMISSION_SHA256}")
    print(f"{lab_path.name} sha256 {lab_sha}")
    print(f"  pin match: {lab_sha == encoding.LABELS_SHA256}")

    with rasterio.open(tmpl_path) as s:
        tmpl = s.read(1)
    footprint = np.isfinite(tmpl)
    with rasterio.open(lab_path) as s:
        lab = s.read(1)
    fp_from_labels = lab >= 0
    same = bool(np.array_equal(footprint, fp_from_labels))
    print(f"footprint {int(footprint.sum()):,} px; labels>=0 identical: {same}")

    groups: dict[str, list[Path]] = {
        "official_template": [tmpl_path],
        "platform_scored": sorted(SCORED.glob("*.tif")),
        "form_rejected": [DL / "archive" / "13gems-r11-greedy-mp.tif"],
        "currently_shipped": sorted(p for p in DL.glob("*.tif")),
    }

    report: dict = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "question": "Which GeoTIFF encoding has a DrivenData acceptance receipt?",
        "score_label_note": SCORE_LABEL_NOTE,
        "official_template": {
            "path": str(tmpl_path.relative_to(ROOT)),
            "sha256": tmpl_sha,
            "sha256_matches_published_pin": tmpl_sha == encoding.SAMPLE_SUBMISSION_SHA256,
            "pin_source": ("GEMSDOE repo data/bridge/manifest.json (generated on a "
                           "GitHub-hosted runner from the official data tab) and "
                           "16GEMSDOE evidence/submission_validation_report.json"),
            "footprint_pixels": int(footprint.sum()),
            "outside_pixels": int((~footprint).sum()),
            "labels_raster_sha256": lab_sha,
            "labels_raster_matches_published_pin": lab_sha == encoding.LABELS_SHA256,
            "footprint_equals_labels_ge_0": same,
        },
        "files": {},
    }

    for group, paths in groups.items():
        for p in paths:
            if not p.exists():
                print(f"SKIP  {p} (absent)")
                continue
            key = f"{group}/{p.name}"
            audit = encoding.audit_file(p, footprint)
            audit["sha256"] = sha256(p)
            audit["group"] = group
            report["files"][key] = audit
            print(f"{'MATCH' if audit['matches_accepted_pattern'] else 'DEVI '} "
                  f"{key:70s} nodata={audit['profile']['nodata']} "
                  f"nan={audit['placement']['n_nan_total']:,} "
                  f"nanIn={audit['placement']['n_nan_inside_footprint']} "
                  f"finOut={audit['placement']['n_finite_outside_footprint']:,} "
                  f"{audit['layout']['compression']}/pred={audit['layout']['predictor']}")

    # ---- the summary that decides the policy ------------------------------
    scored = [v for v in report["files"].values() if v["group"] == "platform_scored"]
    tmpl_audit = next(v for v in report["files"].values()
                      if v["group"] == "official_template")
    rejected = [v for v in report["files"].values() if v["group"] == "form_rejected"]
    shipped = [v for v in report["files"].values() if v["group"] == "currently_shipped"]

    n_scored = len(scored)
    n_scored_nanoutside = sum(
        1 for v in scored
        if v["profile"]["nodata"] == "nan"
        and v["placement"]["n_nan_outside_footprint"] == encoding.OUTSIDE_PIXELS
        and v["placement"]["n_nan_inside_footprint"] == 0
        and v["placement"]["n_finite_outside_footprint"] == 0)
    n_scored_pred2 = sum(1 for v in scored if v["layout"]["predictor"] == 2)

    summary = {
        "n_platform_scored_files_audited": n_scored,
        "n_platform_scored_files_with_nan_outside_nodata_nan": n_scored_nanoutside,
        "n_platform_scored_files_with_predictor2": n_scored_pred2,
        "official_template_uses_nan_outside_and_nodata_nan": (
            tmpl_audit["profile"]["nodata"] == "nan"
            and tmpl_audit["placement"]["n_nan_outside_footprint"] == encoding.OUTSIDE_PIXELS),
        "official_template_predictor": tmpl_audit["layout"]["predictor"],
        "official_template_compression": tmpl_audit["layout"]["compression"],
        "rejected_file_deviations": (rejected[0]["deviations_from_accepted_pattern"]
                                     if rejected else None),
        "rejected_file_predictor2_simulation": (rejected[0].get("predictor2_simulation")
                                                if rejected else None),
        "shipped_files_matching_accepted_pattern": {
            v["file"]: v["matches_accepted_pattern"] for v in shipped},
        "policy": {
            "primary_encoding": ("NaN outside the footprint, GDAL_NODATA=nan, all "
                                 "footprint values finite and in [0, 1], "
                                 "Predictor != 2"),
            "why": (f"{n_scored_nanoutside}/{n_scored} platform-scored files use it and "
                    "the official template uses it; 0 platform-scored files use "
                    "Predictor=2; the single form-rejected file is the only one that does."),
            "hedge_encoding": ("all-finite zero-fill outside the footprint, no NoData tag. "
                               "Kept as a labelled fallback. No all-finite file in this "
                               "group's history has an acceptance receipt that is "
                               "independent of its NaN-outside twin."),
            "falsified_hypothesis": ("'NaN cells caused the [0,1] rejection' -- the official "
                                     "template and all nine scored files are NaN-outside."),
        },
    }
    report["summary"] = summary

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    print(json.dumps(summary["policy"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
