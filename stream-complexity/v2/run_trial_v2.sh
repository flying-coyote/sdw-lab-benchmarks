#!/usr/bin/env bash
# STREAM-COMPLEXITY v2 clean trial: all four arms (B, S, F, BC) concurrently on one shared
# replay clock, 10 s moving-parts sampler throughout, four-arm answer-equality gate,
# per-arm latency. Usage: v2/run_trial_v2.sh <label> [replay_factor]
# Writes everything under results/v2/<label>/. Exits with the gate's exit code.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
LABEL="$1"; RF="${2:-20}"
# drain-detection only: at 1x a file lands every 60 s, so 6 idle 5 s ticks would end the job early
IDLE="$(python3 -c "print(6 if float('$RF') >= 20 else 30)")"; export SMX_BC_IDLE_TICKS="$IDLE"
PY="$HERE/../.venv/bin/python3"
OUT="$HERE/results/v2/$LABEL"
B_IN="$HERE/data/v2_b_in"; BC_IN="$HERE/data/v2_bc_in"
rm -rf "$OUT" "$B_IN" "$BC_IN"; mkdir -p "$OUT" "$B_IN" "$BC_IN"
PIDS=()
cleanup() {
  for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null || true; done
  ( cd streaming && docker compose down -v ) >/dev/null 2>&1 || true
  ( cd feldera && docker compose down ) >/dev/null 2>&1 || true
  ( cd bc && SMX_BC_IN="$BC_IN" SMX_BC_OUT="$OUT" docker compose down ) >/dev/null 2>&1 || true
}
trap cleanup EXIT
log() { echo "[$(date -u +%H:%M:%S)] $*"; }

log "fresh state"
( cd streaming && docker compose down -v ) >/dev/null 2>&1 || true
( cd feldera && docker compose down ) >/dev/null 2>&1 || true
( cd bc && docker compose down ) >/dev/null 2>&1 || true

log "S up"
( cd streaming && docker compose up -d ) >/dev/null 2>&1
for svc in smx-kafka smx-jobmanager; do
  for _ in $(seq 1 90); do [ "$(docker inspect -f '{{.State.Health.Status}}' $svc 2>/dev/null)" = healthy ] && break; sleep 2; done
done
for _ in $(seq 1 60); do [ "$(docker inspect -f '{{.State.Running}}' smx-taskmanager 2>/dev/null)" = true ] && break; sleep 2; done
bash streaming/submit_flink_job.sh > "$OUT/flink-submit.log" 2>&1

log "F up"
( cd feldera && docker compose up -d ) >/dev/null 2>&1
for _ in $(seq 1 90); do [ "$(docker inspect -f '{{.State.Health.Status}}' smx-feldera 2>/dev/null)" = healthy ] && break; sleep 2; done
T0=$(date +%s.%N); bash feldera/deploy_pipeline.sh > "$OUT/feldera-deploy.log" 2>&1
echo "{\"deploy_compile_start_s\": $(python3 -c "print(round($(date +%s.%N)-$T0,2))")}" > "$OUT/feldera-deploy.json"

log "BC up"
( cd bc && SMX_BC_IN="$BC_IN" SMX_BC_OUT="$OUT" docker compose up -d ) >/dev/null 2>&1

log "sinks + B job + sampler"
"$PY" feldera/drain_alerts.py --out-file "$OUT/alerts-feldera.jsonl" --state-file "$OUT/feldera-drain-state.json" \
  --stop-file "$OUT/.f-stop" > "$OUT/feldera-drain.log" 2>&1 & PIDS+=($!); F_DRAIN=$!
for _ in $(seq 1 60); do grep -q '"connected": true' "$OUT/feldera-drain-state.json" 2>/dev/null && break; sleep 0.5; done
"$PY" streaming/consume_alerts.py --out-file "$OUT/alerts-stream.jsonl" --state-file "$OUT/.stream_state.json" \
  --idle-timeout 100000 --stop-file "$OUT/.s-stop" > "$OUT/stream-consumer.log" 2>&1 & PIDS+=($!); S_CONS=$!
"$PY" batch/batch_job.py --in-dir "$B_IN" --out-file "$OUT/alerts-batch.jsonl" --state-file "$B_IN/.batch_state.json" \
  --poll-interval 5 --max-idle-ticks "$IDLE" --quiet & PIDS+=($!); B_JOB=$!
"$PY" v2/sampler.py --out "$OUT/samples.jsonl" --stop-file "$OUT/.sampler-stop" --b-in "$B_IN" \
  > "$OUT/sampler.log" 2>&1 & PIDS+=($!); SAMPLER=$!

RS="$(python3 -c 'import time; print(time.time() + 5)')"
echo "$RS" > "$OUT/replay_start_epoch"
log "replay start epoch $RS factor ${RF}x"
"$PY" batch/land_microbatches.py --out-dir "$B_IN" --replay-factor "$RF" --replay-start-epoch "$RS" --quiet & PIDS+=($!); L1=$!
"$PY" batch/land_microbatches.py --out-dir "$BC_IN" --replay-factor "$RF" --replay-start-epoch "$RS" --quiet & PIDS+=($!); L2=$!
"$PY" streaming/producer.py --replay-factor "$RF" --replay-start-epoch "$RS" --quiet & PIDS+=($!); PROD=$!
"$PY" feldera/replay_http.py --replay-factor "$RF" --replay-start-epoch "$RS" --state-file "$OUT/feldera-replayer-state.json" \
  --control-file "$OUT/feldera-rewind.json" > "$OUT/feldera-replayer.log" 2>&1 & PIDS+=($!); FREP=$!

wait "$L1" "$L2" "$PROD" "$FREP"; log "all replayers finished"
wait "$B_JOB"; log "B drained"
docker wait smx-bc-batch > "$OUT/bc-exit-code" ; log "BC drained (exit $(cat "$OUT/bc-exit-code"))"
for _ in $(seq 1 600); do
  n=$(curl -s localhost:18080/v0/pipelines/smx-detect/stats | python3 -c 'import json,sys; print(json.load(sys.stdin)["global_metrics"]["total_processed_records"])' 2>/dev/null || echo 0)
  [ "$n" -ge 500000 ] 2>/dev/null && break; sleep 2
done
log "F processed $n records"
touch "$OUT/.f-stop"
prev=-1; stable=0
while [ "$stable" -lt 3 ]; do
  sleep 15
  cur=$(docker exec smx-kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic smx-alerts 2>/dev/null | awk -F: '{s+=$NF} END {print s+0}')
  if [ "$cur" = "$prev" ]; then stable=$((stable+1)); else stable=0; fi; prev="$cur"
done
echo "{\"smx_alerts_end_offset\": $prev}" > "$OUT/stream-raw.json"
touch "$OUT/.s-stop"
wait "$S_CONS"; wait "$F_DRAIN"; log "sinks drained (S raw sink records $prev)"
touch "$OUT/.sampler-stop"; wait "$SAMPLER" || true
PIDS=()

set +e
"$PY" v2/compare4.py --arm B="$OUT/alerts-batch.jsonl" --arm S="$OUT/alerts-stream.jsonl" \
  --arm F="$OUT/alerts-feldera.jsonl" --arm BC="$OUT/alerts-bc.jsonl" --out "$OUT/compare.json"
GATE=$?
set -e
"$PY" v2/latency4.py --arm B="$OUT/alerts-batch.jsonl" --arm S="$OUT/alerts-stream.jsonl" \
  --arm F="$OUT/alerts-feldera.jsonl" --arm BC="$OUT/alerts-bc.jsonl" \
  --replay-start-epoch "$RS" --replay-factor "$RF" --out "$OUT/latency.json"
log "trial $LABEL done, gate exit $GATE"
exit "$GATE"
