#!/usr/bin/env bash
# v2 fault battery driver: independent lanes (no shared containers or dirs) run in parallel;
# S1->S2 and F1->F2 share a stack name, so each pair runs sequentially in its own lane.
# Usage: v2/run_faults_v2.sh <tag> [comma list of extra B ids, e.g. B2x,B3x]
cd "$(dirname "$0")/.."
TAG="$1"; EXTRA="${2:-}"
PY=../.venv/bin/python3
mkdir -p "results/v2/faults-$TAG"
pids=()
lane() { "$PY" v2/faults_v2.py --tag "$TAG" --only "$1" > "results/v2/faults-$TAG/lane-$2.log" 2>&1 & pids+=($!); }
lane S1,S2 S; lane F1,F2 F; lane BC1 BC
for b in B1 B2 B3 ${EXTRA//,/ }; do lane "$b" "$b"; done
wait "${pids[@]}"
echo DONE > "results/v2/faults-$TAG/STATUS"
