#!/usr/bin/env python3
"""Build the small, manifest-driven site. Never publishes or changes predictions.

submit.json is the only source of download names/roles/hashes/note. Reports supply
scientific status. Missing/unknown gates default to research-only, never next-slot
advice. The build refuses absent or hash-mismatched download bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
DL = DOCS / 'downloads'
REPO = 'https://github.com/buffedlizard55-lab/13GEMSDOE'
SITE_REVISION = 'r15-audit-20261001'
PAGES = [('index.html', 'Overview'), ('executive_summary.html', 'How to submit'),
         ('evidence.html', 'Evidence'), ('hypotheses.html', 'Research'), ('sources.html', 'Sources & feed')]


def load(path):
    return json.loads((ROOT / path).read_text())


def e(value):
    return html.escape(str(value), quote=True)


def repository(path, label=None):
    return f'<a href="{REPO}/blob/main/{e(path)}" target="_blank" rel="noopener noreferrer">{e(label or path)} ↗</a>'


def external(url, label):
    if not url.startswith('https://'):
        raise ValueError('External site links must use HTTPS')
    return f'<a href="{e(url)}" target="_blank" rel="noopener noreferrer">{e(label)} ↗</a>'


def front():
    m = load('docs/downloads/submit.json')
    if m.get('schema') != 2:
        raise ValueError('Schema2 primary/hedge manifest required; never infer old A/B roles')
    entries = [m['primary'], m['hedge']]
    for alt in m.get('alternates', []):
        entries.extend((alt['primary'], alt['hedge']))
    for rec in entries:
        for suffix, size, digest in [('file', 'bytes', 'sha256'), ('zip', 'zip_bytes', 'zip_sha256')]:
            name = rec[suffix]
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*\.(tif|zip)', name) or Path(name).name != name:
                raise ValueError('Unsafe/non-local download filename')
            p = DL / name
            if not p.is_file() or p.stat().st_size != rec[size] or hashlib.sha256(p.read_bytes()).hexdigest() != rec[digest]:
                raise ValueError(f'Download missing or differs from manifest: {name}')
    note = m['note_for_form']
    if not note.strip() or len(note) > 160 or any(x in note for x in '\r\n'):
        raise ValueError('A single short submission note is required')
    if not m['primary']['file'].endswith('_nan-outside.tif') or not m['hedge']['file'].endswith('_zerofill.tif'):
        raise ValueError('Primary/diagnostic roles inverted')
    return m


def table(headers, rows):
    return '<div class="table-wrap"><table><thead><tr>' + ''.join(f'<th scope="col">{e(h)}</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{v}</td>' for v in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def result_table(r):
    rows = []
    for key, label in [('existing_system_and_segment', '18 system / segment folds'), ('geographic_stress', '4 geographic blocks')]:
        base = r['summaries'][key][r['reference']]
        cand = r['summaries'][key][r['challenger']]
        rows.append([e(label), f'{base["mean_dti"]:.6f}', f'{cand["mean_dti"]:.6f}',
                     f'{cand["paired_mean_delta"]:+.6f}', f'{cand["paired_wins_vs_current_best"]}/{cand["n_folds"]}'])
    return table(['Proxy protocol', 'Lattice reference', '+ Thermal', 'Paired mean Δ', 'Wins'], rows)


def hero(m, root=False):
    prefix = 'docs/' if root else ''
    primary = m['primary']
    return f'''<section class="download-hero" aria-labelledby="download-title" id="download">
<div class="hero-copy"><p class="eyebrow">DOE GEMS · submission workspace</p>
<h1 id="download-title">Download the competition TIFF.</h1>
<p class="hero-lead">One file. The official grid. Checked predictions in <strong>[0, 1]</strong>.</p>
<div class="download-actions"><a class="button primary" data-testid="primary-download" href="{prefix}downloads/{e(primary['file'])}" download>↓ Download submission .tif <span>{primary['bytes']/1e6:.1f} MB</span></a>
<a class="button secondary" href="{prefix}downloads/{e(primary['zip'])}" download>Download .zip</a></div>
<p class="file-name"><code>{e(primary['file'])}</code></p>
<p class="format-line">1 band · float32 · EPSG:32611 · 3730 × 3292 · 100 m</p>
</div><div class="download-status" role="group" aria-label="Download status">
<span class="status good">✓ Local format checked</span>
<h2>Current local reference</h2><p>Stride-5 coverage lattice. <strong>Not a geological discovery or a predicted leaderboard score.</strong></p>
<p class="status-limit">DrivenData acceptance is <strong>not confirmed</strong>. No new experiment is cleared for a weekly slot.</p>
<a href="{prefix}executive_summary.html" class="text-link">Exact submission steps →</a>
</div></section>
<section class="note-panel" aria-labelledby="note-label"><div><h2 id="note-label">Short note for the submission form</h2><code id="submission-note">{e(m['note_for_form'])}</code></div>
<div class="note-action"><button class="button small" type="button" id="copy-note">Copy note</button><span id="copy-status" class="small-text" role="status" aria-live="polite"></span></div></section>
<section aria-label="File integrity and diagnostic encoding"><details class="file-details"><summary>File integrity, encoding &amp; diagnostic alternative</summary>
<p><strong>Primary SHA-256:</strong> <code class="hash">{e(primary['sha256'])}</code></p>
<button class="button small" id="verify-file" type="button" data-sha256="{e(primary['sha256'])}" data-bytes="{primary['bytes']}">Check delivered file</button> <span id="verify-status" role="status" aria-live="polite"></span>
<p>The primary has finite predictions inside the official footprint and <strong>NaN / NoData=nan outside</strong>. LZW, one-row strips, no predictor; matches the measured template convention. A local check is not a platform receipt.</p>
<p><a href="{prefix}downloads/{e(m['hedge']['file'])}" download>Zero-filled diagnostic TIFF</a> · <a href="{prefix}downloads/{e(m['hedge']['zip'])}" download>diagnostic ZIP</a>. Same footprint predictions, zeros outside, no NoData. <strong>Not the official template convention, not a second scientific experiment, and not an automatic second upload.</strong></p>
<p><a href="{prefix}downloads/submit.json">Download manifest</a> · {repository('reports/form_responses.json', 'Recorded form evidence')}</p></details></section>'''


def overview(m, r, lb):
    leader = lb['rows'][0]
    return f'''<section class="section-heading"><p class="eyebrow">Start here</p><h2>A usable download. An honest research trail.</h2><p>Separate the file that works locally from the ideas that still need to earn a submission slot.</p></section>
<div class="cards three"><article class="card"><span class="card-index">01 / SUBMIT</span><h3>Download, then upload once</h3><p>Use the prominent TIFF or its one-TIFF ZIP. Do not upload this website, a report, or the feature stack.</p><a class="text-link" href="executive_summary.html">Follow the submission guide →</a></article>
<article class="card"><span class="card-index">02 / RESEARCH</span><h3>The latest idea did not pass</h3><p>Independent shallow-thermal corridors lost on all <strong>18 + 4</strong> paired folds. We kept the current reference; no slot was spent.</p><a class="text-link" href="hypotheses.html">See the predeclared test →</a></article>
<article class="card"><span class="card-index">03 / AUDIT</span><h3>Repeated 0.1563 investigated</h3><p>GEMSDOE1 and 5GEMSDOE share an exact historical TIFF blob. A different 8GEMSDOE map carries the same reported score label.</p><a class="text-link" href="evidence.html">Identity is not a score receipt →</a></article></div>
<section class="section-heading"><p class="eyebrow">Latest measured experiment · R15</p><h2>Independent data, unchanged standards.</h2><p>2,782 licensed 2 m temperature probes inside the exact footprint; 48 aligned neighbourhoods, {r['field']['positive_pixels']} raster cells. The additional mass did not earn enough truth credit.</p></section>
{result_table(r)}<p class="caption">Local known-catalogue proxy scores only. The two protocols have different scoring domains; do not compare their absolute values as leaderboard estimates.</p>
<div class="callout warning"><h3>Research-only means no weekly slot</h3><p>R14 failed its gate; R15 failed its gate. Older geological maps are retained as archives, not promoted as “next slot” candidates.</p></div>
<section class="split"><div><p class="eyebrow">Competition snapshot</p><h2>{leader['best_public_dw_tversky']:.4f} <span class="muted-heading">public leader</span></h2><p>{e(leader['account'])}, reviewed {e(lb['fetched_utc'][:10])}. The brief’s 0.3049 target is stale. This is an account/team best, not an artifact receipt.</p>{external(lb['source_url'], 'Open official leaderboard')}</div>
<div class="card"><p class="eyebrow">How we work</p><h3>Maximize P(Win). Own the Outcome.</h3><p>Obtain data. Predeclare the mechanism. Hide labels safely. Charge every false-positive pixel. Record failures. Promote only a current-best winner.</p><a class="text-link" href="sources.html">Official sources &amp; automatic review →</a></div></section>'''


def executive(m):
    return f'''<section class="section-heading"><p class="eyebrow">Executive summary</p><h2>Exactly how to make a submission</h2><p>The download at the very top is the competition raster—not a document. These steps prepare an upload; they do not claim a new experiment has cleared the research gate.</p></section>
<ol class="steps"><li><div class="step-number">1</div><div><h3>Download the primary .tif above</h3><p>Keep its unique filename unchanged. The ZIP alternative contains <strong>exactly one identical TIFF</strong>. Choose one format, not both.</p></div></li>
<li><div class="step-number">2</div><div><h3>Open the official competition form</h3><p>Sign in to your enrolled competition account. In the sidebar choose <strong>Submit → Make new submission</strong>.</p>{external(m['form_url'], 'Open DrivenData submission form')}</div></li>
<li><div class="step-number">3</div><div><h3>Select the downloaded raster</h3><p>Choose <code>{e(m['primary']['file'])}</code>, or its one-TIFF ZIP. Do not select <code>submit.json</code>, this summary, a multi-band input raster, or an entire folder.</p></div></li>
<li><div class="step-number">4</div><div><h3>Paste the short note shown above</h3><p>The recipe, revision and date distinguish this reference from archived maps. “Copy note” reports success only if the browser actually copies it; the text remains selectable if clipboard permission is denied.</p></div></li>
<li><div class="step-number">5</div><div><h3>Submit once, then inspect the platform result</h3><p>Only DrivenData’s response confirms acceptance. Retain the filename, full SHA-256, note and result for the submission ledger. An account-best leaderboard value alone is not that receipt.</p></div></li></ol>
<div class="callout warning"><h3>If you see “Predicted values must be in range [0, 1]”</h3><p><strong>Stop—do not blindly repeat uploads.</strong> Use “Check delivered file” above to rule out a wrong/stale/HTML download. The current named TIFF has finite [0,1] values inside the footprint; NaN outside follows the official template. The cause of the earlier rejection is still unresolved.</p><p>The zero-filled twin is explicitly diagnostic, not automatic next-slot advice. A simulated Predictor2 error is not evidence of DrivenData’s decoder. Whether a rejected upload consumes allowance was not verified.</p></div>
<section class="section-heading"><h2>Before using a scarce slot</h2><p>The official allowance is three scored submissions per rolling week, not three per calendar-week reset. A new geological hypothesis must first beat the current best on paired system and geographic-block holdouts. <strong>Neither R14 nor R15 qualifies.</strong></p></section>
<div class="cards two"><article class="card"><h3>Format is checked locally</h3><p>One float32 band, EPSG:32611, 100 m cells, exact shape and affine, finite [0,1] footprint values, correct outside placement, ZIP CRC/identity, and agreement across three TIFF readers.</p>{external(m['format_source'], 'Official format specification')}</article>
<article class="card"><h3>Eligibility and final narrative matter</h3><p>Read the governing rules for eligibility, team/entity restrictions, external-data licences and final reproducibility requirements. Generative-AI assistance must be disclosed in the final narrative under §3.2.</p>{external('https://docs.nlr.gov/docs/fy26osti/96647.pdf', 'Governing Official Rules')}</article></div>
<p class="caption">This workspace has no authenticated competition session and makes no automatic competition uploads. Your account’s available allowance and eligibility are not inferred.</p>'''


def evidence(m, r, siblings):
    repeated = siblings.get('conclusion', {})
    reuse = 'Verified from pinned GitHub trees' if repeated.get('artifact_reuse_established_for_GEMSDOE_and_5GEMSDOE') else 'Verification incomplete; inspect report'
    rows = [['Local format', '<span class="status good">PASS</span>', 'Grid, range, footprint, layout, hashes and independent TIFF decoders.'],
            ['Download delivery', 'Separate HTTP / browser check', 'See CI and live smoke report. On-disk validation alone is not HTTP verification.'],
            ['DrivenData acceptance', '<span class="status caution">UNCONFIRMED</span>', 'No response tied to the current named file/hash is recorded.'],
            ['New scientific clearance', '<span class="status caution">NOT CLEARED</span>', 'R14 failed D2/D3. R15 lost all 18 existing + 4 geographic paired folds.']]
    return f'''<section class="section-heading"><p class="eyebrow">Evidence, not inference</p><h2>Four separate gates.</h2><p>Passing one does not establish the others.</p></section>{table(['Assertion', 'State', 'Evidence boundary'], rows)}
<section class="section-heading"><h2>Why did 0.1563 repeat?</h2><p><strong>{e(reuse)}:</strong> GEMSDOE (GEMSDOE1), 5GEMSDOE and GEMSDOE2 contain the identical historical ens12 blob.</p></section>
<div class="card"><p><strong>Git blob:</strong> <code class="hash">812e61b74050d1350cc2bde1fab0c76ead32e0c4</code></p><p><strong>File SHA-256:</strong> <code class="hash">7f00890a62878d612fb5eef67a9a364a2df819433dde74b6762ce4fc0fc4fe15</code></p><p>Exact byte reuse is established. Which file was uploaded and which submission earned a score are <strong>not established</strong> by a repo filename or rounded account-best score.</p></div>
{table(['Comparison', 'Measured artifact relationship', 'What it means'], [
 ['GEMSDOE1 ↔ 5GEMSDOE', 'Same historical ens12 blob; 570,890 bytes', 'Artifact reuse, not per-upload score attribution'],
 ['ens12 ↔ 8GEMSDOE apex', 'Different file / canonical pixels / support; IoU 0.06703', 'Same reported 0.1563 can refer to distinct maps'],
 ['ens12 ↔ GEMSDOE2 dualunion', 'Distinct pixels; support IoU 0.94191', 'High overlap is not exact identity']])}
<p>{repository('reports/sibling_site_audit_2026-10-01.json', 'Pinned prior-site review')} · {repository('reports/scored_forensics.json', 'Decoded-pixel forensics')} · {repository('reports/leaderboard_ledger.csv', 'Score-attribution ledger')}</p>
<section class="section-heading"><h2>The archived rejection’s cause is unresolved</h2><p>The rejected TIFF decodes to valid footprint values in rasterio/GDAL, tifffile and Pillow. Deliberately ignoring Predictor2 in a simulation can yield [-4, 3], but no server trace shows DrivenData did that. Earlier claims of a confirmed predictor root cause, falsified NaN handling, or a changed validator were withdrawn.</p></section>
<p>{repository('reports/platform_encoding_evidence.json', 'Current byte-level encoding audit')} · {repository('knowledge/13_audit_corrections_2026-10-01.md', 'Correction register')}</p>
<section class="section-heading"><h2>Scientific confirmation, with failures visible</h2><p>No local proxy can stand in for expert hidden truth. The thermal field was built without receiving fault labels; scoring masks and code/source hashes are stored per fold.</p></section>{result_table(r)}
<p>{repository('reports/holdout_r15_2026-10-01.json', 'Full R15 components and fold hashes')} · {repository('knowledge/12_r15_results.md', 'Interpretation & limitations')}</p>
<details><summary>Older rasters — research archive, not next-slot candidates</summary>{archives(m)}</details>
<section class="section-heading"><h2>Operational irregularities addressed</h2></section><ul class="audit-list"><li>Removed failed-gate “next slot” promotion and contradictory primary/hedge instructions.</li><li>Retired schema1 migration commands; new research exports cannot silently replace the live primary.</li><li>Clipboard success is conditional; download integrity is checked against the manifest.</li><li>Band6 identity was independently rerun: radiometric total count, despite misleading embedded text (rho 0.999978, R² 0.998037).</li><li>Missing input sentinels occur inside the valid footprint. Output writers refuse invalid values instead of silently clipping them.</li></ul>
<p>{repository('reports/site_review.json', 'Three-pass review record')} · {repository('reports/band6_identity.json', 'Band6 comparison')} · {external(REPO + '/actions', 'Automated verification runs')}</p>'''


def archives(m):
    out = []
    for alt in m.get('alternates', []):
        # Never infer approval from a filename or an old local win.
        clearance = alt.get('submission_clearance', {})
        if clearance.get('upload_allowed') is True:
            raise ValueError('Alternate promotion needs an explicit current-best review; this archive renderer does not recommend uploads')
        out.append(f'''<article class="archive-item"><h3>{e(alt['label'])}</h3><span class="status caution">RESEARCH ONLY · DO NOT SUBMIT</span><p>{e(clearance.get('reason', 'No current-best scientific clearance recorded.'))}</p>
<p><a href="downloads/{e(alt['primary']['file'])}" download>Archived TIFF</a> · <a href="downloads/{e(alt['primary']['zip'])}" download>one-TIFF ZIP</a></p></article>''')
    return ''.join(out)


def research(r):
    candidates = [
        ('01', 'Survey-corrected 2 m thermal corridors', 'GDR1391 Area, T2m, F2mDAB, location and dates.', 'Warm, same-survey probes aligned over a measured span; possible steam-heated upflow beneath cover. Heat is not displacement.', 'New measured thermal input, not a radiometric edge or paleo-deposit halo. Previously proposed H-G, now tested.', 'Small regional upside; low cost; data obtained.', 'TESTED · FAILED GATE'),
        ('02', 'Displaced lithologic-marker registration', 'Provided RTP/TMI; verified GeoDAWN K/Th/U; elevation as confounder control.', 'Matching multi-channel markers with a consistent nonzero offset across a prospective seam. Contacts/texture can mimic displacement.', 'Test a registration offset, not gradient strength or edge consensus.', 'Medium possible upside; medium-high cost; inputs obtained.', 'NOT IMPLEMENTED'),
        ('03', 'Focal-mechanism plane coherence', 'USGS ComCat individual hypocentres and focal/moment-tensor planes, with uncertainties.', 'Coherent event-plane geometry projected toward a supported shallow trace. Active blind faults may have no scarp; nodal planes are ambiguous.', 'Individual planes, not the provided smoothed seismic-density gate. Revives an untested proposal.', 'Medium / high variance; high cost; event products not yet staged.', 'NOT DATA-READY'),
        ('04', 'Groundwater-head response compartments', 'USGS monitoring sites, time-resolved levels, aquifer/depth/datum/pumping metadata.', 'Persistent cross-boundary head offsets or different responses after harmonization. Pumping/lithology can produce the same pattern.', 'Paired temporal hydraulic contrasts, not surface drainage or static chemistry. Revives an untested proposal.', 'Low-to-medium possible; high cost; comparable network not established.', 'NOT DATA-READY')]
    blocks = []
    for rank, title, layers, signature, difference, cost, status in candidates:
        blocks.append(f'<article class="hypothesis-card"><div class="hypothesis-title"><span class="card-index">{rank}</span><h3>{e(title)}</h3><span class="status caution">{e(status)}</span></div><dl><dt>Exact inputs</dt><dd>{e(layers)}</dd><dt>Physical signature / off-catalogue rationale</dt><dd>{e(signature)}</dd><dt>Difference from implemented approaches</dt><dd>{e(difference)}</dd><dt>Expected DTI / cost / obtainability</dt><dd>{e(cost)} Qualitative planning judgment, not a score forecast.</dd></dl></article>')
    return f'''<section class="section-heading"><p class="eyebrow">Predeclared before implementation</p><h2>Independent observations before another ensemble.</h2><p>Four unimplemented data/transform combinations were ranked. This is repository-level novelty, not a claim of new scientific laws; three revive previously untested proposals.</p></section>
{''.join(blocks)}<p>{repository('knowledge/11_r15_predeclared.md', 'Frozen specification, sources, criteria and gates')}</p>
<section class="section-heading"><h2>Top candidate: measured, then rejected for submission</h2><p>The frozen DAB ≥ 3°C / 1.5 km / ≥3 stations / PCA axis ratio ≥4 / perpendicular RMS ≤300 m rule drew observed spans only. No label-driven field construction, extrapolated regional halo, parameter sweep or after-the-fact threshold tuning.</p></section>{result_table(r)}
<div class="callout warning"><h3>{e(r['scientific_status'])}</h3><p>The thermal union won zero paired folds. All required improvement/win gates failed. It is not downloadable as a new competition recommendation; the current primary is unchanged.</p></div>
<p>Geographic stress folds use 25.6 km tiles, four fixed checkerboard partitions, a 500 m visible-label buffer and a 300 m scoring guard. Existing random/short/isolated/oriented/dense system folds and segment folds are rerun separately. Public covariates remain visible; only catalogue labels are withheld. Neither protocol reproduces hidden expert truth.</p>
<p>{repository('src/gems/thermal.py', 'Thermal transform')} · {repository('src/gems/spatial.py', 'Geographic folds')} · {repository('reports/holdout_r15_2026-10-01.json', 'Per-fold results')} · {repository('knowledge/12_r15_results.md', 'Failure analysis')}</p>
<section class="section-heading"><h2>Next experiment, not next upload</h2><p>Displaced-marker matching has obtainable inputs and a different observation to test. Start with synthetic offset/confounder tests and a frozen paired gate. Event-plane and well-network proposals stay blocked until usable official data are actually acquired.</p></section>'''


def sources(facts, feed, siblings):
    rows = []
    for source in facts['sources']:
        claims = '<ul class="compact-list">' + ''.join(f'<li>{e(c)}</li>' for c in source['claims']) + '</ul>'
        rows.append([external(source['url'], source['title']) + f'<br><span class="small-text">{e(source["publisher"])}</span>', claims,
                     e(source['limits']), e(source['last_reviewed'])])
    observed = []
    for key, rec in sorted(feed.get('sources', {}).items()):
        observed.append([external(rec['url'], rec['title']), e(rec['status']),
                         e(rec.get('last_success_utc', 'No automated success yet')),
                         e(rec.get('error') or ('Content changed: review required' if rec.get('changed_since_previous_success') else 'Observation only, not certification'))])
    prior = [[external(rec.get('site_url', f'https://buffedlizard55-lab.github.io/{name}/'), name),
              f'<code>{e(rec.get("commit", "unverified")[:12])}</code>',
              e(len(rec.get('site_pages_read', []))), e(len(rec.get('shared_ens12_paths', [])))]
             for name, rec in siblings.get('repos', {}).items()]
    return f'''<section class="section-heading"><p class="eyebrow">Verified sources, reusable knowledge</p><h2>Every claim has a boundary and a source.</h2><p>Official competition/scientific sources were reviewed on {e(facts['review_date'])}. Team pages are evidence about artifacts, not independent geological verification.</p></section>
{table(['Official source', 'Supported claims', 'What it does not establish', 'Reviewed'], rows)}
<p>{repository('reports/verified_sources_2026-10-01.json', 'Curated source register')} · {repository('knowledge/01_verified_facts.md', 'Fact base')} · {repository('knowledge/13_audit_corrections_2026-10-01.md', 'Irregularities and corrections')}</p>
<section class="section-heading"><h2>Automated source-change review</h2><p>Daily GitHub-hosted review checks approved open-data / organizer-repository endpoints, records hashes and failures, flags changes, and publishes one reusable bot issue that this page reads automatically. It never polls DrivenData or its forum, overwrites a successful observation with a failed body, or silently certifies new facts.</p></section>
<div class="card feed-status"><h3>Latest hosted review</h3><p id="hosted-review-status">Checking public workflow metadata…</p>{external(REPO + '/actions/workflows/source-review.yml', 'Source-review workflow')}<p class="caption">Workflow status comes from GitHub Actions; current observations come from the marked bot issue. Stored observations are a dated fallback; the leaderboard remains a one-off reviewed snapshot.</p></div>
<p id="source-feed-status" class="caption" role="status">Stored observation run: {e(feed.get('generated_utc', 'Not run'))}. Checking the bot-published current feed. Sandbox TLS failures are not failures of the official datasets.</p>
<div id="source-observations">{table(['Automated endpoint', 'Observation state', 'Last successful observation', 'Limit / error'], observed)}</div>
<p>{repository('reports/open_source_feed.json', 'Stored feed JSON')} · {repository('config/open_sources.json', 'Approved endpoint list')}</p>
<section class="section-heading"><h2>Data obtainability &amp; attribution</h2></section>
{table(['Data', 'Acquisition / validation', 'Licence / limit'], [
 ['Competition template / labels / 19-band stack', 'Autonomously recovered from pinned group mirrors; SHA-256 verified; prepared locally.', 'Official data tab requires competition sign-in. Mirror verification is not a new first-party download.'],
 ['GDR1391 thermal and paleo features', 'Earlier official download in a hosted runner; source hashes and 2,782-probe footprint checked locally.', 'Ayling, Bridget, et al. (2022), INGENIOUS compilation, GBCGE/NBMG/UNR, DOI10.15121/1881483. CC-BY-4.0; derived R15 lines are transformations, not original measurements.'],
 ['GeoDAWN / 3DEP compact derivatives', 'Fetched six pinned products and reran band6 identity.', 'Glen & Earney (2024), DOI10.5066/P93LGLVQ, CC0; USGS National Geospatial Program/3DEP attribution. Derivatives are quantized and coverage varies.'],
 ['New focal-plane / well-head inputs', 'Official APIs identified; complete usable regional tables not staged.', 'Do not call these viable until acquisition, CRS/schema/coverage and licence checks pass.']])}
<p>{repository('reports/gdr1391_fetch.json', 'GDR download hashes')} · {repository('reports/external_manifest.json', 'External-data provenance')} · {external('https://gdr.openei.org/files/1391/2m_temperature_probe_INGENIOUS_regional_data.zip', 'Thermal archive (field-definition README inside)')}</p>
<section class="section-heading"><h2>Prior supplied project sites</h2><p>Read-only pinned HTML/tree audit. “Shared ens12 paths” means exact historical byte identity, not a verified upload or score. Historical user-reported scores remain explicitly unreceipted in the ledger.</p></section>
{table(['Project site', 'Pinned commit', 'Pages inspected', 'Shared ens12 paths'], prior)}
<p>{repository('reports/sibling_site_audit_2026-10-01.json', 'Full prior-site audit with hashes and excerpts')}</p>
<div class="callout"><h3>AI disclosure</h3><p>Generative AI assisted source review, hypothesis design, code and documentation. Participants remain responsible for accuracy/authorship; disclose the extent and use in the final narrative under Official Rules §3.2.</p></div>'''


def document(active, title, body, m, root=False):
    prefix = 'docs/' if root else ''
    if root:
        # Overview links are doc-relative inside the overview body.
        for path, _ in PAGES:
            body = body.replace(f'href="{path}"', f'href="docs/{path}"')
    nav = ''.join(f'<a href="{prefix}{name}"' + (' aria-current="page"' if name == active else '') + f'>{e(label)}</a>' for name, label in PAGES)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="13GEMSDOE: one-click, format-checked competition TIFF; explicit submission steps and auditable geological research.">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self' https://api.github.com; object-src 'none'; base-uri 'self'">
<title>{e(title)} · 13GEMSDOE</title><link rel="stylesheet" href="{prefix}assets/style.css"><script src="{prefix}assets/site.js" defer></script></head>
<body data-site-revision="{SITE_REVISION}"><a class="skip-link" href="#main">Skip to page content</a>
<div class="shell"><header class="masthead"><a class="brand" href="{prefix}index.html" aria-label="13GEMSDOE home"><span class="brand-mark">13</span><span>GEMSDOE<small>Fault mapping, with evidence.</small></span></a>{external('https://www.drivendata.org/competitions/306/competition-doe-gems/', 'Official competition')}</header>
{hero(m, root)}<nav class="page-nav" aria-label="Main navigation">{nav}</nav><main id="main">{body}</main>
<noscript><p class="caption">Downloads work without JavaScript. Copy the selectable note manually; use the dated evidence and workflow links instead of interactive checks.</p></noscript>
<footer><span>13GEMSDOE · Maximize P(Win) / Own the Outcome</span><span>{external(REPO, 'Code & evidence')} · Facts reviewed 2026-10-01</span><p>Local verification ≠ live delivery ≠ platform acceptance ≠ scientific clearance. No competition upload is automated.</p></footer></div></body></html>
'''


def render():
    m = front()
    r = load('reports/holdout_r15_2026-10-01.json')
    if r['gate_passed'] or r['scientific_status'] != 'RESEARCH_ONLY_DO_NOT_SUBMIT':
        raise ValueError('R15 status changed: review narrative and gate before publishing a site')
    lb = load('reports/leaderboard_snapshot_2026-10-01.json')
    facts = load('reports/verified_sources_2026-10-01.json')
    feed = load('reports/open_source_feed.json')
    siblings = load('reports/sibling_site_audit_2026-10-01.json')
    bodies = {'index.html': overview(m, r, lb), 'executive_summary.html': executive(m),
              'evidence.html': evidence(m, r, siblings), 'hypotheses.html': research(r),
              'sources.html': sources(facts, feed, siblings)}
    outputs = {DOCS / name: document(name, label, bodies[name], m) for name, label in PAGES}
    outputs[ROOT / 'index.html'] = document('index.html', 'Submission download', bodies['index.html'], m, root=True)
    return outputs


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true', help='Fail if committed generated HTML is stale')
    args = ap.parse_args()
    mismatches = []
    for path, content in render().items():
        if args.check:
            if not path.exists() or path.read_text() != content:
                mismatches.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)
            print('built', path.relative_to(ROOT))
    if mismatches:
        print('STALE generated site:', ', '.join(mismatches)); return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
