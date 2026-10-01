"""Front-door tests: the pair of files a person uploads must be verifiably correct.

The roles were corrected on 2026-10-01 (schema 2): PRIMARY is the NaN-outside
file (the encoding of the official sample_submission.tif and of all nine
platform-scored group files); HEDGE is the NaN-free zero-filled twin.  The
tests below assert the corrected roles, so the I-19 class of bug -- an alias or
a button quietly pointing at the wrong encoding -- cannot come back.

Run: python -m pytest tests/test_frontdoor.py -q
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import encoding, frontdoor, rio  # noqa: E402


class FrontDoorSynthetic(unittest.TestCase):
    def setUp(self) -> None:
        self.shape = (40, 50)
        p = patch.object(rio, "EXPECTED_SHAPE", self.shape)
        p.start()
        self.addCleanup(p.stop)
        self.valid = np.ones(self.shape, bool)
        self.valid[:5, :] = False            # outside the survey footprint
        self.pred = np.zeros(self.shape, np.float32)
        self.pred[20, 10:30] = 1.0
        self.pred[30, 5] = 0.5
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)

    def publish(self, **kw):
        return frontdoor.publish(self.out, "t_stem", self.pred, self.valid,
                                 note=kw.get("note", "short note"), source={}, status={})

    # --- roles ------------------------------------------------------------
    def test_primary_is_the_nan_outside_file(self) -> None:
        m = self.publish()
        self.assertTrue(m["primary"]["file"].endswith("_nan-outside.tif"))
        self.assertTrue(m["hedge"]["file"].endswith("_zerofill.tif"))
        with rasterio.open(self.out / m["primary"]["file"]) as s:
            arr = s.read(1)
            self.assertTrue(np.isnan(s.nodata), "PRIMARY must declare NoData=nan")
            st = s.tags(ns="IMAGE_STRUCTURE")
        self.assertEqual(st["COMPRESSION"], "LZW")
        self.assertNotIn("PREDICTOR", st)     # I-18/I-22: never a float predictor
        self.assertTrue(np.all(np.isnan(arr[~self.valid])))
        self.assertEqual(int(np.isnan(arr[self.valid]).sum()), 0)
        self.assertTrue(((arr[self.valid] >= 0) & (arr[self.valid] <= 1)).all())

    def test_hedge_is_the_nan_free_twin(self) -> None:
        m = self.publish()
        with rasterio.open(self.out / m["hedge"]["file"]) as s:
            arr = s.read(1)
            self.assertIsNone(s.nodata)
        self.assertEqual(int(np.isnan(arr).sum()), 0)
        self.assertTrue(np.all(arr[~self.valid] == 0.0))
        self.assertTrue(((arr >= 0) & (arr <= 1)).all())   # naive range test

    def test_primary_and_hedge_agree_inside_the_footprint(self) -> None:
        m = self.publish()
        with rasterio.open(self.out / m["primary"]["file"]) as s:
            a = s.read(1)
        with rasterio.open(self.out / m["hedge"]["file"]) as s:
            b = s.read(1)
        np.testing.assert_array_equal(a[self.valid], b[self.valid])

    # --- packaging --------------------------------------------------------
    def test_zip_contains_exactly_the_tif(self) -> None:
        m = self.publish()
        for key in ("primary", "hedge"):
            with zipfile.ZipFile(self.out / m[key]["zip"]) as z:
                self.assertEqual(z.namelist(), [m[key]["file"]])
                self.assertEqual(z.read(m[key]["file"]),
                                 (self.out / m[key]["file"]).read_bytes())

    def test_latest_aliases_point_at_the_primary(self) -> None:
        m = self.publish()
        self.assertEqual((self.out / "latest.tif").read_bytes(),
                         (self.out / m["primary"]["file"]).read_bytes())
        self.assertEqual((self.out / "latest.zip").read_bytes(),
                         (self.out / m["primary"]["zip"]).read_bytes())
        self.assertEqual((self.out / "latest_zerofill.tif").read_bytes(),
                         (self.out / m["hedge"]["file"]).read_bytes())
        with rasterio.open(self.out / "latest.tif") as s:
            self.assertTrue(np.isnan(s.nodata))   # latest.* IS the nan-outside file

    def test_retired_aliases_are_removed(self) -> None:
        for dead in frontdoor.RETIRED_ALIASES:
            (self.out / dead).write_bytes(b"stale")
        self.publish()
        for dead in frontdoor.RETIRED_ALIASES:
            self.assertFalse((self.out / dead).exists(), f"{dead} should be gone")

    def test_manifest_hashes_match_disk(self) -> None:
        m = self.publish()
        saved = json.loads((self.out / "submit.json").read_text())
        self.assertEqual(saved["schema"], 2)
        for k in ("primary", "hedge"):
            self.assertEqual(saved[k]["sha256"],
                             frontdoor.sha256_file(self.out / saved[k]["file"]))
            self.assertEqual(saved[k]["zip_sha256"],
                             frontdoor.sha256_file(self.out / saved[k]["zip"]))
        self.assertEqual(saved, json.loads(json.dumps(m)))

    # --- refusals ---------------------------------------------------------
    def test_names_are_immutable(self) -> None:
        self.publish()
        with self.assertRaises(FileExistsError):
            self.publish()

    def test_note_must_be_one_short_line(self) -> None:
        with self.assertRaises(ValueError):
            self.publish(note="x" * (frontdoor.MAX_NOTE_CHARS + 1))
        with self.assertRaises(ValueError):
            self.publish(note="two\nlines")

    def test_refuses_nan_inside_footprint(self) -> None:
        self.pred[20, 20] = np.nan
        with self.assertRaises(ValueError):
            self.publish()
        self.assertFalse(list(self.out.glob("*.tif")))

    def test_refuses_out_of_range(self) -> None:
        self.pred[20, 20] = 1.0001
        with self.assertRaises(ValueError):
            self.publish()

    def test_refuses_float_sentinel_inside_footprint(self) -> None:
        # the float32 most-negative sentinel is what training_features.tif uses
        # for missing data; if it reaches a submission the platform answers
        # "Predicted values must be in range [0, 1]"
        self.pred[20, 20] = np.float32(-3.4028235e38)
        with self.assertRaises(ValueError):
            self.publish()

    def test_bad_stem_rejected(self) -> None:
        with self.assertRaises(ValueError):
            frontdoor.publish(self.out, "bad name.tif", self.pred, self.valid,
                              note="n", source={}, status={})


class RepoState(unittest.TestCase):
    """The committed download must be the verified pair (skips if not present)."""

    def setUp(self) -> None:
        self.mp = ROOT / "docs" / "downloads" / "submit.json"
        if not self.mp.exists():
            self.skipTest("no submit.json")
        self.m = json.loads(self.mp.read_text())
        self.dl = self.mp.parent

    def test_manifest_is_schema_2_with_primary_and_hedge(self) -> None:
        self.assertEqual(self.m["schema"], 2)
        self.assertIn("primary", self.m)
        self.assertIn("hedge", self.m)
        self.assertNotIn("primary_A", self.m)
        self.assertNotIn("fallback_B", self.m)

    def test_committed_manifest_matches_files(self) -> None:
        for k in ("primary", "hedge"):
            self.assertEqual(frontdoor.sha256_file(self.dl / self.m[k]["file"]),
                             self.m[k]["sha256"])
            self.assertEqual(frontdoor.sha256_file(self.dl / self.m[k]["zip"]),
                             self.m[k]["zip_sha256"])

    def test_committed_primary_is_nan_outside(self) -> None:
        with rasterio.open(self.dl / self.m["primary"]["file"]) as s:
            a = s.read(1)
            self.assertTrue(np.isnan(s.nodata))
        self.assertEqual(int(np.isnan(a).sum()), encoding.OUTSIDE_PIXELS)
        fin = a[np.isfinite(a)]
        self.assertTrue(((fin >= 0) & (fin <= 1)).all())

    def test_latest_alias_is_the_primary(self) -> None:
        self.assertEqual((self.dl / "latest.tif").read_bytes(),
                         (self.dl / self.m["primary"]["file"]).read_bytes())

    def test_retired_aliases_absent_from_the_repo(self) -> None:
        for dead in frontdoor.RETIRED_ALIASES:
            self.assertFalse((self.dl / dead).exists(),
                             f"{dead} must not exist: it inverts the roles (I-19)")

    def test_no_shipped_file_uses_predictor_2(self) -> None:
        for tif in sorted(self.dl.glob("*.tif")):
            lay = encoding.read_layout(tif)["layout"]
            self.assertNotEqual(lay["predictor"], encoding.PREDICTOR_HORIZONTAL,
                                f"{tif.name} uses Predictor=2 -- the sole deviation "
                                "of the one file the form rejected")


if __name__ == "__main__":
    unittest.main()
