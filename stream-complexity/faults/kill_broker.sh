#!/usr/bin/env bash
# Fault (a) from the pre-reg: kill the Kafka broker mid-run.
set -euo pipefail
docker kill smx-kafka
echo "killed smx-kafka"
