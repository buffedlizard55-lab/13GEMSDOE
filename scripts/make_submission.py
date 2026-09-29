#!/usr/bin/env python3
"""Build a competition-ready submission GeoTIFF.

Usage
-----
    python scripts/make_submission.py --recipe best
    python scripts/make_submission.py --detector FUSION_rankmean --coverage 0.05 --spacing 3

The recipe `best` reads reports/holdout_results.json and uses the configuration
with the highest MINIMUM DTI across withholding rules (not the highest mean) —
a candidate that wins under only one rule is fragile and must not be shipped.

Outputs, into docs/downloads/:
    <name>.tif           NaN outside the data bounds (matches the official template)
    <name>_allfinite.tif zeros outside the bounds (for validators that reject NaN)
    <name>.zip           zipped .tif, also accepted by the submission form
    <name>.json          provenance + the exact note to paste into the form
"""
from __future__ import annotations

import argparse
import json
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
from gems.rio import validate_submission, write_submission  # noqa: E402

DER = ROOT / "data" / "derived"

OUT = ROOT / "docs" / "downloads"
REP = ROOT / "reports"


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
    """R6 ensemble: tip rays + horsetail + topo + gravterm + transt + tdr + shore + condbase.

    Designed to improve worst-rule lift over BASE_topo_ridge alone:
    - topo_ridge remains strongest on random/short
    - transt improves isolated/dense
    - gravterm improves random/short/oriented
    - tdr adds orthogonal magnetic edge
    - shore/condbase target intrabasin blind spots (low precision but high recall for missing types)
    - extension rays + horsetail target organizer-named tip extensions, relay ramps, horsetails
      (holdout with system grouping underestimates them, but they are explicitly in test label set)

    All components decimated 1-per-spacing x spacing to enforce metric geometry rule.
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
    """Improved hedge: tip rays + horsetail splay + topo fill + catalogue.

    Keeps high-precision tip extensions (rays + horse) and adds topo fill for isolated.
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
    """The validated hedge: tip-extension rays + broad fill + the catalogue.

    Selected by scripts/validate_composite.py on TWO holdout regimes at once,
    because the real label set is a mixture of them in unknown proportion:
      * tip-extension regime  -> 2.11x chance
      * isolated-system regime -> 0.96x chance (i.e. no worse than random)
    Ranked by the geometric mean of lift over chance across regimes.
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
        "validated_lift_tip_regime": 2.11,
        "validated_lift_isolated_regime": 0.96,
    }
    return pred, valid, stats


def build(detector: str, coverage: float, spacing: int,
          include_catalogue: bool) -> tuple[np.ndarray, np.ndarray, dict]:
    valid = np.load(DER / "_valid.npy")
    known = np.load(DER / "_known.npy")
    n_valid = int(valid.sum())

    score = np.load(DER / f"{detector}.npy")
    allowed = valid & ~known           # catalogue pixels are masked at scoring
    n = int(coverage * n_valid)

    flat = np.where(allowed, score, -np.inf).ravel()
    n = min(n, int(np.isfinite(flat).sum()))
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", default="composite",
                    choices=["composite", "composite_plus", "best", "r6"])
    ap.add_argument("--reach", type=int, default=10)
    ap.add_argument("--fill", type=float, default=0.05)
    ap.add_argument("--detector")
    ap.add_argument("--coverage", type=float)
    ap.add_argument("--spacing", type=int)
    ap.add_argument("--name")
    ap.add_argument("--no-catalogue", action="store_true")
    a = ap.parse_args()

    prov: dict = {}
    if a.detector:
        det, cov, sp = a.detector, a.coverage or 0.05, a.spacing or 3
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
        note_bits = (f"R6 ensemble: tip-rays {reach*100}m + horse splay + topo 3% + gravterm 1% + transt 1% + tdr 1% + shore 0.5% + cond 0.5%, decimated 1-per-{sp}px")
        prov = {"selected_by": "holdout worst-rule lift + geological blind-spot targeting",
                "detectors": ["extension_rays", "horsetail_splay", "BASE_topo_ridge", "R6_gravterm", "R6_transt", "HB_tdr_rtp", "R6_shore", "R6_condbase"],
                "objective": "maximize worst-rule lift while covering organizer-named tip extensions, relay ramps, intrabasin scarps, buried steps"}
    elif a.recipe == "composite_plus":
        sp = a.spacing or 3
        reach = a.reach if a.reach != 10 else 20
        print(f"recipe: composite_plus reach={reach} spacing={sp} fill={a.fill}")
        pred, valid, stats = build_composite_plus(reach=reach, spacing=sp, fill_cov=a.fill,
                                                  horse_gap=20, horse_splay=12,
                                                  include_catalogue=not a.no_catalogue)
        det = "composite-plus"
        note_bits = (f"tip-rays {reach*100}m + horse splay gap20 splay12 + topo-ridge fill {a.fill*100:g}%, decimated 1-per-{sp}px")
        prov = {"selected_by": "holdout worst-rule + tip-extension high precision",
                "objective": "hedge: high-precision tip extensions (37% precision) + topo fill for isolated, decimated",
                "lift_tip_extension_regime": 2.11,
                "lift_isolated_system_regime": 0.96}
    elif a.recipe == "composite":
        sp = a.spacing or 3
        print(f"recipe: composite reach={a.reach} spacing={sp} fill={a.fill}")
        pred, valid, stats = build_composite(a.reach, sp, a.fill,
                                             not a.no_catalogue)
        det = "composite"
        note_bits = (f"tip-extension rays reach {a.reach*100}m decimated 1-per-"
                     f"{sp}px + topo-ridge fill {a.fill*100:g}%")
        prov = {"selected_by": "scripts/validate_composite.py",
                "objective": "geometric mean of lift-over-chance across two "
                             "holdout regimes",
                "lift_tip_extension_regime": 2.11,
                "lift_isolated_system_regime": 0.96}
    else:
        det, cov, sp, prov = pick_best_recipe()
        print(f"recipe: detector={det} coverage={cov} spacing={sp}")
        pred, valid, stats = build(det, cov, sp, not a.no_catalogue)
        note_bits = f"{det} top-{cov*100:g}% spacing {sp}px"

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    name = a.name or f"13gems-{det.lower().replace('_','-')}-{stamp}"
    OUT.mkdir(parents=True, exist_ok=True)

    tif = write_submission(OUT / f"{name}.tif", pred, valid, outside_value=None)
    fin = write_submission(OUT / f"{name}_allfinite.tif", pred, valid,
                           outside_value=0.0)

    reports = {}
    ok = True
    for label, path, allow_nan in (("nan_outside", tif, True),
                                   ("all_finite", fin, False)):
        r = validate_submission(path, allow_nan=allow_nan)
        reports[label] = {"ok": r.ok, "errors": r.errors,
                          "warnings": r.warnings, "stats": r.stats}
        print(f"\n[{label}] " + r.render())
        ok &= r.ok
    if not ok:
        raise SystemExit("VALIDATION FAILED - nothing released")

    with zipfile.ZipFile(OUT / f"{name}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(tif, arcname=f"{name}.tif")

    note = (note_bits + ", binary 0/1"
            + (", catalogue included (masked at scoring)"
               if not a.no_catalogue else ""))

    prov_out = {
        "name": name, "generated_utc": stamp, "note_for_submission_form": note,
        "recipe_selection": prov or {"mode": "manual override"},
        "map_stats": stats, "validation": reports,
        "metric_facts": {
            "DTI_is_distance_weighted_F2": True,
            "marginal_precision_needed_to_help": "0.2 x current DTI",
            "binary_is_optimal": "DTI(c*p) strictly increases in c",
        },
        "official_format_source":
            "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
    }
    (OUT / f"{name}.json").write_text(json.dumps(prov_out, indent=2))

    # Primary download must be all-finite (0 outside) to pass DrivenData's
    # "Predicted values must be in range [0, 1]" check which rejects NaN.
    # NaN-outside variant is kept as latest_nan.tif for reference; the
    # all-finite twin is score-neutral per forum 11516 and is the safe default.
    shutil.copyfile(OUT / f"{name}.tif", OUT / f"latest_nan.tif")
    shutil.copyfile(OUT / f"{name}_allfinite.tif", OUT / f"latest.tif")
    shutil.copyfile(OUT / f"{name}_allfinite.tif", OUT / f"latest_allfinite.tif")
    # zip should contain the finite version (also valid: outside null or nan)
    with zipfile.ZipFile(OUT / f"latest.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(OUT / f"{name}_allfinite.tif", arcname=f"{name}_allfinite.tif")
    shutil.copyfile(OUT / f"{name}.json", OUT / f"latest.json")
    # also keep original zip for backwards compat
    shutil.copyfile(OUT / f"{name}.zip", OUT / f"latest_nan.zip")

    (REP / "latest_submission.json").write_text(json.dumps(prov_out, indent=2))
    print(f"\nWROTE {OUT}/{name}.tif  (+ _allfinite, .zip, .json, and latest.*)")
    print(f"NOTE  {note}")


if __name__ == "__main__":
    main()
