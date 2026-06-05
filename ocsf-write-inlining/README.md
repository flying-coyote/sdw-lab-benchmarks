# DuckLake inlining vs Iceberg — the small-files problem at the source

Isolates one claim made for DuckLake: it inlines small streaming batches into the catalog instead of
writing a data file per commit, so it "never creates tiny files in the first place" — versus Iceberg's
write-a-file-then-compact-later model. Same seeded stream of 100 small commits to three arms; the metric
is data files left behind.

## Result (Tier B)

Inlining off, both DuckLake and Iceberg write **one data file per commit** (100 each; Iceberg also
accumulates a manifest + metadata.json each time → 301 metadata files). Inlining on, DuckLake writes
**0 data files** for the same stream — rows live in the catalog until a flush threshold — and the data is
immediately queryable throughout. That's the difference between "create tiny files, then compact" (the
maintenance job measured in `ocsf-iceberg-metadata`) and not creating them. Full numbers in
[results/RESULTS.md](results/RESULTS.md).

## Run it

```bash
pip install -r ocsf-write-inlining/requirements.txt
python ocsf-write-inlining/run.py
```

Tier B, single machine; file counts are deterministic, the inline threshold is a configured parameter.
It isolates the file-avoidance claim; it doesn't settle warehouse-scale trade-offs (inlined rows trade
file count for catalog growth). Complements the BENCH-D write-contract and iceberg-metadata benchmarks.
