#!/usr/bin/env python3
"""Structural forensics on historical prediction-map artifacts.

This script compares file/pixel identity, support overlap, and distance-to-known-
catalogue mass for the TIFFs in data/scored. Numeric values encoded in artifact
filenames are retained only as *reported score labels*. They are not per-file
public-score receipts. The official leaderboard reports account-level best-public
scores, so this script does not infer a public score, hidden-truth size, or
chance/lift from those labels.

Writes reports/scored_forensics.json.
"""
from __future__ import annotations

import hashlib
import json
from itertools import combinations
from pathlib import Path
import sys

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems.metric import kernel_field_of_truth  # noqa: E402

RAW = ROOT / "data" / "raw"
SCORED = ROOT / "data" / "scored"
OUT = ROOT / "reports" / "scored_forensics.json"
LEADERBOARD_URL = (
    "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"
)

# Values in the TIFF filenames / earlier team notes. They are not independently
# mapped to a DrivenData per-submission receipt; see reports/leaderboard_ledger.csv.
REPORTED_SCORE_LABELS = {
    "gemsdoe1_ens12_LB0.1563.tif": 0.1563,
    "gems8_apex_LB0.1563.tif": 0.1563,
    "gemsdoe2_dualunion_LB0.1560.tif": 0.1560,
    "gems7_halo15_LB0.1461.tif": 0.1461,
    "gems3_pindrop_nodes_LB0.1193.tif": 0.1193,
    "gems3_pindrop_ridge_LB0.1152.tif": 0.1152,
    "gems3_pindrop_discovery_LB0.0830.tif": 0.0830,
    "gems6_hgb88_LB0.0286.tif": 0.0286,
}


def load(path: Path) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(1).astype(np.float32)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_array(array: np.ndarray) -> str:
    """Hash a canonical little-endian C-order array."""
    canonical = np.ascontiguousarray(array, dtype="<f4")
    return hashlib.sha256(canonical.view(np.uint8)).hexdigest()


def sha256_support(mask: np.ndarray) -> str:
    packed = np.packbits(np.asarray(mask, dtype=np.uint8), bitorder="little")
    digest = hashlib.sha256()
    digest.update(str(mask.shape).encode("ascii"))
    digest.update(packed.tobytes())
    return digest.hexdigest()


def main() -> None:
    cat = load(RAW / "existing_faults.tif")  # -1 nodata, 0/1 valid
    valid = cat >= 0
    known = cat > 0
    n_valid = int(valid.sum())
    n_known = int(known.sum())
    unmasked_domain = valid & ~known

    from scipy.ndimage import distance_transform_edt

    dist_pix = distance_transform_edt(~known)
    kfield_known = kernel_field_of_truth(known)

    rep: dict = {
        "grid": {
            "shape": list(cat.shape),
            "n_valid_pixels": n_valid,
            "n_known_fault_pixels": n_known,
            "known_fault_fraction_of_valid": round(n_known / n_valid, 6),
            "crs": "EPSG:32611",
            "pixel_m": 100,
        },
        "score_attribution": {
            "status": "UNVERIFIED_PER_FILE",
            "source_labels": "Historical TIFF filenames and team notes",
            "warning": (
                "Reported numeric labels do not establish the public score of the "
                "corresponding local TIFF. The official leaderboard column is "
                "account-level 'Best public DW-Tversky', not a per-submission receipt."
            ),
            "official_leaderboard_url": LEADERBOARD_URL,
            "ledger": "reports/leaderboard_ledger.csv",
        },
        "identity_scope": {
            "file_sha256": "Exact TIFF file bytes, including metadata/compression",
            "canonical_pixel_sha256": (
                "Decoded float32 pixels after non-finite values and cells outside "
                "the shared valid mask are set to zero; little-endian C-order."
            ),
            "support_sha256": "Boolean positive-value support on the shared grid, including shape.",
            "unmasked_evaluation_support_sha256": (
                "Boolean positive-value support restricted to valid pixels outside the "
                "pixel-exact known-fault mask; this is not true-positive/chargeable support "
                "because new-fault truth is hidden."
            ),
        "interpretation": (
                "Equal file hashes mean byte-identical files; equal canonical pixel "
                "hashes mean identical scored-grid values under the stated canonicalization; "
                "equal support hashes mean the same positive-pixel support. A rounded "
                "score label establishes none of these identities."
            ),
        },
        "maps": {},
        "pairwise": [],
        "findings": [],
    }

    arrs: dict[str, np.ndarray] = {}
    masks: dict[str, np.ndarray] = {}
    file_hashes: dict[str, str] = {}
    pixel_hashes: dict[str, str] = {}
    support_hashes: dict[str, str] = {}
    unmasked_support_hashes: dict[str, str] = {}
    unmasked_masks: dict[str, np.ndarray] = {}

    for name, reported_label in sorted(REPORTED_SCORE_LABELS.items()):
        path = SCORED / name
        if not path.exists():
            continue
        raw = load(path)
        # Canonical analysis values: all non-finite and outside-valid cells are 0.
        array = np.where(np.isfinite(raw), raw, 0.0).astype(np.float32, copy=False)
        array = np.where(valid, array, 0.0).astype(np.float32, copy=False)
        positive = array > 0
        unmasked_positive = positive & unmasked_domain
        mass = float(array.sum())
        unmasked_mass = float(array[unmasked_domain].sum())

        bands = {}
        for lower, upper, label in [
            (0, 0.01, "on_known"),
            (0.01, 3, "within_300m"),
            (3, 10, "300m_1km"),
            (10, 30, "1km_3km"),
            (30, 1e9, "beyond_3km"),
        ]:
            selected = (dist_pix >= lower) & (dist_pix < upper) & valid
            bands[label] = round(float(array[selected].sum()) / mass, 5) if mass > 0 else 0.0

        # Diagnostic only: exact weighted FP if the known catalogue itself were
        # treated as truth. It is not competition FP_w or evidence of public score.
        fp_if_known_were_truth = float((array * (1.0 - kfield_known))[valid].sum())
        file_hash = sha256_file(path)
        pixel_hash = sha256_array(array)
        support_hash = sha256_support(positive)
        unmasked_support_hash = sha256_support(unmasked_positive)
        file_hashes[name] = file_hash
        pixel_hashes[name] = pixel_hash
        support_hashes[name] = support_hash
        unmasked_support_hashes[name] = unmasked_support_hash
        arrs[name] = array
        masks[name] = positive
        unmasked_masks[name] = unmasked_positive

        rep["maps"][name] = {
            "reported_score_label_not_receipt": reported_label,
            "file_sha256": file_hash,
            "canonical_pixel_sha256": pixel_hash,
            "support_sha256": support_hash,
            "unmasked_evaluation_support_sha256": unmasked_support_hash,
            "n_pixels_gt0": int(positive.sum()),
            "coverage_pct_of_valid": round(100 * positive.sum() / n_valid, 4),
            "n_positive_pixels_outside_known_mask": int(unmasked_positive.sum()),
            "probability_mass_outside_known_mask": round(unmasked_mass, 1),
            "unmasked_mass_pct_of_valid": round(100 * unmasked_mass / n_valid, 4),
            "total_mass_sum_p": round(mass, 1),
            "mean_value_where_positive": round(mass / max(int(positive.sum()), 1), 4),
            "max_value": round(float(array.max()), 4),
            "n_distinct_values": int(np.unique(array[positive]).size) if positive.any() else 0,
            "frac_mass_binary_1.0": round(float(array[array >= 0.999].sum()) / mass, 5) if mass else 0.0,
            "mass_by_distance_to_known_catalogue": bands,
            "catalogue_echo_FPw_if_truth_were_catalogue": round(fp_if_known_were_truth, 1),
        }

    names = sorted(arrs)
    for a_name, b_name in combinations(names, 2):
        array_a, array_b = arrs[a_name], arrs[b_name]
        support_a, support_b = masks[a_name], masks[b_name]
        intersection = int((support_a & support_b).sum())
        union = int((support_a | support_b).sum())
        iou = intersection / union if union else 0.0
        union_support = support_a | support_b
        va, vb = array_a[union_support], array_b[union_support]
        corr = (
            float(np.corrcoef(va, vb)[0, 1])
            if union_support.sum() > 2 and np.std(va) > 0 and np.std(vb) > 0
            else None
        )
        eval_a, eval_b = unmasked_masks[a_name], unmasked_masks[b_name]
        eval_intersection = int((eval_a & eval_b).sum())
        eval_union = int((eval_a | eval_b).sum())
        eval_iou = eval_intersection / eval_union if eval_union else 0.0
        score_a = REPORTED_SCORE_LABELS[a_name]
        score_b = REPORTED_SCORE_LABELS[b_name]
        rep["pairwise"].append({
            "a": a_name,
            "b": b_name,
            "reported_score_label_a_not_receipt": score_a,
            "reported_score_label_b_not_receipt": score_b,
            "same_reported_score_label": score_a == score_b,
            "exact_file_bytes": file_hashes[a_name] == file_hashes[b_name],
            "exact_canonical_pixel_values": (
                pixel_hashes[a_name] == pixel_hashes[b_name]
                and np.array_equal(array_a, array_b)
            ),
            "exact_positive_support": (
                support_hashes[a_name] == support_hashes[b_name]
                and np.array_equal(support_a, support_b)
            ),
            "exact_unmasked_evaluation_support": (
                unmasked_support_hashes[a_name] == unmasked_support_hashes[b_name]
                and np.array_equal(eval_a, eval_b)
            ),
            "unmasked_evaluation_support_IoU": round(eval_iou, 5),
            "IoU_of_support": round(iou, 5),
            "pearson_r_on_support_union": round(corr, 5) if corr is not None else None,
            "dice_of_support": round(2 * intersection / (support_a.sum() + support_b.sum()), 5)
            if (support_a.sum() + support_b.sum()) else 0.0,
        })

    matching_labels = [pair for pair in rep["pairwise"] if pair["same_reported_score_label"]]
    rep["findings"].append({
        "id": "F1",
        "question": "Do matching historical score labels establish duplicate maps or equal per-file scores?",
        "answer": (
            "No. The label is not a per-submission receipt. Exact file, canonical-pixel, "
            "and support identities are measured independently below."
        ),
        "evidence": matching_labels,
    })
    echo = {
        name: values["mass_by_distance_to_known_catalogue"]["on_known"]
        + values["mass_by_distance_to_known_catalogue"]["within_300m"]
        for name, values in rep["maps"].items()
    }
    rep["findings"].append({
        "id": "F2",
        "question": "How much of each map is on or within 300 m of the known catalogue?",
        "answer": "Measured fraction of predicted mass; not a public-score attribution.",
        "evidence": {key: round(value, 4) for key, value in sorted(echo.items(), key=lambda item: -item[1])},
        "why_it_matters": (
            "The organizers say known catalogue pixels are masked, predictions near a "
            "known trace are penalized unless they are near new-fault truth, and new-fault "
            "truth may itself lie within 300 m. These distance summaries do not reveal "
            "whether any local prediction matched hidden truth."
        ),
    })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=2) + "\n")
    print(json.dumps({
        "grid": rep["grid"],
        "maps": {
            key: {
                "reported_score_label_not_receipt": value["reported_score_label_not_receipt"],
                "file_sha256": value["file_sha256"],
                "canonical_pixel_sha256": value["canonical_pixel_sha256"],
                "support_sha256": value["support_sha256"],
                "n_pixels_gt0": value["n_pixels_gt0"],
                "coverage_pct_of_valid": value["coverage_pct_of_valid"],
            }
            for key, value in rep["maps"].items()
        },
    }, indent=2))
    print("\n--- pairwise identity/support comparisons ---")
    for pair in sorted(rep["pairwise"], key=lambda item: (not item["same_reported_score_label"], -item["IoU_of_support"])):
        print(
            f"  same_label={pair['same_reported_score_label']} "
            f"file_equal={pair['exact_file_bytes']} pixels_equal={pair['exact_canonical_pixel_values']} "
            f"support_equal={pair['exact_positive_support']} IoU={pair['IoU_of_support']:.4f} "
            f"{pair['a'][:30]} vs {pair['b'][:30]}"
        )
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
