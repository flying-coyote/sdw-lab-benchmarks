#!/usr/bin/env python3
"""Seeded generator for the non-circular query distribution (deterministic-routing-noncircular).

Procedure (frozen in PREREGISTRATION.md):
  * 12 generator families, each a small set of parameterised templates written for this bench on the
    real ejs schema (TPC-H SF10 + soc.conn/dns/assets/ioc/conn_enriched). None of the 11 measured
    engine-join-specialization texts is used as a template; parameters (tables, join paths, group keys,
    filters, thresholds, bucket widths, LIMITs) are drawn from a seeded RNG; the template index within a
    family cycles deterministically (t = i mod n_templates) so every template is represented.
  * Each query carries the generator's own structural label (`family`), assigned here, never by the router.
  * Literal values (IPs, ports, segments, dates) are drawn from the value domains of the pinned parquet
    (assets.ip, conn port/proto domains, TPC-H spec domains); no engine is queried.
  * SQL discipline: one ANSI text per query with $table placeholders (substituted per arm), every
    derived table aliased, deterministic ORDER BY on any LIMIT, exact aggregates (count/sum/min/max)
    in outputs, no AVG/stddev in outputs, no engine-specific functions.
Output: queries/corpus.json (sorted, sha256 recorded in the pre-registration).
Run: ../.venv/bin/python gen_queries.py
"""
import hashlib
import json
import random
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).parent
EJS = HERE.parent / "engine-join-specialization" / "_work"
SEED = 20261115
rng = random.Random(SEED)

ASSET_IPS = sorted(pq.read_table(EJS / "soc" / "assets.parquet", columns=["ip"]).column("ip").to_pylist())
SITES = sorted(set(pq.read_table(EJS / "soc" / "assets.parquet", columns=["site"]).column("site").to_pylist()))
DEPTS = sorted(set(pq.read_table(EJS / "soc" / "assets.parquet", columns=["dept"]).column("dept").to_pylist()))
PORTS = [443, 80, 53, 3389, 22, 445, 25, 21, 123, 161]
CRIT = ["critical", "high", "medium", "low"]
SEV = ["low", "medium", "high"]
STATES = ["SF", "S1", "REJ", "OTH", "RSTO", "S0"]
SEGMENTS = ["AUTOMOBILE", "BUILDING", "FURNITURE", "HOUSEHOLD", "MACHINERY"]
REGIONS = ["AFRICA", "AMERICA", "ASIA", "EUROPE", "MIDDLE EAST"]
NATIONS = ["ALGERIA", "BRAZIL", "CANADA", "CHINA", "FRANCE", "GERMANY", "INDIA", "JAPAN", "KENYA", "PERU"]
SHIPMODES = ["AIR", "MAIL", "RAIL", "SHIP", "TRUCK", "FOB", "REG AIR"]
COLORS = ["green", "red", "blue", "ivory", "khaki", "navy", "olive"]
T0 = 1781080002  # conn/dns span start (floor), span ~3,770 s


def pick(xs):
    return rng.choice(xs)


def date_between(y0=1993, y1=1997):
    return f"{rng.randint(y0, y1)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"


# ------------------------------------------------------------------ families
def scan_agg(t):
    if t == 0:
        k = pick(["proto", "conn_state", "resp_p"])
        return (f"SELECT {k}, count(*) AS n_conn, sum(orig_bytes) AS b_out FROM $conn c "
                f"WHERE resp_p IN ({pick(PORTS)}, {pick(PORTS)}) GROUP BY {k} ORDER BY {k}")
    if t == 1:
        return (f"SELECT qtype, count(*) AS n_q, min(ts) AS first_ts FROM $dns d "
                f"WHERE ts > {T0 + rng.randint(0, 3000)} GROUP BY qtype ORDER BY qtype")
    if t == 2:
        k = pick(["l_returnflag", "l_linestatus", "l_shipmode"])
        return (f"SELECT {k}, count(*) AS n_l, sum(l_quantity) AS qty FROM $lineitem l "
                f"WHERE l_shipdate >= DATE '{date_between()}' GROUP BY {k} ORDER BY {k}")
    k = pick(["dept", "site", "criticality"])
    return (f"SELECT {k}, count(*) AS n_conn, sum(resp_bytes) AS b_in FROM $conn_enriched e "
            f"WHERE proto = '{pick(['tcp', 'udp'])}' GROUP BY {k} ORDER BY {k}")


def point_lookup(t):
    if t == 0:
        return (f"SELECT uid, orig_h, resp_h, resp_p, ts FROM $conn c WHERE orig_h = '{pick(ASSET_IPS)}' "
                f"ORDER BY uid LIMIT {pick([20, 50, 100])}")
    if t == 1:
        return (f"SELECT uid, resp_h, orig_bytes FROM $conn c WHERE orig_h = '{pick(ASSET_IPS)}' "
                f"AND resp_p = {pick(PORTS)} ORDER BY uid LIMIT {pick([10, 25])}")
    if t == 2:
        return (f"SELECT orig_h, query, ts FROM $dns d WHERE orig_h = '{pick(ASSET_IPS)}' "
                f"ORDER BY ts, query LIMIT {pick([20, 50])}")
    return (f"SELECT l_orderkey, l_linenumber, l_quantity FROM $lineitem l "
            f"WHERE l_orderkey = {rng.randint(1, 60_000_000)} ORDER BY l_linenumber LIMIT 10")


def dim_enrichment(t):
    k = pick(["site", "dept", "criticality"])
    if t == 0:
        return (f"SELECT a.{k}, count(*) AS n_conn, sum(c.orig_bytes) AS b_out FROM $conn c "
                f"JOIN $assets a ON c.orig_h = a.ip WHERE c.resp_p = {pick(PORTS)} GROUP BY a.{k} ORDER BY a.{k}")
    if t == 1:
        return (f"SELECT a.{k}, count(*) AS n_q FROM $dns d JOIN $assets a ON d.orig_h = a.ip "
                f"WHERE d.qtype = '{pick(['A', 'AAAA', 'CNAME'])}' GROUP BY a.{k} ORDER BY a.{k}")
    if t == 2:
        return (f"SELECT s.s_nationkey, count(*) AS n_l, sum(l.l_extendedprice) AS rev FROM $lineitem l "
                f"JOIN $supplier s ON l.l_suppkey = s.s_suppkey WHERE l.l_shipmode = '{pick(SHIPMODES)}' "
                f"GROUP BY s.s_nationkey ORDER BY s.s_nationkey")
    return (f"SELECT c.c_mktsegment, count(*) AS n_o, sum(o.o_totalprice) AS tot FROM $orders o "
            f"JOIN $customer c ON o.o_custkey = c.c_custkey WHERE o.o_orderdate < DATE '{date_between()}' "
            f"GROUP BY c.c_mktsegment ORDER BY c.c_mktsegment")


def ioc_match(t):
    sev = pick(SEV)
    if t == 0:  # join form
        return (f"SELECT i.severity, count(*) AS hits, sum(c.orig_bytes) AS b_out FROM $conn c "
                f"JOIN $ioc i ON c.resp_h = i.ioc_value WHERE i.severity <> '{sev}' GROUP BY i.severity ORDER BY i.severity")
    if t == 1:  # IN-subquery form
        return (f"SELECT c.resp_p, count(*) AS hits FROM $conn c WHERE c.resp_h IN "
                f"(SELECT i.ioc_value FROM $ioc i WHERE i.severity = '{sev}') GROUP BY c.resp_p ORDER BY c.resp_p")
    if t == 2:  # dns answers vs ioc
        return (f"SELECT d.qtype, count(*) AS hits FROM $dns d JOIN $ioc i ON d.answer = i.ioc_value "
                f"WHERE i.source = '{pick(['osint-feed-a', 'osint-feed-b', 'internal'])}' GROUP BY d.qtype ORDER BY d.qtype")
    return (f"SELECT count(*) AS hits, sum(c.resp_bytes) AS b_in FROM $conn c WHERE c.resp_p = {pick(PORTS)} "
            f"AND c.resp_h IN (SELECT i.ioc_value FROM $ioc i)")


def two_stream(t):
    p = pick(PORTS)
    a, b = rng.randint(5, 40), rng.randint(20, 80)
    if t == 0:
        return (f"SELECT count(*) AS hosts, sum(x.n_c) AS conns, sum(y.n_d) AS dnsq FROM "
                f"(SELECT orig_h, count(*) AS n_c FROM $conn WHERE resp_p = {p} GROUP BY orig_h) x JOIN "
                f"(SELECT orig_h, count(*) AS n_d FROM $dns GROUP BY orig_h) y ON x.orig_h = y.orig_h "
                f"WHERE x.n_c > {a} AND y.n_d > {b}")
    return (f"SELECT count(*) AS hosts, sum(x.n_dst) AS dsts FROM "
            f"(SELECT orig_h, count(DISTINCT resp_h) AS n_dst FROM $conn WHERE proto = 'tcp' GROUP BY orig_h) x JOIN "
            f"(SELECT orig_h, count(DISTINCT query) AS n_qn FROM $dns GROUP BY orig_h) y ON x.orig_h = y.orig_h "
            f"WHERE x.n_dst > {a * 10} AND y.n_qn > {b // 2}")


def large_large(t):
    if t == 0:
        w = pick([60, 300, 600])
        return (f"SELECT count(*) AS pairs, sum(c.orig_bytes) AS b_out FROM $conn c JOIN $dns d "
                f"ON c.orig_h = d.orig_h AND CAST(floor(c.ts / {w}) AS BIGINT) = CAST(floor(d.ts / {w}) AS BIGINT) "
                f"WHERE c.resp_p = {pick(PORTS)}")
    if t == 1:
        return (f"SELECT e.criticality, count(*) AS n_pair, sum(c.duration) AS dur FROM $conn c "
                f"JOIN $conn_enriched e ON c.uid = e.uid WHERE c.conn_state = '{pick(STATES)}' "
                f"GROUP BY e.criticality ORDER BY e.criticality")
    return (f"SELECT count(*) AS n_pair, sum(l.l_quantity) AS qty FROM $lineitem l JOIN $orders o "
            f"ON l.l_orderkey = o.o_orderkey WHERE o.o_orderdate >= DATE '{date_between()}' "
            f"AND l.l_shipmode = '{pick(SHIPMODES)}'")


def join_3to4(t):
    if t == 0:  # customer-orders-lineitem, varied key
        k = pick(["o.o_orderpriority", "c.c_mktsegment", "l.l_returnflag", "l.l_shipmode"])
        return (f"SELECT {k}, count(*) AS n_l, sum(l.l_extendedprice * (1 - l.l_discount)) AS rev "
                f"FROM $customer c JOIN $orders o ON c.c_custkey = o.o_custkey JOIN $lineitem l ON l.l_orderkey = o.o_orderkey "
                f"WHERE o.o_orderdate >= DATE '{date_between()}' GROUP BY {k} ORDER BY {k}")
    if t == 1:  # partsupp-part-supplier
        return (f"SELECT s.s_nationkey, count(*) AS n_ps, sum(ps.ps_availqty) AS avail FROM $partsupp ps "
                f"JOIN $part p ON ps.ps_partkey = p.p_partkey JOIN $supplier s ON ps.ps_suppkey = s.s_suppkey "
                f"WHERE p.p_name LIKE '%{pick(COLORS)}%' GROUP BY s.s_nationkey ORDER BY s.s_nationkey")
    if t == 2:  # orders-lineitem-supplier-nation (4 tables)
        return (f"SELECT n.n_name, count(*) AS n_l, sum(l.l_quantity) AS qty FROM $orders o "
                f"JOIN $lineitem l ON l.l_orderkey = o.o_orderkey JOIN $supplier s ON l.l_suppkey = s.s_suppkey "
                f"JOIN $nation n ON s.s_nationkey = n.n_nationkey WHERE o.o_orderstatus = '{pick(['F', 'O', 'P'])}' "
                f"GROUP BY n.n_name ORDER BY n.n_name")
    if t == 3:  # customer-orders-lineitem-supplier with the dual (nation) key: the q5-class many-to-many edge
        return (f"SELECT s.s_nationkey, count(*) AS n_l, sum(l.l_extendedprice) AS rev FROM $customer c "
                f"JOIN $orders o ON c.c_custkey = o.o_custkey JOIN $lineitem l ON l.l_orderkey = o.o_orderkey "
                f"JOIN $supplier s ON l.l_suppkey = s.s_suppkey AND c.c_nationkey = s.s_nationkey "
                f"WHERE o.o_orderdate >= DATE '{date_between()}' AND c.c_mktsegment = '{pick(SEGMENTS)}' "
                f"GROUP BY s.s_nationkey ORDER BY s.s_nationkey")
    # SOC 3-table: conn-assets-ioc
    return (f"SELECT a.{pick(['site', 'dept', 'criticality'])} AS grp, count(*) AS hits FROM $conn c "
            f"JOIN $assets a ON c.orig_h = a.ip JOIN $ioc i ON c.resp_h = i.ioc_value "
            f"WHERE i.severity = '{pick(SEV)}' GROUP BY grp ORDER BY grp")


def join_5to6(t):
    if t == 0:  # customer-orders-lineitem-supplier-nation(-region), dual key
        reg = rng.random() < 0.5
        tail = (f"JOIN $region r ON n.n_regionkey = r.r_regionkey WHERE r.r_name = '{pick(REGIONS)}' AND "
                if reg else "WHERE ")
        return (f"SELECT n.n_name, sum(l.l_extendedprice * (1 - l.l_discount)) AS rev FROM $customer c "
                f"JOIN $orders o ON c.c_custkey = o.o_custkey JOIN $lineitem l ON l.l_orderkey = o.o_orderkey "
                f"JOIN $supplier s ON l.l_suppkey = s.s_suppkey AND c.c_nationkey = s.s_nationkey "
                f"JOIN $nation n ON s.s_nationkey = n.n_nationkey {tail}"
                f"o.o_orderdate >= DATE '{date_between()}' GROUP BY n.n_name ORDER BY n.n_name")
    if t == 1:  # part-lineitem-partsupp-supplier-nation
        return (f"SELECT n.n_name, sum(l.l_extendedprice - ps.ps_supplycost * l.l_quantity) AS profit FROM $part p "
                f"JOIN $lineitem l ON p.p_partkey = l.l_partkey JOIN $partsupp ps ON ps.ps_partkey = l.l_partkey AND ps.ps_suppkey = l.l_suppkey "
                f"JOIN $supplier s ON s.s_suppkey = l.l_suppkey JOIN $nation n ON s.s_nationkey = n.n_nationkey "
                f"WHERE p.p_name LIKE '%{pick(COLORS)}%' GROUP BY n.n_name ORDER BY n.n_name")
    # orders-lineitem-supplier-nation-region (no dual key)
    return (f"SELECT r.r_name, count(*) AS n_l, sum(l.l_quantity) AS qty FROM $orders o "
            f"JOIN $lineitem l ON l.l_orderkey = o.o_orderkey JOIN $supplier s ON l.l_suppkey = s.s_suppkey "
            f"JOIN $nation n ON s.s_nationkey = n.n_nationkey JOIN $region r ON n.n_regionkey = r.r_regionkey "
            f"WHERE l.l_shipmode = '{pick(SHIPMODES)}' GROUP BY r.r_name ORDER BY r.r_name")


def topn_agg(t):
    n = pick([10, 20, 50])
    if t == 0:
        return (f"SELECT c.orig_h, sum(c.orig_bytes) AS b_out FROM $conn c JOIN $assets a ON c.orig_h = a.ip "
                f"WHERE a.criticality = '{pick(CRIT)}' GROUP BY c.orig_h ORDER BY b_out DESC, c.orig_h LIMIT {n}")
    if t == 1:
        return (f"SELECT o.o_custkey, sum(l.l_quantity) AS qty FROM $orders o JOIN $lineitem l ON o.o_orderkey = l.l_orderkey "
                f"WHERE o.o_orderdate >= DATE '{date_between()}' GROUP BY o.o_custkey ORDER BY qty DESC, o.o_custkey LIMIT {n}")
    if t == 2:
        return (f"SELECT c.c_name, c.c_custkey, sum(o.o_totalprice) AS tot FROM $customer c JOIN $orders o ON c.c_custkey = o.o_custkey "
                f"JOIN $nation n ON c.c_nationkey = n.n_nationkey WHERE n.n_name = '{pick(NATIONS)}' "
                f"GROUP BY c.c_name, c.c_custkey HAVING sum(o.o_totalprice) > {rng.randint(2, 6)}000000 "
                f"ORDER BY tot DESC, c.c_custkey LIMIT {n}")
    return (f"SELECT d.orig_h, count(*) AS n_q FROM $dns d JOIN $assets a ON d.orig_h = a.ip "
            f"WHERE a.dept = '{pick(DEPTS)}' GROUP BY d.orig_h ORDER BY n_q DESC, d.orig_h LIMIT {n}")


def correlated_exists(t):
    if t == 0:  # orders with a late line (q4-like shape, written fresh)
        return (f"SELECT o.o_orderpriority, count(*) AS n_o FROM $orders o WHERE o.o_orderdate >= DATE '{date_between()}' "
                f"AND EXISTS (SELECT 1 FROM $lineitem l WHERE l.l_orderkey = o.o_orderkey AND l.l_commitdate < l.l_receiptdate) "
                f"GROUP BY o.o_orderpriority ORDER BY o.o_orderpriority")
    if t == 1:  # assets that talked to a port
        return (f"SELECT a.criticality, count(*) AS n_hosts FROM $assets a WHERE EXISTS "
                f"(SELECT 1 FROM $conn c WHERE c.orig_h = a.ip AND c.resp_p = {pick(PORTS)}) "
                f"GROUP BY a.criticality ORDER BY a.criticality")
    if t == 2:  # assets with conns but NOT EXISTS dns
        return (f"SELECT a.site, count(*) AS n_hosts FROM $assets a WHERE a.dept = '{pick(DEPTS)}' AND NOT EXISTS "
                f"(SELECT 1 FROM $dns d WHERE d.orig_h = a.ip AND d.qtype = '{pick(['CNAME', 'AAAA'])}') "
                f"GROUP BY a.site ORDER BY a.site")
    return (f"SELECT s.s_nationkey, count(*) AS n_s FROM $supplier s WHERE NOT EXISTS "
            f"(SELECT 1 FROM $partsupp ps WHERE ps.ps_suppkey = s.s_suppkey AND ps.ps_availqty < {rng.randint(10, 60)}) "
            f"GROUP BY s.s_nationkey ORDER BY s.s_nationkey")


def ueba_two_level(t):
    """UEBA-style two-level aggregation: per entity per time bucket -> per entity baseline -> flag.
    Peak-vs-mean is tested in integer arithmetic (peak * n_buckets > k * total) so no float boundary."""
    w = pick([60, 120, 300, 600])
    k = rng.randint(2, 4)
    if t == 0:
        return (f"SELECT count(*) AS hosts, sum(h.peak) AS peak_sum FROM (SELECT b.orig_h, max(b.n_c) AS peak, "
                f"sum(b.n_c) AS total, count(*) AS nb FROM (SELECT orig_h, CAST(floor(ts / {w}) AS BIGINT) AS bkt, "
                f"count(*) AS n_c FROM $conn WHERE resp_p = {pick(PORTS)} GROUP BY orig_h, CAST(floor(ts / {w}) AS BIGINT)) b "
                f"GROUP BY b.orig_h) h WHERE h.peak * h.nb > {k} * h.total")
    if t == 1:
        return (f"SELECT count(*) AS hosts, sum(h.peak) AS peak_sum FROM (SELECT b.orig_h, max(b.b_out) AS peak, "
                f"sum(b.b_out) AS total, count(*) AS nb FROM (SELECT orig_h, CAST(floor(ts / {w}) AS BIGINT) AS bkt, "
                f"sum(orig_bytes) AS b_out FROM $conn GROUP BY orig_h, CAST(floor(ts / {w}) AS BIGINT)) b "
                f"GROUP BY b.orig_h) h WHERE h.peak * h.nb > {k} * h.total")
    if t == 2:
        return (f"SELECT count(*) AS hosts, sum(h.peak) AS peak_sum FROM (SELECT b.orig_h, max(b.n_q) AS peak, "
                f"sum(b.n_q) AS total, count(*) AS nb FROM (SELECT orig_h, CAST(floor(ts / {w}) AS BIGINT) AS bkt, "
                f"count(*) AS n_q FROM $dns WHERE qtype = '{pick(['A', 'AAAA', 'CNAME'])}' GROUP BY orig_h, CAST(floor(ts / {w}) AS BIGINT)) b "
                f"GROUP BY b.orig_h) h WHERE h.peak * h.nb > {k} * h.total")
    # per-dept baseline: two-level with a dimension join
    return (f"SELECT h.dept, count(*) AS hosts, sum(h.peak) AS peak_sum FROM (SELECT a.dept, b.orig_h, max(b.n_c) AS peak, "
            f"sum(b.n_c) AS total, count(*) AS nb FROM (SELECT orig_h, CAST(floor(ts / {w}) AS BIGINT) AS bkt, count(*) AS n_c "
            f"FROM $conn GROUP BY orig_h, CAST(floor(ts / {w}) AS BIGINT)) b JOIN $assets a ON b.orig_h = a.ip "
            f"GROUP BY a.dept, b.orig_h) h WHERE h.peak * h.nb > {k} * h.total GROUP BY h.dept ORDER BY h.dept")


def window_seq(t):
    p = pick(PORTS)
    if t == 0:  # inter-arrival regularity, beacon-ish
        g = pick([5, 10, 30])
        return (f"SELECT count(*) AS n_gaps FROM (SELECT orig_h, ts - lag(ts) OVER (PARTITION BY orig_h ORDER BY ts, uid) AS gap "
                f"FROM $conn WHERE resp_p = {p}) g WHERE g.gap < {g}")
    return (f"SELECT count(*) AS n_first, sum(f.orig_bytes) AS b_out FROM (SELECT orig_h, orig_bytes, "
            f"row_number() OVER (PARTITION BY orig_h ORDER BY ts, uid) AS rn FROM $conn WHERE resp_p = {p}) f WHERE f.rn = 1")


FAMILIES = [  # (family label, builder, n_templates, count); template index cycles t = i % n_templates
    ("scan_agg", scan_agg, 4, 8), ("point_lookup", point_lookup, 4, 4), ("dim_enrichment", dim_enrichment, 4, 8),
    ("ioc_match", ioc_match, 4, 8), ("two_stream", two_stream, 2, 6), ("large_large", large_large, 3, 6),
    ("join_3to4", join_3to4, 5, 10), ("join_5to6", join_5to6, 3, 6), ("topn_agg", topn_agg, 4, 8),
    ("correlated_exists", correlated_exists, 4, 8), ("ueba_two_level", ueba_two_level, 4, 8),
    ("window_seq", window_seq, 2, 4),
]


def main():
    out, seen = [], set()
    for fam, fn, nt, n in FAMILIES:
        i = 0
        tries = 0
        while i < n:
            tries += 1
            sql = " ".join(fn(i % nt).split())
            if sql in seen and tries < 200:
                continue
            seen.add(sql)
            i += 1
            out.append({"id": f"{fam}_{i:02d}", "family": fam, "sql": sql})
    body = json.dumps({"seed": SEED, "n": len(out), "queries": out}, indent=1, sort_keys=True)
    p = HERE / "queries" / "corpus.json"
    p.write_text(body + "\n")
    print(len(out), "queries ->", p, hashlib.sha256(p.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
