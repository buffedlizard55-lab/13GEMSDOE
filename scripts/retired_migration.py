"""Safe inspection shared by retired schema1/encoding migration commands."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description='Retired migration. Old source remains in Git history; never changes current downloads, aliases or evidence.')
    ap.add_argument('--dry-run', action='store_true', help='Inspect current schema2 roles only; no mutation or inference')
    args = ap.parse_args()
    if not args.dry_run:
        ap.error('Retired before mutation. Use build_site.py / verify_download.py. See knowledge/13_audit_corrections_2026-10-01.md.')
    m = json.loads((ROOT / 'docs/downloads/submit.json').read_text())
    print('SCHEMA', m['schema'], 'PRIMARY', m['primary']['file'], 'DIAGNOSTIC', m['hedge']['file'])
    print('No files changed; no upload; no platform-acceptance or rejection-cause inference.')
    return 0
