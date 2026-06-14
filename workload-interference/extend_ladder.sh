#!/usr/bin/env bash
# #23 extend-ladder (2026-06-14): the first sweep found NO knee for any server arm at ≤4×
# demand. This pushes the 4 graceful arms up the demand ladder to 8/16/32/64× to FIND the knee
# (and its failure shape). Full ladder 0.125→64 so each arm's curve is one continuous result
# (run.py merges by arm name → this supersedes the ≤4× run with a superset). duckdb + trino are
# omitted (they failed the <5% calibration gate; that's constant, not demand-dependent).
# Writes to results/results_extended.json (a copy of results.json is taken first so the ≤4×
# run is preserved).
set -u
REPO=/home/jerem/sdw-lab-benchmarks
EJS=$REPO/engine-join-specialization
NET=ejs-bench_ejs
IMG=ejs-bench-lab
COMPOSE="docker compose -f $EJS/compose.yml -f $EJS/compose.cpuset.yml"
LADDER="0.125 0.25 0.5 1.0 2.0 4.0 8.0 16.0 32.0 64.0"
LOG=$REPO/workload-interference/_work/extend.log
: > "$LOG"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

run_arm(){ # arm
  log "RUN $1 (ladder to 64x, client cpuset 12,13)"
  docker run --rm --cpuset-cpus 12,13 --network $NET -v $REPO:/repo -w /repo/workload-interference $IMG \
    python3 run.py --arm "$1" --ladder $LADDER >>"$LOG" 2>&1 && log "OK $1" || log "FAIL $1"
}
register(){ docker run --rm --network $NET -v $REPO:/repo -w /repo $IMG \
    python3 /repo/workload-interference/_register_soc.py >>"$LOG" 2>&1 || log "register warn"; }
wait_health(){ # container timeout
  local c=$1 t=${2:-180} i=0 s
  while [ $i -lt "$t" ]; do s=$(docker inspect --format '{{.State.Health.Status}}' "$c" 2>/dev/null||echo none)
    [ "$s" = healthy ] && { log "$c healthy ${i}s"; return 0; }; sleep 6; i=$((i+6)); done
  log "$c not healthy ${t}s"; return 1; }
wait_dremio(){ # dremio has no docker healthcheck — poll REST
  local i=0; while [ $i -lt 360 ]; do
    [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:9347/apiv2/server_status 2>/dev/null)" = 200 ] \
      && { sleep 20; log "dremio REST up ${i}s"; return 0; }; sleep 6; i=$((i+6)); done
  log "dremio REST down 360s"; return 1; }

cd "$EJS"
log "=== EXTEND-LADDER START ==="
cp "$REPO/workload-interference/results/results.json" "$REPO/workload-interference/results/results_le4x_backup.json" 2>/dev/null || true
$COMPOSE up -d minio nessie lab >>"$LOG" 2>&1; sleep 6

# clickhouse (both graceful arms)
$COMPOSE --profile engine-clickhouse up -d >>"$LOG" 2>&1
wait_health ejs-clickhouse 150 && { register; run_arm clickhouse_iceberg; run_arm clickhouse_native; }
$COMPOSE stop clickhouse >>"$LOG" 2>&1

# starrocks
$COMPOSE --profile engine-starrocks up -d >>"$LOG" 2>&1
wait_health ejs-starrocks 300 && { register; run_arm starrocks; }
$COMPOSE stop starrocks >>"$LOG" 2>&1

# dremio (REST poll; needs nessie source + clean reflection)
$COMPOSE --profile engine-dremio up -d >>"$LOG" 2>&1
if wait_dremio; then
  register
  run_arm dremio
fi
$COMPOSE stop dremio >>"$LOG" 2>&1
log "=== EXTEND-LADDER DONE ==="
