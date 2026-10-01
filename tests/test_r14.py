"""Tests for the R14/R15 additions: tip folds, propagation operators, tie-breaking.

Run: python -m pytest tests/test_r14.py -q
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import propagation as P          # noqa: E402
from gems.holdout import tip_fold, tip_folds, trace_endpoints  # noqa: E402


def synthetic_catalogue(shape=(120, 160)) -> tuple[np.ndarray, np.ndarray]:
    """Two straight 1-px traces, 40 px and 30 px long, plus a short 8-px one."""
    valid = np.ones(shape, bool)
    valid[:5, :] = False
    known = np.zeros(shape, bool)
    known[30, 20:60] = True          # 40 px, due east
    known[70:100, 100] = True        # 30 px, due south
    known[110, 10:18] = True         # 8 px, too short for min_len=20
    return valid, known


class TraceEndpoints(unittest.TestCase):
    def test_endpoints_of_straight_traces(self) -> None:
        _, known = synthetic_catalogue()
        eps = trace_endpoints(known)
        self.assertEqual(int(eps.sum()), 6)          # two ends per trace
        self.assertTrue(eps[30, 20] and eps[30, 59])
        self.assertTrue(eps[70, 100] and eps[99, 100])

    def test_interior_pixels_are_not_endpoints(self) -> None:
        _, known = synthetic_catalogue()
        eps = trace_endpoints(known)
        self.assertFalse(eps[30, 40])


class TipFold(unittest.TestCase):
    def test_hidden_is_the_trace_tip_and_stays_inside_the_catalogue(self) -> None:
        valid, known = synthetic_catalogue()
        f = tip_fold(known, valid, tip_len=5, name="t", min_len=20)
        self.assertTrue((f.hidden <= known).all())
        # the seeds are the endpoints themselves and the walk adds tip_len more
        self.assertEqual(f.n_hidden, 4 * (1 + 5))    # 4 tips, endpoint + 5 px
        self.assertTrue(f.hidden[30, 20] and f.hidden[30, 25])
        self.assertFalse(f.hidden[30, 26])

    def test_every_catalogue_pixel_is_either_hidden_or_visible(self) -> None:
        valid, known = synthetic_catalogue()
        for tl in (3, 8, 32):
            f = tip_fold(known, valid, tip_len=tl, name=f"t{tl}", min_len=20)
            self.assertEqual(f.meta["known_px_accounted"], int(known.sum()))
            self.assertEqual(int((f.hidden & f.visible).sum()), 0)

    def test_short_segments_are_not_tipped(self) -> None:
        valid, known = synthetic_catalogue()
        f = tip_fold(known, valid, tip_len=5, name="t", min_len=20)
        self.assertFalse(f.hidden[110, 10:18].any())

    def test_hidden_abuts_visible_no_link_px_gap(self) -> None:
        """The whole point of the rule (I-24): hidden truth is 1 px from visible."""
        valid, known = synthetic_catalogue()
        f = tip_fold(known, valid, tip_len=5, name="t", min_len=20)
        d = ndi.distance_transform_edt(~f.visible)
        # a tip_len walk leaves the farthest withheld pixel tip_len+1 from visible
        self.assertLessEqual(float(d[f.hidden].max()), 6.0)
        self.assertLess(float(d[f.hidden].min()), 2.0)
        # ... which is 3-5x INSIDE the metric's 300 m kernel, unlike the
        # pre-existing rules where nothing hidden is within ~16 px of anything
        # visible (I-24)
        self.assertLess(float(d[f.hidden].max()), 16.0)

    def test_eval_mask_excludes_the_visible_catalogue(self) -> None:
        valid, known = synthetic_catalogue()
        f = tip_fold(known, valid, tip_len=5, name="t", min_len=20)
        self.assertEqual(int((f.eval_mask & f.visible).sum()), 0)
        self.assertTrue(f.eval_mask[f.hidden].all())

    def test_tip_folds_are_deterministic_and_account_for_everything(self) -> None:
        valid, known = synthetic_catalogue()
        a = tip_folds(known, valid, tip_lens=(4,), seeds=(1, 2), min_len=20)
        b = tip_folds(known, valid, tip_lens=(4,), seeds=(1, 2), min_len=20)
        self.assertEqual(len(a), 2)
        for x, y in zip(a, b):
            np.testing.assert_array_equal(x.hidden, y.hidden)
            self.assertEqual(x.meta["known_px_accounted"], int(known.sum()))
        # a subsample must withhold strictly fewer pixels than the full set
        self.assertGreater(a[0].n_hidden, a[1].n_hidden)


class AlongStrikeTips(unittest.TestCase):
    def test_emission_is_off_catalogue_and_points_along_the_trace(self) -> None:
        valid, known = synthetic_catalogue()
        vis = known.copy()
        vis[30, 55:60] = False        # hide the east tip so the ribbon has room
        out = P.along_strike_tips(vis, length_px=8)
        self.assertEqual(float(out[vis].max()), 0.0)          # never on the catalogue
        self.assertGreater(float(out.max()), 0.0)
        # the ribbon must extend EAST from (30, 54), not north/south
        self.assertGreater(out[30, 60], 0.0)
        self.assertEqual(out[24, 60], 0.0)
        self.assertEqual(out[36, 60], 0.0)

    def test_amplitude_tapers_with_distance(self) -> None:
        valid, known = synthetic_catalogue()
        vis = known.copy()
        vis[30, 55:60] = False
        out = P.along_strike_tips(vis, length_px=10)
        self.assertGreater(out[30, 58], out[30, 62])
        self.assertGreater(out[30, 62], out[30, 66])

    def test_zero_length_gives_nothing(self) -> None:
        valid, known = synthetic_catalogue()
        out = P.along_strike_tips(known, length_px=0)
        self.assertEqual(float(out.sum()), 0.0)


class IsotropicHalo(unittest.TestCase):
    def test_zero_on_catalogue_and_decreasing_with_distance(self) -> None:
        _, known = synthetic_catalogue()
        h = P.isotropic_halo(known)
        self.assertEqual(float(h[known].max()), 0.0)
        d = ndi.distance_transform_edt(~known)
        near = h[(d == 1)]
        far = h[(d == 6)]
        self.assertGreater(float(near.min()), float(far.max()))


class TieBreaking(unittest.TestCase):
    """I-14: a top-K over a massively tied field must not select by position."""

    @staticmethod
    def _row_deciles(sel: np.ndarray, bins: int = 10) -> np.ndarray:
        rows = np.nonzero(sel)[0]
        return np.histogram(rows, bins=bins, range=(0, sel.shape[0]))[0]

    def test_without_jitter_the_tie_is_resolved_positionally(self) -> None:
        """Measured, not asserted: on a fully tied field a bare argpartition put
        959 of 1000 selected pixels in the FIRST row decile -- the northernmost
        slice of the study area. That is irregularity I-14, and it is why the
        first run of the R14 experiment is void."""
        shape = (100, 100)
        allowed = np.ones(shape, bool)
        field = np.ones(shape, np.float64)          # one enormous tie
        sel = P.budget_from_intensity(field, allowed, 1000) > 0
        dec = self._row_deciles(sel)
        self.assertEqual(int(sel.sum()), 1000)
        self.assertGreater(dec[0], 500)             # concentrated in the north
        self.assertEqual(int((dec == 0).sum()), 7)  # most of the area never sampled

    def test_without_jitter_a_partially_tied_field_is_also_position_biased(self) -> None:
        shape = (100, 100)
        allowed = np.ones(shape, bool)
        field = np.ones(shape, np.float64)
        field[:50, :] = 2.0                          # a distinct top block + a tie
        sel = P.budget_from_intensity(field, allowed, 1000) > 0
        dec = self._row_deciles(sel)
        self.assertGreater(dec[0], 500)

    def test_with_jitter_selection_is_spread_over_the_whole_field(self) -> None:
        shape = (100, 100)
        allowed = np.ones(shape, bool)
        field = np.ones(shape, np.float64)
        j = P.make_jitter(shape)
        sel = P.budget_from_intensity(field, allowed, 1000, jitter=j) > 0
        dec = self._row_deciles(sel)
        self.assertEqual(int(sel.sum()), 1000)
        self.assertTrue((dec > 0).all())             # every band sampled
        self.assertLess(int(dec.max() - dec.min()), 100)   # ~uniform

    def test_jitter_is_deterministic_and_never_reorders_real_differences(self) -> None:
        shape = (50, 50)
        j1, j2 = P.make_jitter(shape), P.make_jitter(shape)
        np.testing.assert_array_equal(j1, j2)
        allowed = np.ones(shape, bool)
        field = np.zeros(shape, np.float64)
        field[0, :10] = 5.0            # 10 genuinely best pixels
        sel = P.budget_from_intensity(field, allowed, 10, jitter=j1) > 0
        self.assertTrue(sel[0, :10].all())
        self.assertEqual(int(sel.sum()), 10)

    def test_tie_fraction_reports_the_pathology(self) -> None:
        shape = (50, 50)
        allowed = np.ones(shape, bool)
        self.assertGreater(P.tie_fraction(np.ones(shape), allowed), 0.99)
        self.assertLess(P.tie_fraction(np.arange(shape[0] * shape[1],
                                                 dtype=float).reshape(shape), allowed), 0.01)


class PrioritisedUnion(unittest.TestCase):
    def test_primary_pixels_are_never_displaced(self) -> None:
        shape = (40, 40)
        allowed = np.ones(shape, bool)
        prim = np.zeros(shape, bool)
        prim[5, 5:15] = True
        filler = np.zeros(shape, bool)
        filler[::2, ::2] = True
        filler[5, 5:15] = True          # overlaps the primary
        out = P.prioritised_union(prim, filler, allowed, 30,
                                  jitter=P.make_jitter(shape)) > 0
        self.assertTrue(out[5, 5:15].all())
        self.assertEqual(int(out.sum()), 30)

    def test_budget_is_respected_when_the_filler_is_large(self) -> None:
        shape = (60, 60)
        allowed = np.ones(shape, bool)
        out = P.prioritised_union(np.zeros(shape, bool), allowed, allowed, 500,
                                  jitter=P.make_jitter(shape)) > 0
        self.assertEqual(int(out.sum()), 500)

    def test_nothing_outside_allowed_is_selected(self) -> None:
        shape = (40, 40)
        allowed = np.zeros(shape, bool)
        allowed[10:, :] = True
        prim = np.zeros(shape, bool)
        prim[0:5, 0:5] = True           # entirely outside `allowed`
        out = P.prioritised_union(prim, allowed, allowed, 200,
                                  jitter=P.make_jitter(shape)) > 0
        self.assertTrue((out <= allowed).all())
        self.assertEqual(int((out & ~allowed).sum()), 0)


class Lattice(unittest.TestCase):
    def test_stride(self) -> None:
        m = P.square_lattice((100, 100), 5)
        self.assertEqual(int(m.sum()), 400)
        self.assertTrue(m[0, 0] and m[5, 5] and not m[1, 1])


if __name__ == "__main__":
    unittest.main()
