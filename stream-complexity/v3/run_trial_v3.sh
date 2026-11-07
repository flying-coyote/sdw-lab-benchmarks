#!/usr/bin/env bash
# STREAM-COMPLEXITY v3 clean trial (PRE-REG-stream-complexity-risingwave-2026-11-07): arms B, S
# and R concurrently on one shared replay clock, 10 s moving-parts sampler throughout,
# three-arm answer-equality gate, per-arm latency. Mirrors v2/run_trial_v2.sh minus F and BC
# (cited from v2, not re-run). Usage: v3/run_trial_v3.sh <label> [replay_factor]
# Writes everything under results/v3/<label>/. Exits with the gate's exit code.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
LABEL="$1"; RF="${2:-20}"
# drain-detection only: at 1x a file lands every 60 s, so 6 idle 5 s ticks would end the job early
IDLE="$(python3 -c "print(6 if float('$RF') >= 20 else 30)")"
PY="$HERE/../.venv/bin/python3"
OUT="$HERE/results/v3/$LABEL"
B_IN="$HERE/data/v3_b_in"
rm -rf "$OUT" "$B_IN"; mkdir -p "$OUT" "$B_IN"
PIDS=()
cleanup() {
  for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null || true; done
  ( cd streaming && docker compose down -v ) >/dev/null 2>&1 || true
  ( cd risingwave && docker compose down -v ) >/dev/null 2>&1 || true
}
trap cleanup EXIT
log() { echo "[$(date -u +%H:%M:%S)] $*"; }

log "fresh state"
( cd streaming && docker compose down -v ) >/dev/null 2>&1 || true
( cd risingwave && docker compose down -v ) >/dev/null 2>&1 || true

log "S up"
( cd streaming && docker compose up -d ) >/dev/null 2>&1
for svc in smx-kafka smx-jobmanager; do
  for _ in $(seq 1 90); do [ "$(docker inspect -f '{{.State.Health.Status}}' $svc 2>/dev/null)" = healthy ] && break; sleep 2; done
done
for _ in $(seq 1 60); do [ "$(docker inspect -f '{{.State.Running}}' smx-taskmanager 2>/dev/null)" = true ] && break; sleep 2; done
bash streaming/submit_flink_job.sh > "$OUT/flink-submit.log" 2>&1

log "R up"
( cd risingwave && docker compose up -d ) >/dev/null 2>&1
for _ in $(seq 1 90); do [ "$(docker inspect -f '{{.State.Health.Status}}' smx-risingwave 2>/dev/null)" = healthy ] && break; sleep 2; done
T0=$(date +%s.%N); "$PY" risingwave/deploy.py "$OUT/edition-probe-risingwave.json" > "$OUT/risingwave-deploy.log" 2>&1
echo "{\"deploy_s\": $(python3 -c "print(round($(date +%s.%N)-$T0,2))")}" > "$OUT/risingwave-deploy.json"
cp "$OUT/edition-probe-risingwave.json" results/edition-probe-risingwave.json
docker logs smx-risingwave 2>&1 | grep -i licen | cut -c1-600 > "$OUT/risingwave-license-log.txt" || true
docker exec smx-risingwave sh -c 'tr "\0" " " < /proc/1/cmdline' > "$OUT/risingwave-pid1.txt" 2>&1 || true

log "sinks + B job + sampler"
"$PY" risingwave/drain_alerts.py --out-file "$OUT/alerts-risingwave.jsonl" --state-file "$OUT/risingwave-drain-state.json" \
  --stop-file "$OUT/.r-stop" > "$OUT/risingwave-drain.log" 2>&1 & PIDS+=($!); R_DRAIN=$!
for _ in $(seq 1 60); do grep -q '"connected": true' "$OUT/risingwave-drain-state.json" 2>/dev/null && break; sleep 0.5; done
"$PY" streaming/consume_alerts.py --out-file "$OUT/alerts-stream.jsonl" --state-file "$OUT/.stream_state.json" \
  --idle-timeout 100000 --stop-file "$OUT/.s-stop" > "$OUT/stream-consumer.log" 2>&1 & PIDS+=($!); S_CONS=$!
"$PY" batch/batch_job.py --in-dir "$B_IN" --out-file "$OUT/alerts-batch.jsonl" --state-file "$B_IN/.batch_state.json" \
  --poll-interval 5 --max-idle-ticks "$IDLE" --quiet & PIDS+=($!); B_JOB=$!
"$PY" v2/sampler.py --arms B,S,R --out "$OUT/samples.jsonl" --stop-file "$OUT/.sampler-stop" --b-in "$B_IN" \
  > "$OUT/sampler.log" 2>&1 & PIDS+=($!); SAMPLER=$!
"$PY" v3/clock_watch.py --out "$OUT/clock-steps.jsonl" --stop-file "$OUT/.sampler-stop" & PIDS+=($!); CLOCK=$!

RS="$(python3 -c 'import time; print(time.time() + 5)')"
echo "$RS" > "$OUT/replay_start_epoch"
log "replay start epoch $RS factor ${RF}x"
"$PY" batch/land_microbatches.py --out-dir "$B_IN" --replay-factor "$RF" --replay-start-epoch "$RS" --quiet & PIDS+=($!); L1=$!
"$PY" streaming/producer.py --replay-factor "$RF" --replay-start-epoch "$RS" --quiet & PIDS+=($!); PROD=$!
"$PY" risingwave/replay_pg.py --replay-factor "$RF" --replay-start-epoch "$RS" --state-file "$OUT/risingwave-replayer-state.json" \
  --control-file "$OUT/risingwave-rewind.json" > "$OUT/risingwave-replayer.log" 2>&1 & PIDS+=($!); RREP=$!

wait "$L1" "$PROD" "$RREP"; log "all replayers finished"
wait "$B_JOB"; log "B drained"
n=0; pn=-1; same=0
for _ in $(seq 1 600); do
  n=$("$PY" -c 'import psycopg; c=psycopg.connect("host=localhost port=14566 user=root dbname=dev", autocommit=True); print(c.execute("SELECT count(*) FROM auth_events").fetchone()[0])' 2>/dev/null || echo 0)
  [ "$n" -ge 500000 ] 2>/dev/null && break
  # a lossy run never reaches 500,000: stop once the count is unchanged for 3 polls
  if [ "$n" = "$pn" ]; then same=$((same+1)); else same=0; fi; pn="$n"; [ "$same" -ge 3 ] && break
  sleep 2
done
log "R table holds $n events"
touch "$OUT/.r-stop"
prev=-1; stable=0
while [ "$stable" -lt 3 ]; do
  sleep 15
  cur=$(docker exec smx-kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic smx-alerts 2>/dev/null | awk -F: '{s+=$NF} END {print s+0}')
  if [ "$cur" = "$prev" ]; then stable=$((stable+1)); else stable=0; fi; prev="$cur"
done
echo "{\"smx_alerts_end_offset\": $prev}" > "$OUT/stream-raw.json"
touch "$OUT/.s-stop"
wait "$S_CONS"; wait "$R_DRAIN"; log "sinks drained (S raw sink records $prev)"
touch "$OUT/.sampler-stop"; wait "$SAMPLER" || true; wait "$CLOCK" || true
PIDS=()
# R input completeness and engine-internal recoveries (beyond the alert gate)
"$PY" - "$OUT/risingwave-input-check.json" <<'PYEOF' || true
import json, sys, psycopg
c = psycopg.connect("host=localhost port=14566 user=root dbname=dev", autocommit=True)
have = {int(u[0].split("-")[1]) for u in c.execute("SELECT event_uid FROM auth_events").fetchall()}
miss = sorted(set(range(1, 500001)) - have); rng = []
for u in miss:
    if rng and u == rng[-1][1] + 1: rng[-1][1] = u
    else: rng.append([u, u])
json.dump({"n_rows": c.execute("SELECT count(*) FROM auth_events").fetchone()[0], "n_distinct_uids": len(have),
           "n_missing_uids": len(miss), "missing_uid_ranges": rng}, open(sys.argv[1], "w"))
PYEOF
docker logs smx-risingwave 2>&1 | grep -E "failure_recovery|recovery start|recovery success|recovery failed|decreasing now" \
  | cut -c1-400 > "$OUT/risingwave-recovery-log.txt" || true

set +e
"$PY" v2/compare4.py --arm B="$OUT/alerts-batch.jsonl" --arm S="$OUT/alerts-stream.jsonl" \
  --arm R="$OUT/alerts-risingwave.jsonl" --out "$OUT/compare.json"
GATE=$?
set -e
"$PY" v2/latency4.py --arm B="$OUT/alerts-batch.jsonl" --arm S="$OUT/alerts-stream.jsonl" \
  --arm R="$OUT/alerts-risingwave.jsonl" \
  --replay-start-epoch "$RS" --replay-factor "$RF" --out "$OUT/latency.json"
log "trial $LABEL done, gate exit $GATE"
exit "$GATE"
