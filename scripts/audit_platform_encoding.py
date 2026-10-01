#!/usr/bin/env python3
"""Audit template, historical TIFF labels and current downloads; NOT server behavior.

Historical API/file name retained for reproducibility. Neither score filenames,
team reports nor a hypothetical decoder establish acceptance of exact bytes.
Run after bash scripts/download_competition_data.sh --small.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from gems import encoding, frontdoor, rio  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    tmpl, labels = rio.resolve_raw('template'), rio.resolve_raw('labels')
    if sha(tmpl) != encoding.SAMPLE_SUBMISSION_SHA256 or sha(labels) != encoding.LABELS_SHA256:
        raise RuntimeError('Official-raster mirror pins mismatch; stop the audit')
    with rasterio.open(tmpl) as s:
        fp = np.isfinite(s.read(1))
    with rasterio.open(labels) as s:
        lab = s.read(1)
    if not np.array_equal(fp, lab >= 0):
        raise RuntimeError('Template and label footprints differ')
    dl = ROOT / 'docs/downloads'
    groups = {'official_template': [tmpl],
              'historical_score_labelled_not_receipted': sorted((ROOT / 'data/scored').glob('*.tif')),
              'user_reported_rejected': [dl / 'archive/13gems-r11-greedy-mp.tif'],
              'currently_shipped': sorted(dl.glob('*.tif'))}
    report = {'generated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
              'question': 'What local encoding facts are measurable, and what remains unverified?',
              'evidence_boundary': 'Historical score labels/team records are not per-file platform receipts. No current download has a remote acceptance receipt here.',
              'legacy_field_warning': 'matches_accepted_pattern is a deprecated alias for matches_template_policy; it NEVER means accepted by DrivenData.',
              'official_template': {'path': str(tmpl.relative_to(ROOT)), 'sha256': sha(tmpl),
                                    'labels_sha256': sha(labels), 'pins_verified': True,
                                    'footprint_pixels': int(fp.sum()), 'outside_pixels': int((~fp).sum()),
                                    'footprint_equals_labels_ge_0': True},
              'files': {}}
    for group, files in groups.items():
        for p in files:
            if not p.exists():
                print('SKIP', p.relative_to(ROOT))
                continue
            audit = encoding.audit_file(p, fp)
            audit.update(sha256=sha(p), group=group, evidence_class='local_decoded_bytes')
            if group == 'user_reported_rejected':
                reads = frontdoor.read_all_readers(p)
                ref = reads['rasterio/GDAL']
                audit['actual_readers'] = {k: {'finite_min': float(a[np.isfinite(a)].min()),
                                               'finite_max': float(a[np.isfinite(a)].max()),
                                               'equals_gdal': bool(np.array_equal(ref, a, equal_nan=True))}
                                          for k, a in reads.items()}
                audit['rejection_source'] = 'user_reported_platform_response; no captured server decoder trace'
            report['files'][f'{group}/{p.name}'] = audit
            print(('MATCH ' if audit['matches_template_policy'] else 'DEVIATION '), group, p.name,
                  audit['layout']['compression'], 'predictor=', audit['layout']['predictor'])
    hist = [v for v in report['files'].values() if v['group'] == 'historical_score_labelled_not_receipted']
    rejected = [v for v in report['files'].values() if v['group'] == 'user_reported_rejected']
    report['summary'] = {
        'n_historical_score_labelled_files_obtained': len(hist),
        'n_historical_score_labelled_matching_template_policy': sum(v['matches_template_policy'] for v in hist),
        'n_captured_current_file_acceptance_receipts': 0,
        'server_rejection_cause': 'UNRESOLVED',
        'policy': {'primary_encoding': 'NaN outside official footprint; NoData=nan; finite [0,1] float32 inside; LZW; no predictor',
                   'why': 'Matches the measured official template and official format text. This is not a platform-acceptance inference.',
                   'hedge_encoding': 'Diagnostic only: zero outside, no NoData; same footprint predictions. Do not automatically spend a second slot.',
                   'predictor_simulation': 'Ignoring differencing can yield out-of-range numbers, but three actual local readers decode the archived rejected file correctly. Platform behavior is unknown.',
                   'nan_handling': 'Template permits NaN outside; actual validator handling of the rejected upload has not been observed.'},
        'rejected_file_actual_readers': rejected[0].get('actual_readers') if rejected else None,
        'rejected_file_hypothetical_decoder': rejected[0].get('predictor2_simulation') if rejected else None,
        'correction_record': 'knowledge/13_audit_corrections_2026-10-01.md'}
    out = ROOT / 'reports/platform_encoding_evidence.json'
    out.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print('wrote', out.relative_to(ROOT), '\nREJECTION CAUSE: UNRESOLVED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
