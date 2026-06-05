# Cloud / VPC Flow Query Suite

**Status:** skeleton (2026-05-24). Queries authored during build phase (gated on EDR shipping).

The query suite tests substrate adequacy across the four cloud-relevant access patterns: streaming-ingest stress, cardinality-explosion aggregations, cross-plane correlation JOINs, and JSON-projection performance.

## Query families (planned)

### Family 1 — Streaming-ingest stress (no query; ingest is the test)

Sustained 100K mixed events/sec for ≥15 minutes. The substrate is asked to ingest, not to answer queries — measures whether the storage engine keeps up with the parse + normalize + write path under mixed VPC Flow + CloudTrail JSON.

Headline metric: sustained-rate ceiling at fixed CPU / memory budget.

### Family 2 — Cardinality-explosion aggregation

```sql
-- Sketch — actual query authored during build phase
SELECT src_ip, dst_ip, action, count() AS flow_count
FROM network_activity
WHERE start_time >= NOW() - INTERVAL 1 HOUR
GROUP BY src_ip, dst_ip, action
ORDER BY flow_count DESC
LIMIT 1000;
```

Tests `GROUP BY` performance at high cardinality and the engine's ability to short-circuit top-N. Variants: with / without time-range pushdown; with / without partition pruning on `region` or `account_id`.

### Family 3 — Cross-plane correlation JOIN

JOIN CloudTrail API activity to VPC Flow network activity within a session window. The architectural use case is "what API call led to this east-west traffic" — a real investigation pattern.

```sql
-- Sketch
SELECT a.principal_arn, a.api_name, a.event_time,
       n.src_ip, n.dst_ip, n.dst_port, n.action
FROM cloud_api_activity a
JOIN network_activity n
  ON a.session_id = n.session_id
 AND n.start_time BETWEEN a.event_time AND a.event_time + INTERVAL 5 MINUTE
WHERE a.api_name LIKE 'AssumeRole%';
```

Tests cross-table JOIN with temporal range condition. The substrate's join-planner quality on streaming-arrival tables is the axis being measured.

### Family 4 — JSON projection under high-fanout request parameters

CloudTrail nests request parameters in JSON; some API calls produce massive nested blobs (think `ec2:RunInstances` with security-group lists, block-device mappings, tags). Test projection performance when only specific nested fields are needed.

```sql
-- Sketch — engine-specific syntax variants
SELECT event_time, principal_arn,
       request_parameters['instancesSet']['items'][1]['imageId'] AS ami_id
FROM cloud_api_activity
WHERE api_name = 'RunInstances';
```

Tests JSON-path projection and schema-on-read efficiency. Engines without first-class semi-structured types pay heavily here.

### Family 5 — Time-windowed anomaly aggregates

`GROUP BY principal_arn` over sliding windows, counting unusual API call rates per principal. Tests window-function performance and the engine's incremental-aggregation story.

### Family 6 — Substrate stress probes

- Top-N by `user_agent` across the entire corpus (large GROUP BY on a high-fanout field)
- Cross-account JOIN against synthetic asset inventory (substrate's identity-resolution under partial information)
- Full-text search inside CloudTrail `error_message` field (semi-structured search at corpus scale)

## Methodology constraints

- **Identical workload across candidates** — same query text against each substrate; per-candidate query rewrites require explicit annotation in the result manifest
- **Pin the corpus** — same Stratus-generated CloudTrail + VPC Flow corpus against each candidate
- **Cold and warm runs** — measure first-execution (cold) and steady-state (warm) latency
- **Streaming-arrival semantics** — ingest is concurrent with query in some families; document whether each query runs against batch-loaded vs. streaming-arrived data

## Authoring schedule

Queries authored as part of the L-effort build phase, after EDR archetype ships. Skeleton serves as the contract between data-generation plan and substrate-evaluation plan.
