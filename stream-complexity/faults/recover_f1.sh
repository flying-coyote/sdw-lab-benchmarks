#!/usr/bin/env bash
# Recovery for v2 fault F1 (docker kill of the Feldera OSS pipeline-manager container).
# EDITION-BOUND: OSS has no checkpoint, so window state is gone and the source must re-send.
# Frozen rewind rule: rewind point = start of the epoch-aligned 60 s window containing
# (last_acked - 2 s lateness), last_acked taken from the REPLAYER's acknowledged sends.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
URL="${SMX_FELDERA_URL:-http://localhost:18080}"

# Step 1: restart the container and wait until the manager is healthy.
docker start smx-feldera >/dev/null
for _ in $(seq 1 120); do curl -sf "$URL/healthz" >/dev/null 2>&1 && break; sleep 0.5; done

# Step 2: restart the pipeline (recording any recompile) and wait for Running + sink attached.
source "$HERE/_feldera_restart_pipeline.sh"

# Step 3: compute the rewind point from the replayer's last acknowledged event time.
R="$(python3 -c 'import json,sys; la=json.load(open(sys.argv[1]))["last_acked"]; print(((la-2)//60)*60)' "$SMX_REPLAYER_STATE")"

# Step 4: re-send from the rewind point to the current replay position, then resume pacing.
echo "{\"rewind_to\": $R}" > "$SMX_CONTROL_FILE"
echo "rewind_to=$R"
