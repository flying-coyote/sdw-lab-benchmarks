#!/usr/bin/env bash
# #23 starrocks_mv arm (P5, the deferred MV-acceleration UPPER BOUND). Brings up the ejs
# stack + StarRocks, registers the SOC tables, builds + SYNC-refreshes the async MVs
# (starrocks_mv_build.py), then runs run.py --arm starrocks_mv on a ladder reaching past
# the base StarRocks knee (64x) so a rightward knee shift is visible. P5 predicts the MV
# shifts the knee right >=2 ladder steps; run.py EXPLAIN-verifies rewrite on every
# scheduled shape and ABORTS the arm if rewrite is not engaged (so a scored result means
# the MVs really took). One engine at a time (isolation), client cpuset 12,13.
set -u
REPO=/home/jerem/sdw-lab-benchmarks
EJS=$REPO/engine-join-specialization
WI=$REPO/workload-interference
NET=ejs-bench_ejs
IMG=ejs-bench-lab
COMPOSE="docker compose -f $EJS/compose.yml -f $EJS/compose.cpuset.yml"
LADDER="16.0 32.0 64.0 128.0 256.0"
LOG=$WI/_work/starrocks_mv.log
mkdir -p "$WI/results"; : > "$LOG"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

register(){ docker run --rm --network $NET -v $REPO:/repo -w /repo $IMG \
    python3 /repo/workload-interference/_register_soc.py >>"$LOG" 2>&1 || log "register warn"; }
wait_health(){ local c=$1 t=${2:-300} i=0 s
  while [ $i -lt "$t" ]; do s=$(docker inspect --format '{{.State.Health.Status}}' "$c" 2>/dev/null||echo none)
    [ "$s" = healthy ] && { log "$c healthy ${i}s"; return 0; }; sleep 6; i=$((i+6)); done
  log "$c NOT healthy ${t}s"; return 1; }

cd "$EJS"
log "=== starrocks_mv START ==="
$COMPOSE up -d minio nessie lab >>"$LOG" 2>&1; sleep 6
$COMPOSE --profile engine-starrocks up -d >>"$LOG" 2>&1
if wait_health ejs-starrocks 300; then
  register
  log "building + refreshing MVs"
  docker run --rm --network $NET -v $REPO:/repo -w /repo/workload-interference $IMG \
    python3 starrocks_mv_build.py >>"$LOG" 2>&1 && log "MV build OK" || { log "MV build FAIL — aborting arm"; $COMPOSE stop starrocks >>"$LOG" 2>&1; exit 2; }
  log "RUN starrocks_mv (ladder $LADDER)"
  docker run --rm --cpuset-cpus 12,13 --network $NET -v $REPO:/repo -w /repo/workload-interference $IMG \
    python3 run.py --arm starrocks_mv --ladder $LADDER >>"$LOG" 2>&1 && log "OK starrocks_mv" || log "FAIL starrocks_mv (rewrite not engaged?)"
  # capture the arm record out of results.json
  docker run --rm -v $REPO:/repo -w /repo/workload-interference $IMG python3 - <<'PY' >>"$LOG" 2>&1
import json, pathlib
b = json.loads(pathlib.Path("results/results.json").read_text())
rec = b.get("arms", {}).get("starrocks_mv")
if rec:
    pathlib.Path("results/phase_c").mkdir(exist_ok=True)
    pathlib.Path("results/phase_c/starrocks_mv.json").write_text(json.dumps({"arm":"starrocks_mv","record":rec},indent=2))
    print("captured starrocks_mv record")
else:
    print("no starrocks_mv record")
PY
fi
$COMPOSE stop starrocks >>"$LOG" 2>&1
log "=== starrocks_mv DONE ==="
