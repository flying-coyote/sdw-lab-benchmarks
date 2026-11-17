# polaris-catalog-dryrun: can Apache Polaris carry a security catalog's governance on open infrastructure?

## What it measures

A feasibility rehearsal for H-CATALOG-AUDITABILITY-01 in three legs on one host, all on Apache Polaris 1.5.0. The control plane (2026-06-15): stand Polaris up in Docker, create a principal and a principal role, and read back the entity metadata. The data plane (2026-06-16, `data_plane.py`): a catalog on MinIO through S3 and STS, a 100,000-row synthetic append, and table-level access control checked from both sides. The audit trail (2026-06-16): operation-level events written to a Postgres-backed `events` table and queried back.

## Result, and whether it is measured

These are pass or fail checks rather than numbers, and each could have failed. The access-control checks passed: the admin principal cannot read table data until a data grant is assigned, and a read-only principal reads every row but its write is refused at the storage layer, because the credentials Polaris vends to it are read-scoped (`results/data_plane.json`, `reader_write_blocked: true`). With the event listener set to `persistence-in-memory-buffer` and relational JDBC persistence, catalog and table creates land in `polaris_schema.events` with principal, event type, resource, timestamp and request ID. The namespace create in the same run emitted no event, so the sink recorded two events for three operations (`results/audit_events.json`; stated in `RESULTS-auditevents-2026-06-16.md` under Coverage). The data-plane scan counts 300,000 rows because appends accumulated across re-runs, which that file declares.

## What would have made it fail

A read-only principal able to write, an admin able to read data without a grant, or no persisted event for a catalog operation. Two of the three would have shown up as a changed field in the result JSON; there is no negative control for the event sink beyond the namespace gap it happened to show.

## Pre-registration

None.

## Reproduce

The control-plane container, from `RESULTS-2026-06-15.md`:

```bash
docker run -d --name polaris-dryrun -p 8181:8181 -p 8182:8182 \
  -e POLARIS_BOOTSTRAP_CREDENTIALS=POLARIS,root,s3cr3t -e POLARIS_PERSISTENCE_TYPE=in-memory \
  -e quarkus.otel.sdk.disabled=true apache/polaris:latest
```

The data plane needs MinIO, `AWS_ENDPOINT_URL_S3` and `AWS_ENDPOINT_URL_STS` pointed at it, `pathStyleAccess: true` and an explicit `TABLE_*_DATA` grant, then `python3 data_plane.py`. The audit leg needs `polaris.event-listener.type=persistence-in-memory-buffer`, `POLARIS_PERSISTENCE_TYPE=relational-jdbc` with a Postgres datasource, and a bootstrap through `apache/polaris-admin-tool:1.5.0`. The details are in each RESULTS file.

## Results

- `RESULTS-2026-06-15.md`, the control plane.
- `RESULTS-dataplane-2026-06-16.md`, the data plane and access control; `results/data_plane.json`.
- `RESULTS-auditevents-2026-06-16.md`, the audit trail and the current state of the question; `results/audit_events.json`.

## Versions and pins

The reproduce block uses `apache/polaris:latest`; the runs recorded Polaris 1.5.0, and the admin tool is pinned at 1.5.0. Postgres 16 for the audit sink. pyiceberg (used by `data_plane.py`) is not pinned in the root `requirements.txt` and this folder has no requirements file of its own (other benches pin 0.11.1, for example `ocsf-iceberg-metadata/requirements.txt`).

## Evidence tier and limits

Tier B, one host, dev configuration (in-memory persistence for the first two legs), synthetic rows, no load. The CloudWatch sink the hypothesis names was not exercised, and the event schema is marked beta upstream. This is a rehearsal of deployability and surface, and the RESULTS files say it is never the Tier-A result.

## Corrections

None.
