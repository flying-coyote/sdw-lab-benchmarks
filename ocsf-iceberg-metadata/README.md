# Iceberg metadata & compaction scaling

The small-files tax, measured. Every Iceberg commit writes a data file, a manifest, and a fresh
metadata.json, so a table fed by many small streaming appends accumulates metadata that scan
*planning* has to read before touching any data. This measures planning time as appends grow, and
what compacting back to one file recovers.

## Result (Tier B)

The transferable finding is the **mechanism**: scan-planning cost grows monotonically with
file/manifest count (because `plan_files()` reads every manifest before touching data, so cost
scales with file count, not data volume), and compaction recovers it. The specific ratios are
**illustrative of the mechanism, not production figures** — measured by pyiceberg's own Python
`plan_files()` on artificially small 5k-row micro-batch files on one machine, so a real query engine
(Trino, Spark) plans differently and faster, and the magnitude is planner-, file-size-, and
host-specific.

This is a **within-Iceberg fragmentation cost**: it is *not* a query-runtime number and *not* the
DuckLake-vs-Iceberg format comparison (that is [BENCH-E](../ocsf-read-scan/), where the two are
roughly interchangeable on read), nor any vendor format-war speedup claim — do not conflate them.
Full numbers in [results/RESULTS.md](results/RESULTS.md). It informs
H-ICEBERG-V4-METADATA-EFFICIENCY-01 (the planning-speed gap V4 metadata targets).

## Run it

```bash
pip install -r ocsf-iceberg-metadata/requirements.txt
python ocsf-iceberg-metadata/run.py
```

Planning = `table.scan().plan_files()` (manifest reading); latencies are machine-specific medians,
the corpus and file counts deterministic. Tier B, single machine. Advances
H-ICEBERG-V4-METADATA-EFFICIENCY-01 / H-ARCH-12.
