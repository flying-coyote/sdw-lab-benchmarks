---
type: benchmark-verification
title: "T8a verification: MCP logging before and after 2026-07-28"
created: 2026-11-09
area: T8a-mcp-before-after
verdict: VERIFIED-WITH-FIXES
---

# T8a verification

**Verdict: VERIFIED-WITH-FIXES.** A full rerun of all 15 cells (10 formal cells × 3 reps, the two no-provider checks
and the three backend cells) reproduced every presence fact and count in RESULTS.md, the analysis script reproduces
the original `results/` byte for byte from the original captures, and an independent recount from raw captures (not
using `analyze.py`) agrees on every headline number except one undercount. Two factual errors (an unsourced clock
reading and a session-header response count), one hypothesis verdict that did not follow its own falsifier (H5), one
missed sub-prediction (H4), one D-arm count convention and two unlogged deviations were corrected or logged in
RESULTS.md. No conclusion about which facts are revision facts and which are SDK facts changes.

Verifier: independent agent, 2026-11-09 local (2026-11-10 UTC), same host (Beelink, Ryzen 7 5800H, WSL2
6.6.87.2), the area's own `venv-v1` (mcp 1.30.0) and `venv-v2` (mcp 2.3.0, with the post-run sub-arm packages), Python
3.12.3, every process under `taskset -c 0-3 nice -n 10`. No git commands. Spend: $0 local; the only model call was the
cross-provider leg (one `gemini-3.8-flash` call via `automation/agy-tracked.sh`, id `t8a-verify`, 15,252 tokens,
within the brief).

## 1. Pre-registration timing and hash

- `sha256sum PREREGISTRATION.md` = `010317ad3d18f7b291cbdba24716a6c4214b1f023e8175a94f8475356ecc043a`, matching
  `PREREGISTRATION.sha256` and the RESULTS.md header.
- mtimes (local −0500): PREREGISTRATION.md 19:55:29 (00:55:29Z), sha file 19:55 (freeze stamped 00:55:38Z), smoke runs
  logged 00:58Z, first surviving capture `runs/A-stdio/rep1/client.otel.jsonl` 20:01:37 (01:01:37Z). The
  pre-registration predates every capture. mtimes are agent-controllable, so this is consistent evidence, not proof.
- Two timestamp problems, now logged as RESULTS deviations 7 and 8: `server_v2.py`, `t8a_common.py` and `run_cell.py`
  were edited at 01:04Z, after the formal runs (end 01:03:34Z), to add the env-gated `--instrument` path, so the formal
  cells ran an unkept earlier version; and `COMMANDS.log` stamps venv creation at the freeze time while the venv
  directories date from 00:47Z. Package installation is not a run, and the rerun on the edited files reproduced every
  presence fact, so neither affects a result.

## 2. Analysis matches the pre-registration

The scored metrics (presence matrix, B→C and A→B diffs, per-cell counts, incidental timings with CV) are the four the
pre-registration names. The arms, transports, call script, capture points and 3 repeats match. Pre-registered
deviations from the plan are all logged: smoke runs, post-run sub-arm install, the unregistered `A-stdio-backend`
reference cell, the analysis tag bug. Hypothesis verdicts checked clause by clause against the falsifiers:

| H | Written verdict | Check |
|---|---|---|
| H1, H2, H3, H6, H7, H10, H11, H12 | supported | follow the falsifiers; data agree |
| H4 | supported | falsifier clause holds, but the predicted A tool-failure line and the shared `Tool %r failed` line did not appear; sub-prediction miss now named in RESULTS |
| H5 | "supported, one nuance" | **did not follow its own falsifier**: "wrong if B differs from C on span count" is triggered (12 vs 11). Reworded to "falsified on the letter of one clause, supported in substance" |
| H8 | wrong in both details, right on outcome | correct |
| H9 | half wrong | correct (A returns code `0`, not `-32002`; C keeps `-32602`) |

## 3. Reproduction

| step | command | outcome |
|---|---|---|
| analysis on original captures | `venv-v2/bin/python analyze.py ../../runs` in `verification/orig-analysis/` | `facts.json`, `matrix.md`, `stability.md`, `timing.md` byte-identical to `results/` |
| full rerun | `verification/rerun/run_all.sh` (copy of the harness with its `cd` pointed at the copy), then the three `--backend` cells | 35 runs (30 formal, 2 no-provider, 3 backend), all `client_rc` 0, no errors; load 16.3 at start, 13.9 at end; chrony 1 µs slow at start |
| analysis on rerun | `analyze.py` in `verification/rerun/` | `stability.md` identical (15/15 cells identical across reps); `facts.json` and `matrix.md` differ only in durations, `wall_ns` and the random trace id in `backend_traceparent` (its trace id again equals the server span's) |
| independent recount | `verification/indep_check.py` on both `runs/` trees (`indep-orig.jsonl`, `indep-rerun.jsonl`) | agrees with RESULTS on request/result counts, `initialize`/`server/discover`, `_meta` stamps (0→11/11, 0→10/10), `Mcp-Method` 11/11, `Mcp-Name` 8 with 0 mismatches, TCP connections 14→1, error codes (A `0`, B/C `-32602`, D `-32602`/`-32600` probe then `0`), HTTP 400 only in C/C-log/D, `notifications/message` 2/2/0/2/2, per-request stderr 10/0/0, deprecation lines 0/4/4, spans 0/12/11 server and 0/11/11 client, 11 shared trace ids, no-provider 0 `traceparent` and 0 spans, D-stdio 105 stderr lines, failure text in A vs B/C |
| source citations | `sed -n` on the pinned site-packages | `lowlevel/server.py:733` (per-request log) and `:794` (`ErrorData(code=0, …)`), `fastmcp/server.py:404`, `client/session.py:566-571, 657, 675, 722`, `mcp_types/version.py:33-44`, `client/client.py:336-341`, `shared/inbound.py:149-159`, `mcpserver/context.py:281,381` all say what RESULTS says they say |
| versions | `pip freeze` diff | `venv-v1` = `requirements-v1.txt`; `venv-v2` = `requirements-v2-subarm.txt`, which is `requirements-v2.txt` plus the five sub-arm packages, as RESULTS states |

Timings: rerun durations ran roughly 1× to 3× the originals for the same cells (for example A-http `tools/call echo`
4.8 to 14.1 ms originally, 15.1 to 17.9 ms in the rerun), under similar host load, while every presence fact was
identical. That supports RESULTS' decision to make no timing claim; the "1.9 to 14.9 ms medians" sentence is a record
of the original run only and does not reproduce as a number.

## 4. Fixes applied (originals kept at `verification/backup/`)

1. **Clock reading (factual).** RESULTS said chrony read 0.59 s slow before the runs. `COMMANDS.log` line 7 records
   0.000055 s fast at the start of the formal runs; the only slow reading (0.63 s) is at final analysis. Rig stamp and
   deviation 6 corrected.
2. **Session-header response count (factual).** RESULTS said `Mcp-Session-Id` on 13 responses in A and B; the raw
   captures show it on all 14 (12 POST, the GET and the DELETE response). `analyze.py` counted only responses
   carrying a JSON-RPC message; its matrix row label now says so (`results/matrix.md` regenerated, only that label
   changed), and the headline row and H2 say 14.
3. **H5 verdict** reworded to follow its pre-registered falsifier (above). The headline OTel row now says 11 client +
   12 server spans for B (11 request spans plus the unparented `notifications/initialized` span) instead of "11+11".
4. **H4** gains the missed sub-prediction.
5. **D arm `traceparent`**: the raw count is 12/12 requests (the probe and `initialize` included); RESULTS said
   11/11, which is the matrix's non-`initialize` convention. Now stated both ways.
6. **Counts table** caption says stderr counts are non-blank lines (B/C files have 2 blank lines each, so `wc -l`
   gives 47/59/57 against the table's 45/57/55).
7. **Deviation 2** wording: the pre-registration is silent on DuckDB rather than having "dropped it".
8. **Deviations 7 and 8** added (post-run harness edit; backfilled venv timestamps).
9. RESULTS header now points at this file instead of "Independent verification: not yet run".

The run summary handed to the parent repeats errors 1, 2 and the "11+11" span count; anyone quoting it should quote
RESULTS.md instead.

## 5. Safety and scope

Fixtures are a benign tool set (`echo`, a canned `scan.v2-beta` string, a tool that raises `ValueError`, a logging
tool, a `fetch_backend` that refuses any URL not starting `http://127.0.0.1`) and one static resource. No attack
payloads, no exploit code, no credentials (grep for key/password/secret/token found none). Every listener binds
127.0.0.1: `server_v2.py` passes `host="127.0.0.1"`, `server_v1.py` relies on the `FastMCP` default
(`host: str = "127.0.0.1"`, `fastmcp/server.py:171`), `proxy_tcp.py` and `backend.py` bind 127.0.0.1 explicitly.
Docker not used. Nothing about any employer. Bench spend $0 against a $0 cap (the Gemini call in section 6 is the verifier leg, not bench spend).

## 6. Cross-provider leg (Gemini)

Prompt and answer: `verification/gemini-prompt.md`, `verification/gemini-response.md` (`gemini-3.8-flash`, one call,
ledger id `t8a-verify`). Five claims sent with the raw-recount excerpts and source lines.

| Claim | Gemini | Resolution against the data |
|---|---|---|
| 1. B→C revision facts | AGREE | Agree on substance, but Gemini missed that the excerpt itself showed 14 session-header responses against RESULTS' 13; fixed (fix 2) |
| 2. A→B SDK facts | OVERCLAIM (B has 12 server spans, not 11) | Gemini right about the summary and headline row, which said "11+11"; RESULTS' H5 body already gave 12. Fixed (fix 3) |
| 3. Code `0` in A, HTTP 400 in C | AGREE | Agree; confirmed at `lowlevel/server.py:794` |
| 4. R2 reinterpretation (`initialize()` offers 2025-11-25 by design; `Client(mode="auto")` adopts 2026-07-28) | AGREE | Agree; source lines and 6/6 C runs confirm |
| 5. H4/H5 "supported" | DISAGREE on H5 (span count falsifier triggered, extra span unparented) | Gemini right; fixed (fix 3). Gemini did not flag H4's sub-prediction miss, which the data show; fixed (fix 4) |

## 7. Claims vs evidence

The claims stay inside one fixture server per SDK on the high-level API, one client per arm, the SDK's own OTel
middleware only, and a header-safe `Mcp-Name`, and RESULTS' Limits section says so. The code-0 finding is correctly
scoped to `FastMCP` 1.30.0 rather than the 2025-11-25 spec. The R2 reinterpretation rests on cited source lines plus
6/6 measured C runs and is stated at the strength the evidence supports. Tier B is the right badge.

## Files

`VERIFICATION.md` (this file); `verification/indep_check.py`, `indep-orig.jsonl`, `indep-rerun.jsonl`;
`verification/orig-analysis/results/` (analysis of the original captures) and `analyze.out`;
`verification/rerun/` (harness copy, `COMMANDS.log`, `pre.txt`, `runs/`, `results/`; to rerun, symlink `venv-v1` and
`venv-v2` from the bench folder into it); `verification/gemini-prompt.md`, `gemini-response.md`;
`verification/backup/` (`RESULTS.md.pre-verify`, `analyze.py.pre-verify`, `results.pre-verify/`).
