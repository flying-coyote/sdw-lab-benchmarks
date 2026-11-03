#!/usr/bin/env bash
# Helper sourced by recover_f1.sh / recover_f2.sh (no step markers of its own): bring the
# pipeline back to a NEW running incarnation, logging every (deployment_status,
# program_status, desired_status, error_code) seen so a recompile is visible, then wait
# until the sink adapter has re-attached to the egress stream.
# The status read right after a manager restart can be a stale "Running" from before the
# kill (seen in smoke 2026-11-03), so Running only counts once /stats answers with an
# incarnation_uuid different from the pre-fault one ($SMX_PRE_INCARNATION).
URL="${SMX_FELDERA_URL:-http://localhost:18080}"; P="${SMX_PIPELINE:-smx-detect}"
STATUS_LOG="${SMX_FAULT_DIR}/pipeline-status-trace.txt"
pstat() { curl -s -m 5 "$URL/v0/pipelines/$P" | python3 -c 'import json,sys; d=json.load(sys.stdin); e=d.get("deployment_error"); print(d["deployment_status"], d["program_status"], d.get("deployment_desired_status"), (e or {}).get("error_code") if isinstance(e, dict) else e)' 2>/dev/null; }
incarn() { curl -s -m 5 "$URL/v0/pipelines/$P/stats" | python3 -c 'import json,sys; print(json.load(sys.stdin)["global_metrics"]["incarnation_uuid"])' 2>/dev/null; }
DRAIN_CONNECTS0="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["n_connects"])' "$SMX_DRAIN_STATE" || echo 0)"
for _ in $(seq 1 600); do
  s="$(pstat || true)"; echo "$(date +%s.%N) $s" >> "$STATUS_LOG"
  set -- $s
  if [ "${1:-}" = "Running" ]; then
    inc="$(incarn || true)"
    if [ -n "$inc" ] && [ "$inc" != "${SMX_PRE_INCARNATION:-}" ]; then echo "$(date +%s.%N) new incarnation $inc" >> "$STATUS_LOG"; break; fi
  elif [ "${1:-}" = "Stopped" ]; then
    r="$(curl -s -X POST "$URL/v0/pipelines/$P/start" || true)"
    echo "$(date +%s.%N) operator issued start: $r" >> "$STATUS_LOG"
  fi
  sleep 0.5
done
for _ in $(seq 1 240); do
  python3 -c 'import json,sys; s=json.load(open(sys.argv[1])); sys.exit(0 if s["connected"] and s["n_connects"] > int(sys.argv[2]) else 1)' "$SMX_DRAIN_STATE" "$DRAIN_CONNECTS0" 2>/dev/null && break
  sleep 0.5
done
echo "$(date +%s.%N) sink adapter re-attached" >> "$STATUS_LOG"
