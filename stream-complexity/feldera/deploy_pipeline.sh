#!/usr/bin/env bash
# F arm deploy: create (or replace) the pipeline from detection.sql, wait for the SQL->Rust
# compile, and start it. One-shot; the running pipeline is what the moving-parts count sees.
# Env: SMX_FELDERA_URL (default http://localhost:18080), SMX_PIPELINE (default smx-detect).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
URL="${SMX_FELDERA_URL:-http://localhost:18080}"
P="${SMX_PIPELINE:-smx-detect}"
RUNTIME_CONFIG="${SMX_RUNTIME_CONFIG:-{}}"
body="$(python3 -c 'import json,sys; print(json.dumps({"name": sys.argv[1], "program_code": open(sys.argv[2]).read(), "runtime_config": json.loads(sys.argv[3])}))' "$P" "$HERE/detection.sql" "$RUNTIME_CONFIG")"
curl -sf -X PUT "$URL/v0/pipelines/$P" -H 'Content-Type: application/json' -d "$body" >/dev/null
for _ in $(seq 1 900); do
  st="$(curl -sf "$URL/v0/pipelines/$P" | python3 -c 'import json,sys; print(json.load(sys.stdin)["program_status"])')"
  case "$st" in Success) break ;; *Error*) echo "compile failed: $st" >&2; exit 1 ;; esac
  sleep 2
done
curl -sf -X POST "$URL/v0/pipelines/$P/start" >/dev/null
for _ in $(seq 1 300); do
  ds="$(curl -sf "$URL/v0/pipelines/$P" | python3 -c 'import json,sys; print(json.load(sys.stdin)["deployment_status"])')"
  [ "$ds" = "Running" ] && { echo "pipeline $P running"; exit 0; }
  sleep 1
done
echo "pipeline $P did not reach Running" >&2; exit 1
