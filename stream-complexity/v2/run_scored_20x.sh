#!/usr/bin/env bash
# v2 scored clean trials: three 20x trials, all four arms concurrently, sequential.
cd "$(dirname "$0")/.."
for N in 1 2 3; do
  bash v2/run_trial_v2.sh "trial-20x-$N" 20 > "results/v2/trial-20x-$N.log" 2>&1
  echo "trial $N exit $?" >> results/v2/scored-20x-status.txt
done
echo DONE >> results/v2/scored-20x-status.txt
