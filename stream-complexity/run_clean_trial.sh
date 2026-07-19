#!/usr/bin/env bash
# End-to-end clean trial: generate the corpus (if absent) -> bring up the streaming
# stack -> submit the Flink job -> replay both arms at an identical paced
# accelerated wall-clock -> wait for both to drain -> compare answers against ground
# truth -> record per-arm latency samples + a moving-parts/config-LOC snapshot.
#
# Env overrides: SMX_SEED (default 20260719), SMX_LIMIT (default: unset = full 500k
# corpus), SMX_REPLAY_FACTOR (default 20). Positional arg $1, if given, pins the
# trial number in results/latency-trial-N.json (otherwise auto-incremented).
#
# Exits with compare_answers.py's exit code (nonzero on ANY answer divergence) — per
# the pre-reg, a mismatch invalidates the whole trial, so a caller (cron, CI, you)
# should treat a nonzero exit here as "do not quote a complexity number from this run."
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

SEED="${SMX_SEED:-20260719}"
LIMIT="${SMX_LIMIT:-}"
REPLAY_FACTOR="${SMX_REPLAY_FACTOR:-20}"
TRIAL_N="${1:-}"

VENV_PY="$HERE/../.venv/bin/python3"
[ -x "$VENV_PY" ] || VENV_PY="python3"

echo "=== [1/7] corpus (seed=$SEED limit=${LIMIT:-<full 500k>}) ==="
if [ ! -f data/events.jsonl ] || [ ! -f data/ground_truth.json ]; then
  LIMIT_ARGS=()
  [ -n "$LIMIT" ] && LIMIT_ARGS=(--limit "$LIMIT")
  "$VENV_PY" gen_corpus.py --seed "$SEED" "${LIMIT_ARGS[@]}" --out-dir data
else
  echo "  data/events.jsonl + ground_truth.json already present — not regenerating"
  echo "  (rm data/events.jsonl data/ground_truth.json to force a fresh corpus)"
fi
mkdir -p data/batch_in results

echo "=== [2/7] streaming stack up ==="
( cd streaming && docker compose up -d )
echo "  waiting for smx-kafka / smx-jobmanager / smx-taskmanager..."
for svc in smx-kafka smx-jobmanager; do
  for _ in $(seq 1 60); do
    status="$(docker inspect -f '{{.State.Health.Status}}' "$svc" 2>/dev/null || echo starting)"
    [ "$status" = "healthy" ] && break
    sleep 2
  done
done
for _ in $(seq 1 60); do
  running="$(docker inspect -f '{{.State.Running}}' smx-taskmanager 2>/dev/null || echo false)"
  [ "$running" = "true" ] && break
  sleep 2
done

echo "=== [3/7] submit Flink job ==="
bash streaming/submit_flink_job.sh
sleep 5   # let the job reach RUNNING and register its watermark/window state before we produce

echo "=== [4/7] replay both arms (replay_factor=${REPLAY_FACTOR}x) ==="
rm -f results/alerts-batch.jsonl results/alerts-stream.jsonl
rm -f data/batch_in/.batch_state.json results/.stream_consumer_state.json
rm -f data/batch_in/window-*.parquet 2>/dev/null || true

# A SHARED wall-clock anchor (see land_microbatches.py / producer.py docstrings): both
# replay processes pace off this same instant, not their own independent time.time(),
# so measure_latency.py's cross-arm comparison isn't confounded by process-launch skew.
REPLAY_START_EPOCH="$("$VENV_PY" -c 'import time; print(time.time() + 3)')"

"$VENV_PY" batch/land_microbatches.py --replay-factor "$REPLAY_FACTOR" \
  --replay-start-epoch "$REPLAY_START_EPOCH" --quiet &
LAND_PID=$!
"$VENV_PY" streaming/producer.py --replay-factor "$REPLAY_FACTOR" \
  --replay-start-epoch "$REPLAY_START_EPOCH" --quiet &
PROD_PID=$!
"$VENV_PY" batch/batch_job.py --poll-interval 5 --max-idle-ticks 6 --quiet &
JOB_PID=$!
"$VENV_PY" streaming/consume_alerts.py --idle-timeout 30 --quiet &
CONS_PID=$!

echo "=== [5/7] moving-parts snapshot (mid-run, both arms actively processing) ==="
sleep 6
"$VENV_PY" measure_complexity.py || true

echo "=== [6/7] waiting for drain ==="
wait "$LAND_PID"; echo "  batch replay finished"
wait "$PROD_PID"; echo "  stream replay finished"
wait "$JOB_PID";  echo "  batch job drained (auto-exit on idle)"
wait "$CONS_PID"; echo "  stream consumer drained (auto-exit on idle)"

echo "=== [7/7] compare answers + latency ==="
set +e
"$VENV_PY" compare_answers.py
COMPARE_EXIT=$?
set -e
TRIAL_ARGS=()
[ -n "$TRIAL_N" ] && TRIAL_ARGS=(--trial-n "$TRIAL_N")
"$VENV_PY" measure_latency.py --replay-start-epoch "$REPLAY_START_EPOCH" \
  --replay-factor "$REPLAY_FACTOR" "${TRIAL_ARGS[@]}"

if [ "$COMPARE_EXIT" -ne 0 ]; then
  echo "!!! answer divergence — this trial's complexity numbers are NOT scoreable (pre-reg P5) !!!"
fi
exit "$COMPARE_EXIT"
