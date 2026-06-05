# Iceberg metadata & compaction scaling

The small-files tax, measured. Every Iceberg commit writes a data file, a manifest, and a fresh
metadata.json, so a table fed by many small streaming appends accumulates metadata that scan
*planning* has to read before touching any data. This measures planning time as appends grow, and
what compacting back to one file recovers.

## Result (Tier B)

Planning grows super-linearly with file count — 87ms at 50 appends, 151ms at 100, **488ms at 200**
(200 data + 601 metadata files), because `plan_files()` reads every manifest. Compacting the same
rows to a single file: **planning ~148× faster (3.3ms), scan ~13× faster**. That gap is the tax a
naive streaming-append-into-Iceberg pattern pays if compaction doesn't keep up, and the mechanism
H-ICEBERG-V4-METADATA-EFFICIENCY-01 says V4 metadata targets. Full numbers in
[results/RESULTS.md](results/RESULTS.md).

## Run it

```bash
pip install -r ocsf-iceberg-metadata/requirements.txt
python ocsf-iceberg-metadata/run.py
```

Planning = `table.scan().plan_files()` (manifest reading); latencies are machine-specific medians,
the corpus and file counts deterministic. Tier B, single machine. Advances
H-ICEBERG-V4-METADATA-EFFICIENCY-01 / H-ARCH-12.
