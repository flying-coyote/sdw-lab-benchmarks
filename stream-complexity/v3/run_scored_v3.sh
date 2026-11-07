#!/usr/bin/env bash
# v3 scored chain (PRE-REG-stream-complexity-risingwave-2026-11-07): three 20x clean trials,
# then the R1 fault on the full corpus at 20x, then the unattended 1x trial. No re-runs:
# whatever each step produces is the scored result.
cd "$(dirname "$0")/.."
ST=results/v3/scored-status.txt
for N in 1 2 3; do
  bash v3/run_trial_v3.sh "trial-20x-$N" 20 > "results/v3/trial-20x-$N.log" 2>&1
  echo "$(date -u +%FT%TZ) trial-20x-$N exit $?" >> "$ST"
done
mkdir -p results/v3/faults-scored
../.venv/bin/python3 v2/faults_v2.py --only R1 --tag scored --results-dir v3 > results/v3/faults-scored/lane-R.log 2>&1
echo "$(date -u +%FT%TZ) R1 exit $?" >> "$ST"
date -u +%FT%TZ > results/v3/trial-1x.started
bash v3/run_trial_v3.sh trial-1x 1 > results/v3/trial-1x.log 2>&1
echo "$(date -u +%FT%TZ) trial-1x exit $?" >> "$ST"
echo DONE >> "$ST"
