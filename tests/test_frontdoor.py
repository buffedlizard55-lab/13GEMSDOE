"""Front-door tests: the pair of files a person uploads must be verifiably correct.

Run: python -m unittest discover -s tests
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
from gems import frontdoor, rio  # noqa: E402


class FrontDoorSynthetic(unittest.TestCase):
    def setUp(self) -> None:
        self.shape = (40, 50)
        for target, value in (("EXPECTED_SHAPE", self.shape),):
            p = patch.object(rio, target, value)
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

    def test_pair_is_written_and_verified(self) -> None:
        m = self.publish()
        a, b = self.out / m["primary_A"]["file"], self.out / m["fallback_B"]["file"]
        with rasterio.open(a) as s:
            arr_a = s.read(1)
            self.assertIsNone(s.nodata)
            st = s.tags(ns="IMAGE_STRUCTURE")
        self.assertEqual(st["COMPRESSION"], "LZW")
        self.assertNotIn("PREDICTOR", st)          # I-18: no float predictor
        self.assertEqual(int(np.isnan(arr_a).sum()), 0)
        self.assertTrue(np.all(arr_a[~self.valid] == 0.0))
        with rasterio.open(b) as s:
            arr_b = s.read(1)
            self.assertTrue(np.isnan(s.nodata))
        self.assertTrue(np.all(np.isnan(arr_b[~self.valid])))
        np.testing.assert_array_equal(arr_a[self.valid], arr_b[self.valid])

    def test_zip_contains_exactly_the_tif(self) -> None:
        m = self.publish()
        with zipfile.ZipFile(self.out / m["primary_A"]["zip"]) as z:
            self.assertEqual(z.namelist(), [m["primary_A"]["file"]])
            self.assertEqual(z.read(m["primary_A"]["file"]),
                             (self.out / m["primary_A"]["file"]).read_bytes())

    def test_latest_aliases_point_at_A_not_the_nan_file(self) -> None:
        m = self.publish()
        self.assertEqual((self.out / "latest.tif").read_bytes(),
                         (self.out / m["primary_A"]["file"]).read_bytes())
        self.assertEqual((self.out / "latest_nan.tif").read_bytes(),
                         (self.out / m["fallback_B"]["file"]).read_bytes())
        with rasterio.open(self.out / "latest.tif") as s:
            self.assertFalse(np.isnan(s.read(1)).any())     # I-19 regression

    def test_manifest_hashes_match_disk(self) -> None:
        m = self.publish()
        saved = json.loads((self.out / "submit.json").read_text())
        for k in ("primary_A", "fallback_B"):
            self.assertEqual(saved[k]["sha256"],
                             frontdoor.sha256_file(self.out / saved[k]["file"]))
        self.assertEqual(saved, json.loads(json.dumps(m)))

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

    def test_bad_stem_rejected(self) -> None:
        with self.assertRaises(ValueError):
            frontdoor.publish(self.out, "bad name.tif", self.pred, self.valid,
                              note="n", source={}, status={})


class RepoState(unittest.TestCase):
    """The committed download must be the verified pair (skips if not present)."""

    def test_committed_manifest_matches_files(self) -> None:
        mp = ROOT / "docs" / "downloads" / "submit.json"
        if not mp.exists():
            self.skipTest("no submit.json")
        m = json.loads(mp.read_text())
        dl = mp.parent
        for k in ("primary_A", "fallback_B"):
            self.assertEqual(frontdoor.sha256_file(dl / m[k]["file"]), m[k]["sha256"])
            self.assertEqual(frontdoor.sha256_file(dl / m[k]["zip"]), m[k]["zip_sha256"])
        self.assertEqual((dl / "latest.tif").read_bytes(), (dl / m["primary_A"]["file"]).read_bytes())
        with rasterio.open(dl / "latest.tif") as s:
            a = s.read(1)
        self.assertEqual(int(np.isnan(a).sum()), 0)
        self.assertTrue(((a >= 0) & (a <= 1)).all())


if __name__ == "__main__":
    unittest.main()
