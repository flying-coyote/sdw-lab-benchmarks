#!/usr/bin/env bash
# Recovery for v2 fault B3 (truncated, non-atomically written micro-batch file). The bare
# batch job has no supervisor; DuckDB raises on the truncated Parquet and the job exits, so
# the operator must wait for a readable file and restart the job.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$HERE/../.venv/bin/python3"

# Step 1: wait until the replacement file for the bad window is a readable Parquet file.
for _ in $(seq 1 600); do
  "$VENV_PY" -c 'import sys, pyarrow.parquet as pq; pq.read_metadata(sys.argv[1])' "$SMX_BAD_FILE" 2>/dev/null && break
  sleep 0.5
done

# Step 2: restart the job process.
nohup "$VENV_PY" "$HERE/batch/batch_job.py" \
  --in-dir "$SMX_BATCH_IN_DIR" --out-file "$SMX_BATCH_OUT_FILE" --state-file "$SMX_BATCH_STATE_FILE" \
  --poll-interval 5 --max-idle-ticks 6 --quiet > /dev/null 2>&1 < /dev/null &
disown
echo $!
