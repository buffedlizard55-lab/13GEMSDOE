#!/usr/bin/env python3
"""Chance-DTI helper for local holdouts with known withheld-truth size.

`dti_chance(mass, n_truth, n_valid)` is retained for controlled hide-and-recover
folds, where `n_truth` is known. It must not be used to infer public/private
hidden-truth size from leaderboard scores. The old public-report path did exactly
that and then reused the inferred size to explain those same scores; that
circular public inference is withdrawn.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems.metric import kernel_offsets  # noqa: E402

N_VALID = 5_167_373
KERNEL_MASS = 5.0  # recorded approximation for the local random-map FP term


def r_of_c(c: float) -> float:
    """Expected kernel credit at a truth pixel for Bernoulli(c) predictions."""
    weights = sorted((k for _, _, k in kernel_offsets()), reverse=True)
    return float(sum(weight * c * (1.0 - c) ** j
                     for j, weight in enumerate(weights)))


def dti_chance(mass: float, n_truth: float, n_valid: int = N_VALID) -> float:
    """Approximate random-map DTI for a local holdout with known ``n_truth``.

    Parameters are the predicted probability mass, actual withheld truth-pixel
    count for this fold, and actual valid footprint size for the same fold. This
    function is not a public/private leaderboard estimator.
    """
    if n_valid <= 0:
        raise ValueError("n_valid must be positive")
    if n_truth <= 0:
        raise ValueError("n_truth must be positive and known for a holdout")
    c = mass / n_valid
    r = r_of_c(c)
    fp = mass * max(0.0, 1.0 - KERNEL_MASS * n_truth / n_valid)
    return r / (0.2 * r + 0.8 + 0.2 * fp / n_truth)


def invalidated_report() -> dict:
    """Return an explicit withdrawal notice, with no public-score estimates."""
    return {
        "status": "WITHDRAWN",
        "observed_date": "2026-09-30",
        "scope": "Public/private leaderboard chance estimates are not available from this calculation.",
        "reason": (
            "The prior public report inferred hidden truth size from account-level "
            "leaderboard scores and then evaluated those same scores against chance "
            "at the inferred size. The estimate was circular. In addition, the local "
            "score-to-file attribution was not supported by per-submission receipts."
        ),
        "public_estimates": None,
        "rows": [],
        "local_holdout_function": {
            "name": "dti_chance(mass, n_truth, n_valid)",
            "allowed_use": (
                "Local hide-and-recover folds only, with the actual withheld-truth "
                "pixel count known independently for each fold."
            ),
            "calibration_source": "reports/holdout_verdict_v3.json",
            "calibration_scope": (
                "The corrected legacy holdout-v3 summary used each fold's eligible "
                "eval area and compared against 30 same-run random controls (median "
                "relative error 0.018, p90 0.073). This is an in-sample local check, "
                "not a universal calibration or a public/private leaderboard baseline. "
                "The separate R8 holdout chance values were not empirically calibrated."
            ),
        },
        "leaderboard_score_scope": (
            "The official leaderboard column is account-level 'Best public "
            "DW-Tversky', not a per-submission receipt. See "
            "reports/leaderboard_snapshot_2026-09-30.json and "
            "reports/leaderboard_ledger.csv."
        ),
    }


def main() -> None:
    out_path = ROOT / "reports" / "chance_baseline.json"
    out_path.write_text(json.dumps(invalidated_report(), indent=2) + "\n")
    print("Public chance/lift report withdrawn: inferred public truth size was circular.")
    print("dti_chance() remains available only for local folds with known truth size.")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
