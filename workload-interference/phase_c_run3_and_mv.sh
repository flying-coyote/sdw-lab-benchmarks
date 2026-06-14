#!/usr/bin/env bash
# Combined finish pass (2026-06-14), one stack lifecycle:
#  (A) run-3 — a clean 3rd independent knee observation for the 4 graceful arms over the
#      knee region (16/32/64x). Combined with run-1 (extend-ladder) + run-2 (phase-C rep3,
#      salvaged) this completes the pre-registered 3x knee reproduction. The earlier
#      phase_c_knee_repro.sh captured nothing (docker run without -i never fed its heredoc
#      to the container), so reps 1-2 were overwritten in results.json; this captures
#      HOST-SIDE (results.json is on disk) so it cannot silently drop a rep.
#  (B) starrocks_mv (#23 P5) — build + SYNC-refresh the async MVs, then run the arm on a
#      ladder past the base knee (to 256x) to see P5's predicted >=2-step rightward shift.
# Captures go to _work/phase_c/ (jerem-owned; results/ is root-owned and unwritable here).
set -u
REPO=/home/jerem/sdw-lab-benchmarks
EJS=$REPO/engine-join-specialization
WI=$REPO/workload-interference
NET=ejs-bench_ejs
IMG=ejs-bench-lab
VENV=$REPO/.venv/bin/python3
COMPOSE="docker compose -f $EJS/compose.yml -f $EJS/compose.cpuset.yml"
KNEE="16.0 32.0 64.0"
MVLADDER="16.0 32.0 64.0 128.0 256.0"
OUT=$WI/_work/phase_c
LOG=$WI/_work/finish.log
mkdir -p "$OUT"; : > "$LOG"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

register(){ docker run --rm --network $NET -v $REPO:/repo -w /repo $IMG \
    python3 /repo/workload-interference/_register_soc.py >>"$LOG" 2>&1 || log "register warn"; }

# host-side capture: pull one arm's record out of the (root-owned but readable) results.json
capture(){ # arm tag
  "$VENV" - "$1" "$2" >>"$LOG" 2>&1 <<PYEOF
import json, pathlib, sys
arm, tag = sys.argv[1], sys.argv[2]
b = json.loads(pathlib.Path("$WI/results/results.json").read_text())
rec = b.get("arms", {}).get(arm)
p = pathlib.Path("$OUT") / f"{tag}_{arm}.json"
if rec is None:
    print(f"capture: NO record for {arm}"); sys.exit(0)
p.write_text(json.dumps({"arm": arm, "tag": tag, "ladder": b["config"]["ladder"],
                         "record": rec}, indent=2))
print(f"capture: wrote {p}")
PYEOF
}

run_arm(){ # arm ladder tag
  log "RUN $1 ($3, ladder $2, client cpuset 12,13)"
  docker run --rm --cpuset-cpus 12,13 --network $NET -v $REPO:/repo -w /repo/workload-interference $IMG \
    python3 run.py --arm "$1" --ladder $2 >>"$LOG" 2>&1 \
    && { log "OK $1 $3"; capture "$1" "$3"; } || log "FAIL $1 $3"
}

wait_health(){ local c=$1 t=${2:-300} i=0 s
  while [ $i -lt "$t" ]; do s=$(docker inspect --format '{{.State.Health.Status}}' "$c" 2>/dev/null||echo none)
    [ "$s" = healthy ] && { log "$c healthy ${i}s"; return 0; }; sleep 6; i=$((i+6)); done
  log "$c NOT healthy ${t}s"; return 1; }
wait_dremio(){ local i=0; while [ $i -lt 360 ]; do
    [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:9347/apiv2/server_status 2>/dev/null)" = 200 ] \
      && { sleep 20; log "dremio REST up ${i}s"; return 0; }; sleep 6; i=$((i+6)); done
  log "dremio REST down 360s"; return 1; }

cd "$EJS"
log "=== FINISH PASS (run-3 + starrocks_mv) START ==="
$COMPOSE up -d minio nessie lab >>"$LOG" 2>&1; sleep 6

# (A) run-3: clickhouse arms
$COMPOSE --profile engine-clickhouse up -d >>"$LOG" 2>&1
wait_health ejs-clickhouse 150 && { register; run_arm clickhouse_iceberg "$KNEE" run3; run_arm clickhouse_native "$KNEE" run3; }
$COMPOSE stop clickhouse >>"$LOG" 2>&1

# (A) run-3: starrocks arm  +  (B) starrocks_mv arm (same StarRocks up)
$COMPOSE --profile engine-starrocks up -d >>"$LOG" 2>&1
if wait_health ejs-starrocks 300; then
  register
  run_arm starrocks "$KNEE" run3
  log "building + SYNC-refreshing MVs for starrocks_mv (P5)"
  if docker run --rm --network $NET -v $REPO:/repo -w /repo/workload-interference $IMG \
       python3 starrocks_mv_build.py >>"$LOG" 2>&1; then
    log "MV build OK"; run_arm starrocks_mv "$MVLADDER" mv
  else
    log "MV build FAIL — skipping starrocks_mv arm"
  fi
fi
$COMPOSE stop starrocks >>"$LOG" 2>&1

# (A) run-3: dremio arm
$COMPOSE --profile engine-dremio up -d >>"$LOG" 2>&1
if wait_dremio; then register; run_arm dremio "$KNEE" run3; fi
$COMPOSE stop dremio >>"$LOG" 2>&1

log "=== FINISH PASS DONE ==="
