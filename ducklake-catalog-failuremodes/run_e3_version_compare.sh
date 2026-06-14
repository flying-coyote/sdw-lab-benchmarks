#!/usr/bin/env bash
# BENCH-E E3 version comparison (#1031 pool timeout): run the IDENTICAL repro under
# the issue's reported-reproducing DuckDB (1.5.2) and the current stack (1.5.3), against
# a fresh postgres:17 catalog each time. A bug that fires on 1.5.2 and not on 1.5.3
# (which is "PR submitted") is a defensible "fixed-between" finding; a bug that fires on
# neither means the minimal repro under-triggers on this host. Tier B, single host.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CUR_VENV="/home/jerem/sdw-lab-benchmarks/.venv/bin/python3"
OLD_VENV="/tmp/ducklake-e3-1.5.2-venv"
PG_IMAGE="${PG_IMAGE:-postgres:17}"
CONTAINER="pg-ducklake-benchE3cmp"
PORT="${PGPORT:-5545}"

cleanup() { docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT

start_pg() {
  cleanup
  docker run --rm -d --name "$CONTAINER" \
    -e POSTGRES_PASSWORD=test -e POSTGRES_DB=ducklake_catalog \
    -p "${PORT}:5432" "$PG_IMAGE" >/dev/null
  for _ in $(seq 1 60); do
    docker exec "$CONTAINER" pg_isready -U postgres -d ducklake_catalog >/dev/null 2>&1 && return 0
    sleep 1
  done
  echo "[e3cmp] postgres did not become ready" >&2; return 1
}

export PGHOST=localhost PGPORT="$PORT" PGDATABASE=ducklake_catalog \
       PGUSER=postgres PGPASSWORD=test PG_IMAGE="$PG_IMAGE"

# --- old version (1.5.2): build a throwaway venv pinned to the reported-reproducing duckdb ---
if [ ! -x "$OLD_VENV/bin/python3" ]; then
  echo "[e3cmp] building throwaway venv with duckdb==1.5.2"
  python3 -m venv "$OLD_VENV"
  "$OLD_VENV/bin/pip" install -q --upgrade pip
  "$OLD_VENV/bin/pip" install -q "duckdb==1.5.2"
fi
echo "[e3cmp] old-version duckdb: $("$OLD_VENV/bin/python3" -c 'import duckdb;print(duckdb.__version__)')"

echo "[e3cmp] === E3 on DuckDB 1.5.2 (reported-reproducing) ==="
start_pg
E3_LABEL="duckdb-1.5.2" E3_OUT="$HERE/results/e3_v1.5.2.json" E3_N_TABLES="${E3_N_TABLES:-60}" \
  "$OLD_VENV/bin/python3" "$HERE/e3_pool_timeout_pg.py" 2>&1 | tail -3 || echo "[e3cmp] old exited non-zero"

echo "[e3cmp] === E3 on DuckDB 1.5.3 (current stack) ==="
start_pg
E3_LABEL="duckdb-1.5.3" E3_OUT="$HERE/results/e3_v1.5.3.json" E3_N_TABLES="${E3_N_TABLES:-60}" \
  "$CUR_VENV" "$HERE/e3_pool_timeout_pg.py" 2>&1 | tail -3 || echo "[e3cmp] current exited non-zero"

echo "[e3cmp] done"
