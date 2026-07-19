#!/usr/bin/env bash
# Submits flink_job.sql into the already-running Flink cluster via the SQL Client in
# embedded (non-interactive, -f file) mode, executed inside the jobmanager container.
# One command = one moving part; measure_complexity.py counts this file, not its
# runtime invocation (it runs once per trial and exits — the JOB it starts is what
# keeps running, tracked as the jobmanager/taskmanager containers already in the
# moving-parts count).
set -euo pipefail
COMPOSE_PROJECT="${SMX_COMPOSE_PROJECT:-smx-stream}"
JOBMANAGER="${SMX_JOBMANAGER_CONTAINER:-smx-jobmanager}"

echo "[submit_flink_job] submitting flink_job.sql into ${JOBMANAGER} ..."
docker exec "${JOBMANAGER}" /opt/flink/bin/sql-client.sh -f /opt/flink/usrlib/flink_job.sql
