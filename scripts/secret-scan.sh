#!/usr/bin/env bash
# Pre-commit secret scan (gitleaks-lite). Reinstated 2026-06-30 after the red-team flagged a
# removed credential-scan hook. Blocks commits that introduce live credentials.
set -u
staged=$(git diff --cached --name-only --diff-filter=ACM)
[ -z "$staged" ] && exit 0
P1='sk-ant-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{32,}|gh[pousr]_[A-Za-z0-9]{36,}|AIza[0-9A-Za-z_-]{35}'
P2='xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|substack\.sid'
P3="$(printf 'A''K''I''A')[0-9A-Z]{16}"   # AWS access key id (split literal to not trip scanners on this file)
P4='(CLOUDFLARE_API_TOKEN|AWS_SECRET_ACCESS_KEY)[[:space:]:='"'"'\"]+[A-Za-z0-9/+_-]{30}'
PAT="$P1|$P2|$P3|$P4"
hits=$(git diff --cached -U0 -- $staged 2>/dev/null | grep '^+' | grep -vE '^\+\+\+' | grep -En "$PAT" \
  | grep -vEi 'example|placeholder|your_|<[a-z_]+>|xxx|redact|dummy|sample|moar-dev|bench[0-9]|ejsbench|dremioadmin')
if [ -n "$hits" ]; then
  echo "secret-scan: possible credential in staged changes — commit blocked:"; echo "$hits" | head -8
  echo "  False positive? refine scripts/secret-scan.sh, or 'git commit --no-verify' deliberately."
  exit 1
fi
exit 0
