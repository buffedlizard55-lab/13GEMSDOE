"""Regression tests for the R9 hypothesis operators.

The geometric cases encode the exact closing semantics documented in
`gems.detectors.strike_gap_close`: gaps up to 3 px close fully (axial), 4 px
closes partially, 5 px and beyond stay open (anchor gate), diagonal reach is
2 steps, and a lone line never extends its free ends.
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from gems import detectors as D  # noqa: E402


def axial_support(gap: int) -> np.ndarray:
    s = np.zeros((15, 60), dtype=bool)
    s[7, 5:10] = True
    s[7, 10 + gap:10 + gap + 10] = True
    return s


class TestStrikeGapClose(unittest.TestCase):
    def test_gaps_up_to_3_close_fully(self):
        for gap in (1, 2, 3):
            g = D.strike_gap_close(axial_support(gap))
            self.assertTrue(g[7, 10:10 + gap].all(), f"gap {gap} not closed")

    def test_gap_4_closes_partially(self):
        g = D.strike_gap_close(axial_support(4))
        self.assertTrue(g[7, 10:14].any())
        self.assertFalse(g[7, 10:14].all())

    def test_gaps_5_and_6_stay_open(self):
        for gap in (5, 6):
            g = D.strike_gap_close(axial_support(gap))
            self.assertFalse(g[7, 10:10 + gap].any(), f"gap {gap} should stay open")

    def test_diagonal_two_step_gap_closes(self):
        s = np.zeros((15, 15), dtype=bool)
        for i in list(range(3, 7)) + list(range(9, 13)):
            s[i, i] = True
        g = D.strike_gap_close(s)
        self.assertTrue(g[7, 7] and g[8, 8])

    def test_no_end_extension(self):
        s = np.zeros((15, 25), dtype=bool)
        s[7, 5:10] = True
        self.assertFalse(D.strike_gap_close(s).any())

    def test_reach_stays_inside_kernel(self):
        # every filled pixel must lie within Euclidean distance 3 of support
        rng = np.random.default_rng(7)
        s = rng.random((40, 40)) > 0.93
        g = D.strike_gap_close(s)
        dist = np.inf * np.ones(s.shape, dtype=np.float32)
        from scipy import ndimage as ndi
        dist = ndi.distance_transform_edt(~s)
        self.assertTrue((dist[g] <= 3.0).all())


class TestEqLineaments(unittest.TestCase):
    def test_output_range_and_shape(self):
        rng = np.random.default_rng(0)
        e = D.eq_lineaments(rng.random((80, 80)).astype(np.float32) * 100,
                            rng.random((80, 80)).astype(np.float32) * 100)
        self.assertEqual(e.shape, (80, 80))
        self.assertGreaterEqual(float(e.min()), 0.0)
        self.assertLessEqual(float(e.max()), 1.0)

    def test_constant_fields_give_finite_output(self):
        a = np.full((50, 50), 5.0, dtype=np.float32)
        e = D.eq_lineaments(a, a)
        self.assertTrue(np.isfinite(e).all())


class TestParallelOffsetCorrection(unittest.TestCase):
    def test_parallel_offset_edge_detected_on_edge_rows(self):
        vis = np.zeros((60, 80), dtype=bool)
        vis[30, 10:40] = True
        edge = np.zeros((60, 80), dtype=np.float32)
        edge[27, 12:36] = 1.0
        c = D.parallel_offset_correction(vis, edge)
        px = np.argwhere(c > 0)
        self.assertTrue(px.size > 0)
        self.assertEqual({int(y) for y, _ in px}, {27})

    def test_crossing_edge_rejected(self):
        vis = np.zeros((60, 80), dtype=bool)
        vis[30, 10:40] = True
        edge = np.zeros((60, 80), dtype=np.float32)
        edge[15:45, 20] = 1.0
        self.assertEqual(float(D.parallel_offset_correction(vis, edge).sum()), 0.0)

    def test_edge_far_from_ring_rejected(self):
        vis = np.zeros((60, 80), dtype=bool)
        vis[30, 10:40] = True
        edge = np.zeros((60, 80), dtype=np.float32)
        edge[27, 42:60] = 1.0
        self.assertEqual(float(D.parallel_offset_correction(vis, edge).sum()), 0.0)

    def test_bad_ring_parameters_rejected(self):
        vis = np.zeros((10, 10), dtype=bool)
        vis[5, 2:8] = True
        with self.assertRaises(ValueError):
            D.parallel_offset_correction(vis, np.zeros((10, 10), np.float32),
                                         off_lo_px=4, off_hi_px=2)


if __name__ == "__main__":
    unittest.main()
