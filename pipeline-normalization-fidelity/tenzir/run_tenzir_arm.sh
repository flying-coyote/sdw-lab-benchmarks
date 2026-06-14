#!/usr/bin/env bash
# Tenzir arm for the pipeline-normalization-fidelity bench (#10).
#
# Runs Tenzir's SHIPPED library OCSF mapping over the pinned corpus and writes the
# emitted OCSF JSONL for score.py. Only the Zeek conn arm is faithful on this corpus
# (see STATUS-2026-06-14.md for why sysmon/cloudtrail/auth are coverage gaps, which is
# itself the P1 finding). The mapping operators are Tenzir's, unedited; this script
# only feeds the corpus and pins versions.
#
# PINNED VERSIONS:
#   Tenzir 6.0.0           (docker image tenzir/tenzir:latest)
#   library commit 671e049 (github.com/tenzir/library @ "Port packages to v6 executor")
#
# PREREQUISITE (one-time, needs authorization to run external library code):
#   git clone https://github.com/tenzir/library /tmp/tenzir-library
#   git -C /tmp/tenzir-library checkout 671e049
#
# NOTE: executing `tenzir --package-dirs=<external clone>` runs third-party TQL from
# the Tenzir library. In this session the auto-permission classifier blocked that as
# "running code from an external clone"; a human must authorize it (or add a Bash
# allow-rule) before this arm can run. The pipeline parses clean under the pin above.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH="$(dirname "$HERE")"
WORK="$BENCH/_work"
LIB="${TENZIR_LIBRARY:-/tmp/tenzir-library}"
OUT="$BENCH/results"
mkdir -p "$OUT"

run_arm() {
  local source="$1" tql="$2"
  echo "[tenzir] $source via $(basename "$tql")"
  docker run --rm \
    -v "$LIB":/library:ro \
    -v "$WORK":/work:ro \
    -v "$HERE/$tql":/q.tql:ro \
    --entrypoint tenzir tenzir/tenzir:latest \
    --package-dirs=/library -f /q.tql > "$OUT/tenzir_${source}.emitted.jsonl"
  echo "[tenzir] wrote $OUT/tenzir_${source}.emitted.jsonl ($(wc -l < "$OUT/tenzir_${source}.emitted.jsonl") events)"
}

# Only zeek_conn is faithful on the JSON corpus (shipped Zeek mapping reads JSON;
# the shipped Sysmon mapping needs raw winlog XML; no shipped CloudTrail-mgmt-events
# or generic-auth mapping exists — those score 0% coverage per the README stop rule).
run_arm zeek_conn map_zeek_conn.tql

echo "[tenzir] score it:"
echo "  ../.venv/bin/python3 $BENCH/score.py --tool tenzir \\"
echo "     --mapping-artifact 'tenzir 6.0.0 / library 671e049 zeek::ocsf::map' \\"
echo "     --emitted zeek_conn=$OUT/tenzir_zeek_conn.emitted.jsonl"
