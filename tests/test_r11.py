import sys, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems import detectors as D


class BasinMagTest(unittest.TestCase):
    def setUp(self):
        n = 120
        yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
        self.rtp = np.where(xx > 80, 50.0, 0.0).astype(np.float32)   # step at x=80
        self.slope = np.where(xx > 40, 0.1, 5.0).astype(np.float32)  # basin east of 40
        self.depth = np.where(xx > 40, 2000.0, 100.0).astype(np.float32)

    def test_detects_buried_step_in_basin_only(self):
        out = D.basin_magnetic_continuity(self.rtp, self.slope, self.depth)
        self.assertEqual(out.shape, self.rtp.shape)
        cols = np.nonzero(out.max(axis=0) > 0)[0]
        self.assertTrue(len(cols) > 0)
        self.assertTrue(np.all(np.abs(cols - 80) <= 3), cols)

    def test_no_output_outside_gate(self):
        out = D.basin_magnetic_continuity(self.rtp, self.slope, self.depth)
        self.assertEqual(float(out[:, :40].max()), 0.0)

    def test_all_nan_is_zero(self):
        nan = np.full((20, 20), np.nan, np.float32)
        self.assertEqual(float(D.basin_magnetic_continuity(nan, nan, nan).max()), 0.0)


if __name__ == "__main__":
    unittest.main()
