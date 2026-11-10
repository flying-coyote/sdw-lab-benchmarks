---
type: evidence
title: "T2 platform telemetry: independent verification"
created: 2026-11-09
tags: [verification, ai-telemetry, opentelemetry, claude-code, ollama]
---

# T2 verification

**Verdict: VERIFIED-WITH-FIXES.** Every headline number reproduces exactly from the captured data. Four
factual slips were corrected in `RESULTS.md`, two stale lines were corrected in `README.md` and
`requirements.txt`, one hypothesis verdict was reworded after the cross-provider check, and a local session
token was redacted from the captured `env.txt` files. None of the fixes changes a field score or a
hypothesis outcome.

Verifier: a separate agent, 2026-11-09 (America/New_York evening, 2026-11-10 UTC), working only from the
files on disk. It did not re-run the live sessions. Re-running Claude Code would produce new captures rather
than reproduce these ones, and the scored quantity is field presence in the captures, so the verification
re-derives every scored value from the raw collector JSONL and journal slices instead. The scorers were
re-run on a copy under a 4-core cap (`nice -n 10 taskset -c 0-3`), with other benches running on the host.

## What was checked, and the result

| Check | Result |
| --- | --- |
| Pre-registration hash | `sha256sum PREREGISTRATION.md` = `8baf545d…a4e24c`, matching `PREREGISTRATION.sha256`, `.frozen` and the top of `RESULTS.md` |
| Pre-registration predates the run | file mtime 00:54Z, freeze 00:55:35Z, first trial file (discarded A1 t1 `env.txt`) 00:56:04Z, first kept trial 00:57:38Z |
| Scorers reproduce | `score.py A1 A2` and `score_ollama.py` re-run on a copy: `claude_scores.json` and `ollama_scores.json` **identical to the shipped files** (parsed-JSON equality) |
| A1: 8 of 12, content withheld | confirmed in 3/3 trials; raw grep of each A1 slice of `collector/out/*.jsonl` gives 0 hits for the sentinel, 0 for `fixtures/known.txt`, 0 for the prompt text, and 3 `<REDACTED>` values per trial |
| A2: 12 of 12, F6 on traces only | confirmed in 3/3 trials; the sentinel appears in the `tool.output` span event (`content`) and in the `assistant_response` log event, and in no other log event |
| H3: zero unstable attributes | confirmed within each configuration (3 trials each); every event type in every trial |
| Event, metric and span counts | 54 items per A1 trial (42 logs, 12 metric points), 60 per A2 trial (+6 spans), per-name counts exactly as stated |
| Tokens and cost | 34,420 cached / 86 output on request 1 in 6/6 trials; output on request 2 24/147/178 (A1), 148/184/24 (A2); per-session `cost_usd` 0.000763 to 0.000843 USD; A1 t1 OTel sum 0.000763 equals `stdout.json` `total_cost_usd` 0.00076293 |
| Lengths and sizes | `prompt_length` 101, `tool_input_size_bytes` 89, `tool_result_size_bytes` 138, `response_length` 24 in every trial |
| `anthropic.*` attributes | `provider=firstParty`, `custom_base_url=False`, `plan=max` on events, confirmed |
| F11 (no client IP) | `score.py` hard-codes `client_ip: False`, so the scorer cannot support this cell; an independent grep of every attribute key in the captures finds only `host.arch` and `host_owned_mcp` matching ip/addr/peer/host, which does support it |
| Ollama default level | 132/137/151 lines; 0 hits for prompt, `read_file`, path, sentinel, `gemma4:e4b`, token keywords; bench latencies match Gin lines (44.93/49.56 s, 45.14/58.83 s, 58.10 s/"1m1s") |
| Ollama debug level | 155/14/14 lines; per trial, 6 `runner.name=…gemma4:e4b` lines, cache-slot `prompt=98` and `prompt=267` equal to the client's `prompt_eval_count` on each turn, `completion request … prompt=448`/`1090`; no output count, text, path or sentinel |
| Versions | Claude Code 2.1.321 confirmed by `service.version`/`app.version` on every record and `claude --version`; collector digest confirmed with `docker image inspect`; venv Python 3.12.3, pip 26.3, no third-party packages |
| Spend | USD 0: subscription OAuth (`anthropic.plan=max`), local Ollama, no Vertex call (billing disabled; the recorded `gcloud` checks are read-only) |
| Safety scope | the only fixture is one labelled inert sentinel line; no attack content, no exploit code, no credentials in fixtures; collector published on `127.0.0.1` only (container listens on `0.0.0.0` inside its own network namespace); private Ollama on `127.0.0.1:11435` |
| Stop rule | all Claude sessions far inside 300 s; slowest Ollama trial 490 s inside the 600 s cap; run 00:55 to 01:15Z inside the 90-minute cap |

## Fixes made in place

1. **`RESULTS.md`, Arm A detail.** "The second [request] read 36,333 [cached tokens]" was true in five of six
   trials. A2 trial 3 read 34,420 and wrote 199 cache-creation tokens. Corrected.
2. **`RESULTS.md`, Headline and Arm C detail.** The foreign `/api/chat` counts were 1, 3 and **4**, not 1, 3 and
   5. Trial 3's window, padded 2 s before the harness start, caught trial 2's own final request (58.83 s,
   ending 01:01:49Z, while trial 3 started at 01:01:49.30Z) and counted it as another client's. The point the
   paragraph makes (an unattributed shared stream) is unchanged. Corrected in both places.
3. **`RESULTS.md`, Arm C detail.** The `/api/show` from `::1` appears in trial 1's window only, not in every
   window, and each window also holds four unlevelled `load_backend:` lines, so "all `level=INFO` or Gin
   lines" was loose. Corrected.
4. **`RESULTS.md`, H6.** Reworded from "survives on a technicality" to "not falsified; the second clause is
   weakly supported", after the cross-provider disagreement below.
5. **`RESULTS.md`, rig stamp and versions.** Noted that only the 0.606 s chrony reading is logged (the 0.58 s
   lower bound is not), and added the Ollama weights blob digest, which the pre-registration asked to record
   and `RESULTS.md` had left out.
6. **`README.md`** said the raw captures still contain the account email; deviation 5 had already scrubbed
   them. **`requirements.txt`** said pip 25.x; the venv has 26.3. Both corrected.
7. **`results/*/env.txt` (7 files, including the discarded trial).** Each held the parent Claude Code
   session's `CLAUDE_CODE_MESSAGING_TOKEN` (a live local-socket token) plus the messaging socket path and two
   session ids, inherited from the environment. This folder is bound for the public lab repo, so the four
   values were replaced with `<redacted-by-verifier>`. Residual grep is clean. No scored file was touched.

## Deviations the original run did not record

- The pre-registration says the collector config was validated with the image's `validate` sub-command
  before the run; `COMMANDS.log` has no such entry. The verifier ran it (`rc=0`) and logged it as a verifier
  command, so the config is valid, but the original run's claim is unevidenced.
- The pre-registration lists "wall time of the session under a monotonic timer" per trial. The Claude Code
  harness (`run_claude_session.sh`) uses `date +%s.%N`, the realtime clock, despite a comment saying
  otherwise (`timing.json` says "realtime clock"). Durations are context only, so nothing scored changes.
- Deviation 3 mentions unsetting `CLAUDECODE`, but the child `claude -p` also inherited
  `CLAUDE_CODE_CHILD_SESSION=1`, `CLAUDE_CODE_BRIDGE_SESSION_ID` and the parent's messaging socket, so it ran
  as a child of the parent session, not as a standalone install. The three session events of interest look
  unaffected, but the run did not test a clean, standalone launch.
- `env.txt` shows `CLAUDE_CODE_EXECPATH=…/versions/2.1.319`. That is the parent's inherited path; the binary
  that ran was `~/.local/bin/claude` at 2.1.321, which `service.version` on every captured record confirms.

## Cross-provider check (Gemini)

The five most important claims, each with a sanitized excerpt of the supporting data (no email, username,
token or project ids), went to `gemini-3.8-flash` through `~/project1/automation/agy-tracked.sh`
(17,257 tokens, 43 s). Prompt: `verification/gemini-prompt.txt`; reply: `verification/gemini-response.md`.

| Claim | Gemini | Resolution against the data |
| --- | --- | --- |
| 1. A1 delivers 8 of 12; content as lengths or `<REDACTED>` | agree | stands |
| 2. A2 delivers 12 of 12; F6 on traces only | agree | stands |
| 3. Ollama default log carries none of the eight fields; shared unattributed stream | agree | stands (the excerpt already carried the corrected foreign count) |
| 4. Debug adds model-per-request and input tokens; H4 debug clause falsified | agree | stands |
| 5. H6 "survives on a technicality" | **overstated** | Gemini is right on the data. The falsifier requires identity, prompt text, tokens and cost together *by default*; no column meets the "by default" condition, and Bedrock would fail it on cost even when enabled. So H6 is plainly not falsified, and the weak part is the ChatGPT Enterprise clause, which rests on tokens and cost being *not stated* rather than documented absent. `RESULTS.md` reworded (fix 4). |

## Claims against evidence

The headline claims stay inside the evidence: one host, one account, one day, one version of each product,
which `RESULTS.md` says. Two framing points are worth a reader's attention, though neither needed a fix. First,
"8 of 12" counts F11 as present on host attributes (`os.type`, `host.arch`, `wsl.version`), which the
pre-registration allows ("client IP or host attributes"), and the table says plainly that there is no client
IP, so a reader skimming the headline alone may over-read it. Second, the documented columns are vendor
descriptions (Tier B for what a feature emits), and the ChatGPT Enterprise column rests on an announcement
and search snippets, which `RESULTS.md` labels as the weakest-sourced. The reading of the debug
`completion request … prompt=448` as a length *in characters* is an inference (it could be bytes); it is not
scored and does not affect H4.

## Open for the owner (not fixed here)

These are personal identifiers that the brief did not ask to publish. They are not secrets, so the verifier
left them for a ruling:

- The five gcloud project ids in `PREREGISTRATION.md` (frozen: editing breaks the hash, so the only options
  are to accept them or to publish a redacted copy alongside the hashed original), `RESULTS.md` and
  `docs-evidence/DOCUMENTED-COLUMNS.md`.
- The `/home/<user>` path in `results/*/env.txt` (`CLAUDE_CODE_EXECPATH`) and in
  `results/ollama-debug-server.log` / `results/ollama-debug-t1/server_log_slice.txt` (`PATH=`).
- The host name (`mine`) on every line of `results/ollama-default-t*/journal.txt`.
- The child Claude Code `session_id` values in `results/claude-*/stdout.json`.

No git commands were run.
