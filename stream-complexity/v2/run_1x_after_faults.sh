#!/usr/bin/env bash
# Starts the unattended 1x trial once the scored F fault lane (PID $1) has exited.
cd "$(dirname "$0")/.."
while kill -0 "$1" 2>/dev/null; do sleep 5; done
date -u +%FT%TZ > results/v2/trial-1x.started
bash v2/run_trial_v2.sh trial-1x 1 > results/v2/trial-1x.log 2>&1
echo "exit $?" > results/v2/trial-1x.status
