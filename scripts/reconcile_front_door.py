#!/usr/bin/env python3
"""Re-audit the EXISTING primary bytes and correct evidence/gate labels only.

No detector rebuild, filename change, prediction change or competition upload.
Use this once when migrating evidence wording; build_site never republishes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from gems import frontdoor  # noqa: E402


def main() -> int:
    dl = ROOT / 'docs/downloads'
    old = json.loads((dl / 'submit.json').read_text())
    paths = {'primary': dl / old['primary']['file'], 'hedge': dl / old['hedge']['file'],
             'primary_zip': dl / old['primary']['zip'], 'hedge_zip': dl / old['hedge']['zip']}
    for role in ('primary', 'hedge'):
        if frontdoor.sha256_file(paths[role]) != old[role]['sha256'] or frontdoor.sha256_file(paths[role+'_zip']) != old[role]['zip_sha256']:
            raise RuntimeError('Existing bytes differ from manifest; do not adopt silently')
    with rasterio.open(paths['primary']) as s:
        pred = s.read(1)
    valid = np.isfinite(pred)
    new = frontdoor.publish(dl, old['stem'], pred, valid, note=old['note_for_form'],
                           source=old['source_artifact'],
                           status={**old['status'], 'platform_acceptance_established': False,
                                   'rejection_cause': 'UNRESOLVED', 'new_scientific_candidate_cleared': False,
                                   'weekly_slots_used_this_review': 0}, existing_paths=paths)
    new['description'] = 'Current existing-protocol local reference: fault-blind stride5 lattice (origin0,0). Coverage baseline, not a geological discovery or predicted leaderboard score.'
    new['evidence_link'] = old.get('evidence_link')
    new['alternates'] = old.get('alternates', [])
    for alt in new['alternates']:
        alt['submission_clearance'] = {'upload_allowed': False,
                                      'status': 'RESEARCH_ARCHIVE_DO_NOT_SUBMIT',
                                      'reason': ('Failed R14 gate D2/D3; cannot use a slot under the standing user rule.'
                                                 if 'r14-' in alt['stem'] else
                                                 'Previous local reference; it has not beaten the current lattice reference.')}
        alt['label'] = ('R14 failed-gate research archive' if 'r14-' in alt['stem'] else
                        'R11 previous local reference — archive only')
        alt['primary']['use'] = 'RESEARCH ARCHIVE ONLY — DO NOT SUBMIT'
        alt['hedge']['use'] = 'Archived diagnostic twin; not a weekly-slot candidate'
        alt['description'] = ('Failed R14 predeclared gate; retained only for reproducibility/forensics.'
                              if 'r14-' in alt['stem'] else
                              'Historical R11 map; not a winner against the current lattice reference.')
        alt['primary']['encoding'] = frontdoor.PRIMARY_ENCODING_TEXT
        alt['hedge']['encoding'] = frontdoor.HEDGE_ENCODING_TEXT
    new['submission_policy'] = {'automatic_upload': False,
                                'new_experiment_slot_recommended': False,
                                'gate_rule': 'A new hypothesis must beat the current best on existing and spatial-block proxy holdouts before using a slot.',
                                'latest_experiment_report': 'reports/holdout_r15_2026-10-01.json',
                                'latest_experiment_status': 'RESEARCH_ONLY_DO_NOT_SUBMIT'}
    if new['primary']['sha256'] != old['primary']['sha256']:
        raise RuntimeError('Prediction byte identity changed unexpectedly')
    (dl / 'submit.json').write_text(json.dumps(new, indent=2, allow_nan=False) + '\n')
    print('Existing primary bytes unchanged:', new['primary']['file'], new['primary']['sha256'])
    print('Alternates are research archives, not weekly-slot recommendations.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
