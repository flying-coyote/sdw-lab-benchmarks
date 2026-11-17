# Iceberg metadata & compaction scaling

## What it measures

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

The ratios in `results/RESULTS.md` re-derive from `results/results.json`: at 200 appends against one
compacted append, planning 208.7 against 1.4 ms (145.5×), pyiceberg scan 400.3 against 40.6 ms (9.9×),
and DuckDB's `iceberg_scan` 72.1 against 6.2 ms (11.7×). All three are measured. Each pyiceberg append
here also writes one manifest, because pyiceberg's default fast-append does not merge them, so planning
cost in this bench mixes manifest count and data-file count; the
[`iceberg-compaction` manifest arm](../iceberg-compaction/RESULTS-MANIFEST-ARM-2026-11-16.md) separates the
two and attributes most of the planning time to manifests.

## What would have made it fail

The mechanism claim would have failed if planning time had stayed flat as appends grew, or if the
compacted table had planned no faster. The DuckDB cross-check guards against a pyiceberg-only artifact.
There is no comparison with a writer that merges manifests, which is what a Java-written table does by
default.

## Pre-registration

None. No pre-registration file exists in this folder.

## Reproduce

```bash
pip install -r ocsf-iceberg-metadata/requirements.txt
python ocsf-iceberg-metadata/run.py
```

Planning = `table.scan().plan_files()` (manifest reading); latencies are machine-specific medians,
the corpus and file counts deterministic. Tier B, single machine. Advances
H-ICEBERG-V4-METADATA-EFFICIENCY-01 / H-ARCH-12. `run.py` also imports DuckDB (for the `iceberg_scan`
cross-check, which installs the iceberg extension at run time) and rewrites `results/RESULTS.md`.

## Results

- [results/RESULTS.md](results/RESULTS.md) and `results/results.json` (2026-06-05), the only run.

## Versions and pins

`requirements.txt` pins pyiceberg 0.11.1 and pyarrow 24.0.0 and does not list DuckDB. `results/results.json`
records no versions at all, so the pyiceberg, pyarrow, DuckDB and iceberg-extension versions the result ran
on are not known from the repo; the pins are the only evidence.

## Evidence tier and limits

Tier B, single machine, 5,000-row micro-batch files. CV is reported for every timing (0.8–10.6%). No rig
stamp (methodology §7b) was recorded, so read absolute milliseconds under §7a.

## Corrections

- *(2026-11-17: re-derived ratios, the manifest note and the layout sections added; no number changed.)*
