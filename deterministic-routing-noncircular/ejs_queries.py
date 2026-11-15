"""Canonical query texts for engine-join-specialization (pre-registered).

SQL discipline (per README): ONE canonical ANSI text per query; per-arm substitution of
table references only ($lineitem, $conn, ...). Declared surface accommodations, applied
uniformly to the canonical text itself (no per-engine variants):
  1. TPC-H comma-joins rewritten to explicit INNER JOIN ... ON with predicates verbatim
     (the FROM-clause order is the spec's order; engines with statistics-based reordering
     may reorder — that capability is part of what is measured).
  2. Interval arithmetic constant-folded (Q5: date '1994-01-01' + interval '1' year ->
     date '1995-01-01').
  3. Deterministic ORDER BY tiebreakers appended where the spec's ordering admits ties
     (Q3: + l_orderkey; Q18: + o_orderkey) so the answer-equality gate compares
     identical row sets, not tie-luck.
  4. floor(ts/300) cast to BIGINT so bucket equality is integer, not float.
No structural rewrites: no manual join reordering, no subquery flattening, no hints,
no engine-specific functions. Gated answers use exact aggregates only (count/sum/min/max);
COUNT(DISTINCT) is excluded from gated answers (approximate on some engines).
"""

# ---------------------------------------------------------------- F1: TPC-H-derived SF10
# Derived from TPC-H (DuckDB tpch dbgen, SF10, validation substitution parameters).
# Not an audited TPC result; not comparable to published TPC-H results.

Q3 = """
SELECT l_orderkey, sum(l_extendedprice * (1 - l_discount)) AS revenue,
       o_orderdate, o_shippriority
FROM $customer
JOIN $orders ON c_custkey = o_custkey
JOIN $lineitem ON l_orderkey = o_orderkey
WHERE c_mktsegment = 'BUILDING'
  AND o_orderdate < DATE '1995-03-15'
  AND l_shipdate > DATE '1995-03-15'
GROUP BY l_orderkey, o_orderdate, o_shippriority
ORDER BY revenue DESC, o_orderdate, l_orderkey
LIMIT 10
"""

Q5 = """
SELECT n_name, sum(l_extendedprice * (1 - l_discount)) AS revenue
FROM $customer
JOIN $orders ON c_custkey = o_custkey
JOIN $lineitem ON l_orderkey = o_orderkey
JOIN $supplier ON l_suppkey = s_suppkey AND c_nationkey = s_nationkey
JOIN $nation ON s_nationkey = n_nationkey
JOIN $region ON n_regionkey = r_regionkey
WHERE r_name = 'ASIA'
  AND o_orderdate >= DATE '1994-01-01'
  AND o_orderdate < DATE '1995-01-01'
GROUP BY n_name
ORDER BY revenue DESC
"""

Q9 = """
SELECT nation, o_year, sum(amount) AS sum_profit
FROM (
  SELECT n_name AS nation,
         EXTRACT(year FROM o_orderdate) AS o_year,
         l_extendedprice * (1 - l_discount) - ps_supplycost * l_quantity AS amount
  FROM $part
  JOIN $lineitem ON p_partkey = l_partkey
  JOIN $supplier ON s_suppkey = l_suppkey
  JOIN $partsupp ON ps_suppkey = l_suppkey AND ps_partkey = l_partkey
  JOIN $orders ON o_orderkey = l_orderkey
  JOIN $nation ON s_nationkey = n_nationkey
  WHERE p_name LIKE '%green%'
) profit
GROUP BY nation, o_year
ORDER BY nation, o_year DESC
"""

Q18 = """
SELECT c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice, sum(l_quantity) AS qty
FROM $customer
JOIN $orders ON c_custkey = o_custkey
JOIN $lineitem ON o_orderkey = l_orderkey
WHERE o_orderkey IN (
  SELECT l_orderkey FROM $lineitem GROUP BY l_orderkey HAVING sum(l_quantity) > 300
)
GROUP BY c_name, c_custkey, o_orderkey, o_orderdate, o_totalprice
ORDER BY o_totalprice DESC, o_orderdate, o_orderkey
LIMIT 100
"""

Q21 = """
SELECT s_name, count(*) AS numwait
FROM $supplier
JOIN $lineitem l1 ON s_suppkey = l1.l_suppkey
JOIN $orders ON o_orderkey = l1.l_orderkey
JOIN $nation ON s_nationkey = n_nationkey
WHERE o_orderstatus = 'F'
  AND l1.l_receiptdate > l1.l_commitdate
  AND EXISTS (
    SELECT 1 FROM $lineitem l2
    WHERE l2.l_orderkey = l1.l_orderkey AND l2.l_suppkey <> l1.l_suppkey
  )
  AND NOT EXISTS (
    SELECT 1 FROM $lineitem l3
    WHERE l3.l_orderkey = l1.l_orderkey AND l3.l_suppkey <> l1.l_suppkey
      AND l3.l_receiptdate > l3.l_commitdate
  )
  AND n_name = 'SAUDI ARABIA'
GROUP BY s_name
ORDER BY numwait DESC, s_name
LIMIT 100
"""

# ---------------------------------------------------------------- F2: SOC join suite
# Shapes implement the pre-registered specs in workloads/edr-sysmon (Family 3 asset
# enrichment) and workloads/cloud-vpcflow (Family 3 time-window correlation) on the
# pinned Zeek corpus.

J1_DIM_ENRICHMENT = """
SELECT a.criticality, count(*) AS conns, sum(c.orig_bytes) AS bytes_out
FROM $conn c
JOIN $assets a ON c.orig_h = a.ip
GROUP BY a.criticality
ORDER BY a.criticality
"""

J2_LARGE_LARGE_CORRELATION = """
SELECT count(*) AS pairs, sum(c.orig_bytes) AS bytes_out
FROM $conn c
JOIN $dns d
  ON c.orig_h = d.orig_h
 AND CAST(floor(c.ts / 300) AS BIGINT) = CAST(floor(d.ts / 300) AS BIGINT)
"""

J3_TWO_STREAMS_AGGREGATE = """
SELECT count(*) AS hosts, sum(x.rdp_cnt) AS rdp_conns, sum(y.dns_cnt) AS dns_queries
FROM (
  SELECT orig_h, count(*) AS rdp_cnt FROM $conn WHERE resp_p = 3389 GROUP BY orig_h
) x
JOIN (
  SELECT orig_h, count(*) AS dns_cnt FROM $dns GROUP BY orig_h
) y ON x.orig_h = y.orig_h
WHERE x.rdp_cnt > 30 AND y.dns_cnt > 50
"""

J4_IOC_SEMIJOIN = """
SELECT count(*) AS hits, sum(orig_bytes) AS bytes_out
FROM $conn
WHERE resp_h IN (SELECT ioc_value FROM $ioc)
"""
# column named ioc_value, not "indicator": INDICATOR is a Calcite reserved word
# (Dremio parse failure) and quoting it would silently break StarRocks (MySQL mode
# reads double-quoted identifiers as string literals)

# ---------------------------------------------------------------- F3: join-tax pair
# Identical answer two ways; per-engine tax = median(T_JOIN) / median(T_FLAT).

T_FLAT = """
SELECT criticality, count(*) AS conns, sum(orig_bytes) AS bytes_out
FROM $conn_enriched
WHERE proto = 'tcp'
GROUP BY criticality
ORDER BY criticality
"""

T_JOIN = """
SELECT a.criticality, count(*) AS conns, sum(c.orig_bytes) AS bytes_out
FROM $conn c
JOIN $assets a ON c.orig_h = a.ip
WHERE c.proto = 'tcp'
GROUP BY a.criticality
ORDER BY a.criticality
"""

QUERIES = {
    # family F1
    "tpch_q3": Q3, "tpch_q5": Q5, "tpch_q9": Q9, "tpch_q18": Q18, "tpch_q21": Q21,
    # family F2
    "soc_j1_dim_enrichment": J1_DIM_ENRICHMENT,
    "soc_j2_large_large": J2_LARGE_LARGE_CORRELATION,
    "soc_j3_two_streams": J3_TWO_STREAMS_AGGREGATE,
    "soc_j4_ioc_semijoin": J4_IOC_SEMIJOIN,
    # family F3
    "tax_t_flat": T_FLAT, "tax_t_join": T_JOIN,
}

FAMILIES = {
    "F1": ["tpch_q3", "tpch_q5", "tpch_q9", "tpch_q18", "tpch_q21"],
    "F2": ["soc_j1_dim_enrichment", "soc_j2_large_large", "soc_j3_two_streams",
           "soc_j4_ioc_semijoin"],
    "F3": ["tax_t_flat", "tax_t_join"],
}

TPCH_TABLES = ["lineitem", "orders", "customer", "supplier", "nation", "region",
               "part", "partsupp"]
SOC_TABLES = ["conn", "dns", "assets", "ioc", "conn_enriched"]


def render(sql: str, refs: dict) -> str:
    """Substitute $table placeholders with arm-specific table references.
    Longest-first so $conn_enriched is not clobbered by $conn."""
    for name in sorted(refs, key=len, reverse=True):
        sql = sql.replace(f"${name}", refs[name])
    return sql


def normalize(rows) -> list:
    """Normalize a result set for cross-engine answer equality: every cell to a string;
    floats/decimals rounded to 2 (monetary aggregates differ only in float-summation
    order, ~1e-10 relative); dates to ISO date strings."""
    out = []
    for row in rows:
        cells = []
        for v in row:
            if v is None:
                cells.append("NULL")
            elif isinstance(v, bool):
                cells.append(str(int(v)))
            elif isinstance(v, float):
                cells.append(f"{v:.2f}")
            elif isinstance(v, int):
                cells.append(str(v))
            else:
                s = str(v)
                # decimal-typed strings and datetime reprs
                try:
                    f = float(s)
                    cells.append(f"{f:.2f}" if "." in s or "e" in s.lower() else str(int(f)))
                except ValueError:
                    cells.append(s[:10] if _looks_like_date(s) else s)
        out.append(cells)
    return out


def _looks_like_date(s: str) -> bool:
    return len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-"


def answers_equal(a: list, b: list, float_tol: float = 0.02) -> bool:
    """Exact match after normalization, with ±0.02 absolute tolerance on numeric cells
    (last-cent float-summation wobble across engines; declared in README)."""
    if len(a) != len(b):
        return False
    for ra, rb in zip(a, b):
        if len(ra) != len(rb):
            return False
        for ca, cb in zip(ra, rb):
            if ca == cb:
                continue
            try:
                if abs(float(ca) - float(cb)) <= float_tol:
                    continue
            except ValueError:
                pass
            return False
    return True
