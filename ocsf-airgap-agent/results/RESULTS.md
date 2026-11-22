---
type: evidence
title: "Air-Gapped Agentic Hunt — Local Model + Code-Action Loop + Offline OCSF Store (Adj.15)"
created: 2026-06-06
tags: [agentic-hunt, air-gap, ollama, ocsf, local-model, tier-b]
---

# Air-gapped agentic hunt — local model + code-action loop + offline OCSF store (Adj.15)

**Tier B for buildability/air-gap mechanics; Tier D for hard-SOC-reasoning capability.** Every component is
on-box and offline: model weights via **Ollama** (local), a ~80-line **code-action** agent loop (the model
emits read-only SQL, we run it over a local DuckDB OCSF store, feed back rows, it iterates), and **offline
content** (the APT29 OCSF telemetry + 3,132
mirrored SigmaHQ rules on disk). H-PRACTITIONER-OWNED-AGENTIC-01.

**Hunt task:** Find the FIRST suspicious executable that was run on the host (the initial dropper) and the user account it ran under. Suspicious executables often live in unusual paths like C:\ProgramData and may have odd names. Report the executable's CommandLine and the User.
**Ground truth:** dropper `"C:\ProgramData\victim\â€®cod.3aka3.scr" /S` run as `DMEVALS\pbeesly`.

| local model | steps | generation time | result |
|---|--:|--:|---|
| gemma4:e4b | 5 | 172.0s | dropper=✓ user=✓ ✅ |
| phi4:latest | 6 | 198.1s | dropper=✗ user=✗ ❌ |

*(corrected 2026-11-16: the phi4 row records a loud failure rather than a wrong answer, because all six steps were queries with no `FROM` clause or an unbound table alias, each returned a DuckDB binder error, the six steps are the `MAX_STEPS = 6` cap in `run.py`, and `final_answer` is `null` in `results.json`. Separately, "OCSF store" in this file's title and text is the bench's label for the corpus and doesn't describe its schema, since `run.py` reads the raw APT29 Parquet under `ocsf-context-collapse-apt29/_work/raw`, whose columns are Sigma field names (`Image`, `CommandLine`, `ParentImage`, `User`, `Hostname`), not OCSF attributes.)*

## What phoned home

- Endpoints contacted: **http://localhost:11434 (Ollama — on-host, loopback only)**.
- External egress: **none — model weights local (Ollama), OCSF store local Parquet, Sigma ruleset a local clone; no component reaches the internet**.
- the DuckDB tool is in-process here; an stdio MCP server exposes the identical tool over stdio (no socket), which is offline by construction — the air-gap property is the transport, demonstrated by the loopback-only ledger.

*(corrected 2026-11-17: this ledger is a fixed statement that `run.py:161-168` writes on every run, not a record of observed traffic, so it could not have shown egress. `run.py` itself makes one network call, to the local Ollama endpoint at `run.py:36`, and the corpus and rules are local paths, but the Ollama daemon's own traffic was not constrained or observed and the model pull needs the network once (scope added 2026-11-22), so offline operation was not measured, and "demonstrated, not asserted" in the Reading below overstates it. A no-route network namespace or a packet capture during the run would be the measurement. Because `run.py` regenerates this file, the bench README carries the same correction.)*

## Reading

The buildability and air-gap mechanics are demonstrated, not asserted: the whole loop — weights, agent,
tools, content — runs with nothing leaving the host, and the only socket is the loopback to the local model
server (an stdio MCP server removes even that). That is the leg of H-PRACTITIONER-OWNED-AGENTIC-01 that is
solidly Tier B. The capability column is the honest other half and the hypothesis's open question: a small
local model is the floor of what runs air-gapped, and whether it can do *useful* multi-step hunt reasoning
— not just one lucky query — is where the lag behind frontier SaaS shows up. Read the result table as the
on-box capability gradient, not as parity with a hosted frontier agent. Tier B mechanics, Tier D capability;
one hunt, one host; the transferable finding is that the stack assembles and stays offline, with a measured
capability floor.
