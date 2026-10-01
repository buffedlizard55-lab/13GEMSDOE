#!/usr/bin/env python3
"""Verify schema2 local downloads; local template policy is NOT acceptance.

Hashes/sizes, one-TIFF ZIP/CRC, alias identity, official grid/footprint/range,
three actual TIFF decoders and top-of-page links are checked independently.
--live delegates to verify_site_http.py for FULL deployed TIFF/ZIP/manifest/site
checks. The earlier empirically-accepted/root-cause prose was withdrawn.
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
from gems import encoding, frontdoor  # noqa: E402

DL = ROOT / "docs" / "downloads"
PAGES = "https://buffedlizard55-lab.github.io/13GEMSDOE/"

results: list[tuple[bool, str]] = []


def check(ok: bool, msg: str) -> None:
    results.append((bool(ok), msg))
    print(("PASS  " if ok else "FAIL  ") + msg)


def entry_checks(label: str, e: dict, prefix: Path = DL) -> None:
    tif, zp = prefix / e["file"], prefix / e["zip"]
    check(tif.exists() and zp.exists(), f"{label}: {e['file']} and its .zip exist")
    if not (tif.exists() and zp.exists()):
        return
    check(frontdoor.sha256_file(tif) == e["sha256"], f"{label}: .tif sha256 matches manifest")
    check(frontdoor.sha256_file(zp) == e["zip_sha256"], f"{label}: .zip sha256 matches manifest")
    with zipfile.ZipFile(zp) as z:
        names = z.namelist()
        check(names == [tif.name], f"{label}: zip holds exactly one entry ({names})")
        check(z.testzip() is None, f"{label}: zip CRCs OK")
        check(hashlib.sha256(z.read(names[0])).hexdigest() == e["sha256"],
              f"{label}: zip entry bytes == .tif bytes")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="also fetch the file from GitHub Pages and compare sha256")
    args = ap.parse_args()
    results.clear()

    mpath = DL / "submit.json"
    check(mpath.exists(), "docs/downloads/submit.json exists")
    if not mpath.exists():
        return 1
    m = json.loads(mpath.read_text())
    check(m.get("schema") == 2, f"manifest is schema 2 (got {m.get('schema')})")
    check("primary" in m and "hedge" in m, "manifest carries primary + hedge keys")
    if "primary" not in m or "hedge" not in m:
        return 1
    P, H = m["primary"], m["hedge"]

    entry_checks("PRIMARY", P)
    entry_checks("HEDGE", H)
    for k, alt in enumerate(m.get("alternates", []), 1):
        entry_checks(f"alt{k}-PRIMARY", alt["primary"])
        entry_checks(f"alt{k}-HEDGE", alt["hedge"])

    # 3: aliases
    same = lambda x, y: (DL / x).exists() and (DL / x).read_bytes() == (DL / y).read_bytes()  # noqa: E731
    check(same("latest.tif", P["file"]), "latest.tif == PRIMARY (the NaN-outside file)")
    check(same("latest.zip", P["zip"]), "latest.zip == PRIMARY zip")
    check(same("latest_zerofill.tif", H["file"]), "latest_zerofill.tif == HEDGE")
    check(same("latest_zerofill.zip", H["zip"]), "latest_zerofill.zip == HEDGE zip")
    for dead in frontdoor.RETIRED_ALIASES:
        check(not (DL / dead).exists(), f"retired alias {dead} is gone (it inverted the roles)")

    # 4 + 5 + 6: pixels, grid, encoding
    p_path, h_path = DL / P["file"], DL / H["file"]
    with rasterio.open(p_path) as s:
        valid = np.isfinite(s.read(1))
    check(int(valid.sum()) == encoding.FOOTPRINT_PIXELS,
          f"PRIMARY footprint is the official {encoding.FOOTPRINT_PIXELS:,} px "
          f"(got {int(valid.sum()):,})")
    for raw in ("data/raw/existing_faults.tif", "data/raw/labels.tif"):
        rp = ROOT / raw
        if rp.exists():
            with rasterio.open(rp) as s:
                lab = s.read(1)
            check(np.array_equal(lab >= 0, valid),
                  f"PRIMARY footprint == official label raster footprint ({raw})")
            break
    else:
        print("SKIP  footprint-vs-label check (data/raw absent; run "
              "bash scripts/download_competition_data.sh --small)")

    facts = frontdoor.check_pair(p_path, h_path, valid)
    problems = frontdoor._all_ok(facts)
    check(not problems, "PRIMARY/HEDGE pixel, grid, layout and reader-agreement gate"
          + (": " + "; ".join(problems) if problems else ""))

    check(facts["primary"]["matches_accepted_pattern"],
          "PRIMARY matches the LOCAL TEMPLATE POLICY platform encoding"
          + (": " + "; ".join(facts["primary"]["deviations_from_accepted_pattern"])
             if not facts["primary"]["matches_accepted_pattern"] else ""))
    check(facts["primary"]["n_nan"] == encoding.OUTSIDE_PIXELS,
          f"PRIMARY has exactly {encoding.OUTSIDE_PIXELS:,} NaN, all outside the footprint")
    check(facts["primary"]["layout"]["predictor"] in (None, "1", 1, "NONE"),
          f"PRIMARY TIFF predictor is none (got {facts['primary']['layout']['predictor']!r})")
    check(facts["hedge"]["n_nan"] == 0 and facts["hedge"]["naive_all_in_0_1"],
          "HEDGE passes a NAIVE whole-array [0, 1] test (0 NaN)")
    check(facts["readers_used"] == ["Pillow", "rasterio/GDAL", "tifffile"],
          f"three independent readers used: {facts['readers_used']}")

    # every official sample_submission.tif structural tag PRIMARY must share
    tmpl = None
    for name in ("sample_submission.tif", "example_submission.tif"):
        if (ROOT / "data" / "raw" / name).exists():
            tmpl = ROOT / "data" / "raw" / name
            break
    if tmpl is not None:
        tl = encoding.read_layout(tmpl)
        pl = encoding.read_layout(p_path)
        for key in ("dtype", "count", "crs", "shape", "transform", "nodata"):
            check(tl["profile"][key] == pl["profile"][key],
                  f"PRIMARY {key} == official template {key} ({tl['profile'][key]})")
        for key in ("compression", "predictor", "sample_format", "bits_per_sample",
                    "tiled", "rows_per_strip"):
            check(tl["layout"][key] == pl["layout"][key],
                  f"PRIMARY TIFF {key} == official template ({tl['layout'][key]})")
    else:
        print("SKIP  template-tag equality (data/raw/sample_submission.tif absent)")

    # 7 + 8: site and README put PRIMARY first
    primary_href = f"downloads/{P['file']}"
    pages = sorted((ROOT / "docs").glob("*.html"))
    check(len(pages) >= 5, f"{len(pages)} site pages found")
    for p in pages:
        body = p.read_text()
        i = body.find("<body")
        head = body[i:i + 4096]
        check(primary_href in head, f"{p.name}: PRIMARY download link within first 4 KB of <body>")
    idx = (ROOT / "docs" / "index.html").read_text()
    first_dl = re.search(r'<a[^>]*href="([^"]+)"[^>]*\sdownload', idx)
    check(bool(first_dl) and first_dl.group(1) == primary_href,
          f"docs/index.html FIRST download link is PRIMARY "
          f"({first_dl.group(1) if first_dl else None})")
    hrefs = set(re.findall(r'href="(downloads/[^"#]+)"',
                           "".join(p.read_text() for p in pages)))
    missing = sorted(h for h in hrefs if not (ROOT / "docs" / h).exists())
    check(not missing, f"every downloads/ link on the site resolves to a file "
                       f"({len(hrefs)} links)" + (f"; MISSING {missing}" if missing else ""))
    readme = (ROOT / "README.md").read_text()
    check(P["file"] in readme[:2500], "README.md first 2.5 KB links the PRIMARY file")
    root_index = ROOT / "index.html"
    check(root_index.exists() and P["file"] in root_index.read_text(),
          "repo-root index.html (GitHub Pages '/') shows the PRIMARY download")
    check((ROOT / ".nojekyll").exists(),
          "repo-root .nojekyll exists (Pages source is '/', so Jekyll would "
          "otherwise process every page and asset)")
    note = m["note_for_form"]
    check(note.strip() and len(note) <= frontdoor.MAX_NOTE_CHARS and not any(c in note for c in "\r\n"),
          f"note is one short line ({len(note)} chars)")
    check(note in idx, "exact note text appears on docs/index.html")
    check(note in root_index.read_text(), "exact note text appears on the root index.html")

    # 9: real deployed delivery is separate from on-disk verification.
    if args.live:
        import subprocess
        code = subprocess.run([sys.executable, str(ROOT / "scripts/verify_site_http.py"), "--live"]).returncode
        check(code == 0, "FULL deployed-site HTTP verification passed")

    bad = [msg for ok, msg in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} checks passed")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
