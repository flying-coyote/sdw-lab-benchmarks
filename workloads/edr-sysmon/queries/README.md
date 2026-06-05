# EDR/Sysmon Query Suite

**Status:** skeleton (2026-05-24). Queries to be authored during build phase.

The query suite tests substrate adequacy across the three EDR-relevant access patterns: point lookup, process-tree traversal, and JOIN-driven enrichment.

## Query families (planned)

### Family 1 — Point lookup

Single-row retrieval by `(host, process_guid)` and `(host, image_path, start_time)`. Tests index design and small-result-set latency.

### Family 2 — Process-tree reconstruction

Recursive CTE walking `process_guid → parent_process_guid` to depth N. Tests recursive-query support and join-planner quality.

```sql
-- Sketch — actual query authored during build phase
WITH RECURSIVE tree AS (
  SELECT process_guid, parent_process_guid, image_path, 0 AS depth
  FROM process_activity
  WHERE host = ? AND process_guid = ?
  UNION ALL
  SELECT p.process_guid, p.parent_process_guid, p.image_path, t.depth + 1
  FROM process_activity p JOIN tree t ON p.process_guid = t.parent_process_guid
  WHERE t.depth < 10
)
SELECT * FROM tree;
```

### Family 3 — Severity-scored process events with asset-inventory JOIN

LATERAL JOIN process events to a synthetic asset-inventory table (asset criticality + owner). Tests cross-table JOIN performance under high cardinality.

### Family 4 — Time-windowed anomaly aggregates

`GROUP BY host` over a rolling window, counting process-create events / image-load events / network-connect events to surface anomalous bursts. Tests time-window aggregation performance.

### Family 5 — Substrate stress probes

- Top-N by image-hash frequency across the entire corpus (large GROUP BY)
- Sliding-window deduplication of `process_create` events
- Full-text search inside command-line strings (mixed-shape stress)

## Methodology constraints

- **Identical workload across candidates** — same query text against each substrate; no per-candidate query rewrites without explicit annotation
- **Pin the corpus** — same OCSF-normalized event stream against each candidate
- **Cold and warm runs** — measure both first-execution (cold) and steady-state (warm) latency

## Authoring schedule

Queries will be authored as part of the L-effort build phase (post-spec). Skeleton serves as the contract between the data-generation plan and the substrate-evaluation plan.
