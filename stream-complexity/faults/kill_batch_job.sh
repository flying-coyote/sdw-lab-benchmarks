#!/usr/bin/env bash
# Fault (c) from the pre-reg: kill the batch job mid-tick. SIGKILL (not SIGTERM) —
# this is meant to be a true crash, not a graceful shutdown, so it actually exercises
# batch_job.py's crash-recovery path (state file + fsync'd alerts file) rather than
# a clean-exit path that wouldn't tell us anything about idempotency under failure.
set -euo pipefail
PID="${1:-$(pgrep -f 'batch/batch_job.py' | head -1)}"
if [ -z "${PID:-}" ]; then
  echo "no running batch_job.py process found (pass its PID as \$1, or start one first)" >&2
  exit 1
fi
kill -9 "$PID"
echo "killed batch_job.py pid=$PID"
