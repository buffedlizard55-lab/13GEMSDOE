'use strict';

// Clipboard denial is common in embedded previews. Never announce false success.
const copyButton = document.getElementById('copy-note');
if (copyButton) {
  copyButton.addEventListener('click', async () => {
    const status = document.getElementById('copy-status');
    const note = document.getElementById('submission-note');
    status.textContent = '';
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error('Unavailable');
      await navigator.clipboard.writeText(note.textContent.trim());
      status.textContent = 'Copied ✓';
    } catch (_) {
      const range = document.createRange();
      range.selectNodeContents(note);
      const selection = window.getSelection();
      if (selection) { selection.removeAllRanges(); selection.addRange(range); }
      status.textContent = 'Not copied. The note is selected—copy it manually.';
    }
  });
}

// A byte check protects against a stale file, a corrupt ZIP route or an HTML error
// page. It does not run a TIFF decoder or imply DrivenData acceptance.
const verifyButton = document.getElementById('verify-file');
if (verifyButton) {
  verifyButton.addEventListener('click', async () => {
    const status = document.getElementById('verify-status');
    const primary = document.querySelector('[data-testid="primary-download"]');
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 20000);
    verifyButton.disabled = true;
    status.classList.remove('error');
    status.textContent = 'Checking delivered bytes…';
    try {
      const response = await fetch(primary.href, {cache: 'no-store', signal: controller.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.arrayBuffer();
      if (data.byteLength !== Number(verifyButton.dataset.bytes)) throw new Error('Unexpected size; wrong or incomplete download');
      if (!window.crypto || !window.crypto.subtle) throw new Error('Secure-context hashing unavailable');
      const digest = await window.crypto.subtle.digest('SHA-256', data);
      const hash = Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, '0')).join('');
      if (hash !== verifyButton.dataset.sha256) throw new Error('SHA-256 differs from the verified file');
      status.textContent = 'Delivered bytes match the checked TIFF ✓ (not a platform receipt).';
    } catch (error) {
      status.classList.add('error');
      status.textContent = `Check failed: ${error.name === 'AbortError' ? 'request timed out' : error.message}. Do not upload an unverified file.`;
    } finally {
      window.clearTimeout(timeout);
      verifyButton.disabled = false;
    }
  });
}

// Only GitHub's public workflow metadata is requested; NEVER competition pages.
const hostedStatus = document.getElementById('hosted-review-status');
if (hostedStatus) {
  (async () => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 12000);
    try {
      const url = 'https://api.github.com/repos/buffedlizard55-lab/13GEMSDOE/actions/workflows/source-review.yml/runs?per_page=1';
      const response = await fetch(url, {signal: controller.signal, headers: {'Accept': 'application/vnd.github+json'}});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const body = await response.json();
      const run = body.workflow_runs && body.workflow_runs[0];
      if (!run) { hostedStatus.textContent = 'No hosted source-review run is recorded yet. Stored observations are dated below.'; return; }
      const stamp = new Date(run.updated_at);
      if (!Number.isFinite(stamp.getTime())) throw new Error('Invalid run timestamp');
      const date = stamp.toISOString().replace('T', ' ').replace('Z', ' UTC');
      const outcome = run.conclusion || run.status || 'unknown';
      const old = Date.now() - stamp.getTime() > 48 * 3600 * 1000;
      hostedStatus.textContent = `Latest workflow: ${outcome}, ${date}${old ? ' (older than 48 hours)' : ''}. A completed workflow can still contain source-fetch failures; inspect its observation artifact. This is not a live leaderboard.`;
    } catch (_) {
      hostedStatus.textContent = 'Workflow metadata unavailable here. Open the source-review workflow to inspect actual runs; stored observations below are not presented as live.';
    } finally { window.clearTimeout(timeout); }
  })();
}

// GitHub issue storage lets a static Pages site show current source observations
// without pushing to main, needing a backend, or scraping competition pages.
const observationPanel = document.getElementById('source-observations');
if (observationPanel) {
  (async () => {
    const status = document.getElementById('source-feed-status');
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 12000);
    try {
      const url = 'https://api.github.com/repos/buffedlizard55-lab/13GEMSDOE/issues?state=all&creator=github-actions%5Bbot%5D&per_page=100&sort=updated';
      const response = await fetch(url, {signal: controller.signal, headers: {'Accept': 'application/vnd.github+json'}});
      if (!response.ok) throw new Error('Feed unavailable');
      const issues = await response.json();
      if (!Array.isArray(issues)) throw new Error('Unexpected issue response');
      const issue = issues.find(r => r.title === 'Automated official-source observations (not competition scores)' && r.user && r.user.login === 'github-actions[bot]' && !r.pull_request);
      if (!issue || typeof issue.body !== 'string' || issue.body.length > 60000) throw new Error('No published bot feed');
      const begin = '<!-- 13GEMSDOE_SOURCE_FEED_V1 -->';
      const end = '<!-- END_13GEMSDOE_SOURCE_FEED_V1 -->';
      if (!issue.body.includes(begin) || !issue.body.includes(end)) throw new Error('Feed envelope missing');
      const block = issue.body.split(begin)[1].split(end)[0].trim();
      if (!block.startsWith('```json\n') || !block.endsWith('```')) throw new Error('Unexpected feed format');
      const feed = JSON.parse(block.slice(8, -3));
      const stamp = new Date(feed.generated_utc);
      if (feed.schema !== 1 || !feed.sources || !Number.isFinite(stamp.getTime())) throw new Error('Invalid feed schema/time');
      const rows = Object.entries(feed.sources);
      if (!rows.length || rows.length > 20) throw new Error('Invalid source count');
      const hosts = new Set(['gdr.openei.org','www.usgs.gov','docs.nlr.gov','docs.nrel.gov','api.waterdata.usgs.gov','api.github.com']);
      const states = new Set(['OBSERVED_OK','REVIEW_REQUIRED','FETCH_FAILED_LAST_SUCCESS_RETAINED','FETCH_FAILED_NO_SUCCESS']);
      const tbody = document.createElement('tbody');
      for (const [id, rec] of rows.sort(([a],[b]) => a.localeCompare(b))) {
        const target = new URL(rec.url);
        if (!/^[a-z][a-z0-9_]{0,31}$/.test(id) || target.protocol !== 'https:' || !hosts.has(target.hostname) || !['','443'].includes(target.port) || target.username || target.password || !states.has(rec.status)) throw new Error('Unapproved source row');
        const row = document.createElement('tr');
        const source = document.createElement('td');
        const link = document.createElement('a');
        link.href = target.href; link.textContent = String(rec.title).slice(0,350) + ' ↗';
        link.target = '_blank'; link.rel = 'noopener noreferrer'; source.append(link); row.append(source);
        const oldEndpoint = rec.last_success_url && rec.last_success_url !== rec.url ? ' Last success was for a previous endpoint.' : '';
        const fields = [rec.status, rec.last_success_utc || 'No successful observation yet', (rec.error || (rec.changed_since_previous_success ? 'Content changed: review required' : 'Observation only, not certification')) + oldEndpoint];
        for (const value of fields) { const cell = document.createElement('td'); cell.textContent = String(value).slice(0,2000); row.append(cell); }
        tbody.append(row);
      }
      const table = observationPanel.querySelector('table');
      table.querySelector('tbody').replaceWith(tbody);
      const old = Date.now() - stamp.getTime() > 48 * 3600 * 1000;
      status.textContent = `Bot-published observation run: ${stamp.toISOString()}${old ? ' (older than 48 hours)' : ''}. Failures retain last successful observations; changed sources require review. NOT a live leaderboard or scientific certification.`;
    } catch (_) {
      status.textContent += ' Hosted observation feed unavailable here; dated stored rows remain as fallback, not presented as current.';
    } finally { window.clearTimeout(timeout); }
  })();
}
