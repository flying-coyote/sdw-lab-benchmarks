#!/usr/bin/env bash
# Recovery for v2 fault BC1 (docker kill of the containerised batch job, restart policy
# on-failure). Steps are counted only if executed: if the restart policy has already
# brought the container back, nothing is done and the count is 0.
set -euo pipefail
if [ "$(docker inspect -f '{{.State.Running}}' smx-bc-batch)" = "true" ]; then
  echo "EXECUTED_STEPS=0 (restart policy restarted the container unaided)"; exit 0
fi
# Step 1: restart the container.
docker start smx-bc-batch >/dev/null
echo "EXECUTED_STEPS=1"
