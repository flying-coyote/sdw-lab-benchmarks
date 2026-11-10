#!/bin/bash
# Measurement lane, reordered 2026-11-10 ~03:10Z: at the observed ~60-75 s per training step (prereg probe: 12.2 s),
# seed 7 cannot finish before the 2h45 no-new-training line, so seeds 8 and 9 cannot start; measure seed 7
# epochs in the order they appear so the most results land inside the 4h cap. Base measurement continues from measure_lane.sh.
cd "$(dirname "$0")"
eval "$(sed -n '/^T0=/,/^epoch_done/p' resume_driver.sh)"
eval "$(sed -n '/^measure() {/,/^}/p;/^wait_for() {/,/^}/p' resume_driver.sh)"
stamp "REORDER measurement lane measure_lane2.sh (seed 7 epochs 1,2,3 as they appear, then 8/9 epoch 3 if produced); waits for the running base measurement"
while pgrep -f "measure.py --ckpt base" >/dev/null; do sleep 15; done
for spec in "7 1" "7 2" "7 3" "8 3" "9 3"; do
  set -- $spec
  if wait_for $1 $2; then measure ckpt/lora-seed$1/epoch$2 lora-seed$1-epoch$2 $1; else stamp "SKIP measure lora seed $1 epoch $2: checkpoint not produced inside the budget"; fi
done
stamp "MEASURE LANE DONE"
