#!/usr/bin/env python3
"""Real Chromium UI/download/clipboard/integrity/axe/mobile regressions.

Uses normal browser security; no --disable-web-security. Local GitHub workflow
metadata can be stubbed for deterministic UI tests ONLY, never as live evidence.
No DrivenData form interaction or competition upload.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect

from serve_site import SiteHandler

ROOT = Path(__file__).resolve().parents[1]
AXE = ROOT / '.cache/browser/node_modules/axe-core/axe.min.js'


def run(base, require_axe=False):
    m = json.loads((ROOT / 'docs/downloads/submit.json').read_text())
    checks = []
    violations = []
    errors = []
    local = base.startswith('http://127.0.0.1:')

    def record(ok, text):
        checks.append({'pass': bool(ok), 'check': text}); print(('PASS ' if ok else 'FAIL '), text, flush=True)

    if require_axe and not AXE.exists():
        raise RuntimeError('Pinned axe-core4.11.0 required: npm install --prefix .cache/browser axe-core@4.11.0')
    cache = ROOT / '.cache/browser_downloads'; cache.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        options = {'headless': True}
        staging = ROOT / '.cache/chromium.json'
        if staging.exists():
            conf = json.loads(staging.read_text())
            options.update(executable_path=conf['executablePath'], args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--no-zygote'])
            if conf.get('libraryPath'):
                options['env'] = {**os.environ, 'LD_LIBRARY_PATH': conf['libraryPath']}
        browser = p.chromium.launch(**options)
        version = browser.version
        context = browser.new_context(accept_downloads=True)
        origin = urlsplit(base).scheme + '://' + urlsplit(base).netloc
        context.grant_permissions(['clipboard-read', 'clipboard-write'], origin=origin)
        if local:
            context.route('https://api.github.com/**', lambda route: route.fulfill(status=200, content_type='application/json', body=json.dumps({'workflow_runs': []})))
        page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
        paths = [''] + ['docs/' + f for f in ('index.html', 'executive_summary.html', 'evidence.html', 'hypotheses.html', 'sources.html')]
        for width, height in ((1440, 1000), (390, 844), (320, 568)):
            page.set_viewport_size({'width': width, 'height': height})
            for index, path in enumerate(paths):
                response = page.goto(base + path, wait_until='networkidle')
                label = f'{path or "root"} {width}x{height}'
                primary = page.get_by_test_id('primary-download')
                box = primary.bounding_box()
                record(response.status == 200 and primary.is_visible() and box and box['y'] >= 0 and box['y']+box['height'] <= height,
                       label + ': primary download visible ABOVE the first fold')
                record(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), label + ': no page-level horizontal overflow')
                record(page.locator('h1').count() == 1 and page.locator('main').count() == 1 and page.title().endswith('13GEMSDOE'), label + ': heading/main/title semantics')
                record(page.locator('#submission-note').inner_text() == m['note_for_form'], label + ': exact selectable short note')
                if width == 1440:
                    with page.expect_download() as d:
                        primary.click()
                    download = d.value; dest = cache / f'{index}-primary.tif'; download.save_as(dest)
                    record(download.suggested_filename == m['primary']['file'] and hashlib.sha256(dest.read_bytes()).hexdigest() == m['primary']['sha256'], label + ': one-click browser TIFF exact name/SHA256')
                    with page.expect_download() as d:
                        page.locator('a.button.secondary').click()
                    download = d.value; dest = cache / f'{index}-primary.zip'; download.save_as(dest)
                    record(download.suggested_filename == m['primary']['zip'] and hashlib.sha256(dest.read_bytes()).hexdigest() == m['primary']['zip_sha256'], label + ': browser ZIP exact name/SHA256')
                    if AXE.exists():
                        page.evaluate(AXE.read_text())  # CDP test instrumentation, not a change to site CSP/security
                        report = page.evaluate('async () => await axe.run(document, {runOnly: {type: "tag", values: ["wcag2a","wcag2aa","wcag21a","wcag21aa","best-practice"]}})')
                        issues = [{key: row[key] for key in ('id', 'impact', 'description', 'helpUrl', 'nodes')} for row in report['violations']]
                        violations.extend({'page': path or 'root', **row} for row in issues)
                        if issues:
                            print("AXE issues", [v["id"] for v in issues], flush=True)
                            (ROOT / ".cache/axe_violations.json").write_text(json.dumps(violations, indent=2))
                        record(not issues, label + ': axe WCAG2/2.1 A/AA + best-practice, no violations')
                if path == '' and width in (1440, 390):
                    page.screenshot(path=str(ROOT / ('.cache/site-desktop.png' if width == 1440 else '.cache/site-mobile.png')), full_page=True)
        page.set_viewport_size({'width': 1440, 'height': 1000})
        page.goto(base, wait_until='networkidle')
        page.locator('#copy-note').click()
        expect(page.locator("#copy-status")).to_contain_text("Copied ✓")
        record(page.evaluate('navigator.clipboard.readText()') == m['note_for_form'], 'Actual granted-permission clipboard round trip matches note')
        page.locator('.file-details > summary').click(); page.locator('#verify-file').click()
        expect(page.locator("#verify-status")).to_contain_text("Delivered bytes match")
        record('not a platform receipt' in page.locator('#verify-status').inner_text(), 'Browser integrity check succeeds for actual TIFF and states evidence limit')
        denied = browser.new_context()
        denied.add_init_script('Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText:async()=>{throw new DOMException("Denied","NotAllowedError")}}})')
        dp = denied.new_page(); dp.goto(base, wait_until='networkidle'); dp.locator('#copy-note').click()
        expect(dp.locator("#copy-status")).to_contain_text("Not copied")
        record('Copied ✓' not in dp.locator('#copy-status').inner_text() and dp.locator('#submission-note').inner_text() == m['note_for_form'], 'Clipboard denial: never false success, note still available')
        record(dp.evaluate('window.getSelection().toString()') == m['note_for_form'], 'Clipboard denial: fallback selects full note')
        denied.close()
        for kind in ('html-error', 'same-size-corruption'):
            negative = browser.new_context()
            payload = (ROOT / 'docs/downloads' / m['primary']['file']).read_bytes()
            if kind == 'html-error':
                payload = b'<!doctype html><h1>Login or error, not TIFF</h1>'
                content_type = 'text/html'
            else:
                payload = payload[:-1] + bytes([payload[-1] ^ 1]); content_type = 'image/tiff'
            negative.route('**/' + m['primary']['file'], lambda route: route.fulfill(status=200, content_type=content_type, body=payload))
            np = negative.new_page(); np.goto(base, wait_until='networkidle')
            np.locator('.file-details > summary').click(); np.locator('#verify-file').click()
            expect(np.locator("#verify-status")).to_contain_text("Check failed")
            text = np.locator('#verify-status').inner_text()
            record('Delivered bytes match' not in text and 'Do not upload' in text, kind + ': browser byte check rejects wrong body without false success')
            record(not np.locator('#verify-file').is_disabled(), kind + ': button recovers after error')
            negative.close()
        if local:
            page.goto(base + 'docs/sources.html', wait_until='networkidle')
            record('No hosted source-review run' in page.locator('#hosted-review-status').inner_text(), 'No workflow run: UI makes no fake live observation claim (local stub)')
            page.route('https://api.github.com/**', lambda route: route.fulfill(status=403, body='Unavailable'))
            page.reload(wait_until='networkidle')
            expect(page.locator("#hosted-review-status")).to_contain_text("unavailable")
            record('not presented as live' in page.locator('#hosted-review-status').inner_text(), 'GitHub metadata failure: dated observations not misrepresented as current')
        if local:
            # A bot issue is storage, not a source of automatically certified facts.
            from publish_source_feed import body_for, TITLE
            from refresh_open_sources import refresh
            import copy
            now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            sample = refresh({}, [{'id': 'gdr1391', 'title': '<img src=x onerror=alert(1)>', 'url': 'https://gdr.openei.org/submissions/1391'}], fetch=lambda _: {'sha256': 'a'*64, 'normalized_content_sha256': 'a'*64}, now=now)
            for kind in ('trusted', 'untrusted-author', 'unapproved-url'):
                fc = browser.new_context()
                sample_case = copy.deepcopy(sample)
                if kind == 'unapproved-url':
                    sample_case['sources']['gdr1391']['url'] = 'javascript:alert(1)'
                user = 'github-actions[bot]' if kind != 'untrusted-author' else 'untrusted-example-author'
                issue = {'title': TITLE, 'user': {'login': user}, 'body': body_for(sample_case)}
                fc.route('https://api.github.com/**', lambda route: route.fulfill(status=200, content_type='application/json', body='{"workflow_runs":[]}'))
                # One-argument route callback avoids interpreting Request as payload.
                payload = json.dumps([issue])
                fc.route('https://api.github.com/**/issues?**', lambda route: route.fulfill(status=200, content_type='application/json', body=payload))
                fp = fc.new_page(); fp.goto(base + 'docs/sources.html', wait_until='networkidle')
                fs = fp.locator('#source-feed-status')
                if kind == 'trusted':
                    expect(fs).to_contain_text('Bot-published observation run')
                    record(fp.locator('#source-observations tbody tr').count() == 1 and 'NOT a live leaderboard' in fs.inner_text(), 'Fresh bot observation displays automatically with evidence boundary')
                    record(fp.locator('#source-observations img').count() == 0 and '<img' in fp.locator('#source-observations').inner_text(), 'Untrusted feed strings rendered as literal text, never HTML')
                else:
                    expect(fs).to_contain_text('unavailable')
                    record('Bot-published observation run' not in fs.inner_text(), kind + ': refuse fabricated or unapproved live feed; retain dated fallback')
                fc.close()
        no_js = browser.new_context(java_script_enabled=False, accept_downloads=True)
        np = no_js.new_page(); np.goto(base)
        with np.expect_download() as d:
            np.get_by_test_id('primary-download').click()
        dest = cache / 'no-js-primary.tif'; d.value.save_as(dest)
        record(hashlib.sha256(dest.read_bytes()).hexdigest() == m['primary']['sha256'], 'JavaScript disabled: actual primary download still works')
        no_js.close()
        record(not errors, 'No uncaught site JavaScript errors in positive browser scenarios')
        context.close(); browser.close()
    failed = [c for c in checks if not c['pass']]
    return {'generated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'base_url': base,
            'browser_version': version, 'normal_browser_security': True,
            'local_workflow_metadata_stub': local, 'platform_acceptance_established': False,
            'axe_used': AXE.exists(), 'axe_violations': violations, 'uncaught_site_errors': errors,
            'primary_sha256': m['primary']['sha256'], 'total': len(checks), 'passed': len(checks)-len(failed),
            'failed': len(failed), 'checks': checks, 'all_passed': not failed}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--base-url'); ap.add_argument('--require-axe', action='store_true')
    ap.add_argument('--output', type=Path, default=ROOT / '.cache/site_browser.json'); args = ap.parse_args()
    server = None
    try:
        if args.base_url:
            base = args.base_url.rstrip('/') + '/'
        else:
            server = ThreadingHTTPServer(('0.0.0.0', 0), SiteHandler)
            threading.Thread(target=server.serve_forever, daemon=True).start(); base = f'http://127.0.0.1:{server.server_port}/'
        try:
            report = run(base, args.require_axe)
        except Exception as ex:
            print("BROWSER CHECK ABORTED:", type(ex).__name__, str(ex), flush=True)
            report = {"status": "ABORTED_SEE_PRIOR_CHECK_LOGS", "base_url": base, "all_passed": False, "passed": 0, "total": 1, "failed": 1, "error": str(ex), "axe_violations": [], "platform_acceptance_established": False}
        args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(report, indent=2) + '\n')
        print(f'\n{report["passed"]}/{report["total"]} browser checks; {len(report["axe_violations"])} axe violations.')
        return 0 if report['all_passed'] else 1
    finally:
        if server:
            server.shutdown(); server.server_close()


if __name__ == '__main__':
    raise SystemExit(main())
