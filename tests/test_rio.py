"""Regression tests for strict submission raster serialization.

Run with the project dependencies installed: ``python -m unittest discover -s tests``.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import rio  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
import make_submission  # noqa: E402


class WriteSubmissionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.shape = (6, 7)
        self.valid = np.ones(self.shape, dtype=bool)
        self.values = np.zeros(self.shape, dtype=np.float32)
        self.values[2, 3] = 1.0
        self.grid_patch = patch.object(rio, "EXPECTED_SHAPE", self.shape)
        self.grid_patch.start()
        self.addCleanup(self.grid_patch.stop)

    def test_accepts_binary_values_and_writes_nodata_outside(self) -> None:
        self.valid[0, 0] = False
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.tif"
            rio.write_submission(path, self.values, self.valid)
            report = rio.validate_submission(
                path, valid_mask=self.valid, require_nodata_outside=True
            )
            self.assertTrue(report.ok, report.render())
            self.assertEqual(report.stats["min"], 0.0)
            self.assertEqual(report.stats["max"], 1.0)
            self.assertTrue(report.stats["outside_nodata_ok"])

    def test_rejects_values_above_one_instead_of_clipping(self) -> None:
        self.values[1, 1] = 1.0001
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "must-not-exist.tif"
            with self.assertRaisesRegex(ValueError, r"\[0, 1\]"):
                rio.write_submission(path, self.values, self.valid)
            self.assertFalse(path.exists())

    def test_rejects_negative_values_instead_of_clipping(self) -> None:
        self.values[1, 1] = -0.01
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, r"\[0, 1\]"):
                rio.write_submission(Path(tmp) / "candidate.tif", self.values, self.valid)

    def test_rejects_nonfinite_inside_footprint(self) -> None:
        self.values[1, 1] = np.nan
        with self.assertRaisesRegex(ValueError, "must all be finite"):
            rio.write_submission("unused.tif", self.values, self.valid)

    def test_rejects_shape_and_mask_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "prediction shape"):
            rio.write_submission("unused.tif", self.values[:-1], self.valid)
        with self.assertRaisesRegex(ValueError, "valid-mask shape"):
            rio.write_submission("unused.tif", self.values, self.valid[:-1])

    def test_rejects_invalid_outside_fill(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside_value"):
            rio.write_submission("unused.tif", self.values, self.valid, outside_value=2.0)


class DetectorSelectionValidationTests(unittest.TestCase):
    def test_zero_coverage_is_rejected_before_topk_slicing(self) -> None:
        with self.assertRaisesRegex(ValueError, "coverage must be in \\(0, 1\\]"):
            make_submission.build("unused", 0.0, 1, False)

    def test_nonpositive_spacing_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "spacing must be a positive integer"):
            make_submission.build("unused", 0.05, 0, False)


if __name__ == "__main__":
    unittest.main()
