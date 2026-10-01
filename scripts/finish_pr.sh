#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Finish session 8: push, open the PR, merge it to main, and confirm Pages.
#
# WHY THIS EXISTS: the GitHub token in this sandbox expired mid-session
# (`gh auth status` -> "The github.com token in GH_TOKEN is no longer valid"),
# so the work is committed locally on arena/01a0f510-13gemsdoe but was never
# pushed. Reconnect GitHub in Arena, then run this once:
#
#     bash scripts/finish_pr.sh
#
# It is idempotent: it re-checks the build before pushing, and it will not
# open a second PR if one already exists for this branch.
# ---------------------------------------------------------------------------
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
BRANCH="arena/01a0f510-13gemsdoe"
BASE="main"
REPO="buffedlizard55-lab/13GEMSDOE"

echo "== 0. auth =="
gh auth status || { echo "FAIL: GitHub is still not connected. Reconnect it in Arena and re-run."; exit 1; }

echo "== 1. re-verify before publishing anything =="
PY=.venv/bin/python; [[ -x "$PY" ]] || PY=python3
$PY scripts/verify_download.py | tail -3
$PY -m pytest tests -q | tail -3
$PY scripts/audit_platform_encoding.py | tail -12
$PY scripts/fetch_sgmc_truth.py | tail -3

echo "== 2. push =="
git push origin "$BRANCH"

echo "== 3. PR =="
if URL=$(gh pr view "$BRANCH" --repo "$REPO" --json url --jq .url 2>/dev/null) && [[ -n "$URL" ]]; then
  echo "PR already exists: $URL"
else
  URL=$(gh pr create --repo "$REPO" --base "$BASE" --head "$BRANCH" \
        --title "Session 8: the [0,1] rejection's real cause (TIFF Predictor=2), data blocker closed, R14/R15" \
        --body-file .github/PR_BODY_SESSION8.md)
  echo "opened $URL"
fi

echo "== 4. merge =="
gh pr merge "$URL" --repo "$REPO" --merge --delete-branch=false \
  || gh pr merge "$URL" --repo "$REPO" --merge

echo "== 5. confirm Pages rebuilt from the new main =="
sleep 20
gh api "repos/$REPO/pages/builds/latest" --jq '{status, commit, updated_at}'
echo
echo "Live URLs to check by hand:"
echo "  https://buffedlizard55-lab.github.io/13GEMSDOE/"
echo "  https://buffedlizard55-lab.github.io/13GEMSDOE/docs/"
echo "  https://buffedlizard55-lab.github.io/13GEMSDOE/docs/executive_summary.html"
echo
echo "Primary download that must resolve:"
$PY - <<'PYEOF'
import json, pathlib
m = json.loads(pathlib.Path("docs/downloads/submit.json").read_text())
print("  https://buffedlizard55-lab.github.io/13GEMSDOE/docs/downloads/" + m["primary"]["file"])
print("  sha256 " + m["primary"]["sha256"])
print("  note for the form: " + m["note_for_form"])
PYEOF
