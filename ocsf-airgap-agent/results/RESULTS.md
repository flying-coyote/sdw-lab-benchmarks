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

## What phoned home

- Endpoints contacted: **http://localhost:11434 (Ollama — on-host, loopback only)**.
- External egress: **none — model weights local (Ollama), OCSF store local Parquet, Sigma ruleset a local clone; no component reaches the internet**.
- the DuckDB tool is in-process here; an stdio MCP server exposes the identical tool over stdio (no socket), which is offline by construction — the air-gap property is the transport, demonstrated by the loopback-only ledger.

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
