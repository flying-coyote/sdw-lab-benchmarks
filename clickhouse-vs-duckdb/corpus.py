"""Deterministic OCSF-shaped event corpus for the engine comparison.

Every column is a pure function of the row index, computed with DuckDB's `hash()`
over a string-salted key, so the corpus is the same on every run and on every
thread count — no `random()` (whose row assignment is thread-order-dependent in a
parallel engine) and no wall-clock. The whole point of writing it to a single
Parquet file is fairness: ClickHouse and DuckDB then read the *same bytes*, so any
latency difference is the engine, not the input.

Shape: a flattened slice of OCSF Network Activity (4001) and Authentication
(3002) — the columns a SOC actually filters and aggregates on. One UTC day of
events; a small set of hot source IPs so "top talkers" has real heavy hitters; an
~8% failure rate so the failed-auth-burst query has something to find.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from common import BASE_EPOCH  # noqa: E402

WINDOW_S = 86_400          # one UTC day of traffic
N_USERS = 2_000            # user-name cardinality
BASE_MS = BASE_EPOCH * 1000

# Common destination ports, picked deterministically per row (1-based list index).
PORTS = [80, 443, 22, 53, 3389, 445, 8080, 3306]


def gen_select(n: int) -> str:
    """The generating SELECT. Deterministic: column = f(row index)."""
    ports = "[" + ", ".join(str(p) for p in PORTS) + "]"
    return f"""
    SELECT
      i AS row_id,
      {BASE_MS} + (i % {WINDOW_S}) * 1000 + (hash(i::VARCHAR || 't') % 1000)::BIGINT AS time,
      (1 + hash(i::VARCHAR || 'a') % 6)::INTEGER AS activity_id,
      (CASE WHEN hash(i::VARCHAR || 'c') % 2 = 0 THEN 4001 ELSE 3002 END)::INTEGER AS class_uid,
      (1 + hash(i::VARCHAR || 's') % 6)::INTEGER AS severity_id,
      (CASE WHEN hash(i::VARCHAR || 'h') % 1000 < 3
            THEN '10.99.99.' || (hash(i::VARCHAR || 'h2') % 10)::VARCHAR
            ELSE '10.' || (hash(i::VARCHAR || 'i1') % 256)::VARCHAR || '.'
                       || (hash(i::VARCHAR || 'i2') % 256)::VARCHAR || '.'
                       || (hash(i::VARCHAR || 'i3') % 256)::VARCHAR
       END) AS src_ip,
      ('10.0.' || (hash(i::VARCHAR || 'd1') % 256)::VARCHAR || '.'
                || (hash(i::VARCHAR || 'd2') % 256)::VARCHAR) AS dst_ip,
      ({ports})[(1 + hash(i::VARCHAR || 'p') % 8)::BIGINT]::INTEGER AS dst_port,
      ('user' || (hash(i::VARCHAR || 'u') % {N_USERS})::VARCHAR) AS user_name,
      (hash(i::VARCHAR || 'bi') % 100000)::BIGINT AS bytes_in,
      (hash(i::VARCHAR || 'bo') % 1000000)::BIGINT AS bytes_out,
      (CASE WHEN hash(i::VARCHAR || 'st') % 100 < 8 THEN 2 ELSE 1 END)::INTEGER AS status_id
    FROM range(0, {n}) t(i)
    """


def fingerprint(con, n: int):
    """Order-independent corpus fingerprint (sums commute), for the determinism
    check. Two generations of the same n must produce the same tuple."""
    row = con.execute(
        f"""
        SELECT
          count(*),
          sum(hash(time::VARCHAR)::HUGEINT % 1000000007),
          sum(hash(src_ip)::HUGEINT % 1000000007),
          sum(hash(user_name)::HUGEINT % 1000000007),
          sum(bytes_in), sum(bytes_out), sum(status_id), sum(class_uid)
        FROM ({gen_select(n)})
        """
    ).fetchone()
    return [str(x) for x in row]


def write_parquet(con, n: int, path: str):
    """Materialise the corpus to one Parquet file both engines will read."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con.execute(f"COPY ({gen_select(n)}) TO '{path}' (FORMAT parquet)")
    return path
