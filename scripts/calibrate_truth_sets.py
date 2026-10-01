#!/usr/bin/env python3
"""R15-A -- which local truth set actually predicts the public leaderboard?

WHY
---
Every score this repository has ever produced is a *proxy*: hide part of the
known USGS/INGENIOUS catalogue and try to recover it.  That proxy is now known
to be weak.  The sibling repo 16GEMSDOE published a post-hoc calibration
against 15 publicly scored files
(https://github.com/buffedlizard55-lab/16GEMSDOE/blob/main/evidence/proxy_calibration_vs_lb.json):

    known_dense (the catalogue itself)   Spearman rho = 0.171, p = 0.541
    sgmc_offcat                          Spearman rho = 0.393, p = 0.148
    sgmc_gap                             Spearman rho = 0.518, p = 0.048

i.e. a catalogue-recovery proxy does NOT rank submissions the way DrivenData
does, while faults from the **USGS State Geologic Map compilation (SGMC)** that
are absent from the competition catalogue do -- which is exactly the kind of
target the competition describes ("faults manually identified by experts that
are NOT contained within the current public USGS database").

This script does not inherit that result.  It re-derives it here, from bytes
this repository can verify, over a family of explicitly defined truth sets, and
picks the one that correlates best.  Whatever wins becomes the selection proxy
for R15-B; whatever loses is recorded as losing.

TRUTH SETS (all inside the official 5,167,373-px footprint)
  known_dense            the whole USGS/INGENIOUS catalogue (60,988 px)
  known_hidden25         a spatially-blocked 25 % of it (this repo's old proxy)
  sgmc_offcat_rK         SGMC fault pixels at least K px from the catalogue,
                         K in {0, 3, 8, 16, 32}

SCORING RULE (organiser-verified)
  Known-catalogue pixels are masked / excluded from evaluation in both rounds
  (chrisk-dd, DrivenData Staff, forum 11516 post 2, 2026-09-16).  So the
  evaluation mask is always `footprint & ~known`, and TP/FP/FN are computed with
  src.gems.metric.dti exactly as published.

DATA PROVENANCE (free, official, public)
  data/external/derived_sgmc_faults_100m_u8.tif -- faults from the USGS State
  Geologic Map compilation for NV and CA
  (https://mrdata.usgs.gov/geology/state/shp/NV.zip and .../CA.zip, sha256 pins
  in 16GEMSDOE evidence/ci/external_verification.json), rasterised onto the
  competition grid; 110,732 fault px, nodata 255 exactly on the 7,111,787
  outside-footprint px (asserted below).  Fetched with
  scripts/fetch_sgmc_truth.py.

Run:  python scripts/calibrate_truth_sets.py
Out:  reports/truthset_calibration.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi
from scipy import stats as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import encoding, metric  # noqa: E402
from gems.holdout import build_folds  # noqa: E402
from gems import rio  # noqa: E402

RAW = ROOT / "data" / "raw"
EXT = ROOT / "data" / "external_sgmc"
SCORED = ROOT / "data" / "scored"
OUT = ROOT / "reports" / "truthset_calibration.json"

# Recorded public scores.  Source: reports/leaderboard_ledger.csv (team-recorded
# from the public leaderboard page; `verified` = NO there and it stays NO here).
# The file sha256 column of that ledger is re-checked against the bytes below.
LEDGER = ROOT / "reports" / "leaderboard_ledger.csv"
SGMC_RINGS = (0, 3, 8, 16, 32)

# Two scored files are not in this repo's ledger. Their public scores are taken
# from the sibling registry 16GEMSDOE registry/submissions.json (also
# team-recorded, also NOT a per-submission receipt). Keyed by file sha256.
SUPPLEMENT = {
    # 12GEMSDOE r7-nms3-dem10-scarp_0c9199f14e62, account named "SDCF9"
    "0c9199f14e625d7b2539a0a045803b74d6494ce568d185abecc193fe7e93c6f2": "0.1294",
    # its all-finite twin: the SAME submission content in the other encoding.
    # Excluded from the correlation (EXCLUDE_FROM_CORR) because it is not an
    # independent observation.
    "ce3f70fa2e1e7bbea60c8c62a2f805c22d15b8a8905ebec757259617ceb02fbc": "0.1294",
}
EXCLUDE_FROM_CORR = {"ce3f70fa2e1e7bbea60c8c62a2f805c22d15b8a8905ebec757259617ceb02fbc"}


def load_ledger() -> list[dict]:
    import csv
    rows = []
    with open(LEDGER, newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append(r)
    return rows


def dti_for(pred: np.ndarray, truth: np.ndarray, eval_mask: np.ndarray) -> dict:
    p = np.nan_to_num(pred, nan=0.0).astype(np.float64)
    p = np.clip(p, 0.0, 1.0)
    p = np.where(eval_mask, p, 0.0)
    res = metric.dti(p, truth.astype(np.uint8), eval_mask=eval_mask)
    d = res.as_dict()
    d["n_predicted_in_mask"] = int((p > 0).sum())
    return d


def main() -> int:
    t0 = time.time()
    with rasterio.open(rio.resolve_raw("labels", RAW)) as s:
        lab = s.read(1)
    valid = lab >= 0
    known = lab > 0
    assert int(valid.sum()) == encoding.FOOTPRINT_PIXELS
    assert int(known.sum()) == 60988

    sg_path = EXT / "derived_sgmc_faults_100m_u8.tif"
    if not sg_path.exists():
        raise SystemExit(f"{sg_path} missing -- run python scripts/fetch_sgmc_truth.py")
    with rasterio.open(sg_path) as s:
        sg = s.read(1)
        sg_crs, sg_tfm, sg_nd = str(s.crs), tuple(s.transform)[:6], s.nodata
    assert sg_crs == encoding.EXPECTED_CRS, sg_crs
    assert sg_tfm == encoding.EXPECTED_TRANSFORM, sg_tfm
    assert np.array_equal(sg == sg_nd, ~valid), \
        "SGMC nodata mask must equal the outside-footprint mask"
    sgmc = (sg == 1) & valid
    print(f"SGMC fault px inside footprint: {int(sgmc.sum()):,}")
    print(f"  of which already in the catalogue: {int((sgmc & known).sum()):,}")
    print(f"  catalogue px reproduced by SGMC: {int((known & sgmc).sum()):,} / {int(known.sum()):,}")

    truths: dict[str, np.ndarray] = {"known_dense": known.copy()}
    # known_dense is the DEGENERATE proxy: its truth pixels are exactly the
    # pixels the organiser says are masked out of evaluation, so it can only be
    # scored by NOT applying the masking rule. Kept because the sibling repo's
    # calibration used it, and because scoring it that way is precisely why it
    # ranks submissions unlike the platform does.
    masks: dict[str, np.ndarray] = {"known_dense": valid.copy()}
    for k in SGMC_RINGS:
        if k == 0:
            m = sgmc & ~known
        else:
            dil = ndi.binary_dilation(known, iterations=k)
            m = sgmc & ~dil
        truths[f"sgmc_offcat_r{k}"] = m
        # off-catalogue truth, so the organiser masking rule applies directly
        masks[f"sgmc_offcat_r{k}"] = valid & ~known
        print(f"  sgmc_offcat_r{k}: {int(m.sum()):,} px")

    # the repo's own proxy, for comparison
    folds = build_folds(known, valid, n_folds=1, hide_frac=0.25, seed=20261001,
                        link_px=8, buffer_px=5)
    truths["known_hidden25"] = folds[0].hidden
    # the hidden systems ARE the truth here, so they must not be masked; the
    # remaining VISIBLE catalogue is masked exactly as the organiser does
    masks["known_hidden25"] = folds[0].eval_mask
    print(f"  known_hidden25 (fold '{folds[0].name}'): {int(folds[0].hidden.sum()):,} px")

    for t, mk in masks.items():
        print(f"  eval mask for {t:18s}: {int(mk.sum()):,} px")

    rows = load_ledger()
    by_sha = {r["file_sha256"]: r for r in rows if r.get("file_sha256")}
    files = sorted(SCORED.glob("*.tif"))
    if not files:
        raise SystemExit("data/scored empty -- run python scripts/fetch_data.py")

    per_file = []
    for f in files:
        import hashlib
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        rec = by_sha.get(h)
        raw = rec.get("reported_score_label_not_receipt") if rec else SUPPLEMENT.get(h)
        try:
            score = float(raw)
        except (TypeError, ValueError):
            score = None
        with rasterio.open(f) as s:
            pred = s.read(1).astype(np.float32)
        entry = {"file": f.name, "sha256": h, "bytes": f.stat().st_size,
                 "ledger_match": bool(rec),
                 "ledger_artifact_id": rec["artifact_id"] if rec else None,
                 "public_score": score}
        for tname, tm in truths.items():
            # two masking policies, because the calibration turns out to be
            # sensitive to this choice and that sensitivity is itself a result
            for pol, mk in (("masked", masks[tname]), ("unmasked", valid)):
                d = dti_for(pred, tm, mk)
                entry[f"{tname}|{pol}"] = {
                    "dti": round(d["dti"], 6),
                    "precision_w": round(d["precision_w"], 6),
                    "recall_w": round(d["recall_w"], 6),
                    "n_truth": d["n_truth"],
                    "n_predicted_in_mask": d["n_predicted_in_mask"]}
            entry[tname] = entry[f"{tname}|masked"]
        per_file.append(entry)
        print(f"  {f.name:44s} lb={score} " +
              " ".join(f"{t}={entry[t]['dti']:.4f}" for t in truths))

    scored = [e for e in per_file
              if e["public_score"] is not None and e["sha256"] not in EXCLUDE_FROM_CORR]
    corr = {}
    keys = [f"{t}|{pol}" for t in truths for pol in ("masked", "unmasked")]
    for tname in keys:
        x = np.array([e[tname]["dti"] for e in scored])
        y = np.array([e["public_score"] for e in scored])
        if len(set(y.tolist())) < 3 or np.std(x) == 0:
            corr[tname] = {"n": len(scored), "spearman_rho": None,
                           "note": "degenerate (no variance)"}
            continue
        rho, p = st.spearmanr(x, y)
        tau, pt = st.kendalltau(x, y)
        corr[tname] = {"n": len(scored),
                       "spearman_rho": round(float(rho), 4),
                       "spearman_p": round(float(p), 4),
                       "kendall_tau": round(float(tau), 4),
                       "kendall_p": round(float(pt), 4),
                       "n_truth_px": int(truths[tname.split("|")[0]].sum()),
                       "masking_policy": tname.split("|")[1]}
    best = max((k for k, v in corr.items() if v.get("spearman_rho") is not None),
               key=lambda k: corr[k]["spearman_rho"], default=None)

    report = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "script": "scripts/calibrate_truth_sets.py",
        "runtime_s": round(time.time() - t0, 1),
        "organiser_masking_rule": {
            "quote": ("Pixels corresponding to known USGS/INGENIOUS faults are masked / "
                      "excluded from evaluation, so they do not count towards penalty terms."),
            "who": "chrisk-dd (DrivenData Staff)", "when": "2026-09-16",
            "where": ("https://community.drivendata.org/t/scoring-clarification-are-known-"
                      "usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-"
                      "final-round-label-set/11516/2"),
            "eval_masks": {k: int(v.sum()) for k, v in masks.items()},
        },
        "sgmc_source": {
            "official_urls": ["https://mrdata.usgs.gov/geology/state/shp/NV.zip",
                              "https://mrdata.usgs.gov/geology/state/shp/CA.zip"],
            "rasterised_by": "16GEMSDOE GitHub Actions runner (evidence/ci/external_verification.json)",
            "fetched_here_by": "scripts/fetch_sgmc_truth.py",
            "fault_px_inside_footprint": int(sgmc.sum()),
            "catalogue_px_reproduced_by_sgmc": int((known & sgmc).sum()),
            "nodata_equals_outside_footprint": True,
        },
        "truth_sets": {k: int(v.sum()) for k, v in truths.items()},
        "excluded_from_correlation": sorted(EXCLUDE_FROM_CORR),
        "correlation_with_public_score": corr,
        "best_truth_set": best,
        "per_file": per_file,
        "caveats": [
            "Public scores are team-recorded, not per-submission receipts "
            "(reports/leaderboard_ledger.csv, verified = NO).",
            "The public leaderboard column is an account-level BEST, so several "
            "uploads by one account collapse to one number (irregularity I-3).",
            "n is small and two files are the all-finite/NaN twins of one "
            "submission, so the effective sample is smaller than it looks.",
            "A high rho here says the truth set RANKS submissions like the "
            "platform does; it does not say the absolute DTI equals the public "
            "score, and it does not make any number here a leaderboard claim.",
        ],
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print("\n=== Spearman rho vs recorded public score (masked = organiser rule) ===")
    for k, v in sorted(corr.items(), key=lambda kv: -(kv[1].get("spearman_rho") or -9)):
        print(f"  {k:32s} rho={v.get('spearman_rho')} p={v.get('spearman_p')} "
              f"tau={v.get('kendall_tau')} n={v['n']} truth_px={v.get('n_truth_px')}")
    print(f"\nBEST truth set: {best}")
    print(f"wrote {OUT.relative_to(ROOT)} in {report['runtime_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
