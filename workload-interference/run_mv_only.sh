#!/usr/bin/env bash
# starrocks_mv (#23 P5) ONLY — re-run after the make_mvs.sql REFRESH MANUAL fix. Brings up
# StarRocks, registers SOC, builds + SYNC-refreshes the MVs, runs the arm on a ladder past
# the base knee (to 256x) for P5's predicted >=2-step rightward shift. Host-side capture to
# _work/phase_c/mv_starrocks_mv.json (results/ is root-owned). One engine, client cpuset 12,13.
set -u
REPO=/home/jerem/sdw-lab-benchmarks
EJS=$REPO/engine-join-specialization
WI=$REPO/workload-interference
NET=ejs-bench_ejs
IMG=ejs-bench-lab
VENV=$REPO/.venv/bin/python3
COMPOSE="docker compose -f $EJS/compose.yml -f $EJS/compose.cpuset.yml"
MVLADDER="16.0 32.0 64.0 128.0 256.0"
OUT=$WI/_work/phase_c
LOG=$WI/_work/mv_only.log
mkdir -p "$OUT"; : > "$LOG"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

register(){ docker run --rm --network $NET -v $REPO:/repo -w /repo $IMG \
    python3 /repo/workload-interference/_register_soc.py >>"$LOG" 2>&1 || log "register warn"; }
capture(){ "$VENV" - "$1" "$2" >>"$LOG" 2>&1 <<PYEOF
import json, pathlib, sys
arm, tag = sys.argv[1], sys.argv[2]
b = json.loads(pathlib.Path("$WI/results/results.json").read_text())
rec = b.get("arms", {}).get(arm)
p = pathlib.Path("$OUT") / f"{tag}_{arm}.json"
if rec is None:
    print(f"capture: NO record for {arm}"); sys.exit(0)
p.write_text(json.dumps({"arm": arm, "tag": tag, "ladder": b["config"]["ladder"], "record": rec}, indent=2))
print(f"capture: wrote {p}")
PYEOF
}
wait_health(){ local c=$1 t=${2:-300} i=0 s
  while [ $i -lt "$t" ]; do s=$(docker inspect --format '{{.State.Health.Status}}' "$c" 2>/dev/null||echo none)
    [ "$s" = healthy ] && { log "$c healthy ${i}s"; return 0; }; sleep 6; i=$((i+6)); done
  log "$c NOT healthy ${t}s"; return 1; }

cd "$EJS"
log "=== starrocks_mv (P5) re-run START ==="
$COMPOSE up -d minio nessie lab >>"$LOG" 2>&1; sleep 6
$COMPOSE --profile engine-starrocks up -d >>"$LOG" 2>&1
if wait_health ejs-starrocks 300; then
  register
  log "building + SYNC-refreshing MVs (REFRESH MANUAL fix)"
  if docker run --rm --network $NET -v $REPO:/repo -w /repo/workload-interference $IMG \
       python3 starrocks_mv_build.py >>"$LOG" 2>&1; then
    log "MV build OK"
    log "RUN starrocks_mv (ladder $MVLADDER, client cpuset 12,13)"
    docker run --rm --cpuset-cpus 12,13 --network $NET -v $REPO:/repo -w /repo/workload-interference $IMG \
      python3 run.py --arm starrocks_mv --ladder $MVLADDER >>"$LOG" 2>&1 \
      && { log "OK starrocks_mv"; capture starrocks_mv mv; } || log "FAIL starrocks_mv (rewrite not engaged?)"
  else
    log "MV build FAIL — see log"
  fi
fi
$COMPOSE stop starrocks >>"$LOG" 2>&1
log "=== starrocks_mv (P5) re-run DONE ==="
