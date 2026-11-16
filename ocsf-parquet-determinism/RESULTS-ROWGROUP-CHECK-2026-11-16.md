---
type: benchmark-results
title: "Determinism probe, post-hoc row-group check (2026-11-16)"
created: 2026-11-16
evidence_tier: B (first-party, single host, agent-run; post-hoc, not pre-registered)
---

# Row-group order or row-group contents? (run 2026-11-16)

`rowgroup_check_2026_11_16.py` (new) reuses the unmodified probe's corpus and coalesced SQL, writes the default
multi-threaded store three times per build, and compares every row group across files by an order-independent hash of
its rows. `RESULTS.md` and `determinism_probe.py` are untouched. Same Beelink host, Python 3.12.3, the session's
June-pin (DuckDB 1.5.3) and current (DuckDB 2.0.0) venvs. Raw: `rowgroup-check-2026-11-16-{current,june-pins}.json`.

| build | file bytes (3 writes) | row groups per file | row groups shared by content, any pair |
|---|---|---|---|
| DuckDB 2.0.0 (13:47:24Z) | 2,864,991 / 2,781,884 / 2,782,542 | 6 / 5 / 5 | one, between files 1 and 2, same position |
| DuckDB 1.5.3 (13:47:27Z) | 2,793,153 / 2,790,275 / 2,864,730 | 6 / 6 / 6 | one between files 0 and 1, one between 1 and 2, same positions |

**Reading.** The files still differ on DuckDB 2.0.0, so the June finding holds on the current release. Most row
groups hold a different set of rows from one write to the next, and the number of row groups can change, which
matches `RESULTS.md`'s root cause (rows reach the writer in thread-finish order) and is more than a reordering of fixed
row groups. An adversarial review's own six-file run (2026-11-16, scratchpad, not in the repo) also saw identical row
groups land at different positions on 1.5.3, so both effects occur; this run did not reproduce a position swap.
