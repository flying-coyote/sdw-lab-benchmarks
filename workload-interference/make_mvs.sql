-- make_mvs.sql — pre-built async materialized views for the `starrocks_mv` arm (#23).
--
-- This is an OPERATOR step, run once by hand against StarRocks before the starrocks_mv
-- scored pass (engines.py's StarRocksMV client does NOT build these — it only flips
-- enable_materialized_view_rewrite ON and EXPLAIN-verifies that run.py's scheduled shapes
-- rewrite onto these MVs). The README labels this arm an UPPER BOUND: hand-built TOTAL
-- coverage of the scheduled set on a static table, EXPLAIN-verified rewrite. That is the
-- whole point of the arm — it is not the realistic state, it is the ceiling, so the MVs
-- below are deliberately one-per-scheduled-shape with the exact grouping each shape needs.
--
-- Coverage target: the six scheduled shapes in mix.py (j1, j4, port_scan, long_duration,
-- scan_aggregate, rollup_5min). The interactive PROBE is intentionally NOT covered — it is
-- the foreground latency instrument, and giving the MV layer the probe answer for free
-- would measure the cache, not the interactive experience under scheduled load.
--
-- Refs use the Iceberg external catalog `iceberg` (created by the StarRocks client's
-- SR_CATALOG_SQL). Run this AFTER that catalog exists. SET catalog default_catalog first so
-- the MVs live in StarRocks-internal storage (async, refreshed from the external Iceberg
-- base), which is what makes them a usable rewrite target.
--
-- Build + verify (operator):
--   mysql -h 127.0.0.1 -P 9030 -u root < make_mvs.sql
--   -- wait for async refresh to finish, then:
--   SHOW MATERIALIZED VIEWS;                 -- all six ACTIVE, last refresh SUCCESS
--   -- run.py --arm starrocks_mv aborts the scored pass if any scheduled shape's EXPLAIN
--   -- does not name one of these MVs (rewrite not engaged == arm not scored).
--
-- MANUAL refresh: the bench measures a STATIC table, so the MVs are refreshed once at build,
-- never auto-refreshed mid-run (no refresh contention competing for the cpuset during a scored
-- window). Re-run REFRESH MATERIALIZED VIEW <name> WITH SYNC MODE by hand if the base corpus is
-- reseeded. NB (2026-06-14): StarRocks 4.1 rejects `REFRESH MANUAL` on an external-catalog MV
-- without a refresh interval (error 1064 "ASYNC need to specify refresh interval for external
-- table"); REFRESH MANUAL is both the fix and the documented build-once/static intent, so the
-- six MVs below use REFRESH MANUAL. The SYNC-mode refresh after build is unchanged.

CREATE DATABASE IF NOT EXISTS wi_mv;
SET CATALOG default_catalog;
USE wi_mv;

-- j1 — dim enrichment (conn × assets), GROUP BY criticality.
-- The MV pre-joins conn→assets and pre-aggregates per criticality; the scheduled j1 text
-- (count(*), sum(orig_bytes) GROUP BY criticality ORDER BY criticality) rewrites onto it.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_j1
DISTRIBUTED BY HASH(criticality)
REFRESH MANUAL
AS
SELECT a.criticality AS criticality,
       count(*)            AS conns,
       sum(c.orig_bytes)   AS bytes_out
FROM iceberg.soc.conn c
JOIN iceberg.soc.assets a ON c.orig_h = a.ip
GROUP BY a.criticality;

-- j4 — IOC semi-join (count + sum of conn whose resp_h is an indicator).
-- The semi-join is materialized as the matched aggregate; the scheduled j4 text rewrites
-- onto the single-row aggregate.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_j4
DISTRIBUTED BY HASH(hits)
REFRESH MANUAL
AS
SELECT count(*)          AS hits,
       sum(c.orig_bytes) AS bytes_out
FROM iceberg.soc.conn c
WHERE c.resp_h IN (SELECT ioc_value FROM iceberg.soc.ioc);

-- port_scan — per source host, distinct resp_p / resp_h over tcp.
-- COUNT(DISTINCT) is not additively re-aggregatable, so the MV pre-computes the exact
-- per-orig_h distinct counts (filtered to tcp); the scheduled port_scan text
-- (HAVING COUNT(DISTINCT resp_p) > 10, ORDER BY ... LIMIT 10) rewrites onto the
-- per-host distinct-count rows.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_port_scan
DISTRIBUTED BY HASH(orig_h)
REFRESH MANUAL
AS
SELECT orig_h                  AS orig_h,
       count(DISTINCT resp_p)  AS unique_ports,
       count(DISTINCT resp_h)  AS unique_hosts
FROM iceberg.soc.conn
WHERE proto = 'tcp'
GROUP BY orig_h;

-- long_duration — top connections by duration > 60.
-- A pre-filtered projection of the columns the scheduled shape selects; the ORDER BY
-- duration DESC LIMIT 10 rewrites onto the filtered subset (far smaller than scanning conn).
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_long_duration
DISTRIBUTED BY HASH(orig_h)
REFRESH MANUAL
AS
SELECT orig_h     AS orig_h,
       resp_h     AS resp_h,
       duration   AS duration,
       orig_bytes AS orig_bytes,
       resp_bytes AS resp_bytes
FROM iceberg.soc.conn
WHERE duration > 60;

-- scan_aggregate — group-by resp_p count (the H-ARCH-02 concurrency-sweep shape).
-- Additive count per resp_p; the scheduled scan_aggregate (ORDER BY resp_p) rewrites onto it.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_scan_aggregate
DISTRIBUTED BY HASH(resp_p)
REFRESH MANUAL
AS
SELECT resp_p   AS resp_p,
       count(*) AS c
FROM iceberg.soc.conn
GROUP BY resp_p;

-- rollup_5min — 5-minute additive rollup over conn (floor(ts/300) buckets).
-- Bucket cast to BIGINT (ejs rule 4) so bucket equality is integer; additive aggregates
-- (count, sum, sum) match the scheduled rollup_5min text exactly and rewrite onto it.
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_rollup_5min
DISTRIBUTED BY HASH(bucket)
REFRESH MANUAL
AS
SELECT CAST(floor(ts / 300) AS BIGINT) AS bucket,
       count(*)        AS conns,
       sum(orig_bytes) AS bytes_out,
       sum(resp_bytes) AS bytes_in
FROM iceberg.soc.conn
GROUP BY CAST(floor(ts / 300) AS BIGINT);
