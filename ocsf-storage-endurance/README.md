# Storage endurance — is write-intensive NVMe over-specified for security data?

H-STORAGE-ENDURANCE-01: security workloads consume well under 1 DWPD (drive-writes-per-day), so the
write-intensive (~10 DWPD) NVMe tiers vendors push are over-specified; read-intensive (or HDD/object
cold) is cost-correct. Realized DWPD needs a multi-week field run; what's measurable single-machine is
its driver — **write amplification** (physical bytes written per logical byte ingested) — which this
measures and then uses to *project* DWPD transparently across ingest-volume and drive scenarios.

## Result (Tier B)

Measured write amplification is **~0.43** — below 1, because columnar compression (~4.6× here) outweighs
the 2× compaction rewrite, so fewer bytes hit disk than the raw log volume. Projected DWPD stays far
under the ~1 read-intensive threshold across realistic security volumes: ~0.11 DWPD at 1 TB/day on a
4 TB drive, ~0.54 even at 5 TB/day. That supports the over-specification claim — and real Zeek/EDR logs
compress more than this synthetic set, which lowers DWPD further. Full numbers + the projection table in
[results/RESULTS.md](results/RESULTS.md).

## Run it

```bash
pip install -r ocsf-storage-endurance/requirements.txt
python ocsf-storage-endurance/run.py
```

The write-amplification ratio is measured; the DWPD figures are a transparent projection (re-run with
your own ingest volume, drive capacity, compaction regime). A multi-week realized-DWPD run on a live
ingest path is the Tier-A gate. Tier B, single machine.
