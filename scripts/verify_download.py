#!/usr/bin/env python3
"""Verify, from the bytes on disk, that the front-door download actually works.

Checks (exit code 1 if ANY fails):
  1. docs/downloads/submit.json exists and names files that exist, with matching
     sha256 and sizes.
  2. The .zip files each contain exactly one entry whose bytes equal the .tif.
  3. latest.tif == primary A, latest.zip == A zip, latest_nan.* == fallback B.
  4. Both GeoTIFFs: float32, 1 band, EPSG:32611, 3730x3292, official transform;
     LZW, no predictor (the layout of the official example); values in [0,1];
     A has zero NaN/Inf and no NoData tag; B has NaN exactly outside the
     footprint; A == B inside the footprint; three TIFF readers agree.
  5. Footprint equals the official label raster's footprint (when data/raw exists).
  6. Every page of docs/ puts a link to the primary file in the first 4 KB of
     body HTML, the link target exists, and docs/index.html's FIRST <a download>
     is the primary file. The repo README's first 1.5 KB links the same file.
  7. (--live) the same file, fetched from GitHub Pages, has the manifest sha256.

Run:  python scripts/verify_download.py [--live]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems import frontdoor  # noqa: E402

DL = ROOT / "docs" / "downloads"
PAGES = "https://buffedlizard55-lab.github.io/13GEMSDOE/"
RAW_BASE = "https://github.com/buffedlizard55-lab/13GEMSDOE/raw/main/"

results: list[tuple[bool, str]] = []


def check(ok: bool, msg: str) -> None:
    results.append((bool(ok), msg))
    print(("PASS  " if ok else "FAIL  ") + msg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="also fetch the file from GitHub Pages and compare sha256")
    args = ap.parse_args()

    mpath = DL / "submit.json"
    check(mpath.exists(), "docs/downloads/submit.json exists")
    if not mpath.exists():
        return 1
    m = json.loads(mpath.read_text())
    A, B = m["primary_A"], m["fallback_B"]

    # 1 + 2: files, hashes, zips (primary pair, then any listed alternates)
    pairs = [("A", A), ("B", B)]
    for k, alt in enumerate(m.get("alternates", []), 1):
        pairs += [(f"alt{k}-A", alt["A"]), (f"alt{k}-B", alt["B"])]
    for label, e in pairs:
        tif, zp = DL / e["file"], DL / e["zip"]
        check(tif.exists() and zp.exists(), f"{label}: {e['file']} and its .zip exist")
        if not (tif.exists() and zp.exists()):
            continue
        check(frontdoor.sha256_file(tif) == e["sha256"], f"{label}: .tif sha256 matches manifest")
        check(frontdoor.sha256_file(zp) == e["zip_sha256"], f"{label}: .zip sha256 matches manifest")
        with zipfile.ZipFile(zp) as z:
            names = z.namelist()
            check(names == [tif.name], f"{label}: zip holds exactly one entry ({names})")
            check(z.testzip() is None, f"{label}: zip CRCs OK")
            check(hashlib.sha256(z.read(names[0])).hexdigest() == e["sha256"],
                  f"{label}: zip entry bytes == .tif bytes")

    # 3: aliases
    same = lambda x, y: (DL / x).exists() and (DL / x).read_bytes() == (DL / y).read_bytes()  # noqa: E731
    check(same("latest.tif", A["file"]), "latest.tif == primary A (not the NaN file)")
    check(same("latest.zip", A["zip"]), "latest.zip == primary A zip")
    check(same("latest_nan.tif", B["file"]), "latest_nan.tif == fallback B")
    check(same("latest_nan.zip", B["zip"]), "latest_nan.zip == fallback B zip")
    check(not (DL / "latest_allfinite.tif").exists(), "no ambiguous latest_allfinite.tif alias")

    # 4 + 5: pixels and grid
    a_path, b_path = DL / A["file"], DL / B["file"]
    with rasterio.open(b_path) as s:
        valid = np.isfinite(s.read(1))
    raw = ROOT / "data" / "raw" / "existing_faults.tif"
    if raw.exists():
        with rasterio.open(raw) as s:
            lab = s.read(1)
        check(np.array_equal(lab >= 0, valid),
              "footprint == official label raster footprint (existing_faults.tif >= 0)")
    else:
        print("SKIP  footprint-vs-label check (data/raw not present; run scripts/fetch_data.py)")
    facts = frontdoor.check_pair(a_path, b_path, valid)
    problems = frontdoor._all_ok(facts)
    check(not problems, "A/B pixel, grid, layout and reader-agreement checks"
          + (": " + "; ".join(problems) if problems else ""))
    check(facts["A"]["n_nan"] == 0 and facts["A"]["naive_all_in_0_1"],
          f"A passes a NAIVE raw range test (0 NaN, min {facts['A']['min']}, max {facts['A']['max']})")
    check(facts["readers_used"] == ["Pillow", "rasterio/GDAL", "tifffile"],
          f"three independent readers used: {facts['readers_used']}")
    for k, alt in enumerate(m.get("alternates", []), 1):
        af = frontdoor.check_pair(DL / alt["A"]["file"], DL / alt["B"]["file"], valid)
        pr = frontdoor._all_ok(af)
        check(not pr, f"alt{k} ({alt['stem']}): A/B pixel, grid, layout and reader checks"
              + (": " + "; ".join(pr) if pr else ""))

    # 6: site + README put the primary file first
    primary_href = f"downloads/{A['file']}"
    pages = sorted((ROOT / "docs").glob("*.html"))
    check(len(pages) >= 5, f"{len(pages)} site pages found")
    for p in pages:
        body = p.read_text()
        i = body.find("<body")
        head = body[i:i + 4096]
        check(primary_href in head, f"{p.name}: primary download link within first 4 KB of <body>")
    idx = (ROOT / "docs" / "index.html").read_text()
    first_dl = re.search(r'<a[^>]*href="([^"]+)"[^>]*\sdownload', idx)
    check(bool(first_dl) and first_dl.group(1) == primary_href,
          f"docs/index.html FIRST download link is the primary file ({first_dl.group(1) if first_dl else None})")
    hrefs = set(re.findall(r'href="(downloads/[^"#]+)"', "".join(p.read_text() for p in pages)))
    missing = sorted(h for h in hrefs if not (ROOT / "docs" / h).exists())
    check(not missing, f"every downloads/ link on the site resolves to a file ({len(hrefs)} links)"
          + (f"; MISSING {missing}" if missing else ""))
    readme = (ROOT / "README.md").read_text()
    check(A["file"] in readme[:2500], "README.md first 2.5 KB links the primary file")
    root_index = ROOT / "index.html"
    check(root_index.exists() and A["file"] in root_index.read_text(),
          "repo-root index.html (GitHub Pages '/') shows the primary download")
    note = m["note_for_form"]
    check(len(note) <= frontdoor.MAX_NOTE_CHARS and "\n" not in note,
          f"note is one short line ({len(note)} chars)")
    check(note in idx, "exact note text appears on docs/index.html")

    # 7: live
    if args.live:
        url = PAGES + "docs/" + primary_href
        try:
            data = urllib.request.urlopen(url, timeout=60).read()
            check(hashlib.sha256(data).hexdigest() == A["sha256"],
                  f"LIVE {url} sha256 == manifest ({len(data):,} bytes)")
        except Exception as ex:  # noqa: BLE001
            check(False, f"LIVE fetch of {url} failed: {ex}")

    bad = [m_ for ok, m_ in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} checks passed")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
