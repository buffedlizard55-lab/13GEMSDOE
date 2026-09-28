#!/usr/bin/env python3
"""Reconstruct data/raw/ without a DrivenData login.

PROVENANCE WARNING
------------------
These are MIRRORS held in this group's own public GitHub repositories, not
first-party downloads from the competition data tab. One of them is known to be
mislabelled (see knowledge/02_irregularities.md, I-1): the file named
`example_submission.tif` is value-identical to the known fault catalogue, while
the official problem description says the sample "predicts total fault
absence". Blob SHAs are pinned below so every byte can be re-verified.

If you have a DrivenData login, prefer the official files:
  https://www.drivendata.org/competitions/306/competition-doe-gems/data/
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SCORED = ROOT / "data" / "scored"

REPO = "buffedlizard55-lab/GEMSDOE"

SINGLE = {
    "existing_faults.tif": ("4ad3c1f3f19823e40924589bee7e51e44ae3a2e7", 425830),
    "example_submission.tif": ("7d865a9921a40ed2ea4c742a6a25b1fa2f357c5a", 1599597),
}
PARTS = [f"data/bridge/gems-geodawn-numerical-features.tif.part-00{i}"
         for i in range(5)]

# previously leaderboard-scored submissions, for forensics + holdout calibration
SCORED_FILES = {
    "gemsdoe1_ens12_LB0.1563.tif": ("GEMSDOE", "812e61b74050d1350cc2bde1fab0c76ead32e0c4"),
    "gems8_apex_LB0.1563.tif": ("8GEMSDOE", "d3aac36c0d38464793640b30920d2a3bea4c4143"),
    "gemsdoe2_dualunion_LB0.1560.tif": ("GEMSDOE2", "fd56d5c4806521438ee89cc9bd7dd1cf89e9fd44"),
    "gems7_halo15_LB0.1461.tif": ("7GEMSDOE", "06c2e93680efb5106acd46aad60fca571ea33975"),
    "gems3_pindrop_nodes_LB0.1193.tif": ("GEMSDOE3", "fdd931161c431a583cf7039362e51832e59d07ad"),
    "gems3_pindrop_ridge_LB0.1152.tif": ("GEMSDOE3", "b298154c2e405095db5e58f9c5232618ef4827f1"),
    "gems3_pindrop_discovery_LB0.0830.tif": ("GEMSDOE3", "32a4a6d2d4df8ef8e880120f36d2a4d94f134f8a"),
    "gems6_hgb88_LB0.0286.tif": ("6GEMSDOE", "3957f33ad98537c14db71425667dcbf199629af2"),
}


def gh_blob(repo: str, sha: str, dest: Path) -> int:
    import base64
    out = subprocess.run(["gh", "api", f"repos/{repo}/git/blobs/{sha}",
                          "--jq", ".content"], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"gh api failed for {repo}@{sha}: {out.stderr[:300]}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = base64.b64decode(out.stdout)
    dest.write_bytes(data)
    return len(data)


def gh_raw(repo: str, path: str) -> bytes:
    out = subprocess.run(["gh", "api", f"repos/{repo}/contents/{path}",
                          "-H", "Accept: application/vnd.github.raw"],
                         capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(f"gh api failed for {path}: {out.stderr[:300]}")
    return out.stdout


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = {"source": "mirrors in this group's own public repos",
                "warning": "see knowledge/02_irregularities.md I-1", "files": {}}

    for name, (sha, size) in SINGLE.items():
        dest = RAW / name
        if dest.exists() and dest.stat().st_size == size:
            print(f"  have {name}")
        else:
            n = gh_blob(REPO, sha, dest)
            print(f"  fetched {name} ({n:,} bytes)")
        manifest["files"][name] = {
            "blob_sha": sha, "bytes": dest.stat().st_size,
            "md5": hashlib.md5(dest.read_bytes()).hexdigest()}

    feats = RAW / "gems-geodawn-numerical-features.tif"
    if feats.exists() and feats.stat().st_size == 418912844:
        print("  have gems-geodawn-numerical-features.tif")
    else:
        print("  fetching 19-band feature stack (419 MB, 5 parts)...")
        with open(feats, "wb") as fh:
            for p in PARTS:
                fh.write(gh_raw(REPO, p))
                print(f"    {p.rsplit('.', 1)[-1]}")
    manifest["files"]["gems-geodawn-numerical-features.tif"] = {
        "bytes": feats.stat().st_size, "parts": len(PARTS)}

    SCORED.mkdir(parents=True, exist_ok=True)
    for name, (repo, sha) in SCORED_FILES.items():
        dest = SCORED / name
        if dest.exists():
            print(f"  have {name}")
        else:
            gh_blob(f"buffedlizard55-lab/{repo}", sha, dest)
            print(f"  fetched {name}")
        manifest["files"][f"scored/{name}"] = {"repo": repo, "blob_sha": sha}

    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "data_manifest.json").write_text(
        json.dumps(manifest, indent=2))
    print("\nwrote reports/data_manifest.json")


if __name__ == "__main__":
    sys.exit(main())
