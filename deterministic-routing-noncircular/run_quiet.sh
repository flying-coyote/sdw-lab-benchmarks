#!/usr/bin/env bash
# QUIET REPLICATION 2026-11-16 orchestrator (new file; run_all.sh and its logs untouched). Same engine order as
# run_all.sh. Load/chrony gate before each cell (pre-registered: wait while load1 > 1.0, max 300 s).
set -u
cd "$(dirname "$0")"
L=logs/quiet-2026-11-16
stamp() { # $1 = cell name
  local w=0
  while awk '{exit !($1>1.0)}' /proc/loadavg && [ $w -lt 300 ]; do sleep 15; w=$((w+15)); done
  echo "$(date -u +%FT%TZ) cell=$1 load=$(cut -d' ' -f1-3 /proc/loadavg) waited_s=$w gate_expired=$([ $w -ge 300 ] && echo yes || echo no) chrony_system_time=\"$(chronyc tracking | sed -n 's/^System time *: //p')\"" | tee -a $L/stamps.log
}
arm() { stamp "arm:$1"; docker exec drn-lab python -B run_engines_quiet.py --arm "$1" --set all >> "$L/run_$1.log" 2>&1; }
echo "== $(date -u +%FT%TZ) ClickHouse" | tee -a $L/run_quiet.log
docker compose --profile engine-clickhouse up -d clickhouse >> $L/run_quiet.log 2>&1
until docker exec drn-clickhouse clickhouse-client --password drnbench123 --query "SELECT 1" >/dev/null 2>&1; do sleep 5; done
docker exec drn-lab python -B check_counts_quiet.py > $L/data_gate_counts.log 2>&1 || { echo "GATE1 FAIL, stopping" | tee -a $L/run_quiet.log; docker stop drn-clickhouse; exit 1; }
arm clickhouse_iceberg; arm clickhouse_native
docker stop drn-clickhouse >> $L/run_quiet.log
echo "== $(date -u +%FT%TZ) StarRocks" | tee -a $L/run_quiet.log
docker compose --profile engine-starrocks up -d starrocks >> $L/run_quiet.log 2>&1
until [ "$(docker inspect -f '{{.State.Health.Status}}' drn-starrocks 2>/dev/null)" = "healthy" ]; do sleep 10; done
sleep 15; arm starrocks
stamp "sr_attempts_probe"; docker exec drn-lab python -B sr_probe_quiet.py > $L/sr_attempts_probe.log 2>&1
docker stop drn-starrocks >> $L/run_quiet.log
echo "== $(date -u +%FT%TZ) Trino" | tee -a $L/run_quiet.log
docker compose --profile engine-trino up -d trino >> $L/run_quiet.log 2>&1
until docker exec drn-trino trino --execute "SELECT 1" >/dev/null 2>&1; do sleep 10; done
arm trino
docker stop drn-trino >> $L/run_quiet.log
echo "== $(date -u +%FT%TZ) DONE" | tee -a $L/run_quiet.log
