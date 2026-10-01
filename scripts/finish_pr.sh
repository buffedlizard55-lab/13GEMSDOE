#!/usr/bin/env bash
# Safe resume helper for THIS Arena branch only. Never switches/deletes branches,
# pushes to main, force-pushes, or merges a different head commit. Run only after
# the current work is committed and the GitHub connection is functioning.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
BRANCH="arena/01a0f57b-13gemsdoe"
REPO="buffedlizard55-lab/13GEMSDOE"
[[ "$(git branch --show-current)" == "$BRANCH" ]] || { echo "Wrong branch; this session is fixed to $BRANCH"; exit 1; }
[[ -z "$(git status --porcelain)" ]] || { echo 'Commit the reviewed changes on the session branch first; no automatic staging.'; exit 1; }
PY=.venv/bin/python; [[ -x "$PY" ]] || PY=python3
"$PY" -m pytest tests -q
"$PY" scripts/audit_metric.py
"$PY" scripts/build_site.py --check
"$PY" scripts/verify_download.py
"$PY" scripts/verify_site_http.py
"$PY" scripts/verify_site_browser.py --require-axe
HEAD_SHA="$(git rev-parse HEAD)"
git push origin "$BRANCH"
URL="$(gh pr list --repo "$REPO" --base main --head "$BRANCH" --state open --json url --jq '.[0].url // empty')"
if [[ -z "$URL" ]]; then
  URL="$(gh pr create --repo "$REPO" --base main --head "$BRANCH" --title 'Working front-door TIFF, honest R15 failure, source feed and full verification' --body-file .github/PR_BODY_CURRENT.md)"
fi
echo "PR: $URL"
# Fails closed if no checks are registered, pending/failing, or access is blocked.
# No forced merge and no branch deletion. Hosted checks are required in addition
# to local checks; re-run after GitHub registers/completes them if necessary.
gh pr checks "$URL" --repo "$REPO" --watch
gh pr merge "$URL" --repo "$REPO" --merge --match-head-commit "$HEAD_SHA"
gh api "repos/$REPO/pages/builds/latest" --jq '{status, commit, updated_at}'
echo 'Merge response is not deployment proof. Run/watch the deployed Pages smoke test next.'
