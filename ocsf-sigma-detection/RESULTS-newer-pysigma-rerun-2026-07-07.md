---
type: evidence
title: "H-SIGMA-01 Version-Currency Re-Run — newer pySigma (1.4.0) Reproduces Every Prior Finding (2026-07-07)"
created: 2026-07-07
tags: [sigma, pysigma, version-currency, correlation, detection-fidelity, h-sigma-01]
---

# SIGMA-EXEC-MATURITY — the newer-pySigma re-run retires the version-currency sub-condition (2026-07-07)

Pre-registered in `staged-benchmark-open-track-prereg.md` Arm B: H-SIGMA-01 sits at 3.0/5, and one of
the two owed items for 3.5 is a newer-pySigma maturity re-test (the other, a SIEM-native compiler
test, needs an external SIEM and stays open). This bumps pySigma **1.3.3 → 1.4.0** (latest on PyPI,
2026-07-07) and the pySigma backends already at latest (`pysigma-backend-sqlite` 1.1.3,
`pysigma-backend-opensearch` 2.0.3 — no newer release existed for either), then re-runs the three
execution harnesses verbatim: `temporal_execution.py` (OpenSearch PPL), `sqlite_execution.py`
(SQLite), `duckdb_execution.py` (DuckDB, generic-SQL path). Isolated venv
(`pip install pysigma==1.4.0 pysigma-backend-sqlite==1.1.3 pysigma-backend-opensearch==2.0.3
duckdb==1.5.3`) so the bump didn't touch the shared repo `.venv` other benchmarks depend on.
(Version notes: `install.log` shows duckdb 1.5.4 installed first, then pinned down to 1.5.3 before
any harness ran — the run itself used duckdb 1.5.3 per `pip freeze`, where the original 2026-06-23
DuckDB leg documents 1.5.4; immaterial to the compile-layer finding, since the emitted SQL and the
result JSON are byte-identical regardless, but recorded. The transitive
`pysigma-backend-elasticsearch` also moved 2.0.3 → 2.1.0 with the pySigma bump — more version
surface exercised, same output. "Latest on PyPI" for pySigma and both backends is asserted from
the run session, not re-verifiable offline.)

## Result: byte-for-byte identical to the original runs — the falsifier did not trigger

| harness | original (pySigma 1.3.3) | re-run (pySigma 1.4.0) | diff |
|---|---|---|---|
| `sqlite_execution.py` | flagged 70, recall 1.0, precision 0.286, 50 decoy FP | identical | **0 bytes** |
| `duckdb_execution.py` | SILENTLY-DEGRADES, windowless emit, same precision/FP | identical | **0 bytes** |
| `temporal_execution.py` | flagged 80, recall 0.5, precision 0.5, miss-rate 1.0, over-fire 40/40 | identical | **0 bytes** |

`diff` against the pre-run JSON backups (`results/*.json`, backed up before the re-run) returned
empty for all three — not just the same headline numbers, the full JSON (including the verbatim
emitted SQL/PPL strings) is unchanged. The pySigma SQLite backend still compiles `event_count`
windowless (`timespan` dropped); the OpenSearch PPL backend still compiles `temporal_ordered` as an
unordered, tumbling-window `dc(EventID)` count. **The pre-registered falsification condition — "a
newer pySigma release changes the compiled correlation SQL so the dropped-window straddlers are
caught" — did not trigger.**

## Deviation from the pre-reg (documented, not improvised)

The pre-reg's Arm B viability classification claims all three harnesses are "embedded, no
container." That's true for `sqlite_execution.py` and `duckdb_execution.py` (verified by reading
both — in-memory `sqlite3`/`duckdb.connect(":memory:")`, pure-Python corpus generator, zero network
calls) but **false for `temporal_execution.py`**, which POSTs to `OS_HOST` (default
`localhost:9200`) over `_plugins/_ppl` — it needs a live OpenSearch instance, same as the original
2026-06-16 leg. Full detail: `BLOCKER-temporal_execution.md` (this run's scratchpad). Rather than
stand up a container solely to patch a container-free arm, I ran it **after** Arm A's
`zfr-opensearch` stack came up (same container, same OpenSearch 3.7.0, brought up co-resident with
`moar-*` for the NEEDLE-BM25 arm) — same unmodified script, same methodology, only the source of
the OpenSearch instance differs from the (inaccurate) "no container" framing. This is not a
methodology change.

## What it does to H-SIGMA-01

Retires the "newer-pySigma maturity" sub-condition of the path to 3.5: the silent-correlation-drop
finding is not a stale-pySigma artifact, on the current (2026-07-07) release. **Confidence stays at
3.0/5** — this re-run doesn't move the needle on its own (it's a robustness guard, the same shape
as the earlier B-ANSWEREQ re-run), it just closes one of the two owed conditions. The remaining gate
to 3.5 is the SIEM-native compiler test (needs an external SIEM, not runnable in this environment).
Tier B, deterministic, embedded (two of three harnesses) + one opportunistic container-backed leg.
Route through karen → hypothesis-validator → contradiction-detector before any confidence move —
expected disposition: HOLD, sub-condition retired, no magnitude change.
