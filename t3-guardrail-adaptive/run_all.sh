#!/usr/bin/env bash
# Chain for the revised (stop-rule) design; see COMMANDS.log / RESULTS.md deviations.
# usage: run_all.sh <model> [skip_t0]   -- skip_t0=1 when the T0 pass already exists in scores-<model>-t0.jsonl
set -u
cd "$(dirname "$0")"
M=$1; SKIP=${2:-0}
PY=".venv/bin/python"
RUN="nice -n 10 taskset -c 10-13 $PY run.py $M"
SHORT="A1-deepset-test,A2-gandalf,B1-deepset-test,B2-notinject,B3-dolly,B5-jbb-benign"
LONG="A3-itw-jailbreak,B4-itw-regular"
log(){ echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> COMMANDS.log; }
if [ "$SKIP" = "1" ]; then TS="T1,T2,T3,T4,T5,T7"; TL="T1"; else TS="T0,T1,T2,T3,T4,T5,T7"; TL="T0,T1"; fi
log "$RUN --sets $SHORT --transforms $TS --out results/scores-$M-short.jsonl"
$RUN --sets $SHORT --transforms $TS --out results/scores-$M-short.jsonl > results/log-$M-short.txt 2>&1
log "$RUN --sets $LONG --cap-sets $LONG --cap 150 --transforms $TL --out results/scores-$M-long150.jsonl"
$RUN --sets $LONG --cap-sets $LONG --cap 150 --transforms $TL --out results/scores-$M-long150.jsonl > results/log-$M-long150.txt 2>&1
log "$RUN --sets $LONG --cap-sets $LONG --cap 50 --transforms T2,T3,T4,T5,T7 --out results/scores-$M-long50.jsonl"
$RUN --sets $LONG --cap-sets $LONG --cap 50 --transforms T2,T3,T4,T5,T7 --out results/scores-$M-long50.jsonl > results/log-$M-long50.txt 2>&1
log "nice -n 10 taskset -c 10-13 $PY run_stability.py $M"
nice -n 10 taskset -c 10-13 $PY run_stability.py $M > results/log-$M-stability.txt 2>&1
log "model $M chain finished"
