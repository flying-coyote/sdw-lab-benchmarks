#!/usr/bin/env bash
# #23 workload-interference overnight sweep (2026-06-14).
# Runs each arm with the PRE-REGISTERED protocol (default ladder 0.125..4.0, 60s warm-in +
# 300s measured window), bringing up EXACTLY ONE engine profile at a time (memory-safe: 24g
# each on the 48 GB host), with the cpuset 12/2 engine/client split (engines 0-11 via
# compose.cpuset.yml; client pinned 12,13 via --cpuset-cpus). The duckdb_parquet arm is
# embedded and unpinned (it deliberately shares host cores — that IS its architecture).
# Each arm runs in its OWN run.py invocation so a per-arm failure can't lose other arms;
# run.py merges into results/results.json. starrocks_mv is OMITTED (needs the make_mvs.sql
# MV build first — a separate operator step); noted as not-run.
set -u
REPO=/home/jerem/sdw-lab-benchmarks
EJS=$REPO/engine-join-specialization
NET=ejs-bench_ejs
IMG=ejs-bench-lab
COMPOSE="docker compose -f $EJS/compose.yml -f $EJS/compose.cpuset.yml"
LOG=$REPO/workload-interference/_work/sweep.log
mkdir -p "$REPO/workload-interference/_work"
: > "$LOG"
log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

run_arm() {  # $1=cpuset_args ("" for duckdb), rest=arm names
  local cpu="$1"; shift
  log "RUN arm(s): $* ${cpu:+(client cpuset $cpu)}"
  docker run --rm ${cpu:+--cpuset-cpus $cpu} --network $NET \
    -v $REPO:/repo -w /repo/workload-interference $IMG \
    python3 run.py "$@" >>"$LOG" 2>&1 && log "OK: $*" || log "FAIL ($?): $*"
}

wait_healthy() {  # $1=container $2=timeout_s
  local c=$1 t=${2:-180} i=0 s
  while [ $i -lt "$t" ]; do
    s=$(docker inspect --format '{{.State.Health.Status}}' "$c" 2>/dev/null || echo none)
    [ "$s" = "healthy" ] && { log "$c healthy (${i}s)"; return 0; }
    sleep 5; i=$((i+5))
  done
  log "$c NOT healthy after ${t}s"; return 1
}

engine_arm() {  # $1=profile $2=container $3=health_timeout, rest=arm names
  local prof=$1 cont=$2 to=$3; shift 3
  local svc=${prof#engine-}   # compose service name (clickhouse/trino/dremio/starrocks)
  log "--- engine $prof (service $svc) ---"
  $COMPOSE --profile "$prof" up -d >>"$LOG" 2>&1
  if wait_healthy "$cont" "$to"; then
    # insurance: re-register soc tables (Nessie is IN_MEMORY; a restart drops them)
    docker run --rm --network $NET -v $REPO:/repo -w /repo $IMG \
      python3 /repo/workload-interference/_register_soc.py >>"$LOG" 2>&1 || log "register warn"
    for a in "$@"; do run_arm "12,13" --arm "$a"; done
  fi
  # stop ONLY the engine service (NOT `--profile X stop`, which also stops base lab/minio/nessie)
  $COMPOSE stop "$svc" >>"$LOG" 2>&1
  log "stopped $svc"
}

log "=== SWEEP START ==="
rm -f "$REPO/workload-interference/results/results.json"

# 1. duckdb_parquet — embedded, no engine, unpinned
run_arm "" --arm duckdb_parquet

# 2. clickhouse — both arms (iceberg via icebergS3; native needs bench.* tables, tolerated)
engine_arm engine-clickhouse ejs-clickhouse 150 clickhouse_iceberg clickhouse_native

# 3. trino
engine_arm engine-trino ejs-trino 150 trino

# 4. dremio (needs a Nessie source configured in ejs-dremio-data; tolerated if absent)
engine_arm engine-dremio ejs-dremio 200 dremio

# 5. starrocks (base arm; the client creates the iceberg external catalog on connect)
engine_arm engine-starrocks ejs-starrocks 300 starrocks

log "=== SWEEP DONE ==="
