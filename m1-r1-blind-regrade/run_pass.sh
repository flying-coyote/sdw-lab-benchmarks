#!/usr/bin/env bash
# Run prompts of one pass through agy-tracked.sh (Gemini 3.8 Flash), 4 calls in parallel, 2 retries each.
#   ./run_pass.sh <pass> [model] [batch-glob]
# Patched 2026-11-09 by the resume agent (operational only, no prereg change):
#   - global Flash call cap of 36 across all passes (counted in responses/calls.count under flock)
#   - stop rule (b): refuse a call when gemini-5h remaining < 0.10
#   - retry trigger: response must parse as a JSON array holding every manifest row_id of the batch
#   - a batch that fails after 3 tries writes FAILED and a STOP marker so no further calls start
#   - skips batches whose response already validates (resume)
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
P="$1"; MODEL="${2:-gemini-3.8-flash-high}"; GLOB="${3:-*}"
mkdir -p "$HERE/responses/pass$P"
export HERE P MODEL
valid() {  # valid <pass> <batch-file> <response.md>
    "$HERE/.venv/bin/python" -I - "$HERE" "$1" "$2" "$3" <<'EOF'
import json, re, sys, os
here, p, bf, out = sys.argv[1:]
try:
    m = json.load(open(os.path.join(here, "prompts", "manifest.json")))
    rows = next(b["rows"] for b in m["passes"][p]["batches"] if b["file"] == bf)
    arr = json.loads(re.search(r"\[.*\]", open(out).read(), re.S).group(0))
    got = {x.get("row_id") for x in arr if isinstance(x, dict)}
    sys.exit(0 if set(rows) <= got else 1)
except Exception:
    sys.exit(1)
EOF
}
export -f valid
take_call() {  # increments the global counter; non-zero exit if cap reached or stop marker present
    exec 9>"$HERE/responses/calls.lock"; flock 9
    [[ -e "$HERE/responses/STOP" ]] && return 1
    n=$(cat "$HERE/responses/calls.count" 2>/dev/null || echo 0)
    (( n >= 36 )) && { echo "$(date -u +%FT%TZ) CAP 36 reached" >> "$HERE/responses/pass$P/run.log"; return 1; }
    q=$("$HOME/project1/automation/agy-tracked.sh" --quota | python3 -c 'import json,sys;print(json.load(sys.stdin).get("gemini-5h",1))')
    if python3 -c "import sys;sys.exit(0 if float('$q')<0.10 else 1)"; then
        echo "$(date -u +%FT%TZ) STOP gemini-5h $q < 0.10" >> "$HERE/responses/pass$P/run.log"; touch "$HERE/responses/STOP"; return 1
    fi
    echo $((n + 1)) > "$HERE/responses/calls.count"
    exec 9>&-
}
export -f take_call
one() {
    f="$1"; bf="$(basename "$f")"; b="${bf%.txt}"; out="$HERE/responses/pass$P/$b.md"
    if [[ -s "$out" ]] && valid "$P" "$bf" "$out"; then echo "$(date -u +%FT%TZ) SKIP-valid $b" >> "$HERE/responses/pass$P/run.log"; return 0; fi
    for try in 1 2 3; do
        take_call || return 1
        line="$(nice -n 10 taskset -c 0-3 "$HOME/project1/automation/agy-tracked.sh" "m1-p$P-$b-t$try" "$MODEL" "$out" "$(cat "$f")" 2>&1 | tail -1)"
        echo "$(date -u +%FT%TZ) $line" >> "$HERE/responses/pass$P/run.log"
        if grep -q SUCCESS <<<"$line" && valid "$P" "$bf" "$out"; then return 0; fi
    done
    echo "FAILED $b" >> "$HERE/responses/pass$P/run.log"; touch "$HERE/responses/STOP"; return 1
}
export -f one
ls "$HERE/prompts/pass$P"/$GLOB.txt | xargs -P 4 -I{} bash -c 'one "$@"' _ {}
echo "pass $P done"; grep -c SUCCESS "$HERE/responses/pass$P/run.log"; grep -E 'FAILED|STOP|CAP' "$HERE/responses/pass$P/run.log" || true
