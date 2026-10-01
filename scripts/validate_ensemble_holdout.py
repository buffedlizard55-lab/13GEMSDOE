#!/usr/bin/env python3
"""Score the current R8 recipe without catalogue leakage on local holdouts.

Run with the repository environment, e.g. ``.venv/bin/python
scripts/validate_ensemble_holdout.py``. The archived submission raster is used
only to identify the recipe and record its checksum. It is NOT scored directly:
its tip-ray and horsetail layers were made from the full catalogue. Those layers
are reconstructed from each fold's visible catalogue here.

The sweep compares the existing R8 coverages/fusion with the previous local
holdout leader (BASE_topo_ridge, 5% coverage, spacing 3), along with small
predeclared cutoff, spacing, line-width, and fusion alternatives. Scores are
local proxy measurements, not estimates of public/private test performance.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gems import detectors as D  # noqa: E402
from gems.fastscore import FoldScorer, verify_against_reference  # noqa: E402
from gems.holdout import build_folds, label_segments, make_fold  # noqa: E402
from gems.rio import load_footprint, read_band  # noqa: E402

DER = ROOT / "data" / "derived"
RAW = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"
LATEST = json.loads((REPORTS / "latest_submission.json").read_text())
LATEST_NAME = LATEST["name"]
LATEST_FILE = ROOT / "docs" / "downloads" / f"archive/{LATEST_NAME}_allfinite.tif"
N_FOLDS = 3
HIDE_FRAC = 0.25
BUFFER_PX = 5
LINK_PX = 8
SPACING_BASE = 3
BASE_COVERAGE = 0.05


class Ranker:
    """Stable score ranking, matching the selection used in run_holdout3.py."""

    def __init__(self, score: np.ndarray):
        self.score = np.asarray(score, dtype=np.float32)
        self.order = np.argsort(-self.score.ravel(), kind="stable").astype(np.int32)

    def topk(self, allowed: np.ndarray, n: int) -> np.ndarray:
        flat_allowed = np.asarray(allowed, dtype=bool).ravel()
        selected = self.order[flat_allowed[self.order]][:n]
        out = np.zeros(flat_allowed.size, dtype=bool)
        out[selected] = True
        return out.reshape(allowed.shape)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def segment_folds(known: np.ndarray, valid: np.ndarray,
                  n_folds: int = N_FOLDS) -> list:
    """Random holdouts of raw 8-connected catalogue components (not systems)."""
    seg, n_segments = label_segments(known)
    sizes = np.bincount(seg.ravel(), minlength=n_segments + 1)[1:].astype(np.int64)
    target = HIDE_FRAC * int(known.sum())
    rng = np.random.default_rng(20260930)
    folds = []
    ids = np.arange(1, n_segments + 1, dtype=np.int32)
    for i in range(n_folds):
        order = rng.permutation(n_segments)
        cumulative = np.cumsum(sizes[order])
        k = int(np.searchsorted(cumulative, target, side="left")) + 1
        hidden_ids = ids[order[:k]]
        fold = make_fold(known, valid, hidden_ids, seg,
                         f"segment_random_{i}", "segment_random", BUFFER_PX)
        fold.meta.update({"segmentation": "raw 8-connected raster components",
                          "n_catalogue_components": int(n_segments)})
        folds.append(fold)
    return folds


def build_configs() -> list[dict]:
    """A small, explicit local sweep; no public score labels are used."""
    return [
        {"name": "topo_03_sp3", "kind": "topo", "coverage": 0.03, "spacing": 3},
        {"name": "topo_05_sp1", "kind": "topo", "coverage": 0.05, "spacing": 1},
        {"name": "topo_05_sp2", "kind": "topo", "coverage": 0.05, "spacing": 2},
        {"name": "topo_05_sp3", "kind": "topo", "coverage": 0.05, "spacing": 3},
        {"name": "topo_08_sp3", "kind": "topo", "coverage": 0.08, "spacing": 3},
        {"name": "topo_05_sp3_wide1", "kind": "topo", "coverage": 0.05, "spacing": 3, "width_px": 1},
        {"name": "r8_half_union_sp3", "kind": "r8", "factor": 0.5, "spacing": 3},
        {"name": "r8_current_union_sp1", "kind": "r8", "factor": 1.0, "spacing": 1},
        {"name": "r8_current_union_sp2", "kind": "r8", "factor": 1.0, "spacing": 2},
        {"name": "r8_current_union_sp3", "kind": "r8", "factor": 1.0, "spacing": 3},
        {"name": "r8_1p5x_union_sp3", "kind": "r8", "factor": 1.5, "spacing": 3},
        {"name": "r8_no_catalogue_geometry_sp3", "kind": "r8", "factor": 1.0,
         "spacing": 3, "include_rays": False, "include_horsetail": False},
        {"name": "r8_no_topo_sp3", "kind": "r8", "factor": 1.0,
         "spacing": 3, "include_topo": False},
        {"name": "r8_vote2_sp3", "kind": "r8", "factor": 1.0,
         "spacing": 3, "fusion": "vote2"},
        {"name": "r8_union_wide1_sp3", "kind": "r8", "factor": 1.0,
         "spacing": 3, "width_px": 1},
    ]


def main() -> None:
    t0 = time.time()
    verify = verify_against_reference(trials=15)
    if not verify["pass"]:
        raise RuntimeError(f"Fast scorer disagrees with the reference: {verify}")

    valid, known = load_footprint(RAW / "existing_faults.tif")
    n_valid = int(valid.sum())
    n_known = int(known.sum())
    if not LATEST_FILE.exists():
        raise FileNotFoundError(LATEST_FILE)

    # Verify the archived recipe artifact's format and grid, but do not score its
    # full-catalogue ray/horsetail pixels on the holdout (that would leak).
    with rasterio.open(LATEST_FILE) as src:
        pred_meta = {
            "path": str(LATEST_FILE.relative_to(ROOT)),
            "sha256": sha256(LATEST_FILE),
            "shape": list(src.shape), "count": src.count,
            "dtype": src.dtypes[0], "crs": str(src.crs),
            "nodata": None if src.nodata is None else str(src.nodata),
            "positive_pixels_in_valid": int(((src.read(1) > 0) & valid).sum()),
        }
        if src.shape != valid.shape or src.count != 1 or src.dtypes[0] != "float32":
            raise ValueError(f"Unexpected archived candidate grid/format: {pred_meta}")

    # Feature maps are label-independent; the two catalogue-derived components
    # below (tip rays and horsetail splays) are rebuilt per fold from f.visible.
    feature_names = [
        "BASE_topo_ridge", "R8_openness", "R8_tpi", "R8_flow",
        "R8_isocoherence", "R8_remanence", "R8_intersections",
    ]
    scores = {name: np.load(DER / f"{name}.npy").astype(np.float32, copy=False)
              for name in feature_names}
    rankers = {name: Ranker(score) for name, score in scores.items()}

    # Match the historical R8 recipe's listed coverages, but source them from
    # its provenance report so the sweep is mechanically tied to that artifact.
    r8_coverages = {
        "BASE_topo_ridge": float(LATEST["map_stats"]["coverages"]["BASE_topo_ridge"]),
        "R8_openness": float(LATEST["map_stats"]["coverages"]["R8_openness"]),
        "R8_tpi": float(LATEST["map_stats"]["coverages"]["R8_tpi"]),
        "R8_flow": float(LATEST["map_stats"]["coverages"]["R8_flow"]),
        "R8_isocoherence": float(LATEST["map_stats"]["coverages"]["R8_isocoherence"]),
        "R8_remanence": float(LATEST["map_stats"]["coverages"]["R8_remanence"]),
        "R8_intersections": float(LATEST["map_stats"]["coverages"]["R8_intersections"]),
    }
    configs = build_configs()

    # Catalogue-independent terrain gate for a separate low-slope stress subset.
    slope = read_band(RAW / "gems-geodawn-numerical-features.tif", band=19)
    slope_ok = valid & np.isfinite(slope)
    slope_threshold = float(np.nanpercentile(slope[slope_ok], 33.0))
    concealed_zone = slope_ok & (slope <= slope_threshold)
    del slope

    system_folds = build_folds(known, valid, n_folds=N_FOLDS,
                               hide_frac=HIDE_FRAC, seed=20260930,
                               link_px=LINK_PX, buffer_px=BUFFER_PX)
    seg_folds = segment_folds(known, valid, n_folds=N_FOLDS)
    folds = system_folds + seg_folds
    if len(folds) < 10:
        raise RuntimeError(f"Insufficient folds built: {len(folds)}")

    # The same target count per local fold as run_holdout3. Selection is
    # restricted to that fold's eligible domain; no withheld catalogue segment
    # is used to construct the ray/horsetail maps.
    topk_cache: dict[tuple[str, float], np.ndarray] = {}
    rows: list[dict] = []

    for fold_i, fold in enumerate(folds, start=1):
        print(f"[{fold_i:02d}/{len(folds)}] {fold.name} ({fold.rule}), "
              f"hidden={fold.n_hidden:,}, eval={int(fold.eval_mask.sum()):,}")
        eval_mask = fold.eval_mask
        allowed_flat = eval_mask.ravel()
        cache: dict[tuple[str, float], np.ndarray] = {}

        def selected_mask(name: str, coverage: float) -> np.ndarray:
            key = (name, float(coverage))
            if key not in cache:
                n = int(coverage * n_valid)
                cache[key] = rankers[name].topk(eval_mask, n)
            return cache[key]

        def static_component(name: str, coverage: float, spacing: int) -> np.ndarray:
            m = selected_mask(name, coverage)
            return D.decimate_grid(m, scores[name], spacing) if spacing > 1 else m

        # Build fault-geometry features only from this fold's visible labels.
        ray_score = D.extension_rays(fold.visible, reach_px=20)
        horse_score = D.horsetail_splay(fold.visible, max_gap_px=20, splay_len_px=12)
        ray_mask = (ray_score > 0) & eval_mask
        horse_mask = (horse_score > 0) & eval_mask
        del allowed_flat

        fold_scorer = FoldScorer.build(fold.hidden, eval_mask)
        hidden_concealed = fold.hidden & concealed_zone
        concealed_scorer = (
            FoldScorer.build(hidden_concealed, eval_mask)
            if int(hidden_concealed.sum()) > 50 else None
        )

        for cfg in configs:
            spacing = int(cfg["spacing"])
            if cfg["kind"] == "topo":
                candidate = static_component(
                    "BASE_topo_ridge", float(cfg["coverage"]), spacing
                )
                components_this = [candidate]
            else:
                factor = float(cfg["factor"])
                components_this = []
                if cfg.get("include_rays", True):
                    m = ray_mask.copy()
                    if spacing > 1:
                        m = D.decimate_grid(m, ray_score, spacing)
                    components_this.append(m)
                if cfg.get("include_horsetail", True):
                    m = horse_mask.copy()
                    if spacing > 1:
                        m = D.decimate_grid(m, horse_score, spacing)
                    components_this.append(m)
                for name, cov in r8_coverages.items():
                    if name == "BASE_topo_ridge" and not cfg.get("include_topo", True):
                        continue
                    if name not in scores:
                        continue
                    m = selected_mask(name, cov * factor)
                    if spacing > 1:
                        m = D.decimate_grid(m, scores[name], spacing)
                    components_this.append(m)

                if cfg.get("fusion") == "vote2":
                    count = np.zeros(valid.shape, dtype=np.uint8)
                    for m in components_this:
                        count += m
                    candidate = count >= 2
                    del count
                else:
                    candidate = np.zeros(valid.shape, dtype=bool)
                    for m in components_this:
                        candidate |= m

            width = int(cfg.get("width_px", 0))
            if width:
                candidate = (ndi.binary_dilation(
                    candidate, structure=ndi.generate_binary_structure(2, 2),
                    iterations=width) & eval_mask)
            else:
                candidate &= eval_mask

            n_eff = int(candidate.sum())
            result = fold_scorer.score(candidate)
            row = {
                "config": cfg["name"], "family": cfg["kind"],
                "fold": fold.name, "rule": fold.rule,
                "n_truth": fold_scorer.n_truth,
                "n_eval_pixels": int(eval_mask.sum()),
                "n_predicted_eval_pixels": n_eff,
                "coverage_of_eval_pct": round(100.0 * n_eff / eval_mask.sum(), 5),
                "dti": round(float(result["dti"]), 7),
                "precision_w": round(float(result["precision_w"]), 7),
                "recall_w": round(float(result["recall_w"]), 7),
                "dti_concealed": None,
                "n_truth_concealed": 0,
            }
            if concealed_scorer is not None:
                hidden_result = concealed_scorer.score(candidate)
                row["dti_concealed"] = round(float(hidden_result["dti"]), 7)
                row["n_truth_concealed"] = concealed_scorer.n_truth
            rows.append(row)
            del candidate, components_this
        del ray_score, horse_score, ray_mask, horse_mask, cache, fold_scorer, concealed_scorer

    # Tune on the first replicate of each named system rule plus one segment
    # replicate. Keep the remaining folds as a descriptive confirmation set.
    tune_folds = {"random_0", "short_0", "isolated_0", "strike_60_120",
                  "dense_0", "segment_random_0"}
    tune_rows = [r for r in rows if r["fold"] in tune_folds]
    confirm_rows = [r for r in rows if r["fold"] not in tune_folds]

    def summarize(selected_rows: list[dict]) -> dict[str, dict]:
        by_cfg_rule: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
        for row in selected_rows:
            by_cfg_rule[row["config"]][row["rule"]].append(row)
        summary = {}
        for cfg, by_rule in by_cfg_rule.items():
            rule_means = {
                rule: float(np.mean([x["dti"] for x in values]))
                for rule, values in by_rule.items()
            }
            concealed_means = {
                rule: float(np.mean([x["dti_concealed"] for x in values
                                     if x["dti_concealed"] is not None]))
                for rule, values in by_rule.items()
                if any(x["dti_concealed"] is not None for x in values)
            }
            summary[cfg] = {
                "n_folds": sum(len(v) for v in by_rule.values()),
                "dti_mean": float(np.mean([x["dti"] for x in selected_rows
                                            if x["config"] == cfg])),
                "dti_worst_rule_mean": min(rule_means.values()),
                "dti_mean_by_rule": rule_means,
                "dti_concealed_mean_by_rule": concealed_means,
                "precision_w_mean": float(np.mean([x["precision_w"] for x in selected_rows
                                                    if x["config"] == cfg])),
                "recall_w_mean": float(np.mean([x["recall_w"] for x in selected_rows
                                                 if x["config"] == cfg])),
                "predicted_eval_px_mean": float(np.mean([
                    x["n_predicted_eval_pixels"] for x in selected_rows
                    if x["config"] == cfg
                ])),
            }
        return summary

    tune_summary = summarize(tune_rows)
    confirm_summary = summarize(confirm_rows)
    tune_ranked = sorted(
        ((v["dti_worst_rule_mean"], cfg) for cfg, v in tune_summary.items()),
        reverse=True,
    )

    out = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "LOCAL_PROXY_HOLDOUT_ONLY_NOT_PRIVATE_TEST_PERFORMANCE",
        "purpose": (
            "Evaluate the archived R8 recipe as a per-fold rebuild, not by scoring its "
            "full-catalogue raster; compare predeclared cutoff/spacing/width/fusion "
            "alternatives with the historical BASE_topo_ridge local leader."
        ),
        "input_artifact": pred_meta,
        "grid": {"valid_pixels": n_valid, "known_fault_pixels": n_known},
        "protocol": {
            "system_folds": {
                "construction": "group 8-connected trace segments when their 8-px dilations connect",
                "link_px_per_trace": LINK_PX,
                "maximum_gap_px_approx": 2 * LINK_PX,
                "maximum_gap_m_approx": 2 * LINK_PX * 100,
                "n_folds_per_rule": N_FOLDS, "hide_fraction_target": HIDE_FRAC,
                "rules": ["random", "short", "isolated", "oriented", "dense"],
            },
            "segment_folds": {
                "construction": "raw 8-connected pixel components, randomly grouped by pixel mass",
                "n_folds": N_FOLDS, "hide_fraction_target": HIDE_FRAC,
            },
            "buffer_px": BUFFER_PX, "buffer_m": BUFFER_PX * 100,
            "visible_catalogue_only": True,
            "catalogue_dependent_features_rebuilt_per_fold": [
                "extension_rays", "horsetail_splay"
            ],
            "known_fault_mask": (
                "pixel-exact visible catalogue mask; the 5-px buffer is removed from "
                "visible features but remains inside the evaluation domain and can accrue FP"
            ),
            "scoring": "local FoldScorer scores withheld truth only and masks prediction FP outside eval_mask; candidate maps are clipped to eval_mask",
            "masked_prediction_policy": {
                "status": "CONSERVATIVE_LOCAL_CHOICE",
                "policy": "predictions outside eval_mask are discarded before TP and FP calculation",
                "uncertainty": "organizer wording does not resolve whether predictions on exact masked known-fault pixels can contribute TP to nearby new truth; see knowledge/02_irregularities.md Q-1",
            },
            "concealed_subset": "withheld truth pixels in the valid-footprint slope bottom third; proxy stress test only",
            "candidate_selection": (
                "threshold static scores at config coverage times full valid-pixel count, "
                "restricted to each fold's eval_mask; then apply grid decimation"
            ),
            "random_control": (
                "No candidate-to-chance ratio is used. Candidate comparison is by direct "
                "DTI on each fold; the report is a local catalogue-recovery proxy only."
            ),
            "scorer_verification": verify,
            "tuning_folds": sorted(tune_folds),
            "confirmation_folds": sorted({r["fold"] for r in confirm_rows}),
        },
        "r8_base_coverages": r8_coverages,
        "configurations": configs,
        "tune_summary": tune_summary,
        "confirmation_summary": confirm_summary,
        "tune_ranked_by_worst_rule_dti": [
            {"rank": i + 1, "config": cfg, "worst_rule_dti_mean": score}
            for i, (score, cfg) in enumerate(tune_ranked)
        ],
        "results": rows,
        "runtime_s": round(time.time() - t0, 1),
    }
    out_path = REPORTS / "holdout_candidate_r8_2026-09-30.json"
    out_path.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print(f"wrote {out_path} ({len(rows)} rows, {time.time()-t0:.0f}s)")
    for name in ("topo_05_sp3", "r8_current_union_sp3", "r8_half_union_sp3",
                 "r8_vote2_sp3", "r8_union_wide1_sp3"):
        if name in tune_summary:
            print(name, "tune worst/mean",
                  round(tune_summary[name]["dti_worst_rule_mean"], 5),
                  round(tune_summary[name]["dti_mean"], 5),
                  "confirm worst/mean",
                  round(confirm_summary[name]["dti_worst_rule_mean"], 5),
                  round(confirm_summary[name]["dti_mean"], 5))


if __name__ == "__main__":
    main()
