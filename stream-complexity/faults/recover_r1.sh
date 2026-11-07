#!/usr/bin/env bash
# Recovery for v3 fault R1 (docker kill smx-risingwave, the whole single-process cluster).
# Frozen rewind rule (PRE-REG-stream-complexity-risingwave-2026-11-07): RisingWave restores
# window state from its own last checkpoint, but with no broker in front of it the events it
# acknowledged after that checkpoint are gone, so the source re-sends everything above the
# recovered max(event_uid). The drain consumer reconnects through its own retry code
# (adapter, not an operator step). Env: SMX_CONTROL_FILE (the replayer's control file).
set -euo pipefail
PY="${SMX_PY:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/.venv/bin/python3}"
DSN="${SMX_RW_DSN:-host=localhost port=14566 user=root dbname=dev connect_timeout=2}"

# Step 1: start the container again (docker kill does not trigger a restart policy).
docker start smx-risingwave >/dev/null

# Step 2: once the SQL port answers, read the rewind point from the last committed checkpoint.
U="$("$PY" -c '
import sys, time, psycopg
for _ in range(600):
    try:
        with psycopg.connect(sys.argv[1], autocommit=True) as c:
            print(c.execute("SELECT max(event_uid) FROM auth_events").fetchone()[0]); break
    except psycopg.Error:
        time.sleep(0.5)
else:
    sys.exit("SQL port never answered")' "$DSN")"

# Step 3: tell the replayer to re-send every event with a larger event_uid, then resume pacing.
echo "{\"resend_after_uid\": \"$U\"}" > "$SMX_CONTROL_FILE"
echo "resend_after_uid=$U"
