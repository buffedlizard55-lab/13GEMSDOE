#!/usr/bin/env python3
"""Fetch the OFFICIAL external geoscience products this project is allowed to use.

Why this script exists
----------------------
The sandbox/network this repository is developed in cannot reach
`sciencebase.gov`, `usgs.gov`, `gdr.openei.org` or `prd-tnm.s3.amazonaws.com`
directly (TLS egress blocked; limitation L-2). It *can* reach GitHub. Several
sibling repositories in this group already downloaded those official products in
GitHub Actions runners that DO have open egress, recorded their provenance
(source URL, DOI, citation, md5/sha256 of the *official* archive) and committed
compact, re-gridded derivatives.

This script re-stages those derivatives into `data/external/` and verifies each
byte against a pinned digest, so nothing here is taken on trust:

  * sha256 of the product where the sibling provenance file pins it, and
  * git blob SHA-1 (`git hash-object`) of the object actually served by GitHub,
    which is pinned below for every file.

Original official sources (verified from the sibling provenance JSONs, which are
copied into `reports/external_provenance/` by this script):

  1-m/10-m DEM (USGS 3DEP)  https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/
                            tile list OCR-recovered from the competition's own
                            `Digital-elevation-model-links-JSON.pdf`
  GeoDAWN magnetics+radiometrics (USGS data release)
                            https://doi.org/10.5066/P93LGLVQ
                            https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7
  USGS Quaternary fault and fold database (QFFDB)
                            https://earthquake.usgs.gov/static/lfs/nshm/qfaults/Qfaults_GIS.zip
                            https://doi.org/10.5066/P9BCVRCK

Licence: USGS data releases and 3DEP products are U.S. Government public-domain
works; the competition's external-data rule requires a licence permitting use in
the challenge and sharing with the sponsor, which public domain satisfies.
Attribution is recorded in `reports/external_manifest.json`.

No manual input is required: `python scripts/fetch_external_data.py`.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "external"
PROV = ROOT / "reports" / "external_provenance"

# name -> (repo, path, git blob sha1, expected sha256 or None, official source)
PRODUCTS = {
    "lidar_scarp_features_u8.tif": (
        "7GEMSDOE", "external/dem/lidar_scarp_features_u8.tif",
        "da733b53147efad5c141ffdb96e469ec5b4da8b8", None,
        "USGS 3DEP 1 m DEM (716 tiles) -> 2 m morphometrics -> 100 m aggregate",
    ),
    "geodawn_rad_u8.tif": (
        "7GEMSDOE", "external/geodawn_rad/geodawn_rad_u8.tif",
        "80704748f974ea9dbc002924ddf971a957186ae6", "c22420f75999030d7cc65c9e31e50d232ea6158423bca051613a18a8b20ba682",
        "https://doi.org/10.5066/P93LGLVQ (K, Th, U, TC)",
    ),
    "geodawn_extensions_u8.tif": (
        "7GEMSDOE", "external/geodawn_extensions/geodawn_extensions_u8.tif",
        "2fb1d57fdd33b0bdea51f2abef58fb5cddf53aa5", "a35a9c6d2a14786f4dab85481ee59769213072f5dab5b2535ea82ae4d9bb7d9b",
        "https://doi.org/10.5066/P93LGLVQ (Th/K, U/K, U/Th, TMI up-150 m)",
    ),
    "qfaults_prior_u8.tif": (
        "7GEMSDOE", "external/qfaults/qfaults_prior_u8.tif",
        "b6b4c2193fad0b9266849d0838e27dee640a03d4",
        "538b45735833b341fc455dbbf06c47bc82a8bd8943c254ae6d3a5a07e72e22ca",
        "https://earthquake.usgs.gov/static/lfs/nshm/qfaults/Qfaults_GIS.zip "
        "(https://doi.org/10.5066/P9BCVRCK)",
    ),
    "topo_u8.tif": (
        "5GEMSDOE", "data/aux_bridge/topo/topo_u8.tif.part-000",
        "5388687c1396d98ba4a2298af431361eabd213f1", "a6398d9950965dec6aae6ccecdaa6ced48645d133eab222cbdd11def9bdabfa4",
        "USGS 3DEP DEM -> 9 topographic channels at 100 m",
    ),
    "radiometric_u8.tif": (
        "5GEMSDOE", "data/aux_bridge/radiometric/radiometric_u8.tif.part-000",
        "dfc512ff03c0b610653217cf21ab9196b051b4ad", "6cb051f70f941fd78028fe66a9f71e87204fcd8d9a85903df0b94993bad1ec4d",
        "https://doi.org/10.5066/P93LGLVQ -> 7 radiometric channels at 100 m",
    ),
}

# provenance records to keep in-repo (small, auditable, committable)
PROVENANCE = [
    ("7GEMSDOE", "external/qfaults/qfaults_prior.json"),
    ("7GEMSDOE", "external/qfaults/observed_schema.json"),
    ("7GEMSDOE", "external/dem/lidar_scarp_features.json"),
    ("7GEMSDOE", "external/geodawn_rad/geodawn_rad.json"),
    ("7GEMSDOE", "external/geodawn_extensions/geodawn_extensions.json"),
    ("7GEMSDOE", "external/geodawn_rad/observed_files.json"),
    ("7GEMSDOE", "knowledge/inherited_evidence/qfaults_stats.json"),
    ("7GEMSDOE", "knowledge/dem_pilot_source.json"),
    ("5GEMSDOE", "data/aux_bridge/topo/manifest.json"),
    ("5GEMSDOE", "data/aux_bridge/radiometric/manifest.json"),
    ("5GEMSDOE", "data/evidence/radiometric/radiometric_channel.report.json"),
]


def gh_raw(repo: str, path: str) -> bytes:
    out = subprocess.run(
        ["gh", "api", f"repos/buffedlizard55-lab/{repo}/contents/{path}",
         "-H", "Accept: application/vnd.github.raw"],
        capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(f"gh api failed for {repo}/{path}: {out.stderr[:300].decode('utf8', 'replace')}")
    return out.stdout


def git_hash_object(data: bytes) -> str:
    p = subprocess.run(["git", "hash-object", "--stdin"], input=data,
                       capture_output=True, check=True)
    return p.stdout.decode().strip()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    PROV.mkdir(parents=True, exist_ok=True)
    manifest = {
        "purpose": "external official geoscience products, re-staged and hash-verified",
        "licence": "USGS public domain (U.S. Government works); attribution required: "
                   "'Map services and data available from U.S. Geological Survey, "
                   "National Geospatial Program.' and the GeoDAWN data-release citation "
                   "Glen, J.M.G., and Earney, T.E., 2024, https://doi.org/10.5066/P93LGLVQ",
        "egress_note": "sciencebase.gov / usgs.gov / prd-tnm.s3.amazonaws.com are TLS-blocked "
                       "from this sandbox (limitation L-2); files are fetched from the "
                       "sibling-repo GitHub mirrors that staged them in open-egress runners",
        "files": {},
    }

    for name, (repo, path, blob_sha, sha256, source) in PRODUCTS.items():
        dest = OUT / name
        if dest.exists():
            data = dest.read_bytes()
            print(f"  have {name} ({len(data):,} bytes) - re-verifying")
        else:
            print(f"  fetching {name} from buffedlizard55-lab/{repo}:{path}")
            data = gh_raw(repo, path)
            dest.write_bytes(data)
        got_sha = hashlib.sha256(data).hexdigest()
        got_blob = git_hash_object(data)
        ok_sha = (sha256 is None) or (got_sha == sha256)
        ok_blob = (blob_sha is None) or (got_blob == blob_sha)
        rec = {
            "bytes": len(data), "sha256": got_sha, "git_blob_sha1": got_blob,
            "mirror": f"https://github.com/buffedlizard55-lab/{repo}/blob/HEAD/{path}",
            "official_source": source,
            "sha256_matches_sibling_provenance": bool(ok_sha),
            "blob_matches_sibling_git_tree": bool(ok_blob),
            "pinned_sha256": sha256, "pinned_git_blob_sha1": blob_sha,
        }
        manifest["files"][name] = rec
        flag = "OK " if (ok_sha and ok_blob) else "MISMATCH"
        print(f"    {flag} sha256={got_sha[:16]}… blob={got_blob[:12]}… {len(data):,} bytes")
        if not (ok_sha and ok_blob):
            print("    !! digest mismatch - refusing to continue", file=sys.stderr)
            (ROOT / "reports" / "external_manifest.json").write_text(
                json.dumps(manifest, indent=2))
            return 2

    for repo, path in PROVENANCE:
        dest = PROV / f"{repo}__{path.replace('/', '_')}"
        data = gh_raw(repo, path)
        dest.write_bytes(data)
        manifest.setdefault("provenance_records", {})[dest.name] = {
            "mirror": f"https://github.com/buffedlizard55-lab/{repo}/blob/HEAD/{path}",
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        }
        print(f"  provenance {dest.name} ({len(data):,} bytes)")

    (ROOT / "reports" / "external_manifest.json").write_text(
        json.dumps(manifest, indent=2))
    print("\nwrote reports/external_manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
