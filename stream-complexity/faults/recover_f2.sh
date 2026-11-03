#!/usr/bin/env bash
# Recovery for v2 fault F2 (SIGKILL of the pipeline process inside the Feldera container,
# manager left up). Same frozen rewind rule as F1, minus the container restart.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Step 1: restart the pipeline (recording any recompile) and wait for Running + sink attached.
source "$HERE/_feldera_restart_pipeline.sh"

# Step 2: compute the rewind point from the replayer's last acknowledged event time.
R="$(python3 -c 'import json,sys; la=json.load(open(sys.argv[1]))["last_acked"]; print(((la-2)//60)*60)' "$SMX_REPLAYER_STATE")"

# Step 3: re-send from the rewind point to the current replay position, then resume pacing.
echo "{\"rewind_to\": $R}" > "$SMX_CONTROL_FILE"
echo "rewind_to=$R"
