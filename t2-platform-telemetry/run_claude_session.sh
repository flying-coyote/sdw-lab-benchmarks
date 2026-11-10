#!/usr/bin/env bash
# T2 arm A: one scripted Claude Code session with OpenTelemetry export to the local collector.
# Usage: run_claude_session.sh <config A1|A2> <trial N>
# Writes results/claude-<config>-t<N>/{stdout.json,stderr.txt,timing.json} and leaves the collector's
# JSONL files to be split per trial by the caller (the collector appends; we snapshot line offsets).
set -u
CFG="$1"; TRIAL="$2"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/results/claude-${CFG}-t${TRIAL}"; mkdir -p "$OUT"
PROMPT='Read the file fixtures/known.txt and reply with exactly the sentinel token it contains, nothing else.'

# Documented defaults (A1). Export intervals shortened so a short -p session flushes before exit.
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317
export OTEL_METRIC_EXPORT_INTERVAL=1000
export OTEL_LOGS_EXPORT_INTERVAL=1000
if [ "$CFG" = "A2" ]; then
  export OTEL_LOG_USER_PROMPTS=1
  export OTEL_LOG_ASSISTANT_RESPONSES=1
  export OTEL_LOG_TOOL_DETAILS=1
  export OTEL_LOG_TOOL_CONTENT=1
  export OTEL_METRICS_INCLUDE_VERSION=true
  export CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1
  export OTEL_TRACES_EXPORTER=otlp
  export OTEL_TRACES_EXPORT_INTERVAL=1000
fi
env | grep -E '^(OTEL_|CLAUDE_CODE_)' | sort > "$OUT/env.txt"

# Record collector file offsets so the trial's events can be sliced out afterwards.
for s in logs metrics traces; do
  f="$HERE/collector/out/$s.jsonl"; [ -f "$f" ] && wc -l < "$f" || echo 0
done > "$OUT/offsets_before.txt"

cd "$HERE"
t0=$(date +%s.%N)   # realtime only for the log; monotonic measured inside python below
# Not nested inside the parent Claude Code session: unset its marker vars.
env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
  nice -n 10 taskset -c 0-3 timeout 300 \
  claude -p "$PROMPT" --model haiku --allowedTools Read --output-format json \
  > "$OUT/stdout.json" 2> "$OUT/stderr.txt"
rc=$?
t1=$(date +%s.%N)
# Give the exporters a moment past the last export interval, then snapshot offsets.
sleep 4
for s in logs metrics traces; do
  f="$HERE/collector/out/$s.jsonl"; [ -f "$f" ] && wc -l < "$f" || echo 0
done > "$OUT/offsets_after.txt"
python3 - "$t0" "$t1" "$rc" > "$OUT/timing.json" <<'EOF'
import sys, json
t0, t1, rc = float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
print(json.dumps({"wall_s_realtime": round(t1 - t0, 3), "exit_code": rc,
                  "note": "realtime clock; see chrony offset in COMMANDS.log"}))
EOF
echo "trial $CFG t$TRIAL rc=$rc wall=$(python3 -c "print(round($t1-$t0,1))")s"
