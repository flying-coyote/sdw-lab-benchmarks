# chDB pin reconfirmation, 2026-11-23

Tier B, single host. This file keeps the output behind the README's 2026-11-22 statement that a fresh
venv with the root `requirements.txt` chDB pins (`chdb==4.1.8`, `chdb-core==26.3.0`) reproduces the
Parquet equality undercount. The 2026-11-22 re-run kept no output, so the script was run again on
2026-11-23 in a new venv holding only `duckdb==1.5.3`, `chdb==4.1.8` and `chdb-core==26.3.0` and what pip
resolved for them (Python 3.12.3). The venv's pyarrow (26.0.1) is not the root pin (23.0.1); the script
does not use pyarrow, which chdb pulls in.

Command, from `clickhouse-vs-duckdb/`: `python mechanism_chdb_bloom.py` (20.7 s wall).

`select version()` in that venv's chDB session returns `26.3.9.1`.

## pip freeze

```
chdb==4.1.8
chdb-core==26.3.0
duckdb==1.5.3
numpy==2.5.5
pandas==3.1.1
pyarrow==26.0.1
python-dateutil==4.0.0
tzdata==2026.6
```

## Script stdout (unedited)

```
Default dirty pages decay period: 5000ms
truth: {'user42': 5099, 'user1337': 4972, 'user256': 5000, 'user1023': 5022}

[default (v3 reader, bloom pushdown on)]  DIVERGES
   user42: 5092  <-- 5092 vs truth 5099
   user1337: 4966  <-- 4966 vs truth 4972
   user256: 4988  <-- 4988 vs truth 5000
   user1023: 5012  <-- 5012 vs truth 5022

[use_native_reader_v3=0 (older reader)]  ALL CORRECT
   user42: 5099
   user1337: 4972
   user256: 5000
   user1023: 5022

[bloom_filter_push_down=0]  ALL CORRECT
   user42: 5099
   user1337: 4972
   user256: 5000
   user1023: 5022

[filter_push_down=0 (min/max only)]  DIVERGES
   user42: 5092  <-- 5092 vs truth 5099
   user1337: 4966  <-- 4966 vs truth 4972
   user256: 4988  <-- 4988 vs truth 5000
   user1023: 5012  <-- 5012 vs truth 5022

[use_native_reader=0]  DIVERGES
   user42: 5092  <-- 5092 vs truth 5099
   user1337: 4966  <-- 4966 vs truth 4972
   user256: 4988  <-- 4988 vs truth 5000
   user1023: 5012  <-- 5012 vs truth 5022

```
