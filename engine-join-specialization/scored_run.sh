#!/usr/bin/env bash
# Scored timed passes: one engine at a time (methodology isolation), 1 warmup + 7 trials,
# then the CV-gated comparison. Run from the bench dir.
set -u
cd "$(dirname "$0")"

echo "== power plan:"; powercfg.exe /getactivescheme 2>/dev/null || echo "(powercfg unavailable)"

run_arm() { docker compose exec -T lab python run_bench.py --arm "$1"; }

echo "== StarRocks pass"
docker stop ejs-clickhouse ejs-trino ejs-dremio 2>/dev/null
docker compose --profile engine-starrocks up -d starrocks
until [ "$(docker inspect -f '{{.State.Health.Status}}' ejs-starrocks 2>/dev/null)" = "healthy" ]; do sleep 10; done
run_arm starrocks
docker stop ejs-starrocks

echo "== ClickHouse passes (iceberg, then native)"
docker compose --profile engine-clickhouse up -d clickhouse
until docker exec ejs-clickhouse clickhouse-client --password ejsbench123 --query "SELECT 1" >/dev/null 2>&1; do sleep 5; done
run_arm clickhouse_iceberg
run_arm clickhouse_native
docker stop ejs-clickhouse

echo "== Trino pass"
docker compose --profile engine-trino up -d trino
until docker exec ejs-trino trino --execute "SELECT 1" >/dev/null 2>&1; do sleep 10; done
run_arm trino
docker stop ejs-trino

echo "== Dremio pass"
docker compose --profile engine-dremio up -d dremio
until [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:9347/apiv2/login 2>/dev/null)" != "000" ]; do sleep 5; done
sleep 20
run_arm dremio
docker stop ejs-dremio

echo "== compare"
docker compose exec -T lab python run_bench.py --compare
echo "SCORED RUN COMPLETE"
