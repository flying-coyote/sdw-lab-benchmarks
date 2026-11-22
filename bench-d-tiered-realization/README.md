# bench-d-tiered-realization: does a hot/warm/cold split across DuckLake and Iceberg beat one backend?

## What it measures

Two things, in two passes. The 2026-06-15 core (`bench_d.py`) times write-plus-commit and query-after-write at 1k, 10k and 100k-row batches for three storage paths: DuckLake with a local catalog, ClickHouse native MergeTree, and Iceberg through pyiceberg to Nessie and MinIO. The 2026-06-16 integrating run (`bench_d_integrating*.py`) tests H-TIERED-REALIZATION-01 end to end: DuckLake as the hot tier, Iceberg as warm and compacted cold, behind one watermark-fenced read contract, against two single-backend nulls (one Iceberg table, one DuckLake table) on three pre-registered service levels for freshness, planning and storage.

## Result, and whether it is measured

Measured. All three storage paths commit in well under a second even at 100k-row batches (70 to 124 ms for Iceberg in June, up to 151 ms in the 2026-06-28 re-run), so the "1 to 5 minutes" file-write band in the desk research is a streaming checkpoint interval and not an Iceberg commit cost (`RESULTS-2026-06-15.md`, `results/bench_d.json`). In the integrating run the null wins on all three service levels at lab scale: the tiered hot tier's 27.8 ms freshness ties a single DuckLake's 26.5 ms, a fragmented single Iceberg table's planning climbs past 200 ms but compaction alone flattens it to about 10 to 13 ms, and a DuckDB-written ZSTD Parquet file of the same corpus is 14.7 MB against the Iceberg table's 18.7 MB. No
DuckLake table was written at ZSTD (the measured DuckLake table is 21.4 MB at its Snappy default, against
19.1 MB for the bare DuckDB Snappy file, so the table is about 12% larger than the bare file), so the storage
verdict rests on a codec comparison and not on a DuckLake table (`bench_d_integrating_sweep.py`
`storage_parity`, `results/bench_d_integrating_sweep.json`, `results/bench_d_integrating_null.json`;
corrected 2026-11-22: this said "a single DuckLake stores 14.7 MB"). The read-contract oracle is the sharpest result: a reader pinned to one watermark counts 700,000 rows, a naive per-branch reader duplicates the 50,000-row day being moved, and a stale pin drops it (`results/bench_d_integrating_tiered.json`). The hot-freshness tie was predicted by
construction in the pre-registration (both arms read the same local DuckLake store), so of the three service
levels only planning and storage could have gone the tiered arm's way (added 2026-11-22).

## What would have made it fail

The pre-registration commits the decision rule in numbers before the integrating run: the tiered arm had to beat both nulls on a named service level by more than both arms' CV. It could have won on planning if a cross-backend split had stayed flat where a compacted single table did not, and it did not.

## Pre-registration

`PRE-REGISTRATION-integrating-2026-06-16.md`. There is no hash file, so whether the text changed after the run cannot be checked from the folder. It was committed in the same commit as the Window 1 null baseline (`eb651b9`), so commit history shows the freeze only ahead of Windows 2 and 3 (`d06841a`, `776eab8`) (checked 2026-11-22). Five departures, two declared and three found on 2026-11-17 (recounted 2026-11-22; this said four, one declared):

- Declared: the 10,000-append sweep step was not reached (resource-capped).
- Declared: the compacted single Iceberg stands in for the planned all-Iceberg three-table degenerate control.
- The pre-registration requires the decision rule to be signed off by a named external reviewer before execution. The sign-off box is unchecked in the pre-registration and in `STATUS-integrating-2026-06-16.md`, and the RESULTS Gate section moves the sign-off to "before the verdict is read as final".
- The 10-append fragmented planning cell has a CV of 94.1% (`cv_blown: true`), above the run's own 30% ceiling, and RESULTS still reports its 43.6 ms; the 100, 1,000 and 3,000-append cells are clean.
- `expire_snapshots` failed at every sweep step under Nessie, so the compacted arm is an overwrite without snapshot expiry.

## Reproduce

The Iceberg arms run inside the `ejs-lab` container on the ejs network, because Nessie advertises the internal MinIO endpoint. The full recipe is in `STATUS-integrating-2026-06-16.md` under "Vantage"; in short:

```bash
docker cp bench-d-tiered-realization/bench_d_integrating.py ejs-lab:/work/bench-d-tiered-realization/
docker cp lib/common.py ejs-lab:/work/lib/common.py
docker exec -e S3_ENDPOINT=http://minio:9000 -e NESSIE_URI=http://nessie:19120/iceberg/ \
  -e MINIO_HOST=minio:9000 -e OUT_DIR=/work/results \
  ejs-lab python3 /work/bench-d-tiered-realization/bench_d_integrating.py
# then bench_d_integrating_tiered.py and bench_d_integrating_sweep.py the same way
```

The 3,000-append sweep step took about four minutes to build; the 10,000 step exhausted the container.

## Results

- Entry point: `RESULTS-integrating-2026-06-16.md`, the integrating run and its verdict, with the 2026-11-17 correction note at the top.
- `RESULTS-2026-06-15.md`, the commit-latency core, and `RESULTS-reproduction-2026-06-28.md`, an independent re-run of its DuckLake and Iceberg arms that keeps the ordering and the sub-second commit, though two Iceberg cells drifted past the 5 to 25% that file quotes for run-to-run drift (1k rows, second run, 98.2 vs 70.6 ms, +39%; 10k rows, second run, 94.9 vs 71.7 ms, +32%).
- `STATUS-integrating-2026-06-16.md`, the checkpoint and run recipe.
- Data: `results/bench_d.json`, `results/bench_d-reproduction-2026-06-28.json`, `results/bench_d_integrating_{null,tiered,sweep}.json`.

## Versions and pins

DuckDB 1.5.3 and pyiceberg 0.11.1, recorded in the integrating JSON; ClickHouse 26.5.1 in the June RESULTS. pyiceberg is not pinned in the root `requirements.txt` and this folder has no requirements file of its own (other benches pin 0.11.1, for example `ocsf-iceberg-metadata/requirements.txt`).

## Evidence tier and limits

Tier B, one host, warm cache, a synthetic uniform-random connection corpus, aggregate output only, two-day hot window and one run per cell. The regime that motivates tiering, multi-day retention priced per GB per day in a hot store, is not reached on one host, so the verdict removes the lab-scale performance case for tiering and leaves the cost case unmeasured.

## Corrections

- 2026-11-17: dated note added to `RESULTS-integrating-2026-06-16.md` covering the planning figures quoted from the first pass, the blown 10-append cell, the failed snapshot expiry and the missing sign-off.
