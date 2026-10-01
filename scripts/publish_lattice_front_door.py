#!/usr/bin/env python3
"""Publish the R13-6 lattice candidate (sq5) as the front-door PRIMARY and keep the R11
greedy recipe as the listed ALTERNATE (session 7, 2026-10-01).

Why: under the frozen R13 rule (knowledge/09_r13_hypotheses.md, addendum A) the
fault-blind stride-5 lattice beat both references on tune and confirmation, won 6/6
confirmation rule means and 18/18 paired folds vs greedy_r11
(reports/holdout_r13_lattice_2026-10-01.json). The repository doctrine is that the holdout
best gets the slot. It is a COVERAGE-GEOMETRY baseline, not a geological prediction.

Run ONCE: submission names are immutable (gems.frontdoor.write_pair raises FileExistsError on a
re-run). Refuses to run if the R13 lattice report does not say WINS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gems import frontdoor                                     # noqa: E402
from gems.rio import load_footprint                             # noqa: E402
from validate_r13_lattice_holdout import square_lattice         # noqa: E402

DL = ROOT / "docs" / "downloads"
STEM = "13gems_20261001_r13-lattice-s5"
NOTE = ("r13 lattice-s5 A-zerofill 20261001 | fault-blind every-5th-px grid, coverage baseline | "
        "local holdout 18/18 win, not a LB claim")
DESCRIPTION = ("a fault-blind lattice (every 5th row and column, 4 % of the footprint). It is the "
               "repository's best local hold-out map under the frozen R13 rule (18/18 paired folds "
               "vs the R11 recipe) and it is a coverage-geometry baseline, not a geological "
               "prediction. It is NOT a predicted leaderboard score.")


def entry(m: dict) -> dict:
    return {"A": {k: m["primary_A"][k] for k in ("file", "bytes", "sha256", "zip", "zip_bytes",
                                                  "zip_sha256")},
            "B": {k: m["fallback_B"][k] for k in ("file", "bytes", "sha256", "zip", "zip_bytes",
                                                   "zip_sha256")}}


def main() -> int:
    rep = json.loads((ROOT / "reports" / "holdout_r13_lattice_2026-10-01.json").read_text())
    verdict = list(rep["verdict_predeclared"].values())[0]
    if rep["selected_on_tune"] != "sq5" or not verdict.startswith("WINS"):
        raise SystemExit(f"R13 lattice rule did not select sq5 as a WIN: {verdict}")
    old = json.loads((DL / "submit.json").read_text())
    alts = old.get("alternates", [])
    if old["stem"] != STEM:
        alts = [{"label": "R11 greedy recipe (second candidate)", "stem": old["stem"],
                 "note_for_form": old["note_for_form"],
                 "description": ("the R11 greedy marginal-precision recipe (topographic ridge 5 % + "
                                 "three greedy blocks): the previous holdout best, a real map built "
                                 "from the geophysics/topography bands."),
                 "evidence_link": "https://github.com/buffedlizard55-lab/13GEMSDOE/blob/main/"
                                  "reports/holdout_r11_2026-09-30.json",
                 **entry(old)}]
    valid, _ = load_footprint(ROOT / "data" / "raw" / "existing_faults.tif")
    pred = (square_lattice(valid.shape, 5) & valid).astype(np.float32)
    m = frontdoor.publish(
        DL, STEM, pred, valid, note=NOTE,
        source={"recipe": "R13-6 square lattice, stride 5, origin (0,0), footprint-masked",
                "register": "knowledge/09_r13_hypotheses.md (addendum A)",
                "holdout_report": "reports/holdout_r13_lattice_2026-10-01.json",
                "positive_pixels": int((pred > 0).sum())},
        status={"artifact_status": "HOLDOUT_BEST_LOCAL_PROXY_ONLY_NOT_A_LB_CLAIM",
                "rule_verdict": verdict, "form_response_recorded": None,
                "form_responses_log": "reports/form_responses.json"})
    m["description"] = DESCRIPTION
    m["evidence_link"] = ("https://github.com/buffedlizard55-lab/13GEMSDOE/blob/main/"
                          "reports/holdout_r13_lattice_2026-10-01.json")
    m["alternates"] = alts
    (DL / "submit.json").write_text(json.dumps(m, indent=2) + "\n")
    print("published", STEM, "positives:", int((pred > 0).sum()),
          "| alternates:", [a["stem"] for a in alts])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
