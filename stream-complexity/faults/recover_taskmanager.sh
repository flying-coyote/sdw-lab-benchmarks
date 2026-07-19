#!/usr/bin/env bash
# Recovery for fault (b). One shell command = one step (see recover_broker.sh for the
# counting convention). This is where checkpointing (execution.checkpointing.interval
# in streaming/docker-compose.yml) is supposed to pay for itself: once the
# taskmanager re-registers, the jobmanager's configured restart-strategy
# (fixed-delay, 10 attempts) reschedules the job onto it and resumes from the last
# completed checkpoint, with no manual job resubmission needed.
set -euo pipefail

# Anchor BEFORE step 1, so step 2 only accepts a completion signal that happened
# during THIS recovery, never a stale pre-fault snapshot. This anchor matters: an
# earlier version of this script polled /jobs/<id> for "all vertices RUNNING" and
# reported recovery in well under a second — which turned out to be a real bug, not
# a fast recovery. The jobmanager's own log showed the actual RESTARTING->RUNNING
# transition happening ~5s later (the configured restart-strategy.fixed-delay.delay),
# matching a checkpoint-restore log line right after. The REST job-overview endpoint
# can report a stale "RUNNING" read from BEFORE the jobmanager has even detected the
# taskmanager is gone (region failover keeps the job-level state loose), so vertex
# status alone is not proof; the jobmanager's own log transition is.
SINCE_EPOCH="$(date +%s)"  # unix seconds — unambiguous, sidesteps any docker-daemon-timezone guessing

# Step 1: restart the SAME container.
docker start smx-taskmanager

# Step 2: wait for the jobmanager's own log to report the job actually leaving
# RUNNING and coming back (or, if region failover keeps the job-level state at
# RUNNING throughout, for the source to report resuming from a checkpoint) —
# either line is unambiguous proof a real recovery cycle completed, not a stale
# read.
for i in $(seq 1 60); do
  # `|| true`: under `set -e -o pipefail`, a plain `var=$(... | grep ... | tail ...)`
  # assignment WOULD abort the whole script the instant grep finds no match (a classic
  # bash gotcha — command-substitution assignments are not exempted from errexit the
  # way an `if cmd; then` conditional is) — confirmed live: an earlier version of this
  # line took the script down after ~0.6s on the very first no-match iteration, which
  # briefly (and wrongly) looked like a suspiciously fast recovery in results/faults.json
  # until the jobmanager's own log showed the real RESTARTING->RUNNING transition
  # happening ~23s later. `|| true` lets a genuinely-empty `$hit` fall through to the
  # `[ -n "$hit" ]` check below, which is where "did we find it yet" is supposed to be
  # decided.
  hit="$(docker logs --since "$SINCE_EPOCH" smx-jobmanager 2>&1 \
    | grep -E 'switched from state RESTARTING to RUNNING|Recovering subtask .* to checkpoint' \
    | tail -1 || true)"
  if [ -n "$hit" ]; then
    echo "recovery confirmed via jobmanager log: $hit"
    exit 0
  fi
  sleep 1
done
echo "no RESTARTING->RUNNING / checkpoint-recovery log line seen within timeout" >&2
exit 1
