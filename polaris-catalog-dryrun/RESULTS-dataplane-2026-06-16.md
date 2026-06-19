---
type: evidence
title: "Polaris Data-Plane Dry-Run — Catalog-on-S3 and Table-RBAC on MinIO (2026-06-16)"
created: 2026-06-16
tags: [apache-polaris, iceberg-catalog, minio, rbac, h-catalog-auditability-01]
---

# Polaris data-plane dry-run — catalog-on-S3 + table-RBAC works on the open MinIO substrate (2026-06-16)

POLARIS-AUDIT, the leg the 2026-06-15 control-plane rehearsal deferred (`RESULTS-2026-06-15.md`: "the full
data-plane dry-run … remains the next step and needs S3 storage"). This run **solves the MinIO/S3 integration
friction the prior run flagged** and exercises the data plane end-to-end: catalog-on-object-store, a 100k-row
table data write + read-back, and table-level RBAC enforced down to the storage credentials. `data_plane.py`
+ `results/data_plane.json`. Tier B, single host, **dev config (Polaris 1.5.0 in-memory persistence)** —
a feasibility de-risk for the Q3 catalog before AWS dollars, **never the Tier-A result**.

## The integration recipe (the friction, now solved)

Polaris 1.5.0's S3 catalog needs three things against MinIO; each missing one walls a *different* way, which
is why the prior run stopped at "FILE unsupported":

1. **`AWS_ENDPOINT_URL_S3` + `AWS_ENDPOINT_URL_STS` both pointed at MinIO.** Polaris vends *subscoped*
   credentials via STS AssumeRole even for its own metadata writes — with no STS endpoint it fails
   `Failed to get subscoped credentials: STS 403 invalid token`. MinIO's AssumeRole accepts the (nominal)
   roleArn and returns temp creds scoped to the caller's policy.
2. **`pathStyleAccess: true`** in the catalog `storageConfigInfo`. The default (virtual-host `bucket.host`)
   throws `UnknownHostException` against MinIO; path-style routes to `host/bucket`.
3. **An explicit data grant.** `service_admin` can *manage* the catalog (create catalog/table) but is **not**
   authorized for `LOAD_TABLE_WITH_READ_DELEGATION` — a `TABLE_READ_DATA`/`TABLE_WRITE_DATA` catalog-role
   must be granted and assigned. This is the management-plane / data-plane privilege separation, and it is
   itself the table-RBAC finding.

## Result

| step | outcome |
|---|---|
| Catalog-on-S3 (`s3://polaris-sdw/q3p`, path-style) | ✅ created (HTTP 201) |
| Table create (`soc.events`) → `metadata.json` to MinIO | ✅ written via STS-vended creds (769 B object) |
| Data write — 100k synthetic rows/append via pyiceberg (vended-credentials) | ✅ data + manifests + parquet to MinIO (append-idempotent; cumulative across re-runs) |
| Read-back | ✅ scan returns all rows |
| **Table-RBAC — admin** | ✅ blocked from data until granted (`LOAD_TABLE_WITH_READ_DELEGATION` Forbidden for `service_admin` until a `TABLE_*_DATA` role is assigned) |
| **Table-RBAC — read-only principal** | ✅ reads all rows; **WRITE BLOCKED at the S3 layer** (`OSError: multipart upload denied`) — the reader's *vended credentials* are read-scoped, so it cannot write to storage even by going around the API |

## What it says

The Q3 catalog's governance story is feasible on fully open infrastructure: Apache Polaris 1.5.0 runs a real
Iceberg REST catalog over MinIO/S3, writes and reads table data through STS-vended scoped credentials, and
**enforces least-privilege both directions** — an admin can't read data without a data grant, and a read-only
principal can't write, the latter enforced not as an API gate but in the *storage credentials themselves*
(defense-in-depth: the scoped creds MinIO hands a reader simply cannot PUT). That credential-scoping is the
property a mutable SIEM index can't offer. The integration recipe above is the concrete, reusable answer to
"can we self-host catalog governance before paying AWS," and it goes well beyond the prior control-plane
rehearsal.

## What it does NOT show (the still-open gate)

- **Operation-level audit-EVENT log forwarding** (the literal "audit trail of catalog operations to
  JDBC/CloudWatch" H-CATALOG-AUDITABILITY-01 names) is **still not exercised** — it is a Polaris *beta,
  configurable, not-default-on* feature (confirmed control-plane). What works for free is the **entity-level
  audit metadata** (create/update timestamps + entityVersion per object). The operation-event-log leg is the
  remaining gate and the reason this does not move confidence.
- Dev config: **in-memory persistence** (the server warns it is test-only), single host, Polaris 1.5.0,
  synthetic rows, one schema shape. Not a production deployment, not a scale or concurrency test.

## What it does to the hypothesis

Strengthens H-CATALOG-AUDITABILITY-01's feasibility leg materially — catalog-on-open-storage + table-RBAC +
credential-scoped enforcement are now first-party demonstrated, not asserted — but **HOLD, no magnitude move**:
the operation-level audit-event-forwarding leg (the core *auditability* claim, as opposed to *governability*)
is untested and the config is dev-grade. Route through karen → hypothesis-validator → contradiction-detector;
expected disposition HOLD-with-attach. Boundary: synthetic structured rows only; no real telemetry.
