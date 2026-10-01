#!/usr/bin/env python3
"""Publish the front-door submission pair (A zero-fill, B NaN-outside) for an
ALREADY ARCHIVED prediction map, without rebuilding the map.

Why this exists (2026-10-01, session 7)
---------------------------------------
* ``latest.tif`` was still the NaN-outside file the form rejected: the session-6
  flip script re-zipped but never replaced ``latest.tif`` (irregularity I-19).
* Every file this repository generated used TIFF ``PREDICTOR=2`` (integer
  differencing) on float32 data; none of the files the platform is recorded as
  having scored did (predictor 3 or none), nor does the official example
  (irregularity I-18). The predictions are unchanged; only the byte layout is.

The map is read from the archived NaN-outside GeoTIFF (footprint = its finite
cells; cross-checked against the official label raster when ``data/raw`` is
present) and the pixel identity against the archived all-finite twin is
asserted before anything is written, so this cannot drift the prediction (the
I-15 concern that forbids a rebuild).

Usage:  python scripts/publish_front_door.py            # publishes r11
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import frontdoor  # noqa: E402

DL = ROOT / "docs" / "downloads"
REP = ROOT / "reports"
RAW = ROOT / "data" / "raw"

SRC_NAN = DL / "archive" / "13gems-r11-greedy-mp.tif"            # archived strict twin
SRC_FIN = DL / "archive" / "13gems-r11-greedy-mp_allfinite.tif"  # archived finite twin
STEM = "13gems_20261001_r11-greedy-mp"
NOTE = ("r11 greedy-mp A-zerofill 20261001 | topo ridge 5% + 3 greedy blocks | "
        "local holdout win, not a LB claim")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stem", default=STEM)
    ap.add_argument("--note", default=NOTE)
    a = ap.parse_args()

    src_nan = SRC_NAN if SRC_NAN.exists() else DL / "13gems-r11-greedy-mp.tif"
    src_fin = SRC_FIN if SRC_FIN.exists() else DL / "13gems-r11-greedy-mp_allfinite.tif"
    for p in (src_nan, src_fin):
        if not p.exists():
            raise SystemExit(f"missing archived source {p}")

    with rasterio.open(src_nan) as s:
        nan_arr = s.read(1)
    with rasterio.open(src_fin) as s:
        fin_arr = s.read(1)
    valid = np.isfinite(nan_arr)
    if (RAW / "existing_faults.tif").exists():
        with rasterio.open(RAW / "existing_faults.tif") as s:
            lab = s.read(1)
        if not np.array_equal(lab >= 0, valid):
            raise SystemExit("FATAL: archived footprint != official label footprint")
        footprint_check = "equals official label raster footprint (existing_faults.tif >= 0)"
    else:
        footprint_check = "label raster not present; footprint taken from archived file"
    pred = np.where(valid, nan_arr, 0.0).astype(np.float32)
    if not np.array_equal(pred, fin_arr):
        raise SystemExit("FATAL: archived NaN and finite twins disagree - refusing to publish")

    prov = json.loads((REP / "latest_submission.json").read_text())
    src = {
        "recipe": "greedy_r11 (R11-4 greedy marginal-precision assembly)",
        "archived_sources": [str(src_nan.relative_to(ROOT)), str(src_fin.relative_to(ROOT))],
        "footprint_check": footprint_check,
        "pixels_identical_to_archived_allfinite": True,
        "positive_cells": int((pred > 0).sum()),
        "holdout_report": "reports/holdout_r11_2026-09-30.json",
        "provenance_manifest": "reports/latest_submission.json",
        "selection_note": prov.get("recipe_selection", {}).get("selected_by"),
        "reencoding_reason": "I-18 (predictor 2 on float32) and I-19 (latest.tif was the NaN file)",
    }
    status = {
        "holdout_claim": ("Local hide-and-recover catalogue-recovery win vs topo_05_sp3 "
                          "(confirm worst-rule-mean DTI 0.09175 vs 0.08694, 18/18 paired folds). "
                          "NOT a leaderboard or private-test claim."),
        "form_response_recorded": None,
        "form_responses_log": "reports/form_responses.json",
    }
    m = frontdoor.publish(DL, a.stem, pred, valid, note=a.note, source=src, status=status)
    f = m["local_verification"]
    print("A:", m["primary_A"]["file"], m["primary_A"]["sha256"][:12], m["primary_A"]["bytes"], "bytes")
    print("B:", m["fallback_B"]["file"], m["fallback_B"]["sha256"][:12], m["fallback_B"]["bytes"], "bytes")
    print("readers:", f["readers_used"], "agree A/B:", f["all_readers_agree_A"], f["all_readers_agree_B"])
    print("A layout:", f["A"]["layout"], " B layout:", f["B"]["layout"])
    print("A==B inside footprint:", f["A_equals_B_inside_footprint"], "positives:", f["A"]["n_positive"])
    print("note:", m["note_for_form"], f"({len(m['note_for_form'])} chars)")

    # point the older provenance manifests at the new primary (no stale names)
    for jp in (REP / "latest_submission.json", DL / "latest.json"):
        if not jp.exists():
            continue
        obj = json.loads(jp.read_text())
        obj["primary_upload"] = {
            "front_door_manifest": "docs/downloads/submit.json",
            "primary_A": m["primary_A"]["file"], "fallback_B": m["fallback_B"]["file"],
            "supersedes": "primary_upload from session 6 (13gems-r11-greedy-mp_allfinite.tif, "
                          "PREDICTOR=2 layout) - same pixels, new byte layout",
        }
        jp.write_text(json.dumps(obj, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
