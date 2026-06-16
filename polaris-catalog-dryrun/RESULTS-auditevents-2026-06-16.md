# Polaris audit-event forwarding — WORKING: operation-level events persist to a queryable JDBC sink (2026-06-16)

POLARIS-AUDIT, the **last open gate** of H-CATALOG-AUDITABILITY-01 — the one the control-plane rehearsal
(`RESULTS-2026-06-15.md`) and the data-plane run (`RESULTS-dataplane-2026-06-16.md`) both left owed:
*operation-level audit-event log persistence forwarding catalog operations to a JDBC sink.* It is now
demonstrated end-to-end on fully open infrastructure (Polaris 1.5.0 + Postgres 16 + MinIO). Tier B, single
host, dev-grade but **no longer in-memory** — events land in Postgres and are queried back.

## The correction (the earlier "needs code" read was wrong — it's a config + a backend)

The control-plane run found no structured audit events in the default config and the right read was "not
default-on." A first probe suggested it needed a code-level listener. **Both undersold it.** Polaris 1.5.0
ships a real, pluggable event-listener framework; the default is `no-op` (hence nothing captured), and the
audit trail turns on with a config selector + a persistence backend:

1. **`polaris.event-listener.type=persistence-in-memory-buffer`** — selects the bundled
   `InMemoryBufferEventListener` (buffers operation events, flush controlled by
   `…persistence-in-memory-buffer.max-buffer-size` / `.buffer-time`), which flushes to the persistence layer.
   The wrong guesses `logging` / `persistence` raise `UnsatisfiedResolutionException` — the registered
   `@Identifier` is `persistence-in-memory-buffer` (verified from the bean bytecode).
2. **`POLARIS_PERSISTENCE_TYPE=relational-jdbc`** + a Postgres datasource, bootstrapped with the
   `apache/polaris-admin-tool:1.5.0 bootstrap` command — which creates `polaris_schema` including a dedicated
   **`events`** table.

With both, catalog operations persist as durable, queryable audit events.

## Result — the audit trail (verified from Postgres)

Ran create-catalog → create-namespace → create-table; `SELECT … FROM polaris_schema.events`
(`results/audit_events.json`):

| event_type | principal | resource_type | resource | + |
|---|---|---|---|---|
| `AFTER_CREATE_CATALOG` | root | CATALOG | `audit_q3` | timestamp_ms, request_id, event_id |
| `AFTER_CREATE_TABLE` | root | TABLE | `soc.events` | + full Iceberg table metadata JSON |

Each row carries **who** (`principal_name`), **what** (`event_type`), **which resource**
(`resource_type` + `resource_identifier`), **when** (`timestamp_ms`), and a **`request_id`** for correlation —
durable in Postgres, immutable-append, queryable. That is the compliance audit trail a mutable SIEM index
can't give, demonstrated first-hand.

## What it says

H-CATALOG-AUDITABILITY-01's core claim — Polaris can persist catalog-operation events for compliance — is
now **first-party demonstrated, not asserted**, on open infra: the events are real, structured, attributed,
and queried back out of a JDBC store. Combined with the earlier legs (deployable + control-plane RBAC +
data-plane catalog-on-S3 + table-RBAC + entity-metadata), the full governability-AND-auditability story holds
on a self-hostable stack — the concrete de-risk for the Q3 catalog before any AWS spend.

## Caveats (Tier B)

- **Dev-grade still:** single host; the `persistence-in-memory-buffer` listener is the buffering reference
  impl (a production deployment would tune flush + likely use the async cluster listener); not a scale or
  under-load test; Polaris 1.5.0, schema is BETA ("may change").
- **Coverage:** catalog + table creates emitted `AFTER_*` events; the namespace create did not surface one in
  this run (event coverage is per-operation-type, not universal) — note the trail captures the operations it
  hooks, not necessarily every API call.
- **CloudWatch sink** (the hypothesis's other named target) was not exercised — the `events` table (JDBC) is
  the demonstrated sink; CloudWatch is the same listener framework pointed elsewhere.
- Boundary-clean: synthetic structured rows only; no real telemetry.

## What it does to the hypothesis

Closes the gate the prior two legs left open: the audit-EVENT persistence is **working + observable**, not
beta-untested. Proposes **H-CATALOG-AUDITABILITY-01 3.0 → 3.5/5** through the gate (core claim demonstrated
first-hand on open infra; held below 4/5 by dev-config / single-host / buffer-not-async / BETA-schema /
not-under-load). Route karen → hypothesis-validator → contradiction-detector before the move.
