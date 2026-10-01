#!/usr/bin/env python3
"""DEPRECATED (session 7) - historical record only; do not run.

The all-finite file this script promoted was never confirmed accepted by the form and
was written with TIFF PREDICTOR=2; session 7 replaced it with the A/B front-door files
(src/gems/frontdoor.py, scripts/publish_front_door.py).

One-time encoding-policy flip, recorded for audit (2026-09-30, session 6).

Why
---
The team uploaded the NaN-outside primary ``13gems-r11-greedy-mp.tif`` and
the DrivenData form returned
``Predicted values must be in range [0, 1]``. Historically NaN-outside files
from this group WERE accepted and scored (the pindrop trio recorded by sha256
prefix f347b70daa / 37f9d5b855 / 4e03fc9705 — re-verified against the archived
bytes in ``data/scored/`` this session), so the platform validator changed or is
inconsistent. Either way the platform is the arbiter, so the ALL-FINITE
encoding (0.0 outside the survey footprint, no NoData tag) becomes the primary
upload encoding:

  * passes a masked read AND a naive raw range test (no NaN anywhere),
  * for a binary {0,1} map, zero-fill outside the footprint is score-neutral:
    0 is a non-prediction, so TP_w and FP_w are unchanged under any scorer,
  * identical CRS / transform / shape / dtype / band count.

What this script does (idempotent; re-running only re-verifies):
  1. writes/updates the append-only evidence log ``reports/form_responses.json``;
  2. writes ``reports/primary_flip_2026-09-30.json`` with before/after hashes;
  3. re-points ``reports/latest_submission.json`` and
     ``docs/downloads/latest.json`` at the all-finite file via a new
     ``primary_upload`` field;
  4. rewrites ``docs/downloads/latest.zip`` and
     ``docs/downloads/13gems-r11-greedy-mp.zip`` so they wrap the ALL-FINITE
     GeoTIFF (the old zip wrapped the rejected NaN encoding);
  5. re-verifies the primary file bytes: no NaN, [0,1], exact grid.

``scripts/make_submission.py`` now writes this policy by default for every
future build; this script exists to fix the already-archived R11 artifact
without rebuilding it (a rebuild would drift the map, irregularity I-15).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
DL = ROOT / "docs" / "downloads"
REP = ROOT / "reports"

ART = "13gems-r11-greedy-mp"
FIN = DL / f"{ART}_allfinite.tif"
NAN = DL / f"{ART}.tif"

RESPONSES = {
    "log": "append-only record of DrivenData submission-form responses",
    "note": "Scores/acceptances recorded by the team are marked "
            "team_recorded; they are not platform receipts. "
            "Verify every entry against the file sha256 before acting on it.",
    "responses": [
        {
            "date_utc": "2026-09-27 (approx; team-recorded)",
            "artifact": "gems3_pindrop_nodes",
            "file": "data/scored/gems3_pindrop_nodes_LB0.1193.tif",
            "sha256_prefix": "f347b70daa",
            "encoding": "nan_outside (float32, NoData=nan, 7,111,787 NaN cells)",
            "outcome": "ACCEPTED_AND_SCORED",
            "score_label": 0.1193,
            "source": "team submission notes quoted in the project brief; "
                      "sha256 prefix re-verified against archived bytes 2026-09-30",
            "evidence_class": "team_recorded_not_receipt",
        },
        {
            "date_utc": "2026-09-27 (approx; team-recorded)",
            "artifact": "gems3_pindrop_discovery",
            "file": "data/scored/gems3_pindrop_discovery_LB0.0830.tif",
            "sha256_prefix": "37f9d5b855",
            "encoding": "nan_outside (float32, NoData=nan, 7,111,787 NaN cells)",
            "outcome": "ACCEPTED_AND_SCORED",
            "score_label": 0.0830,
            "source": "team submission notes; sha256 prefix re-verified 2026-09-30",
            "evidence_class": "team_recorded_not_receipt",
        },
        {
            "date_utc": "2026-09-27 (approx; team-recorded)",
            "artifact": "gems3_pindrop_ridge",
            "file": "data/scored/gems3_pindrop_ridge_LB0.1152.tif",
            "sha256_prefix": "4e03fc9705",
            "encoding": "nan_outside (float32, NoData=nan, 7,111,787 NaN cells)",
            "outcome": "ACCEPTED_AND_SCORED",
            "score_label": 0.1152,
            "source": "team submission notes; sha256 prefix re-verified 2026-09-30",
            "evidence_class": "team_recorded_not_receipt",
        },
        {
            "date_utc": "2026-09-30",
            "artifact": ART,
            "file": f"{ART}.tif (NaN-outside primary)",
            "sha256_prefix": None,
            "encoding": "nan_outside (float32, NoData=nan, 7,111,787 NaN cells)",
            "outcome": "REJECTED",
            "message": "Predicted values must be in range [0, 1]",
            "source": "team report to the session (user), 2026-09-30; file "
                      "downloaded from this site's front-page primary button",
            "evidence_class": "user_reported_platform_response",
            "action_taken": "predeclared I-8 triage step 2 executed: all-finite "
                            "encoding promoted to PRIMARY (site, zip, latest.*); "
                            "NaN-outside demoted to record-only secondary",
        },
        {
            "date_utc": "2026-09-29/30 (approx; team-recorded)",
            "artifact": "r7-nms3-dem10-scarp (12GEMSDOE)",
            "file": "12GEMSDOE r7-nms3-dem10-scarp_0c9199f14e62_allfinite",
            "sha256_prefix": None,
            "encoding": "all_finite zero-fill (name says _allfinite)",
            "outcome": "ACCEPTED_AND_SCORED (label SDCF9; score not recorded)",
            "score_label": None,
            "source": "team submission notes quoted in the project brief",
            "evidence_class": "team_recorded_not_receipt",
        },
    ],
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_finite(path: Path) -> dict:
    with rasterio.open(path) as src:
        raw = src.read(1)
        return {
            "driver": src.driver, "count": src.count, "dtype": src.dtypes[0],
            "crs": str(src.crs), "shape": list(src.shape),
            "nodata": None if src.nodata is None else str(src.nodata),
            "transform": list(src.transform)[:6],
            "n_nan": int(np.isnan(raw).sum()),
            "n_inf": int(np.isinf(raw).sum()),
            "min": float(raw.min()), "max": float(raw.max()),
            "n_positive": int((raw > 0).sum()),
            "raw_all_in_[0,1]_naive": bool(np.all((raw >= 0) & (raw <= 1))),
        }


def patch_primary_field(json_path: Path) -> None:
    obj = json.loads(json_path.read_text())
    obj["primary_upload"] = {
        "encoding": "all_finite_zero_fill",
        "file": f"{ART}_allfinite.tif",
        "zip": f"{ART}.zip",
        "zip_contains": f"{ART}_allfinite.tif",
        "latest_aliases": {"latest.tif": "all-finite primary",
                           "latest_allfinite.tif": "all-finite primary (alias)",
                           "latest_nan.tif": "record-only NaN-outside secondary"},
        "secondary_record_only": {"encoding": "nan_outside_strict",
                                  "file": f"{ART}.tif"},
        "policy_source": ("reports/form_responses.json; reports/primary_flip_2026-09-30.json; "
                          "knowledge/02_irregularities.md I-8; user-reported form "
                          "rejection of the NaN-outside encoding, 2026-09-30"),
    }
    sim = obj.get("platform_check_simulation", {})
    if "nan_outside_variant" in sim:
        sim["nan_outside_variant"]["note"] = (
            "REJECTED by the form on 2026-09-30 with 'Predicted values must be "
            "in range [0, 1]' (team upload of this file). Kept on disk and on "
            "the site as a RECORD-ONLY secondary; the front-page primary button "
            "now serves the all-finite encoding.")
    if "all_finite_variant" in sim:
        sim["all_finite_variant"]["note"] = (
            "PRIMARY upload encoding as of 2026-09-30: passes a naive raw range "
            "check AND a masked read; outside-footprint cells are exactly 0.0 "
            "(score-neutral for a binary map).")
    obj["encoding_policy_note"] = (
        "Primary download/upload encoding flipped to all-finite 2026-09-30 "
        "(session 6). This JSON was produced by make_submission.py under the "
        "old NaN-outside-primary policy and then patched by "
        "scripts/flip_primary_encoding.py; predictions are byte-identical "
        "inside the survey footprint in both variants.")
    json_path.write_text(json.dumps(obj, indent=2))


def main() -> int:
    for p in (FIN, NAN):
        if not p.exists():
            raise SystemExit(f"missing {p}")

    # 1. evidence log (append-only: never drop existing entries)
    rpath = REP / "form_responses.json"
    if rpath.exists():
        log = json.loads(rpath.read_text())
        have = {r.get("sha256_prefix") or r.get("file") for r in log["responses"]}
        for r in RESPONSES["responses"]:
            key = r.get("sha256_prefix") or r.get("file")
            if key not in have:
                log["responses"].append(r)
        RESPONSES.update({"responses": log["responses"]})
    rpath.write_text(json.dumps(RESPONSES, indent=2) + "\n")

    # 2. flip report with before/after hashes
    zip_main = DL / f"{ART}.zip"
    zip_latest = DL / "latest.zip"
    before = {str(p.name): (sha256(p) if p.exists() else None)
              for p in (zip_main, zip_latest)}
    report = {
        "executed_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "reason": ("form rejected the NaN-outside primary on 2026-09-30 with "
                   "'Predicted values must be in range [0, 1]'; predeclared I-8 "
                   "triage step 2 executed and made DEFAULT"),
        "predictions_changed": False,
        "primary_before": {"file": f"{ART}.tif (nan_outside)"},
        "primary_after": {"file": f"{ART}_allfinite.tif (all_finite)"},
        "zip_before_sha256": before,
        "finite_verification": verify_finite(FIN),
        "nan_verification": verify_finite(NAN),
        "in_footprint_identity": None,  # filled below
    }
    with rasterio.open(FIN) as f, rasterio.open(NAN) as n:
        a, b = f.read(1), n.read(1)
        m = ~np.isnan(b)
        report["in_footprint_identity"] = bool(np.array_equal(a[m], b[m]))
        report["outside_footprint_all_zero"] = bool(np.all(a[~m] == 0.0))
    if not report["in_footprint_identity"]:
        raise SystemExit("FATAL: finite and NaN variants differ inside the footprint")

    # 4. rewrite the zips to wrap the FINITE tif
    for zpath, arc in ((zip_main, FIN.name), (zip_latest, FIN.name)):
        tmp = zpath.with_suffix(".zip.tmp")
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(FIN, arcname=arc)
        shutil.move(tmp, zpath)
    # latest_nan.zip keeps wrapping the strict variant (unchanged semantics)
    report["zip_after_sha256"] = {str(p.name): sha256(p)
                                  for p in (zip_main, zip_latest)}
    (REP / "primary_flip_2026-09-30.json").write_text(
        json.dumps(report, indent=2) + "\n")

    # 3. point the manifests at the finite primary
    patch_primary_field(REP / "latest_submission.json")
    patch_primary_field(DL / "latest.json")

    # 5. print verification
    v = report["finite_verification"]
    print(f"primary : {FIN.name}")
    print(f"  nan={v['n_nan']} inf={v['n_inf']} range=[{v['min']}, {v['max']}] "
          f"positive={v['n_positive']} dtype={v['dtype']} nodata={v['nodata']}")
    print(f"  grid {v['crs']} {v['shape']} transform {v['transform']}")
    print(f"  in-footprint identical to NaN variant: {report['in_footprint_identity']}")
    print(f"zips rewritten: {zip_main.name}, {zip_latest.name} -> wrap {FIN.name}")
    print("wrote reports/form_responses.json, reports/primary_flip_2026-09-30.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
