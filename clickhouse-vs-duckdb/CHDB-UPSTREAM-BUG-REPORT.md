# Draft upstream bug report — ClickHouse/chDB Parquet Bloom-filter pushdown silently undercounts

> **✅ REPRODUCES AT SCALE — fileable, but it is SCALE-DEPENDENT (re-tested 2026-06-06).** Two full
> 2,000-value sweeps on chdb **4.1.8** (embedded ClickHouse **26.3.9.1**) over DuckDB-1.5.3-written files with
> Bloom filters confirmed present:
> - **10M rows / ~814 row groups → 0 / 2,000 undercount** (does NOT reproduce)
> - **100M rows / ~8,139 row groups → 285 / 2,000 undercount** (reproduces; shortfalls of 3–13 rows each, e.g.
>   user102: 50369 vs 50380)
>
> So the bug is real and the report is fileable, but it is **scale- (row-group-count-) dependent**, and the
> original draft's "reproduced cheaply at 10M" claim is unreliable — at 10M it does not reliably trigger. **A
> filer must reproduce at ~100M (~8,000 row groups), not 10M.** The repro below is updated to 100M. This is
> itself the methodology lesson: a "cheap" smaller-scale isolation can hide a scale-dependent correctness bug,
> so the isolation scale has to be validated against the scale the bug was first seen at. See the hypothesis
> tracker (H-ENGINE-ANSWER-EQUIVALENCE-01) for the corrected note.

**Status:** draft, **fileable** at <https://github.com/ClickHouse/ClickHouse/issues> (and reference
<https://github.com/chdb-io/chdb>), reproducing at 100M per the notice above. Filing left to Jeremy per the
contribute-don't-own posture — this is the reproduction and the isolation packaged so a maintainer can act on it.

---

## Title

**v3 Parquet reader** silently undercounts a string equality filter via **Bloom-filter pushdown** over a
DuckDB-written file — wrong `count(*)`, no error; a regression vs the older reader, which reads the same file
correctly

## Summary

`SELECT count(*) FROM file('x.parquet', Parquet) WHERE user_name = 'userN'` returns **fewer** rows than
actually match, over a DuckDB-written Parquet file (~10M rows, ~814 row groups, a ~2000-distinct string
column that DuckDB wrote **with Bloom filters**). No error or warning — a confident, wrong number.

The miscount is isolated to the **Bloom-filter pushdown path**:

| condition | result |
|---|---|
| default settings (v3 reader, Bloom pushdown on) | **undercounts** (e.g. user42: 5092 vs truth 5099; user256: 4988 vs 5000) |
| `SET input_format_parquet_use_native_reader_v3 = 0` (fall back to the older reader) | **correct** |
| `SET input_format_parquet_bloom_filter_push_down = 0` | **correct** |
| `SET input_format_parquet_filter_push_down = 0` (min/max only) | still wrong — so it is **not** min/max pruning |
| **clickhouse-server 25.10** (v3 reader not default there) | **correct** on the same file |
| same data written by **pyarrow (no Bloom filter)** | **correct** |
| `LIKE 'userN'` (same engine, same file) | correct (LIKE isn't a Bloom-probe point lookup) |
| same data in a ClickHouse **MergeTree** table | correct (no Parquet Bloom path) |

So the **v3 reader's** Bloom-filter probe is producing **false negatives** — it prunes row groups that *do*
contain matching rows. The missing rows sit in the tail row groups; which probe values trip it varies
run-to-run, but it is always an undercount, always on `=`/`IN`, never on `LIKE`.

**Attribution is resolved (it's ClickHouse, not DuckDB):** the *older* reader — both `clickhouse-server 25.10`
and chDB with `use_native_reader_v3=0` — reads the **same** DuckDB Bloom filter **correctly**, so the Bloom
filter DuckDB wrote is conformant and the defect is specifically in the **v3 reader's Bloom-pushdown**
implementation. It is a regression introduced with the v3 reader (default since 25.11; chDB 4.1.8 embeds
26.3, which has v3 on by default).

## This is default configuration, not a misconfiguration

`SELECT value, changed FROM system.settings WHERE name='input_format_parquet_bloom_filter_push_down'`
returns `1, 0` — **default-on, unchanged**. Bloom-filter pushdown was made default-on in ClickHouse by
[PR #80058](https://github.com/ClickHouse/ClickHouse/pull/80058) (merged 2025-05-14). Pushdown/skipping is
an optimization that must never change results, so a *default-on* setting that changes a count is a
correctness bug by definition.

## Environment

- chDB **4.1.8** (PyPI 2026-05-22) — `SELECT version()` reports embedded ClickHouse **26.3.9.1**
- Also reproduce on standalone **clickhouse-server** (test your version; Bloom pushdown is default-on since 25.5)
- DuckDB **1.5.3** wrote the file (column encoding `PLAIN_DICTIONARY`, **with** a Bloom filter)
- Cross-checks correct on the same file: DuckDB, pyarrow, Polars, DataFusion, Trino

## Minimal reproduction (~30 s)

```python
import duckdb
from chdb import session as chs

PQ = "/tmp/ch_bloom_repro.parquet"
N, RG = 100_000_000, 12_288   # ~8,139 row groups — SCALE MATTERS: at 10M / ~814 groups it does NOT
                              # reliably trigger; at 100M ~285/2000 values undercount. Use the larger scale.
con = duckdb.connect()
gen = ("SELECT ('user' || (hash(i::VARCHAR || 'u') % 2000)::VARCHAR) AS user_name "
       "FROM range(0, %d) t(i)" % N)
con.execute(f"COPY ({gen}) TO '{PQ}' (FORMAT parquet, ROW_GROUP_SIZE {RG})")   # DuckDB writes a Bloom filter

sess = chs.Session()
def ch(sql): return int(sess.query(sql, "CSV").data().strip().splitlines()[-1].strip('"'))
for v in ["user42", "user1337", "user256", "user1023"]:
    truth = con.execute(f"SELECT count(*) FROM ({gen}) WHERE user_name = '{v}'").fetchone()[0]
    deflt = ch(f"SELECT count(*) FROM file('{PQ}', Parquet) WHERE user_name = '{v}'")
    v2    = ch(f"SELECT count(*) FROM file('{PQ}', Parquet) WHERE user_name = '{v}' "
              f"SETTINGS input_format_parquet_use_native_reader_v3=0")
    nobloom = ch(f"SELECT count(*) FROM file('{PQ}', Parquet) WHERE user_name = '{v}' "
                 f"SETTINGS input_format_parquet_bloom_filter_push_down=0")
    print(f"{v}: truth={truth} v3_default={deflt} v2={v2} bloom_off={nobloom}"
          f"{'  <-- v3 UNDERCOUNTS' if deflt != truth else ''}")
```

(The lab's isolations: `mechanism_chdb_bloom.py` — the per-setting toggle table; `_work/diag_bloom_origin.py`
— the DuckDB-vs-pyarrow Bloom-presence cross-check.)

## Localization

The bug is in the **v3 reader's Bloom-filter pushdown**, isolated by toggling one thing at a time:
disabling Bloom pushdown fixes it; min/max pushdown is *not* implicated (`filter_push_down=0` doesn't fix
it); and falling back to the older reader (`use_native_reader_v3=0`) fixes it while leaving Bloom pushdown
on. Because the older reader consumes the **same** DuckDB Bloom filter correctly, DuckDB's Bloom filter is
conformant and the v3 reader's Bloom probe (split-block Bloom filter, xxHash64 of the PLAIN-encoded value)
is computing a false-negative for values that are present — most likely a hash/canonicalization or
row-group-skip-bounds error in the v3 path. A `parquet-cli` Bloom-filter dump confirming "maybe present"
for the dropped values would localize it further within the v3 probe.

## Why it matters

For analytical and security workloads a `count(*) WHERE col = x` is a threshold or a compliance figure. A
fast, silent undercount is worse than a slow correct answer because nothing signals the number is wrong; a
timing-only benchmark would publish the engine as competitive and never notice. Only a cross-engine /
ground-truth answer-equality check surfaced it.

## Provenance

SDW Lab cross-engine answer-equality study: benchmark R3 (`clickhouse-vs-duckdb/`), generalized across
engines in `multi_engine_correctness.py`, mechanism isolated in `mechanism_chdb_bloom.py`.
