#!/usr/bin/env python3
"""Re-publish the front door under the CORRECTED encoding policy (schema 2).

What was wrong
--------------
Sessions 6-7 shipped ``*_A_zerofill.tif`` as the primary download and
``*_B_nan-outside.tif`` as "only if the form rejects A".  That ordering was
based on the guess that the NaN cells caused the form's
``Predicted values must be in range [0, 1]`` rejection.

Measured 2026-10-01 (``scripts/audit_platform_encoding.py``,
``reports/platform_encoding_evidence.json``):

* the official ``sample_submission.tif`` (sha256 2176d08e...) carries
  7,111,787 NaN cells and ``GDAL_NODATA = nan``;
* 9 of the 10 files this group has a public score for carry exactly the same
  NaN placement -- 0 NaN inside the 5,167,373-pixel footprint, 0 finite cells
  outside it; the 10th is the all-finite twin of one of them and shares its
  recorded score, so it has no independent receipt;
* 0 scored files use TIFF ``Predictor``; the single form-rejected file is the
  only one in the project's history that uses ``Predictor = 2``.

So the NaN-outside encoding is the one with acceptance receipts, and the
zero-filled encoding is the unproven hedge.  This script swaps them.

What it does
------------
1. reads the predictions back out of the already-published NaN-outside files
   (pixels are NOT recomputed, so the change is provably encoding-only);
2. moves the session-7 ``*_A_zerofill`` / ``*_B_nan-outside`` files and zips
   into ``docs/downloads/archive/``;
3. republishes each candidate as ``<stem>_nan-outside.tif`` (PRIMARY) and
   ``<stem>_zerofill.tif`` (HEDGE) with a new immutable stem, refreshes the
   ``latest.*`` aliases and rewrites ``docs/downloads/submit.json`` at schema 2;
4. prints the manifest so the site build can be verified against it.

Run:  python scripts/republish_front_door_v2.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import frontdoor, rio  # noqa: E402

DL = ROOT / "docs" / "downloads"
ARCHIVE = DL / "archive"

# The two candidates already validated in this repository, carried over
# unchanged in pixel content.  `source` is the session-7 NaN-outside file whose
# in-footprint pixels become the new primary.
CANDIDATES = [
    {
        "role": "primary",
        "stem": "13gems_20261001_r13-lattice-s5_v2",
        "source": "13gems_20261001_r13-lattice-s5_B_nan-outside.tif",
        "label": "R13-6 fault-blind stride-5 lattice (holdout best)",
        "note": ("r13 lattice-s5 v2 20261001 | fault-blind every-5th-px grid, "
                 "coverage baseline | local holdout 18/18 win, not a LB claim"),
        "description": ("a fault-blind lattice (every 5th row and column, 4 % of the "
                        "footprint). It is the repository's best local hold-out map "
                        "under the frozen R13 rule (18/18 paired folds vs the R11 "
                        "recipe) and it is a coverage-geometry baseline, not a "
                        "geological prediction. It is NOT a predicted leaderboard score."),
        "evidence_link": ("https://github.com/buffedlizard55-lab/13GEMSDOE/blob/main/"
                          "reports/holdout_r13_lattice_2026-10-01.json"),
        "source_artifact": {
            "recipe": "R13-6 square lattice, stride 5, origin (0,0), footprint-masked",
            "register": "knowledge/09_r13_hypotheses.md (addendum A)",
            "holdout_report": "reports/holdout_r13_lattice_2026-10-01.json",
            "pixels_copied_from": None,   # filled in below
        },
    },
    {
        "role": "alternate",
        "stem": "13gems_20261001_r11-greedy-mp_v2",
        "source": "13gems_20261001_r11-greedy-mp_B_nan-outside.tif",
        "label": "R11-4 greedy marginal-precision recipe (second candidate)",
        "note": ("r11 greedy-mp v2 20261001 | topo ridge 5% + 3 greedy blocks | "
                 "local holdout win, not a LB claim"),
        "description": ("the R11 greedy marginal-precision recipe (topographic ridge 5 % "
                        "plus three greedy blocks): the previous holdout best, a real map "
                        "built from the geophysics/topography bands."),
        "evidence_link": ("https://github.com/buffedlizard55-lab/13GEMSDOE/blob/main/"
                          "reports/holdout_r11_2026-09-30.json"),
        "source_artifact": {
            "recipe": ("topo_ref BASE_topo_ridge 5 % spacing 3 + R10_vent@0.25 % + "
                       "R8_tpi@0.25 % + R10_dzt_field@0.25 %, each >300 m from prior, "
                       "catalogue included"),
            "register": "knowledge/07_r11_hypotheses.md",
            "holdout_report": "reports/holdout_r11_2026-09-30.json",
            "pixels_copied_from": None,
        },
    },
]

# session-7 files superseded by this migration
SUPERSEDED = [
    "13gems_20261001_r11-greedy-mp_A_zerofill.tif",
    "13gems_20261001_r11-greedy-mp_A_zerofill.zip",
    "13gems_20261001_r11-greedy-mp_B_nan-outside.tif",
    "13gems_20261001_r11-greedy-mp_B_nan-outside.zip",
    "13gems_20261001_r13-lattice-s5_A_zerofill.tif",
    "13gems_20261001_r13-lattice-s5_A_zerofill.zip",
    "13gems_20261001_r13-lattice-s5_B_nan-outside.tif",
    "13gems_20261001_r13-lattice-s5_B_nan-outside.zip",
    "latest.tif", "latest.zip", "latest_nan.tif", "latest_nan.zip",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    valid, _ = rio.load_footprint(ROOT / "data" / "raw" / "existing_faults.tif")
    print(f"footprint {int(valid.sum()):,} px")

    preds: dict[str, np.ndarray] = {}
    for c in CANDIDATES:
        src = DL / c["source"]
        if not src.exists():
            raise SystemExit(f"source file missing: {src}")
        with rasterio.open(src) as s:
            arr = s.read(1)
        if int(np.isnan(arr[valid]).sum()) != 0:
            raise SystemExit(f"{src.name}: NaN inside the footprint -- refusing")
        pred = np.nan_to_num(arr, nan=0.0).astype(np.float32)
        preds[c["stem"]] = pred
        c["source_artifact"]["pixels_copied_from"] = f"docs/downloads/{c['source']}"
        c["source_artifact"]["positive_pixels"] = int((pred[valid] > 0).sum())
        print(f"read {c['source']:56s} positives={int((pred[valid] > 0).sum()):,}")
        del arr

    if args.dry_run:
        print("--dry-run: nothing written")
        return 0

    # 1. archive the superseded session-7 artifacts (pixels preserved, provenance kept)
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    moved = []
    for name in SUPERSEDED:
        p = DL / name
        if p.exists():
            dest = ARCHIVE / f"session7-superseded-{name}"
            shutil.move(str(p), dest)
            moved.append(f"{name} -> archive/{dest.name}")
    print(f"archived {len(moved)} superseded files")

    # 2. publish the primary, then each alternate, then re-attach the alternates
    manifest = None
    for c in CANDIDATES:
        if c["role"] != "primary":
            continue
        manifest = frontdoor.publish(
            DL, c["stem"], preds[c["stem"]], valid, note=c["note"],
            source=c["source_artifact"],
            status={"artifact_status": "HOLDOUT_BEST_LOCAL_PROXY_ONLY_NOT_A_LB_CLAIM",
                    "encoding_status": ("PRIMARY matches the encoding of the official "
                                        "template and of all 9 platform-scored group "
                                        "files (reports/platform_encoding_evidence.json)"),
                    "form_response_recorded": None,
                    "form_responses_log": "reports/form_responses.json"})
        manifest["description"] = c["description"]
        manifest["evidence_link"] = c["evidence_link"]
        manifest["label"] = c["label"]

    alternates = []
    for c in CANDIDATES:
        if c["role"] == "primary":
            continue
        paths = frontdoor.write_pair(DL, c["stem"], preds[c["stem"]], valid)
        facts = frontdoor.check_pair(paths["primary"], paths["hedge"], valid)
        problems = frontdoor._all_ok(facts)
        if problems:
            raise RuntimeError(f"alternate {c['stem']} failed: {'; '.join(problems)}")
        alternates.append({
            "label": c["label"], "stem": c["stem"], "note_for_form": c["note"],
            "description": c["description"], "evidence_link": c["evidence_link"],
            "primary": {"file": paths["primary"].name,
                        "bytes": paths["primary"].stat().st_size,
                        "sha256": frontdoor.sha256_file(paths["primary"]),
                        "zip": paths["primary_zip"].name,
                        "zip_bytes": paths["primary_zip"].stat().st_size,
                        "zip_sha256": frontdoor.sha256_file(paths["primary_zip"])},
            "hedge": {"file": paths["hedge"].name,
                      "bytes": paths["hedge"].stat().st_size,
                      "sha256": frontdoor.sha256_file(paths["hedge"]),
                      "zip": paths["hedge_zip"].name,
                      "zip_bytes": paths["hedge_zip"].stat().st_size,
                      "zip_sha256": frontdoor.sha256_file(paths["hedge_zip"])},
        })
    manifest["alternates"] = alternates
    manifest["supersedes"] = {
        "session": "session 7 (2026-10-01) schema-1 manifest",
        "reason": ("encoding roles were inverted: the zero-filled file was primary and the "
                   "NaN-outside file was the fallback. Measurement shows the opposite: "
                   "the NaN-outside encoding is the one the official template uses and "
                   "the one all 9 platform-scored group files use; the only file the form "
                   "ever rejected is the only one written with TIFF Predictor=2."),
        "evidence": "reports/platform_encoding_evidence.json",
        "archived_files": moved,
    }
    (DL / "submit.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"\npublished primary {manifest['primary']['file']}")
    print(f"          hedge   {manifest['hedge']['file']}")
    print(f"          alternates {[a['stem'] for a in alternates]}")
    print(f"wrote {DL/'submit.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
