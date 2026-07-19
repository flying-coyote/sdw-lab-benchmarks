#!/usr/bin/env bash
# Recovery for fault (c). ONE step: just restart the process. It is safe to do
# because of batch_job.py's own idempotency design (persisted state file + a
# rebuild-from-output fallback if that state file was itself lost to the hard
# kill — see batch/batch_job.py's module docstring) — no distributed coordination,
# no peer, no re-election, which is the expected, honest asymmetry P3 predicts
# (batch needs FEWER recovery steps than either Kafka or Flink fault).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$HERE/../.venv/bin/python3"
[ -x "$VENV_PY" ] || VENV_PY=python3

IN_DIR="${SMX_BATCH_IN_DIR:-$HERE/data/batch_in}"
OUT_FILE="${SMX_BATCH_OUT_FILE:-$HERE/results/alerts-batch.jsonl}"
STATE_FILE="${SMX_BATCH_STATE_FILE:-$IN_DIR/.batch_state.json}"
LOG_FILE="${SMX_BATCH_JOB_LOG:-/dev/null}"

# Step 1: restart the job process.
nohup "$VENV_PY" "$HERE/batch/batch_job.py" \
  --in-dir "$IN_DIR" --out-file "$OUT_FILE" --state-file "$STATE_FILE" \
  --poll-interval 5 --max-idle-ticks 6 --quiet \
  > "$LOG_FILE" 2>&1 < /dev/null &
disown
echo $!
