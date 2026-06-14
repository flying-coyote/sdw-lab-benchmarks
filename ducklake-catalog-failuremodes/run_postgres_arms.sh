#!/usr/bin/env bash
# BENCH-E Postgres arms (E2 #1184, E3 #1031): bring up one postgres:17 catalog
# container, run both arms against it, tear it down. E1 needs no Postgres and is run
# separately (e1_crossstore_delete.py). Tier B, single host.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="/home/jerem/sdw-lab-benchmarks/.venv/bin/python3"
PG_IMAGE="${PG_IMAGE:-postgres:17}"
CONTAINER="pg-ducklake-benchE"
PORT="${PGPORT:-5544}"   # off the default 5432 to avoid colliding with any local pg

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

cleanup
echo "[run] starting $PG_IMAGE as $CONTAINER on :$PORT"
docker run --rm -d --name "$CONTAINER" \
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=ducklake_catalog \
  -p "${PORT}:5432" "$PG_IMAGE" >/dev/null

# wait for readiness
echo -n "[run] waiting for postgres"
for _ in $(seq 1 60); do
  if docker exec "$CONTAINER" pg_isready -U postgres -d ducklake_catalog >/dev/null 2>&1; then
    echo " ready"; break
  fi
  echo -n "."; sleep 1
done

export PGHOST=localhost PGPORT="$PORT" PGDATABASE=ducklake_catalog \
       PGUSER=postgres PGPASSWORD=test PG_IMAGE="$PG_IMAGE"

# E2 uses one fresh PG database per probe so catalogs never collide on DATA_PATH
echo "[run] creating per-probe databases for E2"
for i in 0 1 2 3; do
  docker exec "$CONTAINER" psql -U postgres -d ducklake_catalog \
    -c "CREATE DATABASE ducklake_e2_${i};" >/dev/null 2>&1 || true
done

echo "[run] === E2 (#1184 wide-table wall) ==="
"$VENV" "$HERE/e2_wide_table_pg.py" || echo "[run] E2 exited non-zero"

# E3 (#1031) is run by run_e3_version_compare.sh — it needs the 1.5.2-vs-1.5.3
# controlled comparison to tell "fixed" from "under-triggered", so it owns its own
# container lifecycle and is not run here.
echo "[run] E2 done (run E3 via run_e3_version_compare.sh)"
