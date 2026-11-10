#!/usr/bin/env bash
# Adjudication runner (added 2026-11-09 by the resume agent; run_pass.sh is hardwired to prompts/passN).
# Sends prompts/adjudication/adj-b*.txt to Gemini 4 Argon through agy-tracked.sh, sequentially,
# with a hard cap of 4 Argon calls in total (pre-registered), retrying a batch only while budget remains.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL="${1:-gemini-4-argon-high}"
mkdir -p "$HERE/responses/adjudication"
LOG="$HERE/responses/adjudication/run.log"
calls=0
valid() {
    "$HERE/.venv/bin/python" -I - "$HERE" "$1" "$2" <<'EOF'
import json, re, sys, os
here, bf, out = sys.argv[1:]
try:
    a = json.load(open(os.path.join(here, "prompts", "adjudication", "assignment.json")))
    rows = next(b["rows"] for b in a["batches"] if b["file"] == bf)
    arr = json.loads(re.search(r"\[.*\]", open(out).read(), re.S).group(0))
    sys.exit(0 if set(rows) <= {x.get("row_id") for x in arr if isinstance(x, dict)} else 1)
except Exception:
    sys.exit(1)
EOF
}
for f in "$HERE"/prompts/adjudication/adj-b*.txt; do
    bf="$(basename "$f")"; b="${bf%.txt}"; out="$HERE/responses/adjudication/$b.md"
    if [[ -s "$out" ]] && valid "$bf" "$out"; then echo "SKIP-valid $b" >> "$LOG"; continue; fi
    ok=0
    for try in 1 2 3; do
        (( calls >= 4 )) && { echo "$(date -u +%FT%TZ) CAP 4 Argon calls reached" >> "$LOG"; break; }
        calls=$((calls + 1))
        line="$(nice -n 10 taskset -c 0-3 "$HOME/project1/automation/agy-tracked.sh" "m1-adj-$b-t$try" "$MODEL" "$out" "$(cat "$f")" 2>&1 | tail -1)"
        echo "$(date -u +%FT%TZ) $line" >> "$LOG"
        if grep -q SUCCESS <<<"$line" && valid "$bf" "$out"; then ok=1; break; fi
        grep -q SKIPPED <<<"$line" && break
    done
    (( ok )) || echo "FAILED $b" >> "$LOG"
done
echo "argon calls: $calls"; cat "$LOG"
