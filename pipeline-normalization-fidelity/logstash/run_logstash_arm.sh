#!/usr/bin/env bash
# Logstash two-edition arm of pipeline-normalization-fidelity (#10) — H-PIPELINE-OCSF-FIDELITY-01.
# Pre-registered (gemini-20260616-pipeline-tier-dewitt-reconciliation.md §3): bench BOTH editions —
# the OSS/Apache build vs the Elastic-distribution binary — and let the measured delta decide whether
# "Logstash" is one tool or two. Result (2026-06-16): identical (both ship NO native OCSF mapping), so
# ONE "Logstash", and the DeWitt distinction is moot (a 0%-availability finding is a capability statement,
# not a publishable performance result -> both editions nameable). Tier B, single host, synthetic corpus.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OSS_IMG="docker.elastic.co/logstash/logstash-oss:7.10.2"      # last Apache-2.0 OSS Logstash
ELASTIC_IMG="docker.elastic.co/logstash/logstash:8.17.0"      # Elastic distribution (Elastic License 2.0)

echo "== STEP 1: shipped-plugin availability (the P1 question — does it ship an OCSF codec/filter?) =="
for img in "$OSS_IMG" "$ELASTIC_IMG"; do
  echo "-- $img --"
  docker run --rm --entrypoint /usr/share/logstash/bin/logstash-plugin "$img" list 2>/dev/null \
    | grep -iE "ocsf|cef" || echo "  (no ocsf/cef)"
done
# FINDING: both ship logstash-codec-cef (CEF) but NO ocsf codec or filter -> no native OCSF normalization.

echo "== STEP 2: passthrough run (the only available path; no OCSF codec to invoke) + score =="
PASS='input { stdin { codec => json_lines } } output { stdout { codec => json_lines } }'
for ed in oss elastic; do
  img=$([ "$ed" = oss ] && echo "$OSS_IMG" || echo "$ELASTIC_IMG")
  head -200 "$HERE/_work/zeek_conn.corpus.jsonl" \
    | docker run --rm -i "$img" logstash -e "$PASS" --log.level=error 2>/dev/null \
    | grep -E '^\{' > "$HERE/logstash/results/${ed}_emitted_zeek_conn.jsonl" || true
  echo "  logstash_$ed emitted $(grep -c . "$HERE/logstash/results/${ed}_emitted_zeek_conn.jsonl") records; OCSF fields: $(grep -oE 'class_uid|activity_id|type_uid' "$HERE/logstash/results/${ed}_emitted_zeek_conn.jsonl" | sort -u | tr '\n' ' ' || echo NONE)"
  # score all four sources with the shared instrument (no OCSF emitted -> 0%, like the Vector arm)
  python3 "$HERE/score.py" --tool "logstash_$ed" \
    --source zeek_conn --source cloudtrail --source sysmon --source auth \
    --emitted "zeek_conn=$HERE/logstash/results/${ed}_emitted_zeek_conn.jsonl"
done
# RESULT: both editions 0% cov/field/value/class/activity_id on all 4 sources, identical.
