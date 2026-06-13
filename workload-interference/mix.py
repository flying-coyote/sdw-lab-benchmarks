"""Pre-registered query mix for the workload-interference bench (#23).

The six scheduled shapes and the interactive probe are carried VERBATIM from the
canonical texts named in README.md §Mechanism — re-derived here from those source
files, not invented:

  j1, j4              from engine-join-specialization/queries.py
                      (J1_DIM_ENRICHMENT, J4_IOC_SEMIJOIN)
  port_scan,          from zeek-flagship-rerun/queries.py
  long_duration       (ch_queries: port_scan_detection, long_duration_connections)
  scan_aggregate      the H-ARCH-02 concurrency-sweep scan-aggregate
                      (security-data-that-works/docker/lab/concurrency_sweep.py:
                       group-by-port scan-aggregate), expressed on the conn corpus
  rollup_5min         a 5-minute additive rollup over conn (floor(ts/300) buckets),
                      the README's "5-minute additive rollup"

One canonical ANSI text per shape; per-arm substitution of table references ONLY
(the engine-join-specialization SQL discipline). Surface accommodations applied to
the canonical text uniformly, never per-engine variants:
  - floor(ts/300) cast to BIGINT so bucket equality is integer not float (ejs rule 4).
  - port_scan keeps COUNT(DISTINCT) — it is a SCHEDULED-LOAD shape here, run for its
    arrival pressure, not answer-equality-gated; the gated artifact is the interactive
    PROBE (an exact-aggregate count), so the COUNT(DISTINCT) approximation that ejs
    excludes from gated answers does not touch a gated number here.

Table references resolve per arm exactly as engine-join-specialization/run_bench.py
does (table_refs): Iceberg-cataloged refs for starrocks/starrocks_mv/trino, icebergS3()
with the planted metadata pin for clickhouse_iceberg, bench.<t> for clickhouse_native,
nessie."soc"."<t>" for dremio, and read_parquet('<path>') for duckdb_parquet.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
# Reuse the engine-join-specialization corpus + catalog: same compose stack, same
# sha256-pinned tables. The interference bench plants NO new corpus (README: "Reuses
# the ejs compose stack and sha256-pinned corpora").
EJS = HERE.parent / "engine-join-specialization"
WORK = EJS / "_work"

S3_ENDPOINT = "http://minio:9000"
AK, SK = "ejsbench", "ejsbench123"

# Only the tables the six scheduled shapes + the probe touch.
SOC_TABLES = ["conn", "dns", "assets", "ioc"]

# ---------------------------------------------------------------- scheduled shapes (6)
# $table placeholders, substituted per arm by table_refs() below. Identical discipline
# to engine-join-specialization/queries.py render().

# j1 — dim enrichment (conn × assets), GROUP BY criticality. Verbatim from
# engine-join-specialization J1_DIM_ENRICHMENT.
J1 = """
SELECT a.criticality, count(*) AS conns, sum(c.orig_bytes) AS bytes_out
FROM $conn c
JOIN $assets a ON c.orig_h = a.ip
GROUP BY a.criticality
ORDER BY a.criticality
"""

# j4 — IOC semi-join. Verbatim from engine-join-specialization J4_IOC_SEMIJOIN.
J4 = """
SELECT count(*) AS hits, sum(orig_bytes) AS bytes_out
FROM $conn
WHERE resp_h IN (SELECT ioc_value FROM $ioc)
"""

# port_scan — verbatim from zeek-flagship-rerun port_scan_detection (ch_queries form),
# retargeted from the single flat zeek_native table onto $conn. COUNT(DISTINCT) kept;
# this is a scheduled-load arrival shape, not an equality-gated answer (see module docstring).
PORT_SCAN = """
SELECT orig_h, COUNT(DISTINCT resp_p) AS unique_ports, COUNT(DISTINCT resp_h) AS unique_hosts
FROM $conn
WHERE proto = 'tcp'
GROUP BY orig_h
HAVING COUNT(DISTINCT resp_p) > 10
ORDER BY unique_ports DESC
LIMIT 10
"""

# long_duration — verbatim from zeek-flagship-rerun long_duration_connections.
LONG_DURATION = """
SELECT orig_h, resp_h, duration, orig_bytes, resp_bytes
FROM $conn
WHERE duration > 60
ORDER BY duration DESC
LIMIT 10
"""

# scan_aggregate — the H-ARCH-02 concurrency-sweep scan-aggregate (group-by-port,
# ordered), from concurrency_sweep.py's SQL, expressed on conn's resp_p.
SCAN_AGGREGATE = """
SELECT resp_p, count(*) AS c
FROM $conn
GROUP BY resp_p
ORDER BY resp_p
"""

# rollup_5min — a 5-minute additive rollup over conn (README's "5-minute additive
# rollup"). BIGINT bucket per ejs rule 4; additive aggregates only.
ROLLUP_5MIN = """
SELECT CAST(floor(ts / 300) AS BIGINT) AS bucket,
       count(*) AS conns,
       sum(orig_bytes) AS bytes_out,
       sum(resp_bytes) AS bytes_in
FROM $conn
GROUP BY CAST(floor(ts / 300) AS BIGINT)
ORDER BY bucket
"""

# Ordered list = the staggered 60 s cycle order (README §Mechanism: "Staggered in a
# 60 s cycle"). run.py spreads K shapes evenly across the cycle period.
SCHEDULED = {
    "j1": J1,
    "j4": J4,
    "port_scan": PORT_SCAN,
    "long_duration": LONG_DURATION,
    "scan_aggregate": SCAN_AGGREGATE,
    "rollup_5min": ROLLUP_5MIN,
}
SCHEDULED_ORDER = ["j1", "j4", "port_scan", "long_duration", "scan_aggregate", "rollup_5min"]
K = len(SCHEDULED_ORDER)  # 6 pre-registered shapes

# ---------------------------------------------------------------- interactive probe
# A cheap, point-ish interactive lookup an analyst would actually fire on a 5 s cadence
# while the scheduled load runs. Exact aggregate (count + sum) so it IS answer-checkable
# against the DuckDB oracle (the gated number), with a seeded parameter rotation so a
# repeat does not measure a result cache (README: "seeded parameter rotation so repeats
# don't measure caches"). The {port} slot is filled per-fire by run.py from a seeded
# rotation over a fixed candidate set.
PROBE = """
SELECT count(*) AS conns, sum(orig_bytes) AS bytes_out
FROM $conn
WHERE resp_p = {port} AND proto = 'tcp'
"""

# Candidate ports for the seeded rotation. Common server ports present in a Zeek conn
# corpus; the rotation (run.py, RNG off MASTER_SEED) walks these so consecutive probes
# hit different parameters and the engine result cache cannot serve a repeat.
PROBE_PORTS = [80, 443, 22, 3389, 53, 445, 8080, 25, 23, 3306, 1433, 5432, 139, 21, 389, 636]


def probe_sql(refs: dict, port: int) -> str:
    """Render the interactive probe for one fire at a given rotated port."""
    return render(PROBE, refs).replace("{port}", str(port))


# ---------------------------------------------------------------- per-arm table refs
# Mirrors engine-join-specialization/run_bench.py:table_refs, narrowed to the SOC
# tables this bench touches and extended with the two arms ejs did not have:
# starrocks_mv (same Iceberg refs as starrocks; the MV layer is server-side, the SQL is
# identical and rewrite is the engine's job) and duckdb_parquet (read_parquet on the
# pinned files).

def table_refs(arm: str) -> dict:
    """{logical table name -> arm-specific SQL reference} for the SOC tables.

    Reads engine-join-specialization/_work/table_locations.json for the live Iceberg
    locations (the same file load_tables.py writes), so a reseed that moves a table's
    S3 prefix is picked up with no edit here.
    """
    refs = {}
    if arm == "duckdb_parquet":
        # Byte-identical pinned parquet, read in-process — no server, no catalog.
        for t in SOC_TABLES:
            refs[t] = f"read_parquet('{(WORK / 'soc' / (t + '.parquet')).as_posix()}')"
        return refs

    locations = json.loads((WORK / "table_locations.json").read_text())
    for ident, meta in locations.items():
        ns, name = ident.split(".")
        if ns != "soc" or name not in SOC_TABLES:
            continue
        if arm in ("starrocks", "starrocks_mv", "trino"):
            # Iceberg external catalog ref (StarRocks/Trino REST catalog named `iceberg`).
            refs[name] = f"iceberg.{ns}.{name}"
        elif arm == "clickhouse_iceberg":
            # icebergS3 against the planted sort-last metadata pin (ejs discipline).
            http_loc = meta["location"].replace("s3://", f"{S3_ENDPOINT}/")
            refs[name] = f"icebergS3('{http_loc}', '{AK}', '{SK}')"
        elif arm == "clickhouse_native":
            refs[name] = f"bench.{name}"
        elif arm == "dremio":
            refs[name] = f'nessie."{ns}"."{name}"'
        else:
            raise ValueError(f"unknown arm: {arm}")
    missing = [t for t in SOC_TABLES if t not in refs]
    if missing:
        raise RuntimeError(
            f"{arm}: missing table_locations for {missing}; run "
            f"engine-join-specialization load_tables.py first")
    return refs


def render(sql: str, refs: dict) -> str:
    """Substitute $table placeholders, longest-first (so $conn_enriched, if ever added,
    is not clobbered by $conn). Identical to engine-join-specialization render()."""
    for name in sorted(refs, key=len, reverse=True):
        sql = sql.replace(f"${name}", refs[name])
    return sql


def scheduled_sql(arm: str) -> dict:
    """{shape -> rendered SQL} for the six scheduled shapes on one arm."""
    refs = table_refs(arm)
    return {name: render(sql, refs) for name, sql in SCHEDULED.items()}
