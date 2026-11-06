#!/usr/bin/env bash
# STREAM-FRESHNESS trial at 1x (pre-reg PRE-REG-stream-freshness-2026-11-06.md).
# Arms, all concurrent on one shared replay clock:
#   S         Kafka 4.3.1 + Flink 2.2.1, one job with W + I (freshness/flink_fresh.sql)
#   B5 B60 B300 B900   batch_fresh.py over 60 s files, poll 5/60/300/900 s
#   B5L300    batch_fresh.py over 300 s files, poll 5 s
# Each batch arm runs as 4 replicas at phases (r + 0.5) * poll / 4 after the replay start
# (deviation D3). Usage: freshness/run_fresh_trial.sh <label> [--smoke]
# Writes results/fresh/<label>/. Exits with the answer-equality gate's exit code.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
LABEL="$1"; MODE="${2:-}"
PY="$HERE/../.venv/bin/python3"
if [ "$MODE" = "--smoke" ]; then CORPUS="$HERE/data/fresh-smoke"; else CORPUS="$HERE/data/fresh"; fi
EVENTS="$CORPUS/events.jsonl"; GT="$CORPUS/ground_truth.json"; IOC_TRUTH="$CORPUS/ioc_ground_truth.json"
IOC_LIST="$HERE/data/fresh/ioc_ground_truth.json"   # the frozen 30-address list, same for every arm
OUT="$HERE/results/fresh/$LABEL"
IN60="$HERE/data/fresh_in60_$LABEL"; IN300="$HERE/data/fresh_in300_$LABEL"
rm -rf "$OUT" "$IN60" "$IN300"; mkdir -p "$OUT/batch" "$IN60" "$IN300"
PIDS=()
cleanup() {
  for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null || true; done
  ( cd streaming && docker compose down -v ) >/dev/null 2>&1 || true
  rm -rf "$IN60" "$IN300"
}
trap cleanup EXIT
log() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$OUT/trial.log"; }
log "trial $LABEL mode=${MODE:-scored} corpus=$CORPUS"

log "fresh S state"
( cd streaming && docker compose down -v ) >/dev/null 2>&1 || true
( cd streaming && docker compose up -d ) >/dev/null 2>&1
for svc in smx-kafka smx-jobmanager; do
  for _ in $(seq 1 90); do [ "$(docker inspect -f '{{.State.Health.Status}}' $svc 2>/dev/null)" = healthy ] && break; sleep 2; done
done
for _ in $(seq 1 60); do [ "$(docker inspect -f '{{.State.Running}}' smx-taskmanager 2>/dev/null)" = true ] && break; sleep 2; done
for _ in $(seq 1 60); do
  docker exec smx-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list 2>/dev/null | grep -qx smx-alerts && break; sleep 2
done
docker exec smx-kafka /opt/kafka/bin/kafka-topics.sh --create --if-not-exists --bootstrap-server localhost:9092 \
  --topic smx-ioc-alerts --partitions 1 --replication-factor 1 > "$OUT/topic-create.log" 2>&1
docker cp freshness/flink_fresh.sql smx-jobmanager:/tmp/flink_fresh.sql
docker exec smx-jobmanager /opt/flink/bin/sql-client.sh -f /tmp/flink_fresh.sql > "$OUT/flink-submit.log" 2>&1
grep -q "Job ID" "$OUT/flink-submit.log" || { log "Flink submit did not report a Job ID"; cat "$OUT/flink-submit.log"; exit 2; }
for _ in $(seq 1 60); do
  curl -s localhost:18081/jobs/overview | grep -q '"state":"RUNNING"' && break; sleep 2
done
log "S job running"

"$PY" streaming/consume_alerts.py --out-file "$OUT/alerts-S-W.jsonl" --state-file "$OUT/.s_w_state.json" \
  --idle-timeout 100000 --stop-file "$OUT/.s-stop" --quiet > "$OUT/s-w-consumer.log" 2>&1 & PIDS+=($!); SW=$!
"$PY" freshness/consume_ioc.py --out-file "$OUT/alerts-S-I.jsonl" --stop-file "$OUT/.s-stop" \
  > "$OUT/s-i-consumer.log" 2>&1 & PIDS+=($!); SI=$!

RS="$(python3 -c 'import time; print(round(time.time() + 20, 3))')"
echo "$RS" > "$OUT/replay_start_epoch"
"$PY" freshness/sampler_fresh.py --out "$OUT/host-samples.jsonl" --cgroup-out "$OUT/cpu.json" \
  --stop-file "$OUT/.sampler-stop" > "$OUT/sampler.log" 2>&1 & PIDS+=($!); SAMPLER=$!

BJOBS=(); ARM_ARGS=(); LAT_ARGS=()
start_arm() {  # name poll in_dir lag_log
  local name="$1" poll="$2" in="$3" lag="$4"
  for r in 0 1 2 3; do
    local phase; phase="$(python3 -c "print(round(($r + 0.5) * $poll / 4, 4))")"
    local tag="$name.r$r"
    "$PY" freshness/batch_fresh.py --in-dir "$in" --out-w "$OUT/batch/$tag-W.jsonl" --out-i "$OUT/batch/$tag-I.jsonl" \
      --ioc-file "$IOC_LIST" --poll-interval "$poll" --anchor-epoch "$RS" --phase "$phase" \
      --stats-file "$OUT/batch/$tag-stats.json" --label "$tag" > "$OUT/batch/$tag.log" 2>&1 & PIDS+=($!); BJOBS+=($!)
    ARM_ARGS+=(--arm "$tag=$OUT/batch/$tag-W.jsonl,$OUT/batch/$tag-I.jsonl")
    LAT_ARGS+=(--arm "$tag=$OUT/batch/$tag-W.jsonl,$OUT/batch/$tag-I.jsonl,$lag")
  done
}
start_arm B5 5 "$IN60" "$OUT/lander-60-lag.jsonl"
start_arm B60 60 "$IN60" "$OUT/lander-60-lag.jsonl"
start_arm B300 300 "$IN60" "$OUT/lander-60-lag.jsonl"
start_arm B900 900 "$IN60" "$OUT/lander-60-lag.jsonl"
start_arm B5L300 5 "$IN300" "$OUT/lander-300-lag.jsonl"
log "replay start epoch $RS (1x); 20 batch replicas started"

"$PY" freshness/land_fresh.py --events "$EVENTS" --out-dir "$IN60" --span-seconds 60 --replay-start-epoch "$RS" \
  --lag-log "$OUT/lander-60-lag.jsonl" > "$OUT/lander-60.log" 2>&1 & PIDS+=($!); L60=$!
"$PY" freshness/land_fresh.py --events "$EVENTS" --out-dir "$IN300" --span-seconds 300 --replay-start-epoch "$RS" \
  --lag-log "$OUT/lander-300-lag.jsonl" > "$OUT/lander-300.log" 2>&1 & PIDS+=($!); L300=$!
"$PY" streaming/producer.py --events "$EVENTS" --replay-factor 1 --replay-start-epoch "$RS" --quiet \
  > "$OUT/producer.log" 2>&1 & PIDS+=($!); PROD=$!

wait "$L60" "$L300" "$PROD"; log "replay finished (landers + producer)"
for p in "${BJOBS[@]}"; do wait "$p"; done; log "all batch replicas drained"

topic_end() { docker exec smx-kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic "$1" 2>/dev/null | awk -F: '{s+=$NF} END {print s+0}'; }
prev=-1; stable=0
while [ "$stable" -lt 3 ]; do
  sleep 15
  cur="$(topic_end smx-alerts)/$(topic_end smx-ioc-alerts)"
  if [ "$cur" = "$prev" ]; then stable=$((stable+1)); else stable=0; fi; prev="$cur"
done
echo "{\"smx_alerts_end_offset/smx_ioc_alerts_end_offset\": \"$prev\"}" > "$OUT/stream-raw.json"
touch "$OUT/.s-stop"; wait "$SW"; wait "$SI"; log "S sinks drained ($prev)"
touch "$OUT/.sampler-stop"; wait "$SAMPLER" || true
PIDS=()

set +e
"$PY" freshness/compare_fresh.py --ground-truth "$GT" --ioc-truth "$IOC_TRUTH" \
  --arm "S=$OUT/alerts-S-W.jsonl,$OUT/alerts-S-I.jsonl" "${ARM_ARGS[@]}" --out "$OUT/compare.json" | tee -a "$OUT/trial.log"
GATE=${PIPESTATUS[0]}
set -e
"$PY" freshness/latency_fresh.py --replay-start-epoch "$RS" \
  --arm "S=$OUT/alerts-S-W.jsonl,$OUT/alerts-S-I.jsonl" "${LAT_ARGS[@]}" --out "$OUT/latency.json" | tee -a "$OUT/trial.log"
python3 - "$OUT" <<'PYEOF' | tee -a "$OUT/trial.log"
import glob, json, os, sys
out = sys.argv[1]
cpu = json.load(open(os.path.join(out, "cpu.json")))
print(f"  host CPU median {cpu['host_cpu_pct_median']}% max {cpu['host_cpu_pct_max']}% "
      f"over-50% samples {cpu['host_samples_over_50pct']}/{cpu['host_samples']} flag={cpu['host_load_flag']}; "
      f"S CPU-s {cpu['s_cpu_seconds_total']}")
for p in sorted(glob.glob(os.path.join(out, "batch", "*-stats.json"))):
    s = json.load(open(p))
    print(f"  {s['label']:10s} wakeups {s['poll_wakeups']:5d} queries W/I {s['queries_w']}/{s['queries_i']} "
          f"cpu {s['cpu_total_s']} s")
PYEOF
log "trial $LABEL done, gate exit $GATE"
exit "$GATE"
