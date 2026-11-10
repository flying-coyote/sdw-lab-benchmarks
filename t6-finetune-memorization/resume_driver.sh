#!/bin/bash
# T6 relaunch driver (2026-11-10, after the first run agent died). Two lanes:
#   lane train   (cores 0-3): lora seed 7 -> seed 8 -> seed 9, each gated on the 2h45 no-new-training line
#   lane measure (cores 4-7): base, s7e3, s8e3, s9e3, s7e1, s7e2, each wrapped in timeout to the 4h cap
# Clock: original T0 = corpus generation, uptime 459593.26 - 9 s (gen at 00:58:48Z, t0 stamp 00:58:57Z).
cd "$(dirname "$0")"
T0=459584
CAP=14400; NOTRAIN=9900
el() { awk -v t0=$T0 '{printf "%d", $1 - t0}' /proc/uptime; }
stamp() { echo "$(date -u +%FT%TZ) uptime_elapsed=$(el)s $*" >> COMMANDS.log; }
ENVP="env OMP_NUM_THREADS=4 MKL_NUM_THREADS=4"
epoch_done() { [ -f "ckpt/lora-seed$1/train_log.json" ] && .venv/bin/python -c "import json,sys;l=json.load(open('ckpt/lora-seed$1/train_log.json'));sys.exit(0 if any(e['epoch']==$2 for e in l['epochs_done']) else 1)"; }

lane_train() {
  for s in 7 8 9; do
    if [ "$(el)" -ge $NOTRAIN ]; then stamp "SKIP train lora seed $s: past 2h45 no-new-training line"; continue; fi
    if [ $s = 9 ]; then
      proj=$(.venv/bin/python -c "import json;l=json.load(open('ckpt/lora-seed7/train_log.json'));st=l['steps'];print(round(sum(x['sec'] for x in st[:10])/10*l['steps_per_epoch']*l['epochs']/60,1))")
      if awk -v p=$proj 'BEGIN{exit !(p>35)}'; then stamp "SKIP train lora seed 9: seed-7 projection from first 10 steps = ${proj} min > 35 (prereg rule, 2 seeds)"; continue; fi
      stamp "seed-7 projection from first 10 steps = ${proj} min (<= 35, seed 9 allowed)"
    fi
    stamp "START nice -n 10 taskset -c 0-3 $ENVP .venv/bin/python -u train.py --arm lora --seed $s"
    nice -n 10 taskset -c 0-3 $ENVP timeout $((CAP-$(el))) .venv/bin/python -u train.py --arm lora --seed $s > logs/train-lora-seed$s.txt 2>&1
    stamp "END train lora seed $s rc=$?"
  done
  stamp "FULL-FT arm not started: prereg requires <2h30 cumulative since first training step at LoRA completion; original clock already past 2h00 at relaunch"
}

measure() { # ckpt name seed
  local left=$((CAP-$(el)))
  if [ $left -le 60 ]; then stamp "SKIP measure $1: past 4h cap"; return; fi
  stamp "START nice -n 10 taskset -c 4-7 $ENVP .venv/bin/python -u measure.py --ckpt $1 --arm lora --seed $3 (timeout ${left}s)"
  nice -n 10 taskset -c 4-7 $ENVP timeout $left .venv/bin/python -u measure.py --ckpt $1 --arm lora --seed $3 > logs/measure-$2.txt 2>&1
  stamp "END measure $1 rc=$?"
}
wait_for() { # seed epoch
  while ! epoch_done $1 $2; do
    [ "$(el)" -ge $CAP ] && return 1
    if [ $1 != 7 ] && ! pgrep -f "train.py --arm lora --seed $1" >/dev/null && [ "$(el)" -ge $NOTRAIN ] && ! epoch_done $1 $2; then
      grep -q "SKIP train lora seed $1" COMMANDS.log && return 1
    fi
    sleep 20
  done
}
lane_measure() {
  measure base base 0
  for spec in "7 3" "8 3" "9 3" "7 1" "7 2"; do
    set -- $spec
    if wait_for $1 $2; then measure ckpt/lora-seed$1/epoch$2 lora-seed$1-epoch$2 $1; else stamp "SKIP measure lora seed $1 epoch $2: checkpoint not produced inside the budget"; fi
  done
  stamp "MEASURE LANE DONE"
}
stamp "RELAUNCH driver resume_driver.sh (first run died with empty logs; fixtures reused, training restarted from step 0, no resume point in harness; original T0 clock kept)"
lane_train & lane_measure & wait
stamp "DRIVER DONE"
