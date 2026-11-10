# T2 — Platform telemetry fidelity

One scripted agent session (a prompt, one file-read tool call, one model response) run against the AI
platforms that can be measured on this host, scored on which fields a security team would want actually
arrive in the platform's own telemetry, and compared with what four more platforms document they emit.

- `PREREGISTRATION.md` — question, twelve fields, arms, hypotheses with falsifiers, stop rule, cost cap.
  Frozen before the run (`PREREGISTRATION.sha256`, `.frozen`), not owner-reviewed.
- `RESULTS.md` — the field × platform table (measured / documented / absent), per-trial evidence, deviations.
- `docs-evidence/DOCUMENTED-COLUMNS.md` — the vendor documentation behind every *documented* cell, with URLs
  and the sentences relied on.
- `COMMANDS.log` — every command, UTC.

## Arms

| arm | what | state |
| --- | --- | --- |
| A | Claude Code 2.1.321 OpenTelemetry export into a local `otel/opentelemetry-collector-contrib:0.145.0` (A1 documented defaults, A2 every content gate on), 3 trials each | measured |
| B | Google Vertex AI (Cloud Audit Logs, request-response logging) | not run: billing disabled on every project the account can list; documented only |
| C | Ollama 0.20.6 server log at default level (system service) and at `OLLAMA_DEBUG=1` (private instance on 127.0.0.1:11435), 3 trials each | measured |
| D | AWS Bedrock invocation logging, Azure OpenAI in Foundry diagnostics, GitHub Copilot audit log, ChatGPT Enterprise Compliance API | documented only, no credentials |

## Reproduce

```bash
python3 -m venv .venv            # harness is stdlib-only; see requirements.txt
chmod 777 collector/out          # the collector image runs unprivileged
docker run -d --name t2-otelcol --cpus=1 -p 127.0.0.1:4317:4317 -p 127.0.0.1:4318:4318 \
  -v "$PWD/collector/otel-config.yaml:/etc/otelcol-contrib/config.yaml:ro" -v "$PWD/collector/out:/out" \
  otel/opentelemetry-collector-contrib:0.145.0 --config=/etc/otelcol-contrib/config.yaml
for t in 1 2 3; do ./run_claude_session.sh A1 $t; done
for t in 1 2 3; do ./run_claude_session.sh A2 $t; done
python3 -I score.py
./.venv/bin/python -I run_ollama_session.py --host http://127.0.0.1:11434 --model gemma4:e4b --out results/ollama-default-t1
./journal_slice.sh results/ollama-default-t1
python3 -I score_ollama.py
```

The fixture `fixtures/known.txt` is inert: one labelled sentinel line, no secrets, no exploit content. The
collector binds to localhost only. Raw captures under `results/` and `collector/out/` had the account's `user.email` and account identifiers
replaced with placeholders after scoring (`scrub_identifiers.py`), and the local session token and session ids
in `results/*/env.txt` were redacted at verification; `RESULTS.md` reports the fields' presence.
