#!/bin/bash
# T8a formal runs: 10 cells x 3 reps, then the single-run checks. Everything under taskset -c 0-3 nice -n 10.
cd /tmp/claude-1000/lab-ai-research/t8a-mcp-before-after
PY=./venv-v2/bin/python
log() { echo "$(date -u +%FT%TZ)  $*" >> COMMANDS.log; }
log "formal runs start: chronyc offset: $(chronyc tracking 2>/dev/null | grep 'System time' | sed 's/ \+/ /g'); load: $(cut -d' ' -f1-3 /proc/loadavg)"
for rep in 1 2 3; do
  for arm in A B C Clog D; do
    for tr in stdio http; do
      log "run_cell.py $arm $tr $rep"
      taskset -c 0-3 nice -n 10 $PY run_cell.py $arm $tr $rep >> runs/formal.log 2>&1
    done
  done
done
log "single-run checks: B/C stdio --no-otel"
taskset -c 0-3 nice -n 10 $PY run_cell.py B stdio 1 --no-otel >> runs/formal.log 2>&1
taskset -c 0-3 nice -n 10 $PY run_cell.py C stdio 1 --no-otel >> runs/formal.log 2>&1
log "formal runs end; load: $(cut -d' ' -f1-3 /proc/loadavg)"
echo DONE >> runs/formal.log
