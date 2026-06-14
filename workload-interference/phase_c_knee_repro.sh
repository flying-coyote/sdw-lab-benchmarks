#!/usr/bin/env bash
# #23 Phase C — knee reproduction (2026-06-14). The extend-ladder located the single-host
# knee at 32-64x base demand (dremio earliest ~16-32x), but that was 1x per arm. The
# pre-registration (README) makes a knee claimable only on 3x reproduction at the same
# ladder step. This runs the 4 graceful arms over the knee REGION (16/32/64x — the
# flat->inflection band) 3x each, saving every repetition separately so the band + the
# knee's reproducibility (util>=1 + monotone backlog at the same step) can be judged.
#
# Same rig as extend_ladder.sh: ejs compose stack, one engine profile up at a time
# (isolation), client cpuset 12,13, engines cpuset 0-11 (compose.cpuset.yml). run.py
# writes results/results.json (merge-by-arm) so after each rep we copy that arm's record
# out to results/phase_c/rep<R>_<arm>.json before the next rep overwrites it.
set -u
REPO=/home/jerem/sdw-lab-benchmarks
EJS=$REPO/engine-join-specialization
WI=$REPO/workload-interference
NET=ejs-bench_ejs
IMG=ejs-bench-lab
COMPOSE="docker compose -f $EJS/compose.yml -f $EJS/compose.cpuset.yml"
KNEE_LADDER="16.0 32.0 64.0"
REPS=3
OUT=$WI/results/phase_c
LOG=$WI/_work/phase_c.log
mkdir -p "$OUT"; : > "$LOG"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

register(){ docker run --rm --network $NET -v $REPO:/repo -w /repo $IMG \
    python3 /repo/workload-interference/_register_soc.py >>"$LOG" 2>&1 || log "register warn"; }

capture(){ # arm rep — copy this arm's record out of results.json before the next rep clobbers
  local arm=$1 rep=$2
  docker run --rm -v $REPO:/repo -w /repo/workload-interference $IMG python3 - "$arm" "$rep" <<'PY' >>"$LOG" 2>&1
import json, sys, pathlib
arm, rep = sys.argv[1], sys.argv[2]
rp = pathlib.Path("results/results.json")
blob = json.loads(rp.read_text())
rec = blob.get("arms", {}).get(arm)
if rec is None:
    print(f"capture: no record for {arm}"); sys.exit(1)
outp = pathlib.Path(f"results/phase_c/rep{rep}_{arm}.json")
outp.write_text(json.dumps({"arm": arm, "rep": int(rep), "ladder": blob["config"]["ladder"],
                            "record": rec}, indent=2))
print(f"capture: wrote {outp}")
PY
}

run_rep(){ # arm
  local arm=$1 r
  for r in $(seq 1 $REPS); do
    log "RUN $arm rep $r/$REPS (knee ladder $KNEE_LADDER, client cpuset 12,13)"
    docker run --rm --cpuset-cpus 12,13 --network $NET -v $REPO:/repo -w /repo/workload-interference $IMG \
      python3 run.py --arm "$arm" --ladder $KNEE_LADDER >>"$LOG" 2>&1 \
      && { log "OK $arm rep $r"; capture "$arm" "$r"; } || log "FAIL $arm rep $r"
  done
}

wait_health(){ local c=$1 t=${2:-180} i=0 s
  while [ $i -lt "$t" ]; do s=$(docker inspect --format '{{.State.Health.Status}}' "$c" 2>/dev/null||echo none)
    [ "$s" = healthy ] && { log "$c healthy ${i}s"; return 0; }; sleep 6; i=$((i+6)); done
  log "$c NOT healthy ${t}s"; return 1; }
wait_dremio(){ local i=0; while [ $i -lt 360 ]; do
    [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:9347/apiv2/server_status 2>/dev/null)" = 200 ] \
      && { sleep 20; log "dremio REST up ${i}s"; return 0; }; sleep 6; i=$((i+6)); done
  log "dremio REST down 360s"; return 1; }

cd "$EJS"
log "=== PHASE C (knee 3x reproduction) START ==="
$COMPOSE up -d minio nessie lab >>"$LOG" 2>&1; sleep 6

$COMPOSE --profile engine-clickhouse up -d >>"$LOG" 2>&1
wait_health ejs-clickhouse 150 && { register; run_rep clickhouse_iceberg; run_rep clickhouse_native; }
$COMPOSE stop clickhouse >>"$LOG" 2>&1

$COMPOSE --profile engine-starrocks up -d >>"$LOG" 2>&1
wait_health ejs-starrocks 300 && { register; run_rep starrocks; }
$COMPOSE stop starrocks >>"$LOG" 2>&1

$COMPOSE --profile engine-dremio up -d >>"$LOG" 2>&1
if wait_dremio; then register; run_rep dremio; fi
$COMPOSE stop dremio >>"$LOG" 2>&1

log "=== PHASE C DONE ==="
