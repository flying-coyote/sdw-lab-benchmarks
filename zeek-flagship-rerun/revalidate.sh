#!/usr/bin/env bash
# Flagship revalidation (2026-06-14, Jeremy priority): re-run all 4 arms fresh, same session,
# one query-engine up at a time (isolation), 7 trials + engine-cold, then --compare. The
# published 2026-06-10 results are backed up in results_published_backup/ for the new-vs-old
# validation. minio + nessie stay up throughout (iceberg/dremio arms need them; low overhead).
set -u
cd /home/jerem/sdw-lab-benchmarks/zeek-flagship-rerun
PYV=/home/jerem/sdw-lab-benchmarks/.venv/bin/python
LOG=_work/revalidate.log; : > "$LOG"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

log "=== FLAGSHIP REVALIDATION START ==="

# 1. opensearch (stop the other query engines)
log "--- opensearch ---"
docker stop zfr-clickhouse zfr-dremio >>"$LOG" 2>&1
docker start zfr-opensearch >>"$LOG" 2>&1; sleep 8
$PYV run_bench.py --arm opensearch --engine-cold >>"$LOG" 2>&1 && log "opensearch OK" || log "opensearch FAIL"

# 2. clickhouse_native (only clickhouse)
log "--- clickhouse_native ---"
docker stop zfr-opensearch >>"$LOG" 2>&1
docker start zfr-clickhouse >>"$LOG" 2>&1; sleep 8
$PYV run_bench.py --arm clickhouse_native --engine-cold >>"$LOG" 2>&1 && log "clickhouse_native OK" || log "clickhouse_native FAIL"

# 3. clickhouse_iceberg (clickhouse + minio)
log "--- clickhouse_iceberg ---"
$PYV run_bench.py --arm clickhouse_iceberg --engine-cold >>"$LOG" 2>&1 && log "clickhouse_iceberg OK" || log "clickhouse_iceberg FAIL"

# 4. dremio_iceberg (dremio + minio + nessie; clickhouse stopped)
log "--- dremio_iceberg ---"
docker stop zfr-clickhouse >>"$LOG" 2>&1
docker start zfr-dremio >>"$LOG" 2>&1; sleep 12
# nessie is in-memory; ensure the table is registered + the OFF baseline is clean
$PYV dremio_arm.py register >>"$LOG" 2>&1
$PYV dremio_arm.py source >>"$LOG" 2>&1
$PYV dremio_arm.py reflect-off >>"$LOG" 2>&1
$PYV run_bench.py --arm dremio_iceberg --engine-cold >>"$LOG" 2>&1 && log "dremio_iceberg OK" || log "dremio_iceberg FAIL"

# 5. compare
log "--- compare ---"
$PYV run_bench.py --compare >>"$LOG" 2>&1 && log "compare OK" || log "compare FAIL"
log "=== FLAGSHIP REVALIDATION DONE ==="
