#!/usr/bin/env bash
# One engine at a time (methodology isolation); anchors then corpus per arm; resumable.
set -u
cd "$(dirname "$0")"
arm() { docker exec drn-lab python run_engines.py --arm "$1" --set all --resume >> "logs/run_$1.log" 2>&1; }
echo "== $(date -u +%FT%TZ) ClickHouse"; docker stop drn-starrocks drn-trino 2>/dev/null
docker compose --profile engine-clickhouse up -d clickhouse
until docker exec drn-clickhouse clickhouse-client --password drnbench123 --query "SELECT 1" >/dev/null 2>&1; do sleep 5; done
arm clickhouse_iceberg; arm clickhouse_native
docker stop drn-clickhouse
echo "== $(date -u +%FT%TZ) StarRocks"
docker compose --profile engine-starrocks up -d starrocks
until [ "$(docker inspect -f '{{.State.Health.Status}}' drn-starrocks 2>/dev/null)" = "healthy" ]; do sleep 10; done
sleep 15; arm starrocks
docker stop drn-starrocks
echo "== $(date -u +%FT%TZ) Trino"
docker compose --profile engine-trino up -d trino
until docker exec drn-trino trino --execute "SELECT 1" >/dev/null 2>&1; do sleep 10; done
arm trino
docker stop drn-trino
echo "== $(date -u +%FT%TZ) DONE"
