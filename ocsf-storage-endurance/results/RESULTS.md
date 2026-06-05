# Storage endurance — is write-intensive NVMe over-specified for security data? (results)

**Tier B.** Write amplification is measured on 5,000,000 synthetic OCSF rows; DWPD is *projected*
from it plus the scenario assumptions below — not a field measurement (a multi-week realized-DWPD run is
the Tier-A gate).

## Measured

- Compression (logical → zstd parquet): **4.62×**
- Compaction write factor (stream 20 small files, then compact one): **2.0×**
- **Write amplification** (physical bytes written to storage per logical byte ingested): **0.4325**

Note the write amplification is **below 1** — even with a compaction pass rewriting the data, compression
means fewer bytes hit the disk than the raw log volume. That is the crux of the endurance argument.

## Projected DWPD

DWPD = daily physical bytes written ÷ drive capacity, using the measured write amplification.

| daily raw ingest (TB) | DWPD, 4 TB drive | DWPD, 8 TB drive |
|---|---|---|
| 0.1 | 0.0108 | 0.0054 |
| 0.5 | 0.0541 | 0.027 |
| 1.0 | 0.1081 | 0.0541 |
| 5.0 | 0.5406 | 0.2703 |

Read-intensive endurance is ~1.0 DWPD; the
write-intensive tier vendors push is ~10.0 DWPD.

## Reading

Across realistic security daily volumes and drive sizes, projected DWPD sits far below the ~1 DWPD a
read-intensive drive sustains — and orders of magnitude below the ~10 DWPD write-intensive tier — which
supports H-STORAGE-ENDURANCE-01: paying the write-intensive premium for a security-telemetry store is
over-specifying endurance the workload never consumes, because compression makes physical writes a
fraction of logical ingest even with compaction. The honest scope: the write-amplification number is
measured on synthetic data (compression is data-dependent — real Zeek/EDR logs often compress more, which
*lowers* DWPD further), and the DWPD figures are a transparent projection a reader can re-run with their
own ingest volume, drive capacity, and compaction regime. A multi-week realized-DWPD run on a live ingest
path is the Tier-A gate. Tier B, single machine.
