-- R arm detection (STREAM-COMPLEXITY v3): ">=5 failed logins per (user, src_ip) in a 60 s
-- epoch-aligned event-time tumbling window", RisingWave v3.1.1 SQL. Input arrives by INSERT
-- over the PostgreSQL wire protocol (no broker), carrying the same fields as the other arms;
-- event_time is a generated column, so the watermark sits on a column the engine derives.
-- Output is read through a subscription.
CREATE TABLE auth_events (
  event_uid      VARCHAR,
  "time"         BIGINT,
  class_uid      INT,
  category_uid   INT,
  activity_id    INT,
  type_uid       INT,
  "user"         VARCHAR,
  src_ip         VARCHAR,
  status         VARCHAR,
  status_id      INT,
  ingest_wall_ts DOUBLE PRECISION,
  event_time     TIMESTAMPTZ AS to_timestamp("time"),
  WATERMARK FOR event_time AS event_time - INTERVAL '2' SECOND
) APPEND ONLY;

CREATE MATERIALIZED VIEW alerts AS
SELECT "user", src_ip, window_start, window_end,
       COUNT(*) AS failure_count, MAX(ingest_wall_ts) AS last_ingest_wall_ts
FROM TUMBLE(auth_events, event_time, INTERVAL '1' MINUTE)
WHERE status = 'failure'
GROUP BY "user", src_ip, window_start, window_end
HAVING COUNT(*) >= 5
EMIT ON WINDOW CLOSE;

CREATE SUBSCRIPTION alerts_sub FROM alerts WITH (retention = '1D');
