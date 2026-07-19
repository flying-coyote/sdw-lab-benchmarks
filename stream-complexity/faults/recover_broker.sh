#!/usr/bin/env bash
# Recovery for fault (a). One shell command = one step; faults/run_faults.py counts
# the lines below (excluding comments/blank) as the operator-step tally it records
# into results/faults.json, so keep this literal and honest rather than golfed.
#
# Single-broker KRaft has no peer to re-elect a controller/leader against — that is
# an honest, IN-SCOPE simplification the pre-reg's own honesty boundary names
# ("Kafka+Flink as the canonical stack"), not a shortcut this script is taking: a
# multi-broker production Kafka would have real ISR catch-up and controller
# election to do here, which this single-host single-broker bench does not exercise
# and does not claim to.
set -euo pipefail

# Step 1: restart the SAME container (not `docker compose up`, which would recreate
# it) — the volume-backed log dir and container identity survive a `kill`+`start`.
docker start smx-kafka

# Step 2: wait until the broker answers again.
for i in $(seq 1 60); do
  if docker exec smx-kafka /opt/kafka/bin/kafka-broker-api-versions.sh \
      --bootstrap-server localhost:9092 >/dev/null 2>&1; then
    echo "smx-kafka reachable again"
    exit 0
  fi
  sleep 2
done
echo "smx-kafka did not become reachable within timeout" >&2
exit 1
