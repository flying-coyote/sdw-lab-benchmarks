#!/bin/bash
# Replacement measurement lane (the first lane in resume_driver.sh passed a name as --seed and was killed after the base call failed on argparse).
cd "$(dirname "$0")"
eval "$(sed -n '/^T0=/,/^epoch_done/p' resume_driver.sh)"
eval "$(sed -n '/^measure() {/,/^}/p;/^wait_for() {/,/^}/p' resume_driver.sh)"
stamp "RELAUNCH measurement lane measure_lane.sh (argument bug fixed: seed 0 for base, k for seed k)"
measure base base 0
for spec in "7 3" "8 3" "9 3" "7 1" "7 2"; do
  set -- $spec
  if wait_for $1 $2; then measure ckpt/lora-seed$1/epoch$2 lora-seed$1-epoch$2 $1; else stamp "SKIP measure lora seed $1 epoch $2: checkpoint not produced inside the budget"; fi
done
stamp "MEASURE LANE DONE"
