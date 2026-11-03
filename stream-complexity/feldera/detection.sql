-- F arm detection (STREAM-COMPLEXITY v2): ">=5 failed logins per (user, src_ip) in a
-- 60 s epoch-aligned event-time tumbling window", Feldera OSS v0.375.0 SQL.
-- Input arrives by HTTP ingress (no broker); output read from the view's HTTP egress.
-- LATENESS sits on the derived event_time column (view-level statement): a BIGINT-column
-- LATENESS compiled but gave no waterline through TIMESTAMPADD for emit_final (2026-11-03).
CREATE TABLE auth_events (
  event_uid      VARCHAR,
  "time"         BIGINT NOT NULL,
  class_uid      INT,
  category_uid   INT,
  activity_id    INT,
  type_uid       INT,
  "user"         VARCHAR,
  src_ip         VARCHAR,
  status         VARCHAR,
  status_id      INT,
  ingest_wall_ts DOUBLE
) WITH ('append_only' = 'true');

CREATE LOCAL VIEW auth_ts AS
SELECT *, TIMESTAMPADD(SECOND, "time", TIMESTAMP '1970-01-01 00:00:00') AS event_time
FROM auth_events;
LATENESS auth_ts.event_time INTERVAL 2 SECONDS;

CREATE VIEW alerts
WITH ('emit_final' = 'window_start')
AS
SELECT "user", src_ip, window_start, window_end,
       COUNT(*) AS failure_count, MAX(ingest_wall_ts) AS last_ingest_wall_ts
FROM TABLE(TUMBLE("DATA" => TABLE auth_ts, "TIMECOL" => DESCRIPTOR(event_time),
                  "SIZE" => INTERVAL 60 SECONDS))
WHERE status = 'failure'
GROUP BY "user", src_ip, window_start, window_end
HAVING COUNT(*) >= 5;
