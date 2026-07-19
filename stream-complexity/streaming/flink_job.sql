-- Streaming arm detection job: "≥5 failures per (user, src_ip) in a 60s event-time
-- window" (pre-reg wording), implemented as a Flink SQL tumbling-window aggregation
-- over a Kafka source, sinking alerts to a second Kafka topic.
--
-- IMPLEMENTATION-CHOICE NOTE (the task brief left this open — "PyFlink flink_job.py
-- submitted into the cluster, or Flink SQL via the SQL client — your call, pick what
-- you can make WORK"): this bench uses Flink SQL via the SQL Client rather than
-- PyFlink. PyFlink's Python-Java bridge (pemja) needs a Python interpreter matching
-- the exact minor version baked into the Flink image's Python UDF runner, which is a
-- second moving part of its own to pin and debug on a single quiet-box smoke pass; SQL
-- via the SQL Client needs nothing beyond the connector jar already baked into
-- streaming/Dockerfile.flink. It is filed here as a deliberate, stated deviation from
-- the PyFlink option named in the task brief, not a silent one — see README.md.
--
-- Submitted by streaming/submit_flink_job.sh via:
--   docker exec smx-jobmanager /opt/flink/bin/sql-client.sh -f /opt/flink/usrlib/flink_job.sql

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

-- Tumbling, epoch-aligned (Flink's TUMBLE table-valued function windows align to the
-- epoch when no OFFSET is given) — the SAME grid gen_corpus.py's independent ground
-- truth and batch_job.py's `(time // 60) * 60` both use. window_start/window_end come
-- out as TIMESTAMP_LTZ; the JSON sink serialises them as ISO-8601 strings, which
-- compare_answers.py's canonical_window_start() converts back to epoch seconds.
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
