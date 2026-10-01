#!/usr/bin/env python3
"""R14 research archive only. Failed predeclared gate; DO NOT SUBMIT.

Existing downloads are retained for forensic review, not recommended experiments.
This legacy publication command is disabled. --dry-run may inspect geometry but
must not change the front door or advise spending a weekly slot.
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
from gems import frontdoor, propagation as P, rio  # noqa: E402

DL = ROOT / "docs" / "downloads"
STEM = "13gems_20261001_r14-union-tips10-lat6"
TIP_LEN = 10
TIP_FRAC = 0.01
LATTICE_STRIDE = 6
TOTAL_FRAC = 0.04
NOTE = ("r14 union 20261001 | along-strike tips 1% + stride-6 lattice to 4% total | "
        "fails predeclared gate D2/D3, experiment arm")
DESCRIPTION = (
    "a geological prior with a coverage floor: along-strike propagation ribbons grown "
    "from every tip of the full public fault catalogue (1 % of the footprint), then a "
    "fault-blind stride-6 lattice filling the remainder of a fixed 4 % total budget. "
    "It did NOT pass the predeclared R14 gate (it wins the new tip folds' worst-rule "
    "mean by +39 % over the shipped reference and loses the 15 pre-existing folds by "
    "0.028, beyond the 0.002 allowance), so it is a listed experiment arm, not a "
    "recommendation, and not a predicted leaderboard score.")
EVIDENCE = ("https://github.com/buffedlizard55-lab/13GEMSDOE/blob/main/"
            "reports/holdout_r14_2026-10-01.json")


def build(valid: np.ndarray, known: np.ndarray, jitter: np.ndarray) -> np.ndarray:
    n_valid = int(valid.sum())
    tips = P.along_strike_tips(known, length_px=TIP_LEN)
    # the organiser masks known-fault pixels out of evaluation entirely (forum
    # 11516 post 2), so no mass is ever placed on them: gate D4 is met by
    # construction rather than by luck (F1 / I-27)
    em = valid & ~known
    prim = P.budget_from_intensity(tips, em, int(round(TIP_FRAC * n_valid)),
                                   jitter=jitter) > 0
    lat = P.square_lattice(valid.shape, LATTICE_STRIDE)
    pred = P.prioritised_union(prim, lat, em, int(round(TOTAL_FRAC * n_valid)),
                               jitter=jitter)
    return pred.astype(np.float32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.dry_run:
        raise SystemExit("R14 failed its predeclared gate; no publication allowed and no files changed.")

    valid, known = rio.load_footprint(rio.resolve_raw("labels"))
    jitter = P.make_jitter(valid.shape)
    pred = build(valid, known, jitter)

    n_pos = int((pred > 0).sum())
    on_cat = int(((pred > 0) & known).sum())
    facts = {
        "positive_pixels": n_pos,
        "pct_of_footprint": round(100.0 * n_pos / int(valid.sum()), 4),
        "pixels_on_known_catalogue": on_cat,
        "frac_off_catalogue": round(1.0 - on_cat / max(n_pos, 1), 6),
        "tip_length_px": TIP_LEN, "tip_budget_frac": TIP_FRAC,
        "lattice_stride": LATTICE_STRIDE, "total_budget_frac": TOTAL_FRAC,
        "gate_D4_min_off_catalogue": 0.95,
    }
    print(json.dumps(facts, indent=2))
    if facts["frac_off_catalogue"] < 0.95:
        raise SystemExit("D4 FAILS: emission is not >=95% off-catalogue")
    if args.dry_run:
        print("--dry-run: nothing written")
        return 0



if __name__ == "__main__":
    main()
