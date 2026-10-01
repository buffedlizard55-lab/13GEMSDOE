#!/usr/bin/env python3
"""Execute the frozen thermal/geographic R15 experiment; never publishes/uploads.

Run after scripts/download_competition_data.sh --small. Probes are already
staged with provenance. Requirements: requirements.txt. Output arrays ignored.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
from gems import propagation as P, rio, thermal  # noqa: E402
from gems.fastscore import FoldScorer, verify_against_reference  # noqa: E402
from gems.holdout import build_folds  # noqa: E402
from gems.spatial import spatially_blocked_folds  # noqa: E402
from validate_r10_holdout import segment_folds  # noqa: E402

REGISTER = ROOT / 'knowledge/11_r15_predeclared.md'
OUT = ROOT / 'reports/holdout_r15_2026-10-01.json'
CHALLENGER = 'lattice_s5_plus_thermal'
REFERENCE = 'lattice_s5'


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mask_hash(a: np.ndarray) -> str:
    return hashlib.sha256(str(a.shape).encode() + np.packbits(a, bitorder='little').tobytes()).hexdigest()


def summarise(rows: list[dict], family: str) -> dict:
    by = defaultdict(lambda: defaultdict(list))
    paired = defaultdict(dict)
    for r in rows:
        if r['family'] != family:
            continue
        by[r['config']][r['rule']].append(r['dti'])
        paired[r['fold']][r['config']] = r['dti']
    out = {}
    for name, rules in sorted(by.items()):
        means = {k: float(np.mean(v)) for k, v in sorted(rules.items())}
        differences = [v[name] - v[REFERENCE] for v in paired.values()]
        out[name] = {'mean_dti': float(np.mean([x for v in rules.values() for x in v])),
                     'mean_by_rule': means, 'worst_rule_mean_dti': min(means.values()),
                     'paired_wins_vs_current_best': sum(x > 1e-9 for x in differences),
                     'paired_losses_vs_current_best': sum(x < -1e-9 for x in differences),
                     'n_folds': len(differences), 'paired_mean_delta': float(np.mean(differences))}
    return out


def main() -> int:
    t0 = time.monotonic()
    register_sha = file_hash(REGISTER)  # freeze before construction or scoring
    parity = verify_against_reference(trials=15)
    if not parity['pass']:
        raise RuntimeError('Scorer parity failed')
    with rasterio.open(rio.resolve_raw('template')) as s:
        affine = s.transform
    valid, known = rio.load_footprint(rio.resolve_raw('labels'))
    paths = list((ROOT / 'data/external_gdr1391').rglob('2m_temperature_probe_n83geo.shp'))
    if len(paths) != 1:
        raise RuntimeError('Exactly one staged GDR1391 probe shapefile required')
    probes, probe_stats = thermal.load_probes(paths[0], affine, valid)
    field, field_stats = thermal.build_corridors(probes, affine, valid)
    lat5 = P.square_lattice(valid.shape, 5) & valid
    m = json.loads((ROOT / 'docs/downloads/submit.json').read_text())
    if m['source_artifact']['recipe'].find('lattice') < 0:
        raise RuntimeError('Current primary changed; predeclared reference no longer current')
    with rasterio.open(ROOT / 'docs/downloads' / m['primary']['file']) as s:
        current = s.read(1)
    if not np.array_equal(current[valid], lat5.astype(np.float32)[valid]):
        raise RuntimeError('Rebuilt lattice differs from current primary')
    del current
    rng = np.random.default_rng(20261001)
    configs = {'thermal_corridors': field, REFERENCE: lat5,
               CHALLENGER: lat5 | field, 'lattice_s4': P.square_lattice(valid.shape, 4) & valid,
               'lattice_s6': P.square_lattice(valid.shape, 6) & valid,
               'empty_control': np.zeros(valid.shape, bool),
               'random4pct': (rng.random(valid.shape, dtype=np.float32) < 0.04) & valid}
    for name, a in configs.items():
        if a.shape != valid.shape or np.any(a & ~valid):
            raise RuntimeError(f'Invalid prediction field {name}')
    derived = ROOT / 'data/derived'
    derived.mkdir(parents=True, exist_ok=True)
    np.save(derived / 'R15_thermal_corridors.npy', field)
    source_hashes = {str(p.relative_to(ROOT)): file_hash(p) for p in
                     [REGISTER, ROOT / 'src/gems/thermal.py', ROOT / 'src/gems/spatial.py',
                      Path(__file__), *[paths[0].with_suffix(x) for x in ('.shp', '.shx', '.dbf', '.prj')]]}
    print('Probe/field statistics:', json.dumps({'probes': probe_stats, 'field': field_stats}), flush=True)
    families = [('existing_system_and_segment',
                 build_folds(known, valid, n_folds=3, hide_frac=0.25, seed=20260930,
                             link_px=8, buffer_px=5) + segment_folds(known, valid, n_folds=3)),
                ('geographic_stress', spatially_blocked_folds(known, valid))]
    rows, folds_metadata = [], []
    for family, folds in families:
        for f in folds:
            if f.n_hidden == 0 or not f.eval_mask.any():
                raise RuntimeError(f'Empty confirmation fold: {f.name}')
            if np.any(f.hidden & f.visible) or np.any(f.hidden & ~f.eval_mask):
                raise RuntimeError(f'Invalid mask semantics: {f.name}')
            folds_metadata.append({'family': family, 'fold': f.name, 'rule': f.rule,
                                   'n_truth': f.n_hidden, 'n_visible': f.n_visible,
                                   'n_eval': int(f.eval_mask.sum()),
                                   'hidden_sha256': mask_hash(f.hidden),
                                   'visible_sha256': mask_hash(f.visible),
                                   'eval_sha256': mask_hash(f.eval_mask), 'meta': f.meta})
            scorer = FoldScorer.build(f.hidden, f.eval_mask)
            fold_results = {}
            for name, a in configs.items():
                r = scorer.score(a.astype(np.float32))
                fold_results[name] = r['dti']
                rows.append({'family': family, 'fold': f.name, 'rule': f.rule, 'config': name,
                             'n_eval_pixels': int(f.eval_mask.sum()),
                             'n_predicted_eval_pixels': int((a & f.eval_mask).sum()), **r})
            print(f'[{time.monotonic()-t0:.1f}s] {f.name}: current={fold_results[REFERENCE]:.7f} '
                  f'thermal_union={fold_results[CHALLENGER]:.7f} '
                  f'delta={fold_results[CHALLENGER]-fold_results[REFERENCE]:+.7f}', flush=True)
            del scorer
    summaries = {family: summarise(rows, family) for family, _ in families}
    old, geo = [summaries[f][CHALLENGER] for f, _ in families]
    old_ref, geo_ref = [summaries[f][REFERENCE] for f, _ in families]
    gate = {'non_identical_to_current_best': mask_hash(configs[CHALLENGER]) != mask_hash(lat5),
            'existing_worst_rule_gain_at_least_002': old['worst_rule_mean_dti'] - old_ref['worst_rule_mean_dti'] >= 0.002,
            'existing_paired_wins_at_least_14_of_18': old['n_folds'] == 18 and old['paired_wins_vs_current_best'] >= 14,
            'geographic_worst_rule_gain_at_least_002': geo['worst_rule_mean_dti'] - geo_ref['worst_rule_mean_dti'] >= 0.002,
            'geographic_paired_wins_at_least_3_of_4': geo['n_folds'] == 4 and geo['paired_wins_vs_current_best'] >= 3,
            'register_unchanged_during_run': register_sha == file_hash(REGISTER)}
    passed = all(gate.values())
    report = {'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'status': 'LOCAL_KNOWN_CATALOGUE_PROXY_NOT_PRIVATE_TEST_PERFORMANCE',
              'hypothesis_register': str(REGISTER.relative_to(ROOT)), 'predeclared_before_run': True,
              'register_sha256_before_run': register_sha, 'source_code_hashes': source_hashes,
              'source_provenance': 'reports/gdr1391_fetch.json', 'probes': probe_stats, 'field': field_stats,
              'reference_primary_sha256': m['primary']['sha256'], 'baseline_pixels_rebuilt_identically': True,
              'prediction_support_hashes': {k: mask_hash(v) for k, v in configs.items()},
              'challenger': CHALLENGER, 'reference': REFERENCE, 'scorer_parity': parity,
              'summaries': summaries, 'gate': gate, 'gate_passed': passed,
              'scientific_status': 'CLEARED_LOCAL_PROXY_ONLY' if passed else 'RESEARCH_ONLY_DO_NOT_SUBMIT',
              'competition_upload_performed': False, 'weekly_slots_used': 0,
              'limitations': ['Thermal survey locations are exploration-selected, not a random regional sample.',
                             'Heat, steam and outflow do not establish surface fault displacement.',
                             'Only public catalogue labels are hidden; all public covariates remain available.',
                             'Four geographic folds and 18 existing folds are correlated proxies, not independent discovery receipts.',
                             'No hyperparameter fit or confirmation-score tuning was performed.'],
              'folds': folds_metadata, 'results': rows, 'runtime_s': time.monotonic()-t0}
    OUT.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print('GATE:', json.dumps(gate), '\nVERDICT:', report['scientific_status'], flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
