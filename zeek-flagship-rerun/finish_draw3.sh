#!/usr/bin/env bash
# Finish draw-3: re-run ONLY the opensearch + dremio arms with proper readiness gating
# (revalidate.sh's fixed sleep 8/12 were too short — both failed "connection reset" before the
# service accepted connections). The clickhouse_native + clickhouse_iceberg arms already produced
# fresh draw-3 results in results/ this run; minio+nessie stay up and the Iceberg table is already
# registered. After both arms succeed, --compare and re-capture the full draw to
# results_revalidation3_2026-06-14/.
set -u
cd /home/jerem/sdw-lab-benchmarks/zeek-flagship-rerun
PYV=/home/jerem/sdw-lab-benchmarks/.venv/bin/python
LOG=_work/finish_draw3.log; : > "$LOG"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

wait_os(){ for _ in $(seq 1 60); do
  docker exec zfr-opensearch curl -fs localhost:9200/_cluster/health >/dev/null 2>&1 && { log "opensearch ready"; return 0; }
  sleep 3; done; log "opensearch NOT ready 180s"; return 1; }
wait_dremio(){ for _ in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:9347/apiv2/login 2>/dev/null || echo 000)
  [ "$code" != 000 ] && { sleep 15; log "dremio REST up (code $code)"; return 0; }
  sleep 3; done; log "dremio REST NOT up 270s"; return 1; }

log "=== FINISH-DRAW3 START (opensearch + dremio with readiness gating) ==="
# opensearch arm
docker stop zfr-clickhouse zfr-dremio >>"$LOG" 2>&1
docker start zfr-opensearch >>"$LOG" 2>&1
if wait_os; then
  $PYV run_bench.py --arm opensearch --engine-cold >>"$LOG" 2>&1 && log "opensearch OK" || log "opensearch FAIL"
fi
docker stop zfr-opensearch >>"$LOG" 2>&1

# dremio arm
docker start zfr-dremio >>"$LOG" 2>&1
if wait_dremio; then
  $PYV dremio_arm.py register >>"$LOG" 2>&1
  $PYV dremio_arm.py source   >>"$LOG" 2>&1
  $PYV dremio_arm.py reflect-off >>"$LOG" 2>&1
  $PYV run_bench.py --arm dremio_iceberg --engine-cold >>"$LOG" 2>&1 && log "dremio_iceberg OK" || log "dremio_iceberg FAIL"
fi
docker stop zfr-dremio >>"$LOG" 2>&1

log "--- compare ---"
$PYV run_bench.py --compare >>"$LOG" 2>&1 && log "compare OK" || log "compare FAIL"

# re-capture the full draw (all 4 arms now fresh in results/ if both succeeded)
oks=$(grep -cE "opensearch OK|dremio_iceberg OK" "$LOG")
DST=results_revalidation3_2026-06-14
mkdir -p "$DST"
cp results/raw_opensearch.json results/raw_clickhouse_native.json \
   results/raw_clickhouse_iceberg.json results/raw_dremio_iceberg.json \
   results/comparison.json "$DST/" 2>/dev/null
log "=== FINISH-DRAW3 DONE (os+dremio ok=$oks/2) ==="
