-- STREAM-FRESHNESS streaming arm: the July W detection, unchanged, plus detection I
-- (IOC match), submitted as ONE job via EXECUTE STATEMENT SET.
--
-- Deviation D1 (pre-reg, logged before any scored run): the frozen text says detection I
-- is "a stateless filter joined against a 30-row IOC table". A join against a table in
-- Flink streaming SQL is a regular join that keeps state on both sides, so it is not
-- stateless. The IOC list is instead a literal IN list, which is a genuinely stateless
-- filter and is exactly the predicate batch_fresh.py runs. The 30 addresses are the
-- frozen list in data/fresh/ioc_ground_truth.json (the smoke corpus uses the first 5).
--
-- Submitted by run_fresh_trial.sh: docker cp into smx-jobmanager:/tmp/flink_fresh.sql,
-- then sql-client.sh -f.

SET 'table.local-time-zone' = 'UTC';

CREATE TABLE auth_events (
  `event_uid`      STRING,
  `time`           BIGINT,
  `class_uid`      INT,
  `category_uid`   INT,
  `activity_id`    INT,
  `type_uid`       INT,
  `user`           STRING,
  `src_ip`         STRING,
  `status`         STRING,
  `status_id`      INT,
  `ingest_wall_ts` DOUBLE,
  `event_time`     AS TO_TIMESTAMP_LTZ(`time`, 0),
  WATERMARK FOR `event_time` AS `event_time` - INTERVAL '2' SECOND
) WITH (
  'connector' = 'kafka',
  'topic' = 'smx-auth',
  'properties.bootstrap.servers' = 'smx-kafka:9092',
  'properties.group.id' = 'smx-flink-auth',
  'scan.startup.mode' = 'earliest-offset',
  'format' = 'json',
  'json.fail-on-missing-field' = 'false',
  'json.ignore-parse-errors' = 'true'
);

CREATE TABLE alerts_sink (
  `user`                STRING,
  `src_ip`              STRING,
  `window_start`        TIMESTAMP_LTZ(3),
  `window_end`          TIMESTAMP_LTZ(3),
  `failure_count`       BIGINT,
  `last_ingest_wall_ts` DOUBLE
) WITH (
  'connector' = 'kafka',
  'topic' = 'smx-alerts',
  'properties.bootstrap.servers' = 'smx-kafka:9092',
  'format' = 'json'
);

CREATE TABLE ioc_alerts_sink (
  `event_uid`      STRING,
  `user`           STRING,
  `src_ip`         STRING,
  `time`           BIGINT,
  `ingest_wall_ts` DOUBLE
) WITH (
  'connector' = 'kafka',
  'topic' = 'smx-ioc-alerts',
  'properties.bootstrap.servers' = 'smx-kafka:9092',
  'format' = 'json'
);

EXECUTE STATEMENT SET
BEGIN
INSERT INTO alerts_sink
SELECT
  `user`,
  `src_ip`,
  window_start,
  window_end,
  COUNT(*)                AS failure_count,
  MAX(`ingest_wall_ts`)    AS last_ingest_wall_ts
FROM TABLE(
  TUMBLE(TABLE auth_events, DESCRIPTOR(event_time), INTERVAL '60' SECOND)
)
WHERE `status` = 'failure'
GROUP BY `user`, `src_ip`, window_start, window_end
HAVING COUNT(*) >= 5;

INSERT INTO ioc_alerts_sink
SELECT `event_uid`, `user`, `src_ip`, `time`, `ingest_wall_ts`
FROM auth_events
WHERE `src_ip` IN ('203.0.113.10', '203.0.113.11', '203.0.113.12', '203.0.113.13', '203.0.113.14',
                   '203.0.113.15', '203.0.113.16', '203.0.113.17', '203.0.113.18', '203.0.113.19',
                   '203.0.113.20', '203.0.113.21', '203.0.113.22', '203.0.113.23', '203.0.113.24',
                   '203.0.113.25', '203.0.113.26', '203.0.113.27', '203.0.113.28', '203.0.113.29',
                   '203.0.113.30', '203.0.113.31', '203.0.113.32', '203.0.113.33', '203.0.113.34',
                   '203.0.113.35', '203.0.113.36', '203.0.113.37', '203.0.113.38', '203.0.113.39');
END;
