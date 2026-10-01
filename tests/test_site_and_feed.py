"""Failure-path tests for source freshness, public serving and frozen gates.

No real network calls, credentials, user data or competition submissions.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'src'))
from gems import encoding, rio  # noqa: E402
import build_site  # noqa: E402
import publish_source_feed as publisher  # noqa: E402
import refresh_open_sources as feed  # noqa: E402
import serve_site  # noqa: E402


@pytest.mark.parametrize('url', [
    'https://www.drivendata.org/competitions/306/',
    'https://community.drivendata.org/t/example/1',
    'http://gdr.openei.org/submissions/1391',
    'https://gdr.openei.org.attacker.example/submissions/1391',
    'https://not-used:not-used@gdr.openei.org/submissions/1391',
    'https://gdr.openei.org:abc/submissions/1391',
    'https://api.github.com/example?access_token=not-a-real-token',
    'https://api.github.com/example?%61pi_key=not-a-real-key',
    'http://127.0.0.1/',
    'file:///tmp/example',
])
def test_feed_refuses_unapproved_credential_or_competition_urls(url):
    assert feed.approved(url) is False


def entry():
    return {'id': 'gdr1391', 'title': 'GDR dataset', 'url': 'https://gdr.openei.org/submissions/1391', 'licence': 'CC-BY-4.0'}


def observation(digest='a'*64):
    return {'sha256': digest, 'normalized_content_sha256': digest, 'bytes': 100, 'excerpt': 'Verified transport observation only'}


def test_failed_attempt_retains_prior_success_hash_time_and_body():
    initial = feed.refresh({}, [entry()], fetch=lambda e: observation(), now='2026-10-01T00:00:00Z')
    original = deepcopy(initial)
    def failed(_):
        raise OSError('Synthetic network failure')
    next_run = feed.refresh(initial, [entry()], fetch=failed, now='2026-10-02T00:00:00Z')
    rec = next_run['sources']['gdr1391']
    assert rec['sha256'] == 'a'*64 and rec['excerpt'] == initial['sources']['gdr1391']['excerpt']
    assert rec['last_success_utc'] == '2026-10-01T00:00:00Z'
    assert rec['last_success_url'] == entry()['url']
    assert rec['last_attempt_utc'] == '2026-10-02T00:00:00Z'
    assert rec['status'] == 'FETCH_FAILED_LAST_SUCCESS_RETAINED'
    assert next_run['n_failed'] == 1 and initial == original


def test_changed_success_is_review_required_not_certified_fact():
    previous = feed.refresh({}, [entry()], fetch=lambda e: observation())
    changed = feed.refresh(previous, [entry()], fetch=lambda e: observation('b'*64))
    row = changed['sources']['gdr1391']
    assert row['status'] == 'REVIEW_REQUIRED' and row['changed_since_previous_success'] is True
    assert row['evidence_class'] == 'automated_source_observation_not_scientific_certification'


def test_same_source_unchanged_is_only_an_observation():
    previous = feed.refresh({}, [entry()], fetch=lambda e: observation())
    row = feed.refresh(previous, [entry()], fetch=lambda e: observation())['sources']['gdr1391']
    assert row['status'] == 'OBSERVED_OK' and row['changed_since_previous_success'] is False


def test_changed_source_url_requires_review_even_if_bytes_same():
    previous = feed.refresh({}, [entry()], fetch=lambda e: observation())
    moved = {**entry(), 'url': 'https://gdr.openei.org/submissions/344'}
    assert feed.refresh(previous, [moved], fetch=lambda e: observation())['sources']['gdr1391']['status'] == 'REVIEW_REQUIRED'


def test_invalid_source_id_rejected_before_fetch_or_storage():
    for ident in ('../escape', 'gdr/name', ''):
        with pytest.raises(ValueError, match='Invalid source'):
            feed.refresh({}, [{**entry(), 'id': ident}], fetch=lambda e: pytest.fail('fetch called'))


def test_bot_feed_envelope_round_trip_and_wrong_payloads():
    obj = feed.refresh({}, [entry()], fetch=lambda e: observation())
    assert publisher.parse_feed(publisher.body_for(obj)) == obj
    for body in ('', '{}', publisher.BEGIN + 'not json' + publisher.END):
        with pytest.raises(ValueError):
            publisher.parse_feed(body)


def test_html_observation_drops_scripts_and_normalizes_whitespace():
    parser = feed.VisibleText(); parser.feed('<h1>Source</h1><script>secretNoise()</script><style>noise</style><p> True   text </p>')
    assert parser.text() == 'Source True text'


@pytest.mark.parametrize('url', ['/.git/HEAD', '/.git/config', '/.cache/chromium.json', '/data/raw/labels.tif',
                                  '/docs/../.git/HEAD', '/docs/%2e%2e/.git/config', '/docs/%00file.tif', '/docs/\\../private'])
def test_private_and_traversal_preview_paths_not_exposed(url):
    assert serve_site.public_path(url) is None


def test_preview_symlink_to_private_in_repo_file_denied(tmp_path, monkeypatch):
    (tmp_path / 'docs').mkdir(); (tmp_path / 'data').mkdir()
    secret = tmp_path / 'data/not-public.tif'; secret.write_bytes(b'synthetic-private-data')
    (tmp_path / 'docs/link.tif').symlink_to(secret)
    monkeypatch.setattr(serve_site, 'ROOT', tmp_path)
    assert serve_site.public_path('/docs/link.tif') is None


def test_generated_root_and_every_page_start_with_primary_and_no_inline_js():
    m = build_site.front(); outputs = build_site.render()
    for path, text in outputs.items():
        assert m['primary']['file'] in text.split('<body', 1)[1][:4096]
        assert 'onclick=' not in text and 'Copied ✓' not in text
        assert 'RESEARCH ONLY · DO NOT SUBMIT' in text if path.name == 'evidence.html' else True
        assert 'Second candidate for your next slot' not in text
        assert 'script-src \'self\'' in text


def test_missing_alternate_gate_defaults_to_archive_not_slot_advice():
    m = build_site.front(); m['alternates'][0].pop('submission_clearance')
    rendered = build_site.archives(m)
    assert 'No current-best scientific clearance recorded' in rendered
    assert 'DO NOT SUBMIT' in rendered
    m['alternates'][0]['submission_clearance'] = {'upload_allowed': True}
    with pytest.raises(ValueError, match='promotion'):
        build_site.archives(m)


def test_frozen_scientific_code_and_register_still_match_run():
    r = json.loads((ROOT / 'reports/holdout_r15_2026-10-01.json').read_text())
    for path, digest in r['source_code_hashes'].items():
        if path.startswith(('knowledge/', 'src/', 'scripts/')):
            assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    m = build_site.front()
    assert r['reference_primary_sha256'] == m['primary']['sha256']
    assert r['baseline_pixels_rebuilt_identically'] is True
    assert r['gate_passed'] is False and r['scientific_status'] == 'RESEARCH_ONLY_DO_NOT_SUBMIT'
    for family in r['summaries'].values():
        assert family[r['challenger']]['paired_wins_vs_current_best'] == 0
    assert all(a['submission_clearance']['upload_allowed'] is False for a in m['alternates'])


@pytest.mark.parametrize('dtype', [complex, object])
def test_submission_writer_rejects_nonreal_arrays(dtype, tmp_path, monkeypatch):
    monkeypatch.setattr(rio, 'EXPECTED_SHAPE', (2, 2))
    with pytest.raises(ValueError, match='real numeric'):
        rio.write_submission(tmp_path / 'bad.tif', np.ones((2, 2), dtype=dtype), np.ones((2, 2), bool))
    assert not (tmp_path / 'bad.tif').exists()


@pytest.mark.parametrize('badmask', [np.array([[1, 2], [0, 1]]), np.array([[1., np.nan], [0, 1]])])
def test_submission_writer_rejects_nonbinary_or_nan_mask(badmask, tmp_path, monkeypatch):
    monkeypatch.setattr(rio, 'EXPECTED_SHAPE', (2, 2))
    with pytest.raises(ValueError, match='valid_mask'):
        rio.write_submission(tmp_path / 'bad.tif', np.ones((2, 2)), badmask)
    assert not (tmp_path / 'bad.tif').exists()


def test_writer_ignores_outside_sentinels_without_overflow_and_keeps_inside_exact(tmp_path, monkeypatch):
    monkeypatch.setattr(rio, 'EXPECTED_SHAPE', (2, 2))
    values = np.array([[0, 1], [1e300, -1e300]])
    valid = np.array([[True, True], [False, False]])
    with np.errstate(over='raise', invalid='raise'):
        p = rio.write_submission(tmp_path / 'ok.tif', values, valid)
    with rasterio.open(p) as s:
        got = s.read(1)
    assert np.array_equal(got[valid], [0., 1.]) and np.isnan(got[~valid]).all()


@pytest.mark.parametrize('script', ['publish_front_door.py', 'publish_lattice_front_door.py', 'flip_primary_encoding.py',
                                     'republish_front_door_v2.py', 'publish_r14_union.py'])
def test_retired_or_failed_gate_publishers_exit_before_any_frontdoor_mutation(script):
    p = ROOT / 'docs/downloads/submit.json'; before = p.read_bytes()
    result = subprocess.run([sys.executable, str(ROOT / 'scripts' / script)], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode != 0 and p.read_bytes() == before
    assert ('Retired' in result.stderr or 'failed' in result.stderr)


def test_local_template_policy_rejects_infinity_without_inferring_platform_cause():
    m = build_site.front(); p = ROOT / 'docs/downloads' / m['primary']['file']
    with rasterio.open(p) as src:
        fp = np.isfinite(src.read(1))
    report = encoding.audit_file(p, fp)
    assert report['matches_template_policy'] is True and report['platform_acceptance_established'] is False
    report['range_checks']['n_inf'] = 1
    ok, deviations = encoding.accepted_pattern(report)
    assert not ok and 'infinite' in ' '.join(deviations)


def test_all_zero_format_valid_map_has_no_false_free_rescaling_gain(tmp_path, monkeypatch):
    monkeypatch.setattr(rio, 'EXPECTED_SHAPE', (2, 2))
    valid = np.array([[True, True], [False, False]])
    p = rio.write_submission(tmp_path / 'zero.tif', np.zeros((2, 2)), valid)
    report = rio.validate_submission(p, valid_mask=valid)
    assert report.ok
    assert any('no nonzero map' in warning for warning in report.warnings)
    assert not any('free score increase' in warning for warning in report.warnings)
