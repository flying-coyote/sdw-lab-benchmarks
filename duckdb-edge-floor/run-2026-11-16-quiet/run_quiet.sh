#!/usr/bin/env bash
# QUIET REPLICATION 2026-11-16 edge-floor orchestrator: arm C (control), main arm, arm B, serial.
# No arm starts inside 06:00-07:30Z (pre-registered); drivers gate each cell on load (LOAD_MAX 1.0, 120 s).
set -u
cd "$(dirname "$0")"
L=results/orchestrator.log
nocron() { while :; do m=$((10#$(date -u +%H)*60 + 10#$(date -u +%M))); if [ $m -ge 360 ] && [ $m -lt 450 ]; then sleep 60; else break; fi; done; }
stamp() { echo "$(date -u +%FT%TZ) arm=$1 load=$(cut -d' ' -f1-3 /proc/loadavg) chrony_system_time=\"$(chronyc tracking | sed -n 's/^System time *: //p')\" ollama_ps=\"$(ollama ps | awk 'NR>1{print $1}' | tr '\n' ' ')\"" | tee -a $L; }
nocron; stamp C;    python3 -B driver_armC.py > results/driver-armC.log 2>&1
nocron; stamp main; python3 -B driver.py      > results/driver.log 2>&1
nocron; stamp B;    python3 -B driver_armB.py > results/driver-armB.log 2>&1
echo "$(date -u +%FT%TZ) DONE" | tee -a $L
