# t8a-mcp-before-after (T8a)

## What it measures

What one MCP exchange leaves behind, on the wire, at the client, at the server and at a proxy, before and after the
2026-07-28 protocol revision, over stdio and Streamable HTTP. One fixture server on two releases of the MCP Python SDK
(1.30.0 and 2.3.0) is driven by five client and server pairings, so that the revision's effect (arm B against arm C,
same SDK 2.3.0) can be separated from the SDK's effect (arm A against arm B, same revision 2025-11-25):

| Arm | Client | Server | Negotiated |
|---|---|---|---|
| A | `mcp` 1.30.0 `ClientSession` | `mcp` 1.30.0 `FastMCP` | 2025-11-25 |
| B | `mcp` 2.3.0 `Client(mode="legacy")` | `mcp` 2.3.0 `MCPServer` | 2025-11-25 |
| C | `mcp` 2.3.0 `Client(mode="auto")` (the default) | `mcp` 2.3.0 `MCPServer` | 2026-07-28 |
| C-log | `mcp` 2.3.0 `Client(mode="auto", log_level="info")` | `mcp` 2.3.0 `MCPServer` | 2026-07-28 |
| D | `mcp` 2.3.0 `Client(mode="auto")` | `mcp` 1.30.0 `FastMCP` | 2025-11-25 after fallback |

## Result

The session id, the handshake, the per-request self-description, the routing headers, the cache hints and the
default silence of in-protocol logging moved with the revision, while the OpenTelemetry spans, the trace context, the
masking of a raising tool's error cause, the loss of the per-request stderr line and the missing-resource error code
moved with the SDK; a team that upgrades the SDK but pins the old revision gets the second list and not the first
(`RESULTS.md`, Headline table). These are measured presence facts and counts from real wire captures, none of which
follows from how the fixture was built, and the presence record was identical across repeats in every cell
(`results/stability.md`, 15 of 15 cells).

## What would have made it fail

Each hypothesis in `PREREGISTRATION.md` names its falsifier, and the arm design gives every fact a same-SDK or
same-revision comparison. The pre-registration also recorded an uncertainty (whether 2.3.0 in legacy mode would send
`Mcp-Name`), which the run resolved toward the revision.

## Pre-registration

`PREREGISTRATION.md`, frozen by agent before the run and not owner-reviewed. Its sha256 in `PREREGISTRATION.sha256`
(`010317ad…c043a`) still matches, and the same file records `frozen_utc 2026-11-10T00:55:38Z`; the first formal
capture file is 01:01:37Z (`RESULTS.md`, Deviation 8). Eight deviations are listed in `RESULTS.md`; two were found at
verification, namely three harness files edited after the formal runs (the verifier's re-run on the current files
reproduced every presence fact) and backfilled venv timestamps in `COMMANDS.log`.

## Reproduce

```bash
python3 -m venv venv-v1 && venv-v1/bin/pip install -r requirements-v1.txt
python3 -m venv venv-v2 && venv-v2/bin/pip install -r requirements-v2.txt
bash run_all.sh                      # 5 arms x 2 transports x 3 reps, then the single-run checks
./venv-v2/bin/python analyze.py      # writes results/facts.json, matrix.md, stability.md, timing.md
```

`run_all.sh` changes into the original scratch directory the run used, so its `cd` line has to be pointed at this
folder first. The per-cell captures under `runs/` (2.5 MB, 154 JSONL files) and `COMMANDS.log` are not committed, so
`analyze.py` cannot be re-run from this tree; the committed outputs are in `results/`. The sub-arm (`-instr` cell)
needs the extra packages in `requirements-v2-subarm.txt`.

Files: fixtures `server_v1.py`, `server_v2.py`, `client_v1.py`, `client_v2.py`, `t8a_common.py`, `backend.py`;
capture `proxy_stdio.py` (stdio tee with stderr redirect), `proxy_tcp.py` (raw TCP tee), `parse_http.py` (h11);
harness `run_cell.py`, `run_all.sh`; analysis `analyze.py`.

## Results

- `RESULTS.md` is the entry point: arms, hypothesis verdicts, where each fact is reachable per revision, counts per
  cell, deviations, limits.
- `results/facts.json`, `results/matrix.md`, `results/stability.md` and `results/timing.md` are the analysis
  outputs; the timing table exists only because the pre-registration asked for it, and no latency claim is made.
- `VERIFICATION.md` is the independent full re-run (VERIFIED-WITH-FIXES). Under `verification/`, `backup/` holds
  superseded pre-verification copies (`RESULTS.md.pre-verify`, `analyze.py.pre-verify`, `results.pre-verify`),
  `orig-analysis/` the original analysis output, and `rerun/` with `indep-*.jsonl` and `indep_check.py` the
  verifier's own re-run; none of them is the current result.

## Versions and pins

`requirements-v1.txt` (SDK 1.30.0), `requirements-v2.txt` (SDK 2.3.0, the formal-run freeze) and
`requirements-v2-subarm.txt` (after the sub-arm install) pin every line with `==`. Python 3.12.3, `opentelemetry-sdk`
1.45.2, `starlette` 1.10.0 and `uvicorn` 0.54.0 are named in the `RESULTS.md` rig stamp.

## Evidence tier and limits

Tier B for method (`RESULTS.md`), with statements about what the SDK does taken from the pinned SDK source and cited
`file:line`. One fixture server on each SDK's high-level API, one client per arm, OTel limited to the SDK's built-in
middleware, `Mcp-Name` tested with a header-safe name only, and timings under contention behind a clock 0.6 s off.
See Limits in `RESULTS.md`.

## Corrections

- 2026-11-09: verifier corrections are marked in `RESULTS.md`.
- 2026-11-16: two limits in `RESULTS.md` carry dated corrections (the R5 protocol column and the SEP-986 name rule).
- 2026-11-17: one first-person phrase in `RESULTS.md` (Deviation 1) was recast in neutral voice; this README was added.
