# Storage endurance — is write-intensive NVMe over-specified for security data?

## What it measures

H-STORAGE-ENDURANCE-01: security workloads consume well under 1 DWPD (drive-writes-per-day), so the
write-intensive (~10 DWPD) NVMe tiers vendors push are over-specified; read-intensive (or HDD/object
cold) is cost-correct. Realized DWPD needs a multi-week field run; what's measurable single-machine is
its driver — **write amplification** (physical bytes written per logical byte ingested) — which this
estimates and then uses to *project* DWPD transparently across ingest-volume and drive scenarios.

## Result (Tier B)

Write amplification comes out at **~0.43** — below 1, because columnar compression (~4.6× here) outweighs
the 2× compaction rewrite, so fewer bytes hit disk than the raw log volume. Projected DWPD stays far
under the ~1 read-intensive threshold across realistic security volumes: ~0.11 DWPD at 1 TB/day on a
4 TB drive, ~0.54 even at 5 TB/day. That supports the over-specification claim — and real Zeek/EDR logs
compress more than this synthetic set, which lowers DWPD further. Full numbers + the projection table in
[results/RESULTS.md](results/RESULTS.md).

Which part is measured and which is arithmetic, re-derived from `results/results.json` and `run.py`:

- **Measured:** the compression ratio, 695,510,937 bytes of the data as in-memory Arrow buffers against
  150,394,775 bytes of zstd Parquet, 4.62×. "Logical" here means Arrow buffer bytes, not the bytes of the
  raw log lines a collector would receive, which are usually larger for text logs.
- **Fixed by the design:** the compaction write factor of 2.0. The harness writes the same rows once as 20
  small files and once as one compacted file, so physical bytes are about twice the stored size whatever
  the data; it models exactly one compaction pass, with no further rewrites, deletes, replicas, write-ahead
  log or catalog writes.
- **Arithmetic:** write amplification = physical bytes / logical bytes, about 2.0 / 4.62, recorded as 0.4325 from the byte counts, and DWPD = daily ingest × 0.4325 / drive
  capacity, for the stated ingest and drive sizes.

So the bench is a transparent projection with one measured input, and the 0.43 is better read as "one
compaction pass divided by the measured compression ratio" than as a measured write amplification. No
bytes written to a device were observed.

## What would have made it fail

Less could have failed than the fixed-drive projection suggests. That projection ignores retention: at
5 TB a day and 4.62× the drive receives about 1.08 TB of stored data a day, so a 4 TB drive is full in under
four days. With capacity sized to hold R days of retained data, DWPD = (2.0 × daily stored) / (R × daily
stored) = 2.0 / R whatever the compression ratio (about 0.07 at 30 days), so the under-1-DWPD conclusion
follows from any retention longer than about two days plus the single-compaction assumption, and the
measured 4.62× cannot move it once retention is in the model. The measured ratio remains the storage-sizing
input it is. What could falsify the conclusion is rewrite frequency (repeated compaction, deletes, replicas,
write-ahead log and catalog writes), which the harness fixes at one pass, and a realized-DWPD measurement
from drive counters on a live ingest path is the test that could fail on its own; it has not been run.
*(Rewritten 2026-11-22: this paragraph said the projection would have crossed 1 DWPD at 5 TB a day on a
4 TB drive below a 2.5× ratio, a case no real system reaches once retention is counted.)*

## Pre-registration

None. No pre-registration file exists in this folder.

## Reproduce

```bash
pip install -r ocsf-storage-endurance/requirements.txt
python ocsf-storage-endurance/run.py
```

The DWPD figures are a transparent projection (re-run with your own ingest volume, drive capacity,
compaction regime). A multi-week realized-DWPD run on a live ingest path is the Tier-A gate. Tier B,
single machine. `run.py` rewrites `results/RESULTS.md`, so dated corrections live in this README.

## Results

- [results/RESULTS.md](results/RESULTS.md) and `results/results.json`, the only run.

## Versions and pins

`requirements.txt` pins DuckDB 1.5.3 and pyarrow 24.0.0; `results/results.json` records no versions.

## Evidence tier and limits

Tier B, single machine, 5,000,000 synthetic rows. The compression ratio is data-dependent and belongs to
this generator. No timings are reported.

## Corrections

- *(corrected 2026-11-17: "Measured write amplification is ~0.43" is reworded to separate the measured
  compression ratio from the compaction factor the harness fixes at 2.0; the numbers are unchanged and
  re-derive from `results/results.json`.)*
