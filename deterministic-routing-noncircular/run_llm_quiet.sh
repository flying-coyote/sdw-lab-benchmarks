#!/usr/bin/env bash
# QUIET REPLICATION 2026-11-16: LLM legs, strictly serial, after engines are stopped. Gate per leg as pre-registered.
set -u
cd "$(dirname "$0")"
L=logs/quiet-2026-11-16
unload() { for m in $(ollama ps | awk 'NR>1{print $1}'); do curl -s http://127.0.0.1:11434/api/generate -d "{\"model\":\"$m\",\"keep_alive\":0}" >/dev/null; done; sleep 3; echo "$(date -u +%FT%TZ) ollama ps: $(ollama ps | awk 'NR>1{print $1}' | tr '\n' ' ')" | tee -a $L/stamps.log; }
stamp() { local w=0
  while awk '{exit !($1>1.0)}' /proc/loadavg && [ $w -lt 300 ]; do sleep 15; w=$((w+15)); done
  echo "$(date -u +%FT%TZ) cell=$1 load=$(cut -d' ' -f1-3 /proc/loadavg) waited_s=$w gate_expired=$([ $w -ge 300 ] && echo yes || echo no) chrony_system_time=\"$(chronyc tracking | sed -n 's/^System time *: //p')\"" | tee -a $L/stamps.log; }
unload; stamp "llm:local_gemma4"; python3 -B llm_router_quiet.py --leg local --model gemma4:e4b --subset 01,02 > $L/llm_local_gemma4.log 2>&1
unload; stamp "llm:local_phi4"; python3 -B llm_router_quiet.py --leg local --model phi4:latest --subset 01 > $L/llm_local_phi4.log 2>&1
unload; stamp "llm:agy"; python3 -B llm_router_quiet.py --leg agy --subset 01 > $L/llm_agy.log 2>&1
unload; echo "$(date -u +%FT%TZ) LLM DONE" | tee -a $L/stamps.log
