# Air-gapped local-model agentic hunt — buildability + egress ledger

*Every component on-box and offline: model weights via Ollama (local), a ~80-line code-action agent loop (the model emits read-only SQL, we run it over a local DuckDB OCSF store, feed back rows, it iterates), and offline content (the APT29 OCSF telemetry + 3,132 mirrored SigmaHQ rules on disk). H-PRACTITIONER-OWNED-AGENTIC-01.*

*Tier B for buildability / air-gap mechanics; Tier D for hard-SOC-reasoning capability. One hunt, one host. Read the result column as an on-box capability gradient, not parity with a hosted frontier agent.*

**Hunt task:** find the first suspicious executable run on the host (the initial dropper) and the user account it ran under. **Ground truth:** dropper `"C:\ProgramData\victim\‮cod.3aka3.scr" /S` run as `DMEVALS\pbeesly`.

| local model | steps | generation time | dropper | user | result |
|---|---:|---:|:---:|:---:|:---:|
| gemma3:e4b | 5 | 172.0s | ✓ | ✓ | ✅ |
| phi4:latest | 6 | 198.1s | ✗ | ✗ | ❌ |

*✅ = both the dropper CommandLine and the User correct · ❌ = wrong.*

## Egress ledger

| property | observed |
|---|:---|
| endpoints contacted | `http://localhost:11434` (Ollama — on-host, loopback only) |
| external egress | none — weights local (Ollama), OCSF store local Parquet, Sigma ruleset a local clone |
| transport | DuckDB tool in-process; an stdio MCP server exposes the identical tool over stdio (no socket), offline by construction |

**Security-relevant cell: external egress = none (loopback only).** The buildability and air-gap mechanics are demonstrated, not asserted — the whole loop (weights, agent, tools, content) runs with nothing leaving the host, and the only socket is the loopback to the local model server, which an stdio MCP server removes entirely. That leg of H-PRACTITIONER-OWNED-AGENTIC-01 is solidly Tier B. The capability column is the honest other half and the hypothesis's open question: a small local model is the floor of what runs air-gapped, and whether it can do useful multi-step hunt reasoning — `gemma3:e4b` got both fields right in 5 steps where `phi4` missed both in 6 — is where the lag behind frontier SaaS shows up, and stays Tier D on one hunt. The transferable finding is that the stack assembles and stays offline, with a measured capability floor.
