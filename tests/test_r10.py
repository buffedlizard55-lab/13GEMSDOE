"""Regression tests for the R10 external-data detectors and loader.

These are unit tests on small synthetic grids: they check the operators'
documented behaviour (NaN handling, linearity enforcement, trend removal,
geometric-mean conjunction), not geological skill. Skill is measured by
scripts/validate_r10_holdout.py against the predeclared decision rule.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems import detectors as D  # noqa: E402
from gems import external as X  # noqa: E402


def synthetic_line(shape=(60, 60), width=1.0):
    """A straight N-S linear anomaly in the middle of the grid."""
    a = np.zeros(shape, dtype=np.float32)
    a[:, shape[1] // 2] = width
    return a


class TestOrientedPersistence(unittest.TestCase):
    def test_keeps_long_line_drops_speck(self):
        line = synthetic_line((40, 40)) > 0
        speck = np.zeros((40, 40), dtype=bool)
        speck[5, 5] = True
        keep = D.oriented_persistence(line | speck, coherence_px=9, min_coh=5)
        self.assertTrue(keep[:, 20].all(), "a persistent line must survive")
        self.assertFalse(keep[5, 5], "an isolated speck must not survive")

    def test_empty_input(self):
        keep = D.oriented_persistence(np.zeros((20, 20), dtype=bool))
        self.assertFalse(keep.any())


class TestHighpassResidual(unittest.TestCase):
    def test_removes_regional_linear_trend(self):
        yy, xx = np.mgrid[0:80, 0:80]
        field = (0.5 * xx + 0.25 * yy).astype(np.float32)      # pure regional trend
        hp = D.highpass_residual(field, sigma_px=8.0)
        inner = hp[16:-16, 16:-16]
        self.assertLess(float(np.abs(inner).max()), 0.05 * float(np.abs(field).max()))

    def test_keeps_local_bump(self):
        field = np.zeros((80, 80), dtype=np.float32)
        field[40, 40] = 5.0
        hp = D.highpass_residual(field, sigma_px=8.0)
        self.assertGreater(float(hp[40, 40]), 1.0)

    def test_nan_domain_preserved(self):
        field = np.full((40, 40), np.nan, dtype=np.float32)
        field[10:30, 10:30] = 1.0
        hp = D.highpass_residual(field, sigma_px=4.0)
        self.assertFalse(np.isfinite(hp[0, 0]))
        self.assertTrue(np.isfinite(hp[20, 20]))

    def test_relief_control_reduces_explained_variance(self):
        rng = np.random.default_rng(3)
        relief = rng.normal(size=(80, 80)).astype(np.float32)
        relief = D.ndi.gaussian_filter(relief, 2.0).astype(np.float32)
        field = 3.0 * relief + rng.normal(scale=0.05, size=(80, 80)).astype(np.float32)
        plain = D.highpass_residual(field, sigma_px=8.0)
        resid = D.highpass_residual(field, relief, sigma_px=8.0)
        self.assertLess(float(np.std(resid)), float(np.std(plain)))


class TestDamageZoneTexture(unittest.TestCase):
    def test_constant_input_gives_zero(self):
        a = np.ones((50, 50), dtype=np.float32)
        out = D.damage_zone_texture(a, a)
        self.assertEqual(float(np.nanmax(out)), 0.0)

    def test_linear_texture_anomaly_is_detected(self):
        rng = np.random.default_rng(11)
        s = rng.normal(scale=0.2, size=(80, 80)).astype(np.float32)
        c = rng.normal(scale=0.2, size=(80, 80)).astype(np.float32)
        s = np.abs(D.ndi.gaussian_filter(s, 1.0)).astype(np.float32)
        c = np.abs(D.ndi.gaussian_filter(c, 1.0)).astype(np.float32)
        s[:, 40] += 3.0
        c[:, 40] += 3.0
        out = D.damage_zone_texture(s, c, coherence_px=9, min_coh=5)
        self.assertGreater(float(out[:, 40].max()), 0.0)
        self.assertGreater(float(out[:, 40].sum()), float(out[:, 10].sum()))

    def test_nan_coverage_is_not_invented(self):
        s = np.full((60, 60), np.nan, dtype=np.float32)
        c = np.full((60, 60), np.nan, dtype=np.float32)
        s[:, 30] = 1.0
        c[:, 30] = 1.0
        out = D.damage_zone_texture(s, c)
        self.assertTrue(np.all(np.isfinite(out)))
        self.assertEqual(float(out[0, 0]), 0.0)


class TestLidarScarpComposite(unittest.TestCase):
    def _channels(self, shape=(80, 80)):
        rng = np.random.default_rng(5)
        base = {k: np.abs(rng.normal(scale=0.1, size=shape)).astype(np.float32)
                for k in ("step_max", "ex_max", "ex_mean", "lapneg_max",
                          "lappos_max", "upface_max")}
        for k in base:
            base[k][:, 40] += 1.0
        return base

    def test_missing_channel_raises(self):
        with self.assertRaises(KeyError):
            D.lidar_scarp_composite({"step_max": np.zeros((10, 10), np.float32)})

    def test_detects_paired_scarp_line(self):
        out = D.lidar_scarp_composite(self._channels(), coherence_px=9, min_coh=4)
        self.assertEqual(out.dtype, np.float32)
        self.assertGreater(float(out[:, 40].sum()), float(out[:, 12].sum()))

    def test_upface_switch_changes_output(self):
        ch = self._channels()
        a = D.lidar_scarp_composite(ch, use_upface=True)
        b = D.lidar_scarp_composite(ch, use_upface=False)
        self.assertFalse(np.allclose(a, b))

    def test_no_coverage_returns_zeros(self):
        ch = {k: np.full((40, 40), np.nan, dtype=np.float32)
              for k in ("step_max", "ex_max", "lapneg_max", "lappos_max")}
        out = D.lidar_scarp_composite(ch)
        self.assertEqual(float(np.abs(out).max()), 0.0)


class TestAlterationRatioLineaments(unittest.TestCase):
    def test_linear_alteration_zone_detected(self):
        rng = np.random.default_rng(9)
        uk = rng.normal(scale=0.02, size=(80, 80)).astype(np.float32)
        uth = rng.normal(scale=0.02, size=(80, 80)).astype(np.float32)
        uk[:, 40] += 0.5
        uth[:, 40] += 0.5
        out = D.alteration_ratio_lineaments(uk, uth, sigma_px=8.0)
        self.assertGreater(float(out[:, 40].sum()), float(out[:, 15].sum()))

    def test_requires_both_ratios(self):
        rng = np.random.default_rng(9)
        uk = rng.normal(scale=0.02, size=(80, 80)).astype(np.float32)
        uth = np.zeros((80, 80), dtype=np.float32)   # no anomaly in U/Th
        uk[:, 40] += 0.5
        out = D.alteration_ratio_lineaments(uk, uth, sigma_px=8.0)
        self.assertEqual(float(out.max()), 0.0)


class TestVentConjunction(unittest.TestCase):
    @staticmethod
    def _varied(seed, shape=(40, 40)):
        rng = np.random.default_rng(seed)
        yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
        return (0.1 * xx + 0.05 * yy
                + rng.normal(scale=0.3, size=shape)).astype(np.float32)

    def test_geometric_mean_requires_all(self):
        # constant fields are degenerate for any percentile normaliser, so the
        # conjunction is tested on varied fields (documented in the loader).
        a, b, c, d = (self._varied(i) for i in range(4))
        z = np.zeros_like(a)
        all_present = D.vent_conjunction(a, b, c, d)
        one_missing = D.vent_conjunction(a, b, c, z)
        self.assertGreater(float(all_present.max()), float(one_missing.max()))

    def test_all_zero_field_returns_zero_map(self):
        a = self._varied(0)
        out = D.vent_conjunction(a, a, a, np.zeros_like(a))
        self.assertEqual(float(out.max()), 0.0)

    def test_nan_masks_output(self):
        a = self._varied(1)
        b = a.copy()
        b[:10, :] = np.nan
        out = D.vent_conjunction(a, a, a, b, require_all=True)
        self.assertEqual(float(out[:10, :].max()), 0.0)
        self.assertGreater(float(out[20, 20]), 0.0)

    def test_sparse_inputs_are_not_silently_zeroed(self):
        # regression: robust_norm returns all-zeros on sparse fields, which used
        # to wipe the crest-map inputs of the conjunction.
        sparse = np.zeros((40, 40), dtype=np.float32)
        sparse[:, 20] = np.linspace(0.1, 1.0, 40).astype(np.float32)
        dense = self._varied(2)
        out = D.vent_conjunction(sparse, dense, dense, dense)
        self.assertGreater(float(out[:, 20].max()), 0.0)


@unittest.skipUnless((X.EXT_DIR / X.TOPO).exists(),
                     "data/external not staged (scripts/fetch_external_data.py)")
class TestExternalLoader(unittest.TestCase):
    def test_all_products_match_competition_grid(self):
        for f, present in X.available().items():
            if present:
                self.assertTrue(X.grid_matches_competition(f), f)

    def test_dequantisation_uses_pinned_limits(self):
        prov = X._prov(X.RAD)
        lims = {b["band_name"]: (b["lo"], b["hi"]) for b in prov["bands"]}
        for ch, (lo, hi) in lims.items():
            a = X.read_channel(X.RAD, ch)
            fin = np.isfinite(a)
            self.assertGreaterEqual(float(a[fin].min()), lo - 1e-4)
            self.assertLessEqual(float(a[fin].max()), hi + 1e-4)

    def test_lidar_sqrt_inversion_roundtrip(self):
        prov = X._prov(X.LIDAR)
        xmax, kind = prov["quantisation"]["step_max"]
        self.assertEqual(kind, "sqrt")
        q = np.array([0, 1, 64, 128, 255], dtype=np.uint8)
        v = X._sqrt_from_xmax(q, float(xmax))
        self.assertTrue(np.isnan(v[0]))
        self.assertAlmostEqual(float(v[1]), 0.0, places=6)
        self.assertAlmostEqual(float(v[-1]), float(xmax), delta=xmax / 254.0)

    def test_nodata_is_nan_not_zero(self):
        a = X.read_channel(X.LIDAR, "step_max")
        raw = X.read_raw(X.LIDAR, "step_max")
        self.assertTrue(np.isnan(a[raw == 0]).all())
        self.assertTrue(np.isfinite(a[raw > 0]).all())


if __name__ == "__main__":
    unittest.main()
