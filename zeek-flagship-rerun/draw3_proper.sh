#!/usr/bin/env bash
# Flagship draw-3 (CORRECTED, 2026-06-14). The first draw-3 attempt failed because
# revalidate.sh assumes minio+nessie are already up (it only starts the engine containers),
# but the whole zfr stack was exited — so clickhouse_iceberg/dremio hit "host: minio not
# found" and --compare reused stale results/. This prelude fixes that: start minio+nessie
# (data persists in their volumes; only Nessie's IN_MEMORY catalog is lost), re-register the
# Iceberg table, THEN run revalidate.sh (which manages the engine arms one-at-a-time and keeps
# minio+nessie up). Captures the draw to results_revalidation3_2026-06-14/. No git here.
set -u
cd /home/jerem/sdw-lab-benchmarks/zeek-flagship-rerun
PYV=/home/jerem/sdw-lab-benchmarks/.venv/bin/python
LOG=_work/draw3_proper.log; : > "$LOG"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

log "starting minio + nessie (data persists; nessie IN_MEMORY catalog will be re-registered)"
docker start zfr-minio zfr-nessie >>"$LOG" 2>&1
# wait for minio healthy
for _ in $(seq 1 40); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' zfr-minio 2>/dev/null)" = healthy ] && { log "minio healthy"; break; }
  sleep 3
done
sleep 8  # nessie REST up
log "re-registering zeek.conn_10m into Nessie"
$PYV dremio_arm.py register >>"$LOG" 2>&1 && log "register OK" || { log "register FAIL — aborting"; exit 2; }

log "running revalidate.sh (4 arms, one engine at a time, minio+nessie stay up)"
bash revalidate.sh >>"$LOG" 2>&1

# capture the draw only if all 4 arms succeeded (guard against a repeat of the stale-results bug)
oks=$(grep -cE "opensearch OK|clickhouse_native OK|clickhouse_iceberg OK|dremio_iceberg OK" _work/revalidate.log)
log "arms succeeded: $oks/4"
DST=results_revalidation3_2026-06-14
mkdir -p "$DST"
cp results/raw_opensearch.json results/raw_clickhouse_native.json \
   results/raw_clickhouse_iceberg.json results/raw_dremio_iceberg.json \
   results/comparison.json "$DST/" 2>/dev/null
log "=== DRAW3-PROPER DONE (arms_ok=$oks/4, captured $(ls "$DST" | wc -l) files) ==="
