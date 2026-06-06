# fastparquet silently mis-decodes DuckDB's PLAIN_DICTIONARY string column

A second independent silent-wrong-answer finding from the cross-engine answer-equality study, in a
completely different reader from the ClickHouse Bloom-filter case (see `CHDB-UPSTREAM-BUG-REPORT.md`) — a
pure-Python, non-Arrow decode path.

## What happens

Reading a DuckDB-written Parquet file (10M rows, a ~2000-distinct `user_name` string column DuckDB encoded
as `PLAIN_DICTIONARY`), **fastparquet returns the correct total (10,000,000) and the correct distinct count
(2000), but decodes ~4,672 of the 10M rows to a *different existing value* than every other reader sees.**
The errors mostly cancel in aggregates, so a per-value count looks only slightly off (e.g. `user7` = 531 vs
truth 532), which is exactly what makes it dangerous — the corruption is silent and easy to miss.

It is a **writer × reader interaction**, isolated cleanly:

| file (same logical data) | fastparquet rows decoded ≠ pyarrow |
|---|--:|
| DuckDB-written (`PLAIN_DICTIONARY`) | **4,672** |
| pyarrow-written, dictionary on | 0 |
| pyarrow-written, dictionary off | 0 |

So fastparquet reads pyarrow's encoding perfectly and mis-decodes DuckDB's `PLAIN_DICTIONARY` column. The
other five readers (DuckDB, pyarrow, Polars, DataFusion, Trino) all read the DuckDB file correctly, so the
file is spec-valid — this is fastparquet's decoder, triggered by a legitimate DuckDB encoding choice.

## This is not a misconfiguration

`read_parquet(file)` takes the file's encodings as written; there is no read-side setting that selects the
decode path, so a wrong value out of a spec-valid file is a decode defect by elimination. The historical
DuckDB→fastparquet `dataPageOffset` seek bug ([duckdb#10829](https://github.com/duckdb/duckdb/issues/10829),
fixed DuckDB 0.10.1) is ruled out: that corrupts whole pages and would not leave total **and** distinct
counts exact. fastparquet's `PLAIN_DICTIONARY`/`RLE_DICTIONARY` decode at run boundaries is the likely
location.

## Maintenance reality

fastparquet is **retired**: its README (2026) states the project is being retired now that pandas 3.0 depends
on pyarrow, and the last functional release is **2023.10.1** (2023-10-26). So the practitioner takeaway is
the actionable finding: **do not use fastparquet for correctness-sensitive reads; use pyarrow** — and any
pipeline still defaulting to fastparquet (older pandas `engine='fastparquet'`, some Dask paths) can silently
corrupt values when the file was written by DuckDB. An issue can be filed at
<https://github.com/dask/fastparquet/issues> with the reproduction, but expect no fix.

## Minimal reproduction (~10 s)

```python
import duckdb, pyarrow.parquet as pq, fastparquet
N, RG = 1_000_000, 12_288
con = duckdb.connect()
gen = ("SELECT ('user' || (hash(i::VARCHAR || 'u') % 2000)::VARCHAR) AS user_name "
       "FROM range(0, %d) t(i)" % N)
con.execute(f"COPY ({gen}) TO '/tmp/duck.parquet' (FORMAT parquet, ROW_GROUP_SIZE {RG})")
tbl = pq.read_table('/tmp/duck.parquet')
pq.write_table(tbl, '/tmp/pa.parquet', row_group_size=RG)   # pyarrow re-encode, same data

for f in ['/tmp/duck.parquet', '/tmp/pa.parquet']:
    fp = fastparquet.ParquetFile(f).to_pandas(columns=['user_name'])['user_name'].tolist()
    pa = pq.read_table(f, columns=['user_name']).column(0).to_pylist()
    mism = sum(1 for a, b in zip(pa, fp) if a != b)
    print(f, "rows where fastparquet != pyarrow:", mism)
# DuckDB-written: thousands of mismatches; pyarrow-written: 0
```

(Lab isolation: `mechanism_fastparquet_dict.py`.)

## Provenance

SDW Lab cross-engine answer-equality study (`multi_engine_correctness.py`); surfaced when broadening the
engine set to distinct Parquet readers (`ENGINE-LANDSCAPE-SURVEY.md`).
