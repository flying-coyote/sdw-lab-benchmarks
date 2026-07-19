#!/usr/bin/env bash
# Scored run driver — STREAM-COMPLEXITY, 2026-07-19 quiet box.
# Fresh state (down -v per README), full 500k corpus, 3 CV trials
# (BENCHMARKING-METHODOLOGY), fault battery, complexity snapshot.
set -u
cd "$(dirname "$0")"
LOG=results/scored-run.log
mkdir -p results
{
  echo "=== scored run start (driver PID $$) ==="
  date -u +%FT%TZ
  (cd streaming && docker compose down -v) 2>&1
  rm -rf data/batch_in data/events.jsonl data/ground_truth.json \
         results/alerts-batch.jsonl results/alerts-stream.jsonl \
         results/latency-trial-*.json 2>/dev/null
  python3 gen_corpus.py --seed 20260719
  for N in 1 2 3; do
    echo "=== trial $N ==="; date -u +%FT%TZ
    bash run_clean_trial.sh "$N" || { echo "TRIAL $N FAILED"; echo "FAILED trial $N" > results/SCORED-DONE; exit 1; }
    # fresh arm state between trials, same corpus (offsets/checkpoints wiped)
    (cd streaming && docker compose down -v) 2>&1
    rm -rf data/batch_in results/alerts-batch.jsonl results/alerts-stream.jsonl 2>/dev/null
  done
  echo "=== faults ==="; date -u +%FT%TZ
  python3 faults/run_faults.py || echo "FAULTS FAILED (non-fatal for latency scoring; investigate)"
  echo "=== complexity snapshot (stack up briefly) ==="
  (cd streaming && docker compose up -d) 2>&1
  sleep 45
  python3 measure_complexity.py || echo "COMPLEXITY FAILED"
  (cd streaming && docker compose down) 2>&1
  date -u +%FT%TZ
  echo "OK" > results/SCORED-DONE
  echo "=== scored run complete ==="
} >> "$LOG" 2>&1
