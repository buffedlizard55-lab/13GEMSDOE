"""Local encoding-policy tests; none can establish platform acceptance.

Ignored-Predictor2 arithmetic is a hypothetical reader test, not a causal claim.
Historical TIFF score labels are distinct from platform receipts.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import encoding, rio  # noqa: E402

RAW = ROOT / "data" / "raw"
SCORED = ROOT / "data" / "scored"


def template_path() -> Path | None:
    for n in ("sample_submission.tif", "example_submission.tif"):
        if (RAW / n).exists():
            return RAW / n
    return None


def labels_path() -> Path | None:
    for n in ("labels.tif", "existing_faults.tif"):
        if (RAW / n).exists():
            return RAW / n
    return None


class HypotheticalPredictorTwoFailure(unittest.TestCase):
    """Test our interoperability exclusion without attributing server behavior."""

    def test_ignored_predictor2_decode_leaves_the_0_1_range(self) -> None:
        a = np.zeros((6, 8), np.float32)
        a[:, ::2] = 1.0            # a binary map, every value legal
        sim = encoding.simulate_ignored_predictor2(a)
        self.assertFalse(sim["all_in_0_1"])
        self.assertLess(sim["decoded_min"], 0.0)
        self.assertLess(sim["fraction_in_0_1"], 1.0)

    def test_predictor2_is_flagged_as_a_deviation(self) -> None:
        rep = {"profile": {"dtype": "float32", "count": 1, "crs": "EPSG:32611",
                           "shape": list(encoding.EXPECTED_SHAPE),
                           "transform": list(encoding.EXPECTED_TRANSFORM),
                           "nodata": "nan"},
               "layout": {"predictor": 2, "sample_format": 3, "bits_per_sample": 32},
               "placement": {"n_nan_inside_footprint": 0, "n_finite_outside_footprint": 0,
                             "n_nan_outside_footprint": encoding.OUTSIDE_PIXELS,
                             "finite_min": 0.0, "finite_max": 1.0}}
        ok, dev = encoding.accepted_pattern(rep)
        self.assertFalse(ok)
        self.assertTrue(any("Predictor=2" in d for d in dev))

    def test_predictor3_and_none_are_not_flagged(self) -> None:
        base = {"profile": {"dtype": "float32", "count": 1, "crs": "EPSG:32611",
                            "shape": list(encoding.EXPECTED_SHAPE),
                            "transform": list(encoding.EXPECTED_TRANSFORM),
                            "nodata": "nan"},
                "layout": {"predictor": 1, "sample_format": 3, "bits_per_sample": 32},
                "placement": {"n_nan_inside_footprint": 0,
                              "n_finite_outside_footprint": 0,
                              "n_nan_outside_footprint": encoding.OUTSIDE_PIXELS,
                              "finite_min": 0.0, "finite_max": 1.0}}
        for pred in (1, 3, None):
            rep = dict(base)
            rep["layout"] = dict(base["layout"], predictor=pred)
            ok, dev = encoding.accepted_pattern(rep)
            self.assertTrue(ok, f"predictor={pred} flagged: {dev}")

    def test_zero_fill_is_flagged_as_a_deviation(self) -> None:
        rep = {"profile": {"dtype": "float32", "count": 1, "crs": "EPSG:32611",
                           "shape": list(encoding.EXPECTED_SHAPE),
                           "transform": list(encoding.EXPECTED_TRANSFORM),
                           "nodata": None},
               "layout": {"predictor": 1, "sample_format": 3, "bits_per_sample": 32},
               "placement": {"n_nan_inside_footprint": 0,
                             "n_finite_outside_footprint": encoding.OUTSIDE_PIXELS,
                             "n_nan_outside_footprint": 0,
                             "finite_min": 0.0, "finite_max": 1.0}}
        ok, dev = encoding.accepted_pattern(rep)
        self.assertFalse(ok)
        self.assertTrue(any("nodata" in d for d in dev))
        self.assertTrue(any("outside the footprint" in d for d in dev))

    def test_nan_inside_footprint_is_flagged(self) -> None:
        rep = {"profile": {"dtype": "float32", "count": 1, "crs": "EPSG:32611",
                           "shape": list(encoding.EXPECTED_SHAPE),
                           "transform": list(encoding.EXPECTED_TRANSFORM),
                           "nodata": "nan"},
               "layout": {"predictor": 1, "sample_format": 3, "bits_per_sample": 32},
               "placement": {"n_nan_inside_footprint": 3061,
                             "n_finite_outside_footprint": 0,
                             "n_nan_outside_footprint": encoding.OUTSIDE_PIXELS,
                             "finite_min": 0.0, "finite_max": 1.0}}
        ok, dev = encoding.accepted_pattern(rep)
        self.assertFalse(ok)
        self.assertTrue(any("inside the footprint" in d for d in dev))


class WriterNeverEmitsAPredictor(unittest.TestCase):
    def test_write_submission_layout(self) -> None:
        shape = (40, 50)
        valid = np.ones(shape, bool)
        valid[:5, :] = False
        pred = np.zeros(shape, np.float32)
        pred[20, 10:30] = 1.0
        with tempfile.TemporaryDirectory() as d:
            for outside, want_nodata in ((None, True), (0.0, False)):
                p = Path(d) / f"out_{'nan' if outside is None else 'zero'}.tif"
                from unittest.mock import patch
                with patch.object(rio, "EXPECTED_SHAPE", shape):
                    rio.write_submission(p, pred, valid, outside_value=outside)
                lay = encoding.read_layout(p)["layout"]
                self.assertNotEqual(lay["predictor"], encoding.PREDICTOR_HORIZONTAL)
                self.assertEqual(lay["compression"], "LZW")
                self.assertFalse(lay["tiled"])
                with rasterio.open(p) as s:
                    nd = s.nodata
                    self.assertEqual(bool(nd is not None and np.isnan(nd)), want_nodata)


@unittest.skipUnless(template_path() is not None,
                     "data/raw/sample_submission.tif absent (bash "
                     "scripts/download_competition_data.sh --small)")
class OfficialTemplate(unittest.TestCase):
    def setUp(self) -> None:
        self.t = template_path()
        with rasterio.open(self.t) as s:
            self.arr = s.read(1)
        self.footprint = np.isfinite(self.arr)

    def test_pins(self) -> None:
        import hashlib
        h = hashlib.sha256(self.t.read_bytes()).hexdigest()
        self.assertEqual(h, encoding.SAMPLE_SUBMISSION_SHA256)

    def test_grid_constants(self) -> None:
        with rasterio.open(self.t) as s:
            self.assertEqual(str(s.crs), encoding.EXPECTED_CRS)
            self.assertEqual(tuple(s.shape), encoding.EXPECTED_SHAPE)
            self.assertEqual(tuple(round(v, 6) for v in tuple(s.transform)[:6]),
                             encoding.EXPECTED_TRANSFORM)
            self.assertEqual(s.dtypes[0], "float32")
            self.assertEqual(s.count, 1)
            self.assertTrue(np.isnan(s.nodata))

    def test_footprint_counts(self) -> None:
        self.assertEqual(int(self.footprint.sum()), encoding.FOOTPRINT_PIXELS)
        self.assertEqual(int((~self.footprint).sum()), encoding.OUTSIDE_PIXELS)

    def test_template_matches_the_accepted_pattern(self) -> None:
        rep = encoding.audit_file(self.t, self.footprint)
        self.assertTrue(rep["matches_accepted_pattern"],
                        rep["deviations_from_accepted_pattern"])

    def test_template_layout_is_lzw_striped_no_predictor(self) -> None:
        lay = encoding.read_layout(self.t)["layout"]
        self.assertEqual(lay["compression"], "LZW")
        self.assertEqual(lay["predictor"], encoding.PREDICTOR_NONE)
        self.assertEqual(lay["sample_format"], 3)
        self.assertEqual(lay["bits_per_sample"], 32)
        self.assertFalse(lay["tiled"])

    @unittest.skipUnless(labels_path() is not None, "labels raster absent")
    def test_footprint_equals_labels_ge_zero(self) -> None:
        with rasterio.open(labels_path()) as s:
            lab = s.read(1)
        self.assertTrue(np.array_equal(self.footprint, lab >= 0))


@unittest.skipUnless(bool(sorted(SCORED.glob("*.tif"))),
                     "data/scored absent (python scripts/fetch_data.py)")
class HistoricalScoreLabelledFiles(unittest.TestCase):
    """Check encoding of each obtained historical TIFF; score attribution unknown."""

    def setUp(self) -> None:
        t = template_path()
        if t is None:
            self.skipTest("official template absent")
        with rasterio.open(t) as s:
            self.footprint = np.isfinite(s.read(1))
        self.files = sorted(SCORED.glob("*.tif"))

    def test_nan_outside_files_all_match_the_accepted_pattern(self) -> None:
        matching, nonmatching = [], []
        for f in self.files:
            rep = encoding.audit_file(f, self.footprint)
            (matching if rep["matches_accepted_pattern"] else nonmatching).append(rep)
        self.assertTrue(matching, "no obtained NaN-outside historical TIFF matches template policy")
        for rep in matching:
            self.assertEqual(rep["placement"]["n_nan_outside_footprint"],
                             encoding.OUTSIDE_PIXELS)
            self.assertEqual(rep["placement"]["n_nan_inside_footprint"], 0)
            self.assertEqual(rep["placement"]["n_finite_outside_footprint"], 0)
            self.assertNotEqual(rep["layout"]["predictor"],
                                encoding.PREDICTOR_HORIZONTAL)
        # the only permitted deviation is the all-finite twin, which shares a
        # recorded score with its NaN-outside sibling and so has no
        # independent acceptance receipt
        for rep in nonmatching:
            self.assertEqual(rep["placement"]["n_nan_total"], 0,
                             f"{rep['file']} deviates for a reason other than zero-fill")

    def test_no_scored_file_uses_predictor_2(self) -> None:
        for f in self.files:
            lay = encoding.read_layout(f)["layout"]
            self.assertNotEqual(lay["predictor"], encoding.PREDICTOR_HORIZONTAL,
                                f"{f.name} uses Predictor=2")


@unittest.skipUnless((ROOT / "docs" / "downloads" / "archive"
                      / "13gems-r11-greedy-mp.tif").exists(),
                     "the rejected artifact is not present")
class TheRejectedFile(unittest.TestCase):
    def setUp(self) -> None:
        t = template_path()
        if t is None:
            self.skipTest("official template absent")
        with rasterio.open(t) as s:
            self.footprint = np.isfinite(s.read(1))
        self.p = ROOT / "docs" / "downloads" / "archive" / "13gems-r11-greedy-mp.tif"

    def test_its_only_deviation_is_predictor_2(self) -> None:
        rep = encoding.audit_file(self.p, self.footprint)
        self.assertEqual(rep["layout"]["predictor"], encoding.PREDICTOR_HORIZONTAL)
        self.assertEqual(rep["placement"]["n_nan_inside_footprint"], 0)
        self.assertEqual(rep["placement"]["n_finite_outside_footprint"], 0)
        self.assertEqual(rep["placement"]["n_nan_outside_footprint"],
                         encoding.OUTSIDE_PIXELS)
        self.assertTrue(rep["range_checks"]["nan_aware_all_in_0_1"])
        self.assertEqual(rep["deviations_from_accepted_pattern"],
                         ["Predictor=2 (horizontal differencing) on IEEE-float "
                          "samples; excluded by our interoperability policy, not a diagnosed server cause"])

    def test_rejected_nan_placement_matches_template_without_causal_inference(self) -> None:
        """Placement equality is local evidence; it does not observe server handling."""
        rep = encoding.audit_file(self.p, self.footprint)
        t = template_path()
        self.assertIsNotNone(t)
        tmpl = encoding.audit_file(t, self.footprint)
        self.assertEqual(rep["placement"]["n_nan_total"], tmpl["placement"]["n_nan_total"])
        self.assertEqual(rep["profile"]["nodata"], tmpl["profile"]["nodata"])


if __name__ == "__main__":
    unittest.main()
