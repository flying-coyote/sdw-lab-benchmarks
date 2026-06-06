# Cross-engine NULL / type-coercion / timezone correctness

The answer-equivalence work so far tested `count(*)`/`sum` on equality point-lookups. But the shapes where
security answers silently diverge across engines aren't clean counts — they're NULL three-valued logic, type
coercion, and timezone handling, the parts of SQL that real detections lean on. This bench probes those, over
byte-identical Parquet, against a SQL-standard (or known-UTC) ground truth, with the session timezone forced
to a non-UTC zone so timezone effects are visible.

## Result (Tier B)

SQL engines: DuckDB `1.5.3`, DataFusion `53.0.0`, chDB `4.1.8`. Two patterns:

**Portable traps (identical across all three engines — silent the same way everywhere):** `<>`, `NOT IN`, and
`IN` all silently drop NULL rows; `count(col)` excludes NULLs while `count(*)` doesn't; `''` is not NULL; and
`i = '5'` coerces the string to the int (→ 60) uniformly. These are footguns you carry to every engine.

**Divergences (the same rule gives different answers per engine):**
- **The allowlist footgun, `col NOT IN ('a','b', NULL)`** — by SQL three-valued logic this is **empty**, so a
  detection phrased "flag everything not in the allowlist" matches *nothing* the instant the allowlist picks up
  a NULL. DuckDB and DataFusion return 0 (standard); **chDB returns 80** (it doesn't apply the emptying). Same
  rule, same data, different answer — and on two of three engines it's a silent total-bypass.
- **Time-window counts under a non-UTC session** — the same `WHERE ts >= TIMESTAMP '…12:00' AND ts < '…13:00'`
  over 1,200 instants (UTC-correct window = 600) returns **DuckDB 0 / DataFusion 600 / chDB 0** on a
  UTC-adjusted column and **600 / 600 / 0** on a naive column. No engine is buggy in isolation (the standard
  leaves naive-timestamp + naive-literal tz-resolution to the engine), but a time-bucketed detection is **not
  answer-equivalent** across engines when the session zone isn't UTC.

The safe defaults fall straight out: pin sessions to UTC, store tz-aware (UTC) timestamps, and never let an
allowlist carry a NULL. Full tables in [results/RESULTS.md](results/RESULTS.md).

## Run it

```bash
pip install -r ocsf-temporal-null-coercion/requirements.txt
python ocsf-temporal-null-coercion/run.py
```

Deterministic; the bench forces `TZ=America/New_York` (and each engine's session timezone) so the timezone
divergence is reproducible rather than dependent on the host clock. The per-engine behavior table is the
transferable finding and is version-bound — re-check on upgrades. Tier B, single machine. Extends
H-ENGINE-ANSWER-EQUIVALENCE-01 from reader bugs into query semantics.
