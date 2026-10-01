#!/usr/bin/env python3
"""Recover the eight pinned historical TIFFs WITHOUT the large feature stack.

Labels in filenames are unverified team score records, not platform receipts.
Every cached/downloaded byte stream must match both the Git blob and the forensic
SHA256 pin; corrupted caches fail rather than silently influencing tests.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fetch_data import SCORED_FILES, gh_blob

ROOT = Path(__file__).resolve().parents[1]


def main():
    known = json.loads((ROOT / 'reports/scored_forensics.json').read_text())['maps']
    out = ROOT / 'data/scored'; out.mkdir(parents=True, exist_ok=True)
    for name, (repo, blob) in SCORED_FILES.items():
        p = out / name
        if not p.exists():
            gh_blob(f'buffedlizard55-lab/{repo}', blob, p)
        data = p.read_bytes()
        git_hash = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
        if git_hash != blob or hashlib.sha256(data).hexdigest() != known[name]['file_sha256']:
            raise RuntimeError(f'Historical TIFF pin mismatch: {name}')
        print('PIN VERIFIED', name, len(data))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
