#!/usr/bin/env python3
"""Publish the R14 prioritised-union map as a listed second candidate.

WHAT IT IS
----------
`union_tipsL10_1pct+lat6_4pct` (knowledge/10_r14_hypotheses.md, addendum B.2):
along-strike propagation ribbons grown from every tip of the FULL public fault
catalogue at a 1 % budget, then a stride-6 fault-blind lattice filling the rest
of a fixed 4 % total budget (206,695 px).  A geological prior with a coverage
floor.

WHY IT IS PUBLISHED EVEN THOUGH IT DID NOT PASS THE GATE
--------------------------------------------------------
`reports/holdout_r14_2026-10-01.json` records the honest outcome: it wins the
`tip`-fold worst-rule mean by +39 % over the shipped reference (0.12253 vs
0.08801) and loses the 15 pre-existing folds' worst-rule mean by 0.0279, far
more than gate D3's 0.002 allowance, and it wins only 6 of 9 paired tip folds
against gate D2's 7.  So it does **not** take the primary slot, and the primary
stays `lattice_s5` under repository doctrine.

It is published as a *named, distinct, format-proven* candidate because the two
fold families disagree by construction (I-24: the pre-existing folds and the
SGMC>=16px truth set both hide or exclude everything within ~1.6 km of a mapped
fault, which is exactly where a propagation tip aims), and no local truth set
demonstrably predicts the recorded public scores (I-26).  Three uploads per
rolling 7-day window is enough to settle that empirically; this file is one arm
of that experiment.

Run:  python scripts/publish_r14_union.py [--dry-run]
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

    paths = frontdoor.write_pair(DL, STEM, pred, valid)
    checks = frontdoor.check_pair(paths["primary"], paths["hedge"], valid)
    problems = frontdoor._all_ok(checks)
    if problems:
        raise RuntimeError("verification FAILED, nothing released: " + "; ".join(problems))

    mpath = DL / "submit.json"
    m = json.loads(mpath.read_text())
    alts = m.get("alternates", [])
    if any(a["stem"] == STEM for a in alts):
        raise SystemExit(f"{STEM} is already listed")
    alts.append({
        "label": "R14 prioritised union — geological prior with a coverage floor",
        "stem": STEM, "note_for_form": NOTE, "description": DESCRIPTION,
        "evidence_link": EVIDENCE,
        "gate": {"register": "knowledge/10_r14_hypotheses.md (addendum B.2)",
                 "report": "reports/holdout_r14_2026-10-01.json",
                 "verdict": "does NOT pass the predeclared gate (D2 6/9, D3 loses 0.0279)",
                 "role": "experiment arm, not a recommendation"},
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
    m["alternates"] = alts
    mpath.write_text(json.dumps(m, indent=2) + "\n")
    print(f"published {paths['primary'].name}")
    print(f"          {paths['hedge'].name}")
    print(f"alternates now: {[a['stem'] for a in alts]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
