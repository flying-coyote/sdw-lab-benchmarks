#!/usr/bin/env bash
# Run every prompt of one pass through agy-tracked.sh (Gemini 3.8 Flash), 4 calls in parallel, 2 retries each.
#   ./run_pass.sh <pass> [model]
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
P="$1"; MODEL="${2:-gemini-3.8-flash-high}"
mkdir -p "$HERE/responses/pass$P"
export HERE P MODEL
one() {
    f="$1"; b="$(basename "$f" .txt)"; out="$HERE/responses/pass$P/$b.md"
    for try in 1 2 3; do
        line="$(nice -n 10 taskset -c 0-3 "$HOME/project1/automation/agy-tracked.sh" "m1-p$P-$b-t$try" "$MODEL" "$out" "$(cat "$f")" 2>&1 | tail -1)"
        echo "$(date -u +%FT%TZ) $line" >> "$HERE/responses/pass$P/run.log"
        if grep -q SUCCESS <<<"$line" && grep -q '"row_id"' "$out"; then return 0; fi
    done
    echo "FAILED $b" >> "$HERE/responses/pass$P/run.log"; return 1
}
export -f one
ls "$HERE/prompts/pass$P"/*.txt | xargs -P 4 -I{} bash -c 'one "$@"' _ {}
echo "pass $P done"; grep -c SUCCESS "$HERE/responses/pass$P/run.log"; grep FAILED "$HERE/responses/pass$P/run.log" || true
