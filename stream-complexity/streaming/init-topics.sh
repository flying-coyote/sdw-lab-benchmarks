#!/usr/bin/env bash
# Engine config surface (measure_complexity.py counts this in its "engine_config"
# bucket): explicit topic provisioning rather than relying on Kafka auto-create.
# KAFKA_AUTO_CREATE_TOPICS_ENABLE is set to 'false' in docker-compose.yml — a real,
# common production Kafka governance choice — so this script is not optional
# scaffolding, it's the thing that makes the topics exist at all. Idempotent
# (--if-not-exists): safe to run on every `docker compose up`.
set -euo pipefail
BOOTSTRAP="smx-kafka:9092"

for topic in smx-auth smx-alerts; do
  /opt/kafka/bin/kafka-topics.sh --create --if-not-exists \
    --bootstrap-server "$BOOTSTRAP" \
    --topic "$topic" --partitions 1 --replication-factor 1
done

echo "=== topics on $BOOTSTRAP ==="
/opt/kafka/bin/kafka-topics.sh --bootstrap-server "$BOOTSTRAP" --list
