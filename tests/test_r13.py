"""Unit tests for the R13 helpers (lattices, local contrast, tile quota, halo)."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import validate_r13_holdout as R13                       # noqa: E402
import validate_r13_lattice_holdout as L                 # noqa: E402


class LatticeTests(unittest.TestCase):
    def test_square_density_and_phase(self):
        m = L.square_lattice((100, 100), 5)
        self.assertEqual(int(m.sum()), 400)
        self.assertTrue(m[0, 0] and m[5, 10] and not m[1, 0])

    def test_hex_equal_density(self):
        sq = L.square_lattice((600, 600), 5).sum()
        hx = L.hex_lattice((600, 600), 5).sum()
        self.assertLess(abs(hx - sq) / sq, 0.03)

    def test_hex_rows_alternate(self):
        m = L.hex_lattice((40, 60), 5)
        rows = np.where(m.any(axis=1))[0]
        self.assertGreater(len(rows), 5)
        c0 = np.where(m[rows[0]])[0][0]
        c1 = np.where(m[rows[1]])[0][0]
        self.assertNotEqual(c0, c1)


class R13HelperTests(unittest.TestCase):
    def test_local_contrast_alpha_zero_is_identity(self):
        rng = np.random.default_rng(0)
        s = rng.random((60, 60)).astype(np.float32)
        v = np.ones_like(s, bool)
        out = R13.local_contrast(s, v, 5, 0.0)
        np.testing.assert_allclose(out, s, rtol=1e-6)

    def test_local_contrast_flattens_regional_trend(self):
        yy, xx = np.mgrid[0:80, 0:80]
        trend = 1.0 + 20.0 * (xx / 79.0)
        s = (trend * (1.0 + 0.5 * ((yy % 7) == 0))).astype(np.float32)
        v = np.ones_like(s, bool)
        out = R13.local_contrast(s, v, 6, 1.0)
        # left/right halves differ ~5x in s; far less after local normalisation
        self.assertLess(out[:, 60:].mean() / out[:, :20].mean(), 3.0)
        self.assertGreater(s[:, 60:].mean() / s[:, :20].mean(), 4.0)

    def test_tile_quota_lambda_zero_is_global_percentile(self):
        rng = np.random.default_rng(1)
        ref = rng.random((130, 130)).astype(np.float32)
        v = np.ones_like(ref, bool)
        out = R13.tile_quota(ref, v, 0.0)
        order_ref = np.argsort(ref.ravel())
        self.assertTrue(np.all(np.diff(out.ravel()[order_ref]) >= -1e-6))

    def test_tile_quota_zero_outside_footprint(self):
        ref = np.random.default_rng(2).random((70, 70)).astype(np.float32)
        v = np.zeros_like(ref, bool)
        v[10:50, 10:50] = True
        out = R13.tile_quota(ref, v, 1.0)
        self.assertTrue(np.all(out[~v] == 0))
        self.assertTrue(np.all(out[v] > 0))


if __name__ == "__main__":
    unittest.main()
