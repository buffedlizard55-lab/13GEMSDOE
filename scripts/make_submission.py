#!/usr/bin/env python3
"""Build a locally format-checked prediction artifact; this does not clear upload.

Usage
-----
    python scripts/make_submission.py --recipe best
    python scripts/make_submission.py --detector FUSION_rankmean --coverage 0.05 --spacing 3

The legacy recipe `best` reads reports/holdout_results.json and selects by
minimum DTI across its stored withholding rules (not the highest mean). It is
not automatically updated from newer holdouts and is not an upload gate; every
artifact remains NOT_CLEARED until current paired direct-DTI confirmation.

Outputs, into docs/downloads/:
    <name>.tif           NaN outside the data bounds (per official format text)
    <name>_allfinite.tif zero-filled diagnostic twin; not assumed NoData-equivalent
    <name>.zip           zip of the official-format NaN-outside .tif
    <name>.json          provenance + a descriptive note for the form
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import detectors as D                 # noqa: E402
from gems.rio import (EXPECTED_SHAPE, read_band, validate_submission,
                     write_submission)  # noqa: E402

DER = ROOT / "data" / "derived"

OUT = ROOT / "docs" / "downloads"
REP = ROOT / "reports"


def prediction_identity(values: np.ndarray, valid_mask: np.ndarray) -> dict:
    """Hash canonical scored-grid pixels and positive support, ignoring NoData form."""
    a = np.asarray(values, dtype=np.float32)
    valid = np.asarray(valid_mask, dtype=bool)
    if a.shape != valid.shape:
        raise ValueError(f"prediction/mask shape mismatch: {a.shape} vs {valid.shape}")
    canonical = np.where(np.isfinite(a), a, 0.0)
    canonical = np.where(valid, canonical, 0.0).astype("<f4", copy=False)
    canonical[canonical == 0] = 0.0  # normalize negative zero before hashing
    support = (canonical > 0) & valid
    pixel_hash = hashlib.sha256(np.ascontiguousarray(canonical).tobytes()).hexdigest()
    support_hash = hashlib.sha256(
        str(support.shape).encode("ascii")
        + np.packbits(support.astype(np.uint8), bitorder="little").tobytes()
    ).hexdigest()
    return {
        "canonical_pixel_sha256": pixel_hash,
        "positive_support_sha256": support_hash,
        "positive_pixels": int(support.sum()),
        "identity_scope": "float32 scored-grid values; NaN and outside-footprint cells canonicalized to zero",
    }


def check_existing_prediction_identity(values: np.ndarray,
                                       valid_mask: np.ndarray) -> dict:
    """Fail closed on unreadable archives or exact pixel duplicates.

    Compare both named downloads and historical scored TIFFs. NaN-outside and
    finite-zero twins normalize to the same canonical scored-grid identity.
    """
    candidate = prediction_identity(values, valid_mask)
    exact_matches = []
    same_support = []
    checked = []
    directories = [OUT, ROOT / "data" / "scored"]
    paths = sorted({p for directory in directories if directory.exists()
                    for p in directory.rglob("*.tif") if p.is_file()})

    def display_path(path: Path) -> str:
        resolved = path.resolve()
        try:
            return str(resolved.relative_to(ROOT))
        except ValueError:
            return str(resolved)

    for path in paths:
        try:
            existing = read_band(path)
        except Exception as exc:
            raise RuntimeError(
                f"Cannot verify prediction identity against existing raster {path}: {exc}"
            ) from exc
        if existing.shape != valid_mask.shape:
            continue
        identity = prediction_identity(existing, valid_mask)
        label = display_path(path)
        checked.append(label)
        if identity["canonical_pixel_sha256"] == candidate["canonical_pixel_sha256"]:
            exact_matches.append(label)
        elif identity["positive_support_sha256"] == candidate["positive_support_sha256"]:
            same_support.append(label)
    if exact_matches:
        raise FileExistsError(
            "Prediction identity check failed: canonical scored-grid pixels are "
            "identical to existing artifact(s): " + ", ".join(exact_matches)
        )
    if same_support:
        print("WARNING: candidate support matches existing artifact(s) but pixel "
              "values differ: " + ", ".join(same_support))
    return {
        **candidate,
        "exact_duplicate_matches": exact_matches,
        "same_support_different_values": same_support,
        "existing_rasters_checked": checked,
        "score_uniqueness_claim": (
            "None. Different prediction maps can still round to the same score."
        ),
    }


def pick_best_recipe() -> tuple[str, float, int, dict]:
    """Highest worst-case DTI across withholding rules."""
    res = json.loads((REP / "holdout_results.json").read_text())["results"]
    per_rule = defaultdict(lambda: defaultdict(list))
    for r in res:
        if r["family"].startswith("STAGE2:") and r["family"] != "STAGE2:control":
            per_rule[r["tag"]][r["rule"]].append(r["dti"])
    if not per_rule:                     # fall back to stage 1
        for r in res:
            if r["family"] in ("control", "prior_submission"):
                continue
            per_rule[r["tag"]][r["rule"]].append(r["dti"])

    scored = []
    for tag, rules in per_rule.items():
        rule_means = {k: float(np.mean(v)) for k, v in rules.items()}
        scored.append((min(rule_means.values()), float(np.mean(list(rule_means.values()))),
                       tag, rule_means))
    scored.sort(reverse=True)
    worst, mean, tag, rule_means = scored[0]
    fam, covs, sps = tag.split("|")
    return fam, float(covs[3:]), int(sps[2:]), {
        "tag": tag, "worst_rule_dti": round(worst, 6),
        "mean_rule_dti": round(mean, 6), "per_rule": {k: round(v, 6)
                                                      for k, v in rule_means.items()},
        "runner_up": [{"tag": t, "worst": round(w, 6)} for w, _, t, _ in scored[1:4]],
    }


def build_r6_ensemble(reach: int = 20, spacing: int = 3,
                      topo_cov: float = 0.03, grav_cov: float = 0.01,
                      transt_cov: float = 0.01, tdr_cov: float = 0.01,
                      shore_cov: float = 0.005, cond_cov: float = 0.005,
                      include_catalogue: bool = True) -> tuple[np.ndarray, np.ndarray, dict]:
    """Exploratory R6 union of catalogue geometry, terrain, and field transforms.

    The components represent testable physical hypotheses, not validated fault
    labels. Prior detector-level scores were measured under older local protocols;
    this recipe has not been cleared by the current visible-only confirmation
    comparison. Grid thinning reduces support but does not guarantee a minimum
    separation or optimal DTI. The effect of predictions on masked known pixels
    on nearby truth credit remains unresolved (knowledge/02 Q-1).
    """
    valid = np.load(DER / "_valid.npy")
    known = np.load(DER / "_known.npy")
    n_valid = int(valid.sum())
    allowed = valid & ~known

    def topk_from_score(score: np.ndarray, cov: float) -> np.ndarray:
        if cov <= 0:
            return np.zeros(score.shape, dtype=bool)
        n = int(cov * n_valid)
        flat = np.where(allowed, score, -np.inf).ravel()
        n = min(n, int(np.isfinite(flat).sum()))
        if n <= 0:
            return np.zeros(score.shape, dtype=bool)
        idx = np.argpartition(flat, -n)[-n:]
        mask = np.zeros(flat.size, dtype=bool)
        mask[idx] = True
        return mask.reshape(score.shape)

    # catalogue-derived rays (full catalogue for submission)
    rays = D.extension_rays(known, reach_px=reach)
    m_rays = (rays > 0) & allowed
    n_rays_raw = int(m_rays.sum())
    if spacing > 1:
        m_rays = D.decimate_grid(m_rays, rays, spacing)
    n_rays = int(m_rays.sum())

    horse = D.horsetail_splay(known, max_gap_px=20, splay_len_px=12)
    m_horse = (horse > 0) & allowed
    n_horse_raw = int(m_horse.sum())
    if spacing > 1:
        m_horse = D.decimate_grid(m_horse, horse, spacing)
    n_horse = int(m_horse.sum())

    # load cached detectors
    def load_det(name):
        p = DER / f"{name}.npy"
        return np.load(p) if p.exists() else None

    topo = load_det("BASE_topo_ridge")
    grav = load_det("R6_gravterm")
    transt = load_det("R6_transt")
    tdr = load_det("HB_tdr_rtp")
    shore = load_det("R6_shore")
    cond = load_det("R6_condbase")

    masks = []
    masks.append(m_rays)
    masks.append(m_horse)

    cov_map = {
        "BASE_topo_ridge": (topo, topo_cov),
        "R6_gravterm": (grav, grav_cov),
        "R6_transt": (transt, transt_cov),
        "HB_tdr_rtp": (tdr, tdr_cov),
        "R6_shore": (shore, shore_cov),
        "R6_condbase": (cond, cond_cov),
    }
    details = {}
    for det_name, (score, cov) in cov_map.items():
        if score is None or cov <= 0:
            continue
        m = topk_from_score(score, cov)
        if spacing > 1:
            m = D.decimate_grid(m, score, spacing)
        masks.append(m)
        details[det_name] = {"coverage_target": cov, "n_px_after_decimation": int(m.sum())}

    union = np.zeros(valid.shape, dtype=bool)
    for m in masks:
        union |= m

    pred = union.astype(np.float32)
    if include_catalogue:
        pred = np.maximum(pred, known.astype(np.float32))

    stats = {
        "recipe": "r6_ensemble",
        "tip_ray_reach_px": reach,
        "tip_ray_reach_m": reach * 100,
        "decimation_spacing_px": spacing,
        "coverages": {k: v["coverage_target"] for k, v in details.items()},
        "n_px_per_detector": details,
        "n_tip_ray_px_before_decimation": n_rays_raw,
        "n_tip_ray_px": n_rays,
        "n_horse_px_before_decimation": n_horse_raw,
        "n_horse_px": n_horse,
        "n_union_new_px": int(union.sum()),
        "n_predicted_px": int((pred > 0).sum()),
        "pct_of_valid": round(100.0 * float((pred > 0).sum()) / n_valid, 4),
        "max_value": float(pred.max()),
        "min_value": float(pred.min()),
        "include_known_catalogue": include_catalogue,
    }
    return pred, valid, stats


def build_composite_plus(reach: int = 20, spacing: int = 3, fill_cov: float = 0.05,
                         horse_gap: int = 20, horse_splay: int = 12,
                         include_catalogue: bool = True) -> tuple[np.ndarray, np.ndarray, dict]:
    """Exploratory union of tip-ray, horsetail, and topographic candidate layers.

    Earlier tip-regime measurements are local proxies and do not validate this
    combined map under the current visible-only confirmation protocol.
    """
    valid = np.load(DER / "_valid.npy")
    known = np.load(DER / "_known.npy")
    topo = np.load(DER / "BASE_topo_ridge.npy")
    n_valid = int(valid.sum())
    allowed = valid & ~known

    rays = D.extension_rays(known, reach_px=reach)
    m_rays = (rays > 0) & allowed
    n_rays_raw = int(m_rays.sum())
    if spacing > 1:
        m_rays = D.decimate_grid(m_rays, rays, spacing)
    n_rays = int(m_rays.sum())

    horse = D.horsetail_splay(known, max_gap_px=horse_gap, splay_len_px=horse_splay)
    m_horse = (horse > 0) & allowed
    n_horse_raw = int(m_horse.sum())
    if spacing > 1:
        m_horse = D.decimate_grid(m_horse, horse, spacing)
    n_horse = int(m_horse.sum())

    n_fill = int(fill_cov * n_valid)
    flat = np.where(allowed, topo, -np.inf).ravel()
    n_fill = min(n_fill, int(np.isfinite(flat).sum()))
    idx = np.argpartition(flat, -n_fill)[-n_fill:]
    fill = np.zeros(flat.size, bool); fill[idx] = True
    fill = fill.reshape(topo.shape)
    if spacing > 1:
        fill = D.decimate_grid(fill, topo, spacing)
    n_fill_after = int(fill.sum())

    pred = (m_rays | m_horse | fill).astype(np.float32)
    if include_catalogue:
        pred = np.maximum(pred, known.astype(np.float32))

    stats = {
        "recipe": "composite_plus_rays_horse_fill",
        "tip_ray_reach_px": reach, "tip_ray_reach_m": reach*100,
        "horse_gap_px": horse_gap, "horse_splay_px": horse_splay,
        "decimation_spacing_px": spacing, "fill_coverage": fill_cov,
        "fill_detector": "BASE_topo_ridge",
        "include_known_catalogue": include_catalogue,
        "n_tip_ray_px_before_decimation": n_rays_raw,
        "n_tip_ray_px": n_rays,
        "n_horse_px_before_decimation": n_horse_raw,
        "n_horse_px": n_horse,
        "n_fill_px_before_decimation": n_fill,
        "n_fill_px": n_fill_after,
        "n_predicted_px": int((pred>0).sum()),
        "pct_of_valid": round(100.0*float((pred>0).sum())/n_valid,4),
        "max_value": float(pred.max()), "min_value": float(pred.min()),
    }
    return pred, valid, stats


def build_composite(reach: int, spacing: int, fill_cov: float,
                    include_catalogue: bool) -> tuple[np.ndarray, np.ndarray, dict]:
    """Historical tip-ray plus topographic-fill recipe.

    Its earlier two-regime direct-DTI results are from an older, limited local
    protocol and do not estimate the private test or confer current clearance.
    The former chance/lift figures are withdrawn because they used a mismatched
    evaluation-domain denominator. Re-run the current visible-only multi-rule
    holdout before use.
    """
    valid = np.load(DER / "_valid.npy")
    known = np.load(DER / "_known.npy")
    topo = np.load(DER / "BASE_topo_ridge.npy")
    n_valid = int(valid.sum())
    allowed = valid & ~known

    rays = D.extension_rays(known, reach_px=reach)
    m = (rays > 0) & allowed
    n_rays_raw = int(m.sum())
    if spacing > 1:
        m = D.decimate_grid(m, rays, spacing)
    n_rays = int(m.sum())

    n_fill = int(fill_cov * n_valid)
    flat = np.where(allowed, topo, -np.inf).ravel()
    n_fill = min(n_fill, int(np.isfinite(flat).sum()))
    idx = np.argpartition(flat, -n_fill)[-n_fill:]
    fill = np.zeros(flat.size, bool); fill[idx] = True
    fill = fill.reshape(topo.shape)

    pred = (m | fill).astype(np.float32)
    if include_catalogue:
        pred = np.maximum(pred, known.astype(np.float32))

    stats = {
        "recipe": "composite_tip_rays_plus_fill",
        "tip_ray_reach_px": reach, "tip_ray_reach_m": reach * 100,
        "decimation_spacing_px": spacing, "fill_coverage": fill_cov,
        "fill_detector": "BASE_topo_ridge",
        "include_known_catalogue": include_catalogue,
        "n_tip_ray_px_before_decimation": n_rays_raw,
        "n_tip_ray_px": n_rays, "n_fill_px": int(fill.sum()),
        "n_predicted_px": int((pred > 0).sum()),
        "pct_of_valid": round(100.0 * float((pred > 0).sum()) / n_valid, 4),
        "max_value": float(pred.max()), "min_value": float(pred.min()),
        "historical_chance_lift_status": "WITHDRAWN_DOMAIN_MISMATCH"
    }
    return pred, valid, stats



def build_ranked_union(reach: int = 20, spacing: int = 3, budget_cov: float = 0.06,
                       include_catalogue: bool = True,
                       priorities: dict[str, float] | None = None
                       ) -> tuple[np.ndarray, np.ndarray, dict]:
    """Build an experimental priority-weighted union and thin it on a grid.

    Detector weights come from historical local worst-rule DTI summaries; they
    are not hidden-test estimates and do not clear this recipe for upload. Taking
    a pixelwise maximum prevents a pixel from being counted twice, but nearby
    distinct pixels from different sources can still add support. Grid thinning
    selects at most one point per tile; it does not guarantee a minimum distance
    across tile boundaries or universal metric optimality.

    The exact known-catalogue mask is applied only as locally directed by
    organizer guidance. Whether predictions on those masked pixels can contribute
    TP credit to nearby new truth remains unresolved (knowledge/02 Q-1).
    """
    valid = np.load(DER / "_valid.npy")
    known = np.load(DER / "_known.npy")
    n_valid = int(valid.sum())
    allowed = valid & ~known

    if priorities is None:
        priorities = load_priorities()

    score = np.zeros(valid.shape, dtype=np.float32)
    used = {}
    # Catalogue-derived sources are prioritized for historical hypothesis coverage;
    # this ordering is not a measured holdout advantage or submission clearance.
    rays = D.extension_rays(known, reach_px=reach)
    for name, pr in sorted(priorities.items(), key=lambda kv: -kv[1]):
        if name == "extension_rays":
            src = rays
        elif name == "horsetail_splay":
            src = D.horsetail_splay(known, max_gap_px=20, splay_len_px=12)
        else:
            p = DER / f"{name}.npy"
            if not p.exists():
                continue
            src = np.load(p)
        # robust_norm_nonzero, NOT robust_norm: robust_norm silently returns an
        # all-zero array for any field more than 99% zeros, which would erase
        # extension_rays (0.1% nonzero) and HC_hinge (0.98% nonzero) from the
        # union. Measured in scripts/validate_ranked.py; see the
        # normalisation_note in reports/ranked_ab.json.
        m = np.where(allowed, D.robust_norm_nonzero(src) * pr, 0.0)
        np.maximum(score, m, out=score)
        used[name] = {"priority": round(float(pr), 4),
                      "n_px_above_zero": int((m > 0).sum())}
        del src, m

    n_budget = int(budget_cov * n_valid)
    flat = np.where(allowed, score, -np.inf).ravel()
    n_budget = min(n_budget, int(np.isfinite(flat).sum()))
    if n_budget <= 0:
        raise SystemExit("empty budget")
    thr = np.partition(flat, -n_budget)[-n_budget]
    mask = (score >= max(thr, 0.0)) & allowed
    n_before = int(mask.sum())
    if spacing > 1:
        mask = D.decimate_grid(mask, score, spacing)

    pred = mask.astype(np.float32)
    if include_catalogue:
        pred = np.maximum(pred, known.astype(np.float32))

    stats = {
        "recipe": "ranked_union",
        "tip_ray_reach_px": reach, "tip_ray_reach_m": reach * 100,
        "budget_coverage": budget_cov, "n_budget_px": n_budget,
        "n_px_before_global_decimation": n_before,
        "decimation_spacing_px": spacing,
        "global_decimation": True,
        "sources": used,
        "n_predicted_px": int((pred > 0).sum()),
        "pct_of_valid": round(100.0 * float((pred > 0).sum()) / n_valid, 4),
        "n_new_prediction_px": int(mask.sum()),
        "max_value": float(pred.max()), "min_value": float(pred.min()),
        "include_known_catalogue": include_catalogue,
    }
    return pred, valid, stats


def load_priorities() -> dict[str, float]:
    """Exploratory source weights from worst-rule local DTI summaries.

    These historical weights do not clear a candidate for submission. Chance
    ratios are not used here; all shortlisted maps still require comparison on
    current confirmation folds before any upload.
    """
    import json as _json
    pri: dict[str, float] = {"extension_rays": 1.0, "horsetail_splay": 1.0}
    for name in ("holdout_verdict_v3.json", "holdout_verdict.json"):
        p = REP / name
        if not p.exists():
            continue
        try:
            d = _json.loads(p.read_text())
        except Exception:
            continue
        # Use each detector family's best local worst-rule DTI summary, but
        # treat these historical proxy weights as exploratory—not as clearance.
        best: dict[str, float] = {}
        for row in d.get("table", []):
            fam = row.get("family", "")
            score = row.get("worst_rule_mean_dti")
            if score is None or fam in ("prior_submission", "control",
                                        "control_random"):
                continue
            best[fam] = max(best.get(fam, 0.0), float(score))
        if best:
            top = max(best.values())
            for fam, score in best.items():
                pri[fam] = float(min(max(score, 0.0) / max(top, 1e-9), 1.0))
        break
    return pri

def build_r8_ensemble(reach: int = 20, spacing: int = 3,
                      openness_cov: float = 0.02, tpi_cov: float = 0.01,
                      flow_cov: float = 0.02, iso_cov: float = 0.005,
                      reman_cov: float = 0.005, inter_cov: float = 0.01,
                      topo_cov: float = 0.03,
                      include_catalogue: bool = True) -> tuple[np.ndarray, np.ndarray, dict]:
    """Build an exploratory union of R8 layers and the topographic baseline.

    The components represent testable hypotheses: openness/TPI for subtle
    terrain edges, flow accumulation for drainage anomalies, gravity/topography
    coherence, magnetic remanence divergence, intersection density, and a
    topographic ridge baseline. Literature motivates some mechanisms but does
    not validate fault detection, geothermal targeting, or score contribution.
    The 2026-09-30 per-fold recipe comparison is recorded separately in
    reports/holdout_candidate_r8_2026-09-30.json.

    Grid decimation reduces local redundancy; it does not guarantee a universal
    minimum separation or positive marginal DTI. Catalogue pixels are included
    only per organizer guidance that the exact known-fault pixels are masked;
    their effect on nearby truth credit remains documented as an assumption.
    """
    valid = np.load(DER / "_valid.npy")
    known = np.load(DER / "_known.npy")
    n_valid = int(valid.sum())
    allowed = valid & ~known

    def topk_from_score(score: np.ndarray, cov: float) -> np.ndarray:
        if cov <= 0 or score is None:
            return np.zeros(score.shape, dtype=bool)
        n = int(cov * n_valid)
        flat = np.where(allowed, score, -np.inf).ravel()
        n = min(n, int(np.isfinite(flat).sum()))
        if n <= 0:
            return np.zeros(score.shape, dtype=bool)
        idx = np.argpartition(flat, -n)[-n:]
        mask = np.zeros(flat.size, dtype=bool)
        mask[idx] = True
        return mask.reshape(score.shape)

    rays = D.extension_rays(known, reach_px=reach)
    m_rays = (rays > 0) & allowed
    n_rays_raw = int(m_rays.sum())
    if spacing > 1:
        m_rays = D.decimate_grid(m_rays, rays, spacing)
    horse = D.horsetail_splay(known, max_gap_px=20, splay_len_px=12)
    m_horse = (horse > 0) & allowed
    n_horse_raw = int(m_horse.sum())
    if spacing > 1:
        m_horse = D.decimate_grid(m_horse, horse, spacing)

    def load_det(name):
        p = DER / f"{name}.npy"
        return np.load(p) if p.exists() else None

    openness = load_det("R8_openness")
    tpi = load_det("R8_tpi")
    flow = load_det("R8_flow")
    iso = load_det("R8_isocoherence")
    reman = load_det("R8_remanence")
    inter = load_det("R8_intersections")
    topo = load_det("BASE_topo_ridge")

    masks = [m_rays, m_horse]
    cov_map = {
        "R8_openness": (openness, openness_cov),
        "R8_tpi": (tpi, tpi_cov),
        "R8_flow": (flow, flow_cov),
        "R8_isocoherence": (iso, iso_cov),
        "R8_remanence": (reman, reman_cov),
        "R8_intersections": (inter, inter_cov),
        "BASE_topo_ridge": (topo, topo_cov),
    }
    details = {}
    for det_name, (score, cov) in cov_map.items():
        if score is None or cov <= 0:
            continue
        m = topk_from_score(score, cov)
        if spacing > 1:
            m = D.decimate_grid(m, score, spacing)
        masks.append(m)
        details[det_name] = {"coverage_target": cov, "n_px_after_decimation": int(m.sum())}

    union = np.zeros(valid.shape, dtype=bool)
    for m in masks:
        union |= m
    pred = union.astype(np.float32)
    if include_catalogue:
        pred = np.maximum(pred, known.astype(np.float32))
    stats = {
        "recipe": "r8_ensemble",
        "tip_ray_reach_px": reach, "tip_ray_reach_m": reach*100,
        "decimation_spacing_px": spacing,
        "coverages": {k: v["coverage_target"] for k, v in details.items()},
        "n_px_per_detector": details,
        "n_tip_ray_px_before_decimation": n_rays_raw,
        "n_tip_ray_px": int(m_rays.sum()),
        "n_horse_px_before_decimation": n_horse_raw,
        "n_horse_px": int(m_horse.sum()),
        "n_union_new_px": int(union.sum()),
        "n_predicted_px": int((pred > 0).sum()),
        "pct_of_valid": round(100.0 * float((pred > 0).sum()) / n_valid, 4),
        "max_value": float(pred.max()), "min_value": float(pred.min()),
        "include_known_catalogue": include_catalogue,
    }
    return pred, valid, stats


def build(detector: str, coverage: float, spacing: int,
          include_catalogue: bool) -> tuple[np.ndarray, np.ndarray, dict]:
    if not np.isfinite(coverage) or not 0.0 < coverage <= 1.0:
        raise ValueError(f"coverage must be in (0, 1]; got {coverage}")
    if spacing < 1:
        raise ValueError(f"spacing must be a positive integer; got {spacing}")

    valid = np.load(DER / "_valid.npy").astype(bool)
    known = np.load(DER / "_known.npy").astype(bool)
    if valid.shape != EXPECTED_SHAPE or known.shape != EXPECTED_SHAPE:
        raise ValueError("cached valid/known masks do not match the official grid")
    n_valid = int(valid.sum())

    score = np.load(DER / f"{detector}.npy")
    if score.shape != EXPECTED_SHAPE:
        raise ValueError(f"detector {detector!r} has wrong shape: {score.shape}")
    allowed = valid & ~known           # catalogue pixels are masked at scoring
    n = max(1, int(coverage * n_valid))

    flat = np.where(allowed & np.isfinite(score), score, -np.inf).ravel()
    n = min(n, int(np.isfinite(flat).sum()))
    if n == 0:
        raise ValueError(f"detector {detector!r} has no finite eligible pixels")
    idx = np.argpartition(flat, -n)[-n:]
    mask = np.zeros(flat.size, dtype=bool)
    mask[idx] = True
    mask = mask.reshape(score.shape)

    if spacing > 1:
        _, ori = D.ridge_strength(np.load(DER / "BASE_topo_ridge.npy"), 1.5)
        mask = D.decimate_along_strike(mask, ori, spacing)

    # Binary, because DTI is linear in each p(x) for a fixed argmax and
    # DTI(c*p) strictly increases in c (metric audit A6).
    pred = mask.astype(np.float32)

    if include_catalogue:
        # Weakly dominant: the organizers state known-fault pixels are masked
        # and that "it should not matter whether these known faults are
        # included with predictions or not" (forum 11516 post 2). If masked
        # pixels are dropped entirely this is exactly neutral; if they still
        # supply TP_w credit to a new-fault pixel within 300 m it is a free
        # gain. There is no branch in which it costs anything.
        pred = np.maximum(pred, known.astype(np.float32))

    stats = {
        "detector": detector, "coverage_target": coverage,
        "line_spacing_px": spacing, "include_known_catalogue": include_catalogue,
        "n_predicted_px": int((pred > 0).sum()),
        "pct_of_valid": round(100.0 * float((pred > 0).sum()) / n_valid, 4),
        "n_new_prediction_px": int(mask.sum()),
        "max_value": float(pred.max()), "min_value": float(pred.min()),
    }
    return pred, valid, stats


def build_topo_ref(coverage: float = 0.05, spacing: int = 3,
                   include_catalogue: bool = True
                   ) -> tuple[np.ndarray, np.ndarray, dict]:
    """Build the CURRENT LOCAL HOLDOUT REFERENCE recipe on the full grid.

    This is the exact `topo_05_sp3` configuration that the paired R9
    validation (reports/holdout_r9_2026-09-30.json) re-confirmed as the local
    best under the predeclared worst-rule rule, and that the R8 comparison
    (reports/holdout_candidate_r8_2026-09-30.json) used as its comparator:

      * BASE_topo_ridge score (input-derived: detrended-elevation slope ridge,
        cached in data/derived; contains no catalogue information),
      * top `coverage` of the valid footprint, selected only on
        valid & ~known & finite pixels (known pixels are masked at scoring),
      * `gems.detectors.decimate_grid` at `spacing` px -- the same decimation
        operator used in the holdout (NOT decimate_along_strike),
      * binary output, because DTI(c*p) strictly increases in c (audit A6).

    Selection-domain note: the holdout selects each fold's top-k inside that
    fold's eval_mask; the full-grid artifact selects on the whole valid
    footprint with known pixels excluded. This is the submission-side
    analogue, not a claim of per-fold identity.
    """
    if not np.isfinite(coverage) or not 0.0 < coverage <= 1.0:
        raise ValueError(f"coverage must be in (0, 1]; got {coverage}")
    if spacing < 1:
        raise ValueError(f"spacing must be a positive integer; got {spacing}")

    valid = np.load(DER / "_valid.npy").astype(bool)
    known = np.load(DER / "_known.npy").astype(bool)
    if valid.shape != EXPECTED_SHAPE or known.shape != EXPECTED_SHAPE:
        raise ValueError("cached valid/known masks do not match the official grid")
    n_valid = int(valid.sum())

    score = np.load(DER / "BASE_topo_ridge.npy")
    if score.shape != EXPECTED_SHAPE:
        raise ValueError(f"BASE_topo_ridge has wrong shape: {score.shape}")
    allowed = valid & ~known & np.isfinite(score)
    n = int(coverage * n_valid)
    flat = np.where(allowed, score, -np.inf).ravel()
    if n <= 0 or not np.isfinite(flat).any():
        raise ValueError("no eligible pixels for topo_ref")
    idx = np.argpartition(flat, -n)[-n:]
    mask = np.zeros(flat.size, dtype=bool)
    mask[idx] = True
    mask = mask.reshape(score.shape)
    n_before = int(mask.sum())
    if spacing > 1:
        mask = D.decimate_grid(mask, score, spacing)

    pred = mask.astype(np.float32)
    if include_catalogue:
        # Score-neutral per forum 11516 post 2 ("it should not matter whether
        # these known faults are included with predictions or not"); retained
        # so Phase-2 expert reviewers see complete fault systems in context.
        pred = np.maximum(pred, known.astype(np.float32))

    stats = {
        "recipe": "topo_ref",
        "detector": "BASE_topo_ridge", "coverage_target": coverage,
        "line_spacing_px": spacing, "decimation": "decimate_grid",
        "include_known_catalogue": include_catalogue,
        "n_selected_before_decimation": n_before,
        "n_new_prediction_px": int(mask.sum()),
        "n_predicted_px": int((pred > 0).sum()),
        "pct_of_valid": round(100.0 * float((pred > 0).sum()) / n_valid, 4),
        "max_value": float(pred.max()), "min_value": float(pred.min()),
    }
    return pred, valid, stats


def build_greedy_r11(include_catalogue: bool = True
                     ) -> tuple[np.ndarray, np.ndarray, dict]:
    """R11-4 greedy marginal-precision assembly on the full grid.

    Recipe is READ from reports/holdout_r11_2026-09-30.json (never hand-typed):
    start from topo_05_sp3, then for each accepted (map, coverage) step select
    the top `coverage * n_valid` pixels of that map among valid & ~known pixels
    lying > 300 m (3 px Chebyshev) from the current assembly, decimate_grid at
    3 px, and union. Mirrors scripts/validate_r11_holdout.py block() / far_from().
    """
    from scipy import ndimage as ndi
    rep = json.loads((ROOT / "reports" / "holdout_r11_2026-09-30.json").read_text())
    verdict = next(iter(rep["verdict_predeclared"].values()))
    if rep["selected_on_tune"] != "greedy_r11" or not verdict.startswith("WINS"):
        raise SystemExit(f"greedy_r11 is not the cleared R11 winner: {verdict}")
    recipe = [(str(m), float(c)) for m, c in rep["greedy_recipe"]]
    exclude = int(rep["exclude_px"])
    pred_ref, valid, ref_stats = build_topo_ref(0.05, 3, include_catalogue=False)
    known = np.load(DER / "_known.npy").astype(bool)
    n_valid = int(valid.sum())
    mask = pred_ref > 0
    steps = []
    for stem, cov in recipe:
        score = np.load(DER / f"{stem}.npy").astype(np.float32)
        far = ~ndi.binary_dilation(mask, structure=np.ones((2 * exclude + 1,) * 2, bool))
        allowed = valid & ~known & np.isfinite(score) & far
        n = int(cov * n_valid)
        flat = np.where(allowed, score, -np.inf).ravel()
        order = np.argsort(-flat, kind="stable")[:n]
        order = order[np.isfinite(flat[order])]
        blk = np.zeros(flat.size, dtype=bool)
        blk[order] = True
        blk = D.decimate_grid(blk.reshape(score.shape), score, 3) & allowed
        steps.append({"map": stem, "coverage": cov, "n_added_px": int((blk & ~mask).sum())})
        mask |= blk
        del score, flat, far, allowed
    pred = mask.astype(np.float32)
    if include_catalogue:
        pred = np.maximum(pred, known.astype(np.float32))
    stats = {"recipe": "greedy_r11", "base": ref_stats, "greedy_steps": steps,
             "exclude_px": exclude, "include_known_catalogue": include_catalogue,
             "n_new_prediction_px": int(mask.sum()),
             "n_predicted_px": int((pred > 0).sum()),
             "pct_of_valid": round(100.0 * float((pred > 0).sum()) / n_valid, 4),
             "max_value": float(pred.max()), "min_value": float(pred.min())}
    return pred, valid, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", default="composite",
                    choices=["composite", "composite_plus", "best", "r6", "r8",
                             "ranked", "topo_ref", "greedy_r11"])
    ap.add_argument("--budget", type=float, default=0.06,
                    help="ranked recipe: fraction of the valid footprint to "
                         "predict, before global decimation")
    ap.add_argument("--reach", type=int, default=10)
    ap.add_argument("--fill", type=float, default=0.05)
    ap.add_argument("--detector")
    ap.add_argument("--coverage", type=float)
    ap.add_argument("--spacing", type=int)
    ap.add_argument("--name")
    ap.add_argument("--no-catalogue", action="store_true")
    a = ap.parse_args()
    if a.spacing is not None and a.spacing < 1:
        ap.error("--spacing must be a positive integer")
    if a.reach < 0:
        ap.error("--reach must be non-negative")
    if not 0.0 <= a.fill <= 1.0:
        ap.error("--fill must be in [0, 1]")
    if not 0.0 <= a.budget <= 1.0:
        ap.error("--budget must be in [0, 1]")

    prov: dict = {}
    clearance_override: dict | None = None
    if a.recipe == "greedy_r11":
        print("recipe: greedy_r11 (R11-4, read from reports/holdout_r11_2026-09-30.json)")
        pred, valid, stats = build_greedy_r11(include_catalogue=not a.no_catalogue)
        det = "greedy-r11"
        rep = json.loads((ROOT / "reports" / "holdout_r11_2026-09-30.json").read_text())
        cs = rep["confirmation_summary"]
        steps = "+".join(f"{s['map']}@{s['coverage']*100:g}%" for s in stats["greedy_steps"])
        note_bits = (f"R11-4 greedy marginal-precision: topo top-5% sp3 + {steps} "
                     f"(each >300 m from prior), binary, catalogue included")
        prov = {"selected_by": ("predeclared R11 holdout WIN: "
                                + next(iter(rep["verdict_predeclared"].values()))),
                "holdout_report": "reports/holdout_r11_2026-09-30.json",
                "confirm_worst_rule_mean": {k: v["dti_worst_rule_mean"] for k, v in cs.items()}}
        clearance_override = {
            "status": "CLEARED_LOCAL_HOLDOUT_WIN_NOT_PRIVATE_TEST_CLAIM",
            "reason": ("greedy_r11 beat the in-run topo_05_sp3 reference on tune and "
                       "confirmation worst-rule-mean DTI, won 6/6 confirmation rule "
                       "means and 18/18 paired folds; gain exceeds 10x rebuild drift "
                       "(I-15). Catalogue hide-and-recover proxy only."),
            "holdout_report": "reports/holdout_r11_2026-09-30.json",
            "private_test_claim": False, "upload_allowed": True}
    elif a.recipe == "topo_ref":
        cov = 0.05 if a.coverage is None else a.coverage
        if not np.isfinite(cov) or not 0.0 < cov <= 1.0:
            ap.error("--coverage must be in (0, 1]")
        sp = a.spacing or 3
        print(f"recipe: topo_ref coverage={cov} spacing={sp} (decimate_grid)")
        pred, valid, stats = build_topo_ref(coverage=cov, spacing=sp,
                                            include_catalogue=not a.no_catalogue)
        det = "topo-ref"
        note_bits = (f"BASE_topo_ridge top-{cov*100:g}% of valid, decimate_grid "
                     f"{sp}px (300 m), binary, catalogue included (masked at "
                     f"scoring)")
        prov = {
            "selected_by": ("re-confirmed local best under the predeclared "
                            "paired worst-rule decision rule; see "
                            "reports/holdout_r9_2026-09-30.json (protocol "
                            "regression check PASS) and "
                            "reports/holdout_candidate_r8_2026-09-30.json"),
            "detectors": ["BASE_topo_ridge"],
            "objective": ("ship the exact local holdout reference configuration "
                          "as the primary review artifact; no hidden-test "
                          "performance claim"),
        }
        clearance_override = {
            "status": "BEST_LOCAL_REFERENCE_NOT_PRIVATE_TEST_CLAIM",
            "reason": ("This artifact implements topo_05_sp3, the current local "
                       "holdout best (confirmation worst-rule mean DTI 0.08687, "
                       "mean 0.09763). That is a catalogue hide-and-recover "
                       "proxy, NOT a private-test estimate; remote acceptance "
                       "is unverified. No R9 variant beat it, so it remains the "
                       "best available candidate under the charter gate."),
            "holdout_report": "reports/holdout_r9_2026-09-30.json",
            "private_test_claim": False,
            "upload_allowed": True,
        }
    elif a.detector:
        cov = 0.05 if a.coverage is None else a.coverage
        if not np.isfinite(cov) or not 0.0 < cov <= 1.0:
            ap.error("--coverage must be in (0, 1]")
        det, sp = a.detector, a.spacing or 3
        print(f"recipe: detector={det} coverage={cov} spacing={sp}")
        pred, valid, stats = build(det, cov, sp, not a.no_catalogue)
        note_bits = (f"{det} top-{cov*100:g}% strike-decimated every {sp}px")
    elif a.recipe == "r6":
        sp = a.spacing or 3
        reach = a.reach if a.reach != 10 else 20
        print(f"recipe: R6 ensemble reach={reach} spacing={sp}")
        pred, valid, stats = build_r6_ensemble(reach=reach, spacing=sp,
                                               topo_cov=0.03, grav_cov=0.01,
                                               transt_cov=0.01, tdr_cov=0.01,
                                               shore_cov=0.005, cond_cov=0.005,
                                               include_catalogue=not a.no_catalogue)
        det = "r6-ensemble"
        note_bits = (f"Exploratory R6 union: tip rays {reach*100}m + horsetail + topo/gravity/strain/magnetic/conductivity layers; one candidate selected per {sp}x{sp}-pixel grid tile")
        prov = {"selected_by": "historical local detector measurements; current full-union clearance not established",
                "detectors": ["extension_rays", "horsetail_splay", "BASE_topo_ridge", "R6_gravterm", "R6_transt", "HB_tdr_rtp", "R6_shore", "R6_condbase"],
                "objective": "explore tip geometry, terrain, gravity, magnetic, and conductivity hypotheses; no hidden-test performance claim"}
    elif a.recipe == "r8":
        sp = a.spacing or 3
        reach = a.reach if a.reach != 10 else 20
        print(f"recipe: R8 ensemble reach={reach} spacing={sp}")
        pred, valid, stats = build_r8_ensemble(reach=reach, spacing=sp,
                                               openness_cov=0.02, tpi_cov=0.01,
                                               flow_cov=0.02, iso_cov=0.005,
                                               reman_cov=0.005, inter_cov=0.01,
                                               topo_cov=0.03,
                                               include_catalogue=not a.no_catalogue)
        det = "r8-ensemble"
        note_bits = (f"Exploratory R8 union: {reach*100}m tip rays, horsetail, openness 2%, TPI 1%, flow 2%, isocoherence 0.5%, remanence 0.5%, intersections 1%, topo 3%; one candidate selected per {sp}x{sp}-pixel grid tile; not submission-cleared")
        prov = {"selected_by": "exploratory synthesis of detector hypotheses; the ensemble was not validated as a whole when this artifact was generated",
                "detectors": ["extension_rays", "horsetail_splay", "R8_openness", "R8_tpi", "R8_flow", "R8_isocoherence", "R8_remanence", "R8_intersections", "BASE_topo_ridge"],
                "objective": "test a broad union of mapped-fault geometry, terrain, hydrology, gravity, and magnetic hypotheses; not a hidden-test performance claim",
                "geothermal_basis": "the literature motivates these as permeability and concealed-structure hypotheses; this does not validate their spatial coverage or scoring contribution in this competition"}
    elif a.recipe == "ranked":
        sp = a.spacing or 3
        reach = a.reach if a.reach != 10 else 20
        print(f"recipe: ranked-union budget={a.budget} spacing={sp} reach={reach}")
        pred, valid, stats = build_ranked_union(reach=reach, spacing=sp,
                                                budget_cov=a.budget,
                                                include_catalogue=not a.no_catalogue)
        det = "ranked-union"
        pri = load_priorities()
        top = sorted(pri.items(), key=lambda kv: -kv[1])[:6]
        note_bits = (f"global priority-union of "
                     f"{', '.join(f'{k} {v:.2f}x' for k, v in top)}; "
                     f"budget {a.budget*100:g}% then global {sp}x{sp}-pixel "
                     f"grid thinning")
        prov = {"selected_by": "exploratory weights from historical local worst-rule DTI summaries; not submission clearance",
                "objective": "test a global weighted detector union; grid thinning is not a guaranteed minimum separation or DTI optimum",
                "priorities": {k: round(v, 4) for k, v in top}}
    elif a.recipe == "composite_plus":
        sp = a.spacing or 3
        reach = a.reach if a.reach != 10 else 20
        print(f"recipe: composite_plus reach={reach} spacing={sp} fill={a.fill}")
        pred, valid, stats = build_composite_plus(reach=reach, spacing=sp, fill_cov=a.fill,
                                                  horse_gap=20, horse_splay=12,
                                                  include_catalogue=not a.no_catalogue)
        det = "composite-plus"
        note_bits = (f"tip rays {reach*100}m + horsetail + topo-ridge fill {a.fill*100:g}%; grid-thinning parameter {sp}px; exploratory and not submission-cleared")
        prov = {"selected_by": "historical recipe; not cleared under the latest direct-DTI holdout",
                "objective": "exploratory tip geometry plus topographic fill; former chance/lift figures are withdrawn due domain mismatch"}
    elif a.recipe == "composite":
        sp = a.spacing or 3
        print(f"recipe: composite reach={a.reach} spacing={sp} fill={a.fill}")
        pred, valid, stats = build_composite(a.reach, sp, a.fill,
                                             not a.no_catalogue)
        det = "composite"
        note_bits = (f"historical tip-extension rays reach {a.reach*100}m; grid-thinning parameter {sp}px; "
                     f"topo-ridge fill {a.fill*100:g}%; not submission-cleared")
        prov = {"selected_by": "historical scripts/validate_composite.py local comparison",
                "objective": "previous two-regime proxy results are not private-test performance and do not confer current submission clearance"}
    else:
        det, cov, sp, prov = pick_best_recipe()
        print(f"recipe: detector={det} coverage={cov} spacing={sp}")
        pred, valid, stats = build(det, cov, sp, not a.no_catalogue)
        note_bits = f"{det} top-{cov*100:g}% spacing {sp}px"

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    name = a.name or f"13gems-{det.lower().replace('_','-')}-{stamp}"
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", name)
            or name in {".", ".."}
            or name.lower().endswith((".tif", ".tiff", ".zip"))):
        raise ValueError(
            "--name must be a 1-128 character filename stem using only "
            "letters, digits, dot, underscore, or hyphen; omit extensions"
        )
    OUT.mkdir(parents=True, exist_ok=True)
    reserved = [OUT / f"{name}.tif", OUT / f"{name}_allfinite.tif",
                OUT / f"{name}.zip", OUT / f"{name}.json"]
    collisions = [str(path) for path in reserved if path.exists()]
    if collisions:
        raise FileExistsError(
            "Submission names are immutable and must be unique; already exists: "
            + ", ".join(collisions)
        )

    identity = check_existing_prediction_identity(pred, valid)

    # --- Encoding policy (flipped 2026-09-30, session 6; evidence:
    # reports/form_responses.json, reports/primary_flip_2026-09-30.json,
    # irregularity I-8) ---
    # The team uploaded the NaN-outside primary of 13gems-r11-greedy-mp.tif and
    # the form rejected it with "Predicted values must be in range [0, 1]".
    # Historically NaN-outside files WERE accepted (the pindrop trio the team
    # recorded by sha256 prefix: f347b70daa, 37f9d5b855, 4e03fc9705), so the
    # platform validator changed or is inconsistent — either way the platform is
    # the arbiter. The all-finite encoding (0.0 outside the survey footprint, no
    # NoData tag) passes BOTH a masked read and a naive raw range test, and for
    # a binary {0,1} map zero-fill outside the footprint is score-neutral: 0 is
    # a non-prediction, so TP_w/FP_w are unchanged under any scorer. It is
    # therefore written as the PRIMARY {name}.tif and is what latest.* and the
    # .zip carry. The strict null/NaN-outside variant (what the problem page
    # text describes) is still produced, secondary, for the record:
    # {name}_nanoutside.tif. Record every form response in
    # reports/form_responses.json.
    tif = write_submission(OUT / f"{name}.tif", pred, valid, outside_value=0.0)
    strict = write_submission(OUT / f"{name}_nanoutside.tif", pred, valid,
                              outside_value=None)

    reports = {}
    ok = True
    for label, path, allow_nan, require_nodata in (
        ("all_finite_primary", tif, False, False),
        ("nan_outside_strict", strict, True, True),
    ):
        r = validate_submission(
            path, allow_nan=allow_nan, valid_mask=valid,
            require_nodata_outside=require_nodata,
        )
        official_format_conformant = bool(
            r.ok and r.stats.get("outside_nodata_ok", True)
        )
        reports[label] = {
            "ok": r.ok,
            "official_format_conformant": official_format_conformant,
            "errors": r.errors,
            "warnings": r.warnings,
            "stats": r.stats,
        }
        print(f"\n[{label}] " + r.render())
        ok &= r.ok
        if label == "nan_outside_strict":
            ok &= official_format_conformant
    if not ok:
        raise SystemExit("OFFICIAL-FORMAT VALIDATION FAILED - nothing released")

    # The .zip must carry the PRIMARY (all-finite) GeoTIFF: the form accepts a
    # zip containing a single GeoTIFF, and wrapping the rejected NaN encoding
    # here is what produced a wasted upload on 2026-09-30.
    with zipfile.ZipFile(OUT / f"{name}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(tif, arcname=f"{name}.tif")

    note = (note_bits
            + ("" if clearance_override else
               (", binary 0/1"
                + (", catalogue included (masked at scoring)"
                   if not a.no_catalogue else "")))
            + (("; R11 holdout WIN vs topo_05_sp3 (18/18 folds), NOT a private-test claim"
                if clearance_override["status"].startswith("CLEARED")
                else "; local holdout reference recipe, NOT a private-test claim")
               if clearance_override else
               "; generated for review only, NOT CLEARED by format/identity checks"))

    prov_out = {
        "name": name, "generated_utc": stamp, "note_for_submission_form": note,
        "recipe_selection": prov or {"mode": "manual override"},
        "map_stats": stats, "validation": reports,
        "artifact_status": ((clearance_override["status"]
                             if clearance_override["status"].startswith("CLEARED")
                             else "BEST_LOCAL_REFERENCE_LOCAL_PROXY_ONLY")
                            if clearance_override else "REVIEW_ONLY_NOT_CLEARED"),
        "submission_clearance": clearance_override or {
            "status": "NOT_CLEARED",
            "reason": "Format validation does not establish a DTI gain. Re-run the current paired direct-DTI multi-rule holdout against the latest local best before considering an upload.",
            "private_test_claim": False,
            "upload_allowed": False,
        },
        "prediction_identity": identity,
        "metric_facts": {
            "DTI_is_distance_weighted_F2": True,
            "marginal_precision_needed_to_help": "0.2 x current DTI",
            "binary_is_optimal": "DTI(c*p) strictly increases in c",
        },
        "official_format_source":
            "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
    }
    (OUT / f"{name}.json").write_text(json.dumps(prov_out, indent=2))

    # --- simulated platform checks (diagnostic for the historical remote
    # "Predicted values must be in range [0, 1]" rejection; NOT proof of
    # remote acceptance) -----------------------------------------------
    import rasterio as _rio
    with _rio.open(tif) as src:
        raw_fin = src.read(1)
    with _rio.open(strict) as src:
        raw_nan = src.read(1)
        masked = src.read(1, masked=True)
        nodata_tag = None if src.nodata is None else str(src.nodata)
    sim = {
        "all_finite_primary": {
            "n_nan_raw": int(np.isnan(raw_fin).sum()),
            "raw_all_in_[0,1]_naive": bool(np.all((raw_fin >= 0) & (raw_fin <= 1))),
            "nodata_tag": None,
            "note": ("PRIMARY upload encoding: passes a naive raw range check "
                     "AND a masked read; outside-footprint cells are exactly 0.0, "
                     "which is score-neutral for a binary map. Form-verified as "
                     "the accepted encoding family on 2026-09-30 (see "
                     "reports/form_responses.json)."),
        },
        "nan_outside_variant": {
            "nodata_tag": nodata_tag,
            "n_nan_raw": int(np.isnan(raw_nan).sum()),
            "n_nan_inside_footprint": int((np.isnan(raw_nan) & valid).sum()),
            "raw_all_in_[0,1]_naive": bool(np.all((raw_nan >= 0) & (raw_nan <= 1))),
            "raw_finite_minmax": [float(np.nanmin(raw_nan)), float(np.nanmax(raw_nan))],
            "masked_min": float(masked.min()) if masked.count() else None,
            "masked_max": float(masked.max()) if masked.count() else None,
            "note": ("REJECTED by the form on 2026-09-30 with 'Predicted values "
                     "must be in range [0, 1]' (team upload of "
                     "13gems-r11-greedy-mp.tif). Kept secondary for the record "
                     f"as {name}_nanoutside.tif; do NOT upload first."),
        },
    }
    prov_out["platform_check_simulation"] = sim
    prov_out["primary_upload"] = {
        "encoding": "all_finite_zero_fill",
        "file": f"{name}.tif",
        "zip": f"{name}.zip",
        "zip_contains": f"{name}.tif",
        "secondary_record_only": {"encoding": "nan_outside_strict",
                                  "file": f"{name}_nanoutside.tif"},
        "policy_source": ("reports/form_responses.json; reports/primary_flip_2026-09-30.json; "
                          "knowledge/02_irregularities.md I-8; user-reported form "
                          "rejection of the NaN-outside encoding, 2026-09-30"),
    }
    (OUT / f"{name}.json").write_text(json.dumps(prov_out, indent=2))

    # Primary = all-finite upload-safe encoding; the strict NaN-outside variant
    # is retained under an explicit name for the record and for an A/B response
    # if the platform ever rejects the finite encoding instead.
    shutil.copyfile(OUT / f"{name}.tif", OUT / f"latest.tif")
    shutil.copyfile(OUT / f"{name}.tif", OUT / f"latest_allfinite.tif")  # compat alias
    shutil.copyfile(OUT / f"{name}_nanoutside.tif", OUT / f"latest_nan.tif")
    with zipfile.ZipFile(OUT / f"latest.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(OUT / f"{name}.tif", arcname=f"{name}.tif")
    with zipfile.ZipFile(OUT / f"latest_nan.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(OUT / f"{name}_nanoutside.tif", arcname=f"{name}_nanoutside.tif")
    shutil.copyfile(OUT / f"{name}.json", OUT / f"latest.json")

    (REP / "latest_submission.json").write_text(json.dumps(prov_out, indent=2))
    print(f"\nWROTE {OUT}/{name}.tif (all-finite PRIMARY; + _nanoutside strict, .zip, .json, latest.*)")
    print(f"NOTE  {note}")


if __name__ == "__main__":
    main()
