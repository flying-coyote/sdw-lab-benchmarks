#!/usr/bin/env bash
# Fault (b) from the pre-reg: kill the Flink taskmanager mid-run.
set -euo pipefail
docker kill smx-taskmanager
echo "killed smx-taskmanager"
