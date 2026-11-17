# T2: Platform telemetry fidelity (t2-platform-telemetry)

## What it measures

One scripted agent session (a prompt, one file-read tool call, one model response) run against the AI
platforms that can be measured on this host, scored on which fields a security team would want actually
arrive in the platform's own telemetry, and compared with what four more platforms document they emit.

| arm | what | state |
| --- | --- | --- |
| A | Claude Code 2.1.321 OpenTelemetry export into a local `otel/opentelemetry-collector-contrib:0.145.0` (A1 documented defaults, A2 every content gate on), 3 trials each | measured |
| B | Google Vertex AI (Cloud Audit Logs, request-response logging) | not run: billing disabled on every project the account can list; documented only |
| C | Ollama 0.20.6 server log at default level (system service) and at `OLLAMA_DEBUG=1` (private instance on 127.0.0.1:11435), 3 trials each | measured |
| D | AWS Bedrock invocation logging, Azure OpenAI in Foundry diagnostics, GitHub Copilot audit log, ChatGPT Enterprise Compliance API | documented only, no credentials |

## Result

Claude Code's export at its documented defaults delivered 8 of the 12 fields and withheld the four content fields,
all 12 arrived with every content gate on (the tool output only on the beta traces path), and Ollama's default
server log carried none of the eight content, identity, per-request model or token fields, which came back only in
the client's response body (`RESULTS.md`, Headline). These are measured presence counts on real software, since any
field could have been absent or present; the cells for Vertex AI and the four arm-D platforms come from vendor
documentation and are labelled as documented, not measured.

## What would have made it fail

Each hypothesis in `PREREGISTRATION.md` carries a falsifier, and the known session (fixed prompt, fixed file, fixed
sentinel line) gives a ground truth that every captured value is checked against. There is no planted positive that
a rule was written to find.

## Pre-registration

`PREREGISTRATION.md`, frozen by agent before the run and not owner-reviewed. Its sha256 in `PREREGISTRATION.sha256`
(`8baf545d…4e24c`) still matches, and `.frozen` records 2026-11-10T00:55:35Z; the earliest telemetry timestamp in
`results/claude-A1-t1/` is 2026-11-10T00:57:40Z, after the freeze. Deviations are listed in `RESULTS.md`.

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

The fixture `fixtures/known.txt` is inert (one labelled sentinel line, no secrets, no exploit content), but it and
`COMMANDS.log` are not committed, so a re-run has to recreate the sentinel file from the description in
`PREREGISTRATION.md`. The collector binds to localhost only. Raw captures under `results/` and `collector/out/` had the
account's `user.email` and account identifiers replaced with placeholders after scoring (`scrub_identifiers.py`), and
the local session token and session ids in `results/*/env.txt` were redacted at verification; `RESULTS.md` reports
the fields' presence.

## Results

- `RESULTS.md` is the entry point: the field by platform table (measured, documented, absent), per-trial evidence,
  hypotheses, deviations and limits.
- `docs-evidence/DOCUMENTED-COLUMNS.md` holds the vendor documentation behind every documented cell, with URLs and
  the sentences relied on.
- `results/claude_scores.json` and `results/ollama_scores.json` are the scorer outputs;
  `results/_discarded-claude-A1-t1-collector-perm-error/` is a discarded trial kept for the record.
- `VERIFICATION.md` and `verification/` hold the independent check and its cross-provider prompt and response.

## Versions and pins

`requirements.txt` pins nothing because the harness is standard library only (Python 3.12.3 in the venv). The
collector image is pinned by tag (`otel/opentelemetry-collector-contrib:0.145.0`), not by digest. Claude Code
2.1.321 and Ollama 0.20.6 are named in `RESULTS.md`.

## Evidence tier and limits

`RESULTS.md` gives no single tier letter for the measured arms; it treats vendor documentation as Tier B for what a
product does. One host, three trials per configuration, one version of each product, and two of the six documented
platforms checked only against their own documentation. See Limits in `RESULTS.md`.

## Corrections

- 2026-11-17: four passages of `RESULTS.md` that narrated the run in the first person were recast in neutral voice
  with no change of substance; this README was restructured to the lab layout and now says that `fixtures/known.txt`
  and `COMMANDS.log` are not committed.
