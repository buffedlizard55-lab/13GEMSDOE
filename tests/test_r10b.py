"""Unit tests for the R10b fusion helpers (scripts/validate_r10b_holdout.py).

The fusion is a fixed-budget re-ranking: it must not invent mass, must not let an
out-of-footprint pixel win, and must treat ties the same way the metric's own
ranking does (average ranks, never row-major order).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import validate_r10b_holdout as V  # noqa: E402


class TestPercentileField(unittest.TestCase):
    def test_invalid_pixels_are_below_every_valid_pixel(self):
        score = np.array([[0.0, 1.0, 2.0], [3.0, np.nan, 5.0]], dtype=np.float32)
        valid = np.array([[True, True, True], [True, False, True]])
        p = V.percentile_field(score, valid)
        self.assertAlmostEqual(float(p[1, 1]), -1.0, places=6)
        self.assertTrue(np.all(p[valid] > 0.0))
        self.assertTrue(np.all(p[valid] <= 1.0))

    def test_plateau_shares_one_percentile_not_row_major_order(self):
        # 6 of 9 pixels are exactly zero: they must all get the same percentile,
        # otherwise the fusion would rank them by position (irregularity I-14).
        score = np.zeros((3, 3), dtype=np.float32)
        score[0, 0] = score[1, 2] = score[2, 1] = 1.0
        valid = np.ones((3, 3), dtype=bool)
        p = V.percentile_field(score, valid)
        zeros = p[score == 0.0]
        self.assertEqual(zeros.size, 6)
        self.assertTrue(np.allclose(zeros, zeros[0], atol=1e-6))
        self.assertTrue(np.all(p[score > 0] > zeros[0]))

    def test_monotone_in_score(self):
        rng = np.random.default_rng(7)
        score = rng.random((40, 40)).astype(np.float32)
        valid = np.ones((40, 40), dtype=bool)
        p = V.percentile_field(score, valid)
        a, b = score.ravel(), p.ravel()
        i, j = int(np.argmax(a)), int(np.argmin(a))
        self.assertGreater(float(b[i]), float(b[j]))


class TestFuse(unittest.TestCase):
    def test_weight_endpoints_recover_the_inputs(self):
        rng = np.random.default_rng(11)
        pa = rng.random((20, 20)).astype(np.float32)
        pb = rng.random((20, 20)).astype(np.float32)
        valid = np.ones((20, 20), dtype=bool)
        np.testing.assert_allclose(V.fuse(pa, pb, 0.0, valid), pa, atol=1e-6)
        np.testing.assert_allclose(V.fuse(pa, pb, 1.0, valid), pb, atol=1e-6)

    def test_fusion_never_rescues_an_invalid_pixel(self):
        pa = np.zeros((10, 10), dtype=np.float32)
        pb = np.ones((10, 10), dtype=np.float32)
        valid = np.ones((10, 10), dtype=bool)
        valid[3, 3] = False           # a perfect external score must not matter
        out = V.fuse(pa, pb, 0.5, valid)
        self.assertAlmostEqual(float(out[3, 3]), -1.0, places=6)
        self.assertTrue(np.all(out[valid] > 0.0))

    def test_interior_weight_is_a_convex_combination(self):
        pa = np.full((6, 6), 0.2, dtype=np.float32)
        pb = np.full((6, 6), 0.8, dtype=np.float32)
        valid = np.ones((6, 6), dtype=bool)
        out = V.fuse(pa, pb, 0.25, valid)
        np.testing.assert_allclose(out, 0.35 * np.ones((6, 6)), atol=1e-6)


class TestConfigInventory(unittest.TestCase):
    def test_reference_is_present_and_unique(self):
        cfgs = V.build_configs()
        names = [c["name"] for c in cfgs]
        self.assertEqual(names.count(V.REFERENCE), 1)
        self.assertEqual(names[0], V.REFERENCE)
        self.assertEqual(len(names), len(set(names)))

    def test_declared_mechanisms_are_all_present(self):
        names = {c["name"] for c in V.build_configs()}
        for w in ("015", "030", "050"):
            self.assertIn(f"fuse_vent_w{w}_sp3", names)
        self.assertIn("fuse_alter_w030_sp3", names)
        for extra in ("vent005", "vent010", "alter005", "alter010"):
            self.assertIn(f"topo05_plus_{extra}_sp3", names)

    def test_no_config_requests_more_mass_than_a_sparse_map_can_supply(self):
        # irregularity I-14: a top-k above a map's non-zero support selects by
        # row-major position. The fusion maps are dense by construction, and every
        # union block here is <= 1% of a dense or near-dense field.
        for cfg in V.build_configs():
            for name, cov in [cfg["primary"]] + list(cfg.get("extra", [])):
                if name.startswith("fuse_"):
                    continue
                self.assertIn(name, ("topo", "vent", "alter"))
                self.assertLessEqual(cov, 0.05)


if __name__ == "__main__":
    unittest.main()
