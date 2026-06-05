# A silent cross-engine correctness divergence (C3 answer-equality gate)

**Tier B · single machine · ground-truth-verified.** DuckDB `1.5.3` vs chDB `4.1.8`
(embedded ClickHouse), both reading the **same** Parquet file (10,000,000 rows,
814 row groups). The corpus is a pure function of the row index, so the true count of any
`user_name` value is computable from the generator without either engine — that is the ground truth here.

The C3 timing benchmark refuses to report a latency until both engines return identical answers (a fast
engine that returns the wrong number is not faster, it is wrong). At 100M rows that gate failed, and this
is the isolated, cheaply-reproduced cause.

| user_name | ground truth | DuckDB (Parquet) | chDB `=` (Parquet) | chDB `LIKE` (Parquet) | chDB MergeTree | chDB `=` error |
|---|--:|--:|--:|--:|--:|--:|
| `user42` | 5099 | 5099 | 5092 | 5099 | 5099 | −7 |
| `user1337` | 4972 | 4972 | 4966 | 4972 | 4972 | −6 |
| `user7` | 5108 | 5108 | 5101 | 5108 | 5108 | −7 |
| `user999` | 5055 | 5055 | 5055 | 5055 | 5055 | — |
| `user1500` | 5106 | 5106 | 5096 | 5106 | 5106 | −10 |
| `user256` | 5000 | 5000 | 4988 | 5000 | 5000 | −12 |
| `user1023` | 5022 | 5022 | 5012 | 5022 | 5022 | −10 |
| `user64` | 5144 | 5144 | 5144 | 5144 | 5144 | — |

- DuckDB matches ground truth on every probe: **True**
- chDB `=` over Parquet diverged on **6 of 8** probe
  values, total undercount **52** rows
- chDB `LIKE` correct on all: **True** · chDB MergeTree correct on all:
  **True**

## Reading

Both engines read identical bytes, and the generator says DuckDB is right, so chDB's `=` filter over this
Parquet file is silently dropping genuinely-matching rows — a handful per value, all in the tail row
groups, returned with no error and a confident count. It is not raw scale: the trigger is the row-group
structure (~814 groups), which is why a 10M-row file with a small row-group size reproduces
what the 100M default file showed. And it is specific to the Parquet reader's equality path: the same
predicate via `LIKE`, and the same data in chDB's own MergeTree store, are both correct. So the defect is
narrow and real, in chDB 4.1.8 — not a general indictment of ClickHouse, which is an excellent
engine, but a concrete reproducible miscount in one read path.

The transferable point is the methodology, not the bug. A benchmark that only timed the two engines would
have published chDB as competitive on the selective-lookup query and never noticed it returned the wrong
answer; the cross-engine answer-equality gate is the only reason this surfaced, and it surfaced silently —
no exception, no warning from the engine, just a number that was 49 short out of 50,361 at 100M. For
security data specifically, where a `count(*) WHERE` under a filter is a detection threshold or a
compliance figure, an engine that is fast and silently wrong is worse than one that is slow and right.
Verify across engines; don't trust the speed. (Candidate upstream report to the chDB/ClickHouse project —
left for a human to file with this reproduction.) Tier B, single machine; the reproduction is
deterministic, the lesson is general.
