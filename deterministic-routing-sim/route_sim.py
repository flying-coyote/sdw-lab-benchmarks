#!/usr/bin/env python3
"""Deterministic-routing SIMULATION for H-DETERMINISTIC-ROUTING-01 (lab-free, no engines).

The hypothesis: ordered, auditable, deterministic rules — (R1) time predicate → hot/cold tier,
(R2) parsed query shape Trino-Gateway-style → the measured per-shape winner, (R3) Iceberg manifest
statistics as the only cross-engine cost signal — can assign >=90% of SOC-shaped queries to the
engine the join bench measured as that shape's winner, with the residual misroute cost bounded by
the compressed spread, so the *catastrophic* misroute class reduces to (a) the layout cliffs (the q5
stats-less-native DNF) and (b) the hot/cold tier boundary, both of which the rules key on directly.

This does NOT query engines. It checks the ROUTER'S PICK against the recorded per-(shape,tier)
winners in engine-join-specialization/results/RESULTS.md (and the flagship/needle results). It then
stresses the router with the five production misrouting modes Gemini DR-5 named (2026-06-15):
  1. view obfuscation (a thin SELECT hides a heavy join the AST router never sees)
  2. time-predicate masking (CAST/func around the time column defeats the static extractor)
  3. literal blindness / data skew (fingerprinting strips the literal that sets the cost)
  4. dynamic functions (NOW()/CURRENT_TIMESTAMP can't be statically evaluated at routing time)
  5. cross-engine dialect mismatch (syntactically routable, executes only on one dialect)

HONESTY CAVEATS baked into the output:
  - The ground-truth winner map is a ~10-shape lookup table from ONE host (Tier B, single host,
    2026-06-10 join bench). So high "templated accuracy" is partly circular: the templated corpus
    IS the shapes that were measured. That is exactly DR-5's point — the >=90% in production is a
    denominator artifact of templated traffic. The falsifiable contribution is the PER-MODE
    DEGRADATION and whether R3 (manifest stats) closes the catastrophic modes (1 and the q5 cliff),
    NOT the headline accuracy number.
  - This is a routing-decision simulation, not a live multi-engine routing measurement. Tier B-/sim.

Run: ../.venv/bin/python route_sim.py
"""
import json
import re
from datetime import date
from pathlib import Path

import sqlglot
from sqlglot import exp

OUT = Path(__file__).parent / "results"
NOW_REF = date(2026, 6, 15)   # fixed reference "now" for the sim (deterministic / reproducible)
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

# ── Ground truth: per-(shape, tier) winner, from engine-join-specialization/results/RESULTS.md ──
# Engines: starrocks (SR), clickhouse_iceberg (CHI), clickhouse_native (CHN), trino, dremio.
# tier 'hot'  = recent window → native MergeTree eligible (CHN) ; tier 'cold' = deep history → Iceberg engines.
# A shape may have a CLIFF: an engine that DNFs/timeouts for that shape (the catastrophic class).
# "tie" winners list >1 acceptable engine (a tie was statistically un-claimable in the bench).
WINNERS = {
    # shape:                 (hot-tier winners,            cold-tier winners,        cliff engines for this shape)
    "join_3table":           (["clickhouse_native"],       ["starrocks"],            []),                       # q3 SR cold; CHN 1.364 hot
    "join_6table":           (["starrocks"],               ["starrocks"],            ["clickhouse_native"]),    # q5/q9; CHN DNF on q5 = THE cliff
    "aggjoin":               (["clickhouse_native"],       ["clickhouse_iceberg"],   []),                       # q18 CHN 1.186 hot / CHI 1.485 cold
    "correlated_exists":     (["starrocks"],               ["starrocks"],            []),                       # q21 SR
    "dim_enrichment":        (["clickhouse_native"],       ["starrocks"],            []),                       # j1 CHN 0.126 hot / SR 0.167 cold
    "large_large":           (["starrocks", "clickhouse_iceberg", "clickhouse_native"],
                                                            ["starrocks", "clickhouse_iceberg"], []),           # j2 three-way tie
    "two_stream_aggjoin":    (["clickhouse_native", "clickhouse_iceberg"],
                                                            ["clickhouse_iceberg"],  []),                       # j3 CH tie
    "ioc_semijoin":          (["clickhouse_native"],       ["starrocks", "clickhouse_iceberg"], []),            # j4 CHN 0.069 hot / SR~CHI tie cold
    "scan_aggregation":      (["clickhouse_native"],       ["clickhouse_iceberg"],   []),                       # flagship CHN 0.061 / CHI 0.282
    "point_lookup":          (["clickhouse_native"],       ["clickhouse_iceberg"],   []),                       # needle: sorted-native ties index
}

# Manifest-stat stub: approximate scan rows per base table (the only cross-engine cost signal R3
# reads). Iceberg manifests give exact per-file row counts in ms without asking any engine. Also a
# view→underlying-shape map: whether the router can resolve a view to its base scan (DR-5 mode 1
# says generic AST routers DON'T — they never consult the catalog/metastore before routing).
TABLE_ROWS = {"conn": 10_000_000, "conn_10m": 10_000_000, "iocs": 1_000_000, "dim_host": 14_800,
              "lineitem": 60_000_000, "orders": 15_000_000, "customer": 1_500_000}
NATIVE_CLIFF_ROWS = 40_000_000     # above this fan-out, native MergeTree risks the q5-class timeout
VIEWS = {  # view name -> (true underlying shape, true scan rows). The router only "sees" these if it resolves views.
    "soc_summary_v": ("join_6table", 60_000_000),   # a thin SELECT * hiding a 6-table join (mode 1)
}
HOT_WINDOW_DAYS = 7


class Router:
    """Ordered deterministic rules. resolve_views and use_manifest_stats are toggles so the sim can
    measure each rule's contribution (the DR's claim is that R3/manifest is what saves the cliffs)."""

    def __init__(self, use_catalog=True):
        # use_catalog (R3) = "consult the Iceberg catalog/manifest before routing": resolve views to
        # their true underlying shape and read manifest scan stats. The DR-5 mode-1 point is that a
        # generic AST router does NOT do this. Toggling it isolates R3's contribution.
        self.use_catalog = use_catalog
        self.resolve_views = use_catalog
        self.use_manifest_stats = use_catalog

    # ---- R1: time tier ----
    def time_tier(self, tree):
        """Return 'hot' / 'cold' / 'default'(=cold, but flagged as a parse-failure fallback).
        Static extraction only: a time column compared to a literal date/interval. A function-wrapped
        column (mode 2) or a dynamic NOW() (mode 4) is NOT statically evaluable -> 'default'."""
        for cmp in tree.find_all(exp.LT, exp.LTE, exp.GT, exp.GTE, exp.EQ, exp.Between):
            cols = list(cmp.find_all(exp.Column))
            if not any(self._is_time_col(c) for c in cols):
                continue
            # is the time column wrapped in a function/cast? (mode 2 -> cannot extract a boundary)
            if self._time_col_wrapped(cmp):
                return "default"
            # does the comparison value contain a non-evaluable dynamic func? (mode 4)
            if self._has_dynamic_func(cmp):
                return "default"
            # static literal boundary present -> decide hot/cold by the window it implies
            return self._window_tier(cmp)
        return "default"

    def _is_time_col(self, col):
        return col.name.lower() in {"ts", "_time", "__time", "time", "ingest_time", "event_time", "day"}

    def _time_col_wrapped(self, cmp):
        # the time column appears inside a Func/Cast node (not as a bare column child of the comparison)
        for fn in cmp.find_all(exp.Func, exp.Cast):
            if any(self._is_time_col(c) for c in fn.find_all(exp.Column)):
                return True
        return False

    def _has_dynamic_func(self, cmp):
        names = {"now", "current_timestamp", "current_date", "today", "getdate", "sysdate"}
        for fn in cmp.find_all(exp.Func, exp.Anonymous, exp.CurrentTimestamp, exp.CurrentDate):
            nm = (fn.name or fn.sql_name() if hasattr(fn, "sql_name") else fn.name) or ""
            if str(nm).lower() in names:
                return True
        # textual fallback for NOW()/CURRENT_TIMESTAMP that parse as keywords
        s = cmp.sql().lower()
        return any(k in s for k in ("now(", "current_timestamp", "current_date"))

    def _window_tier(self, cmp):
        """Decide hot/cold by the depth of the window the predicate implies vs NOW_REF — the core of
        R1 (recent window → hot engine, deep history → lakehouse). A static date literal within
        HOT_WINDOW_DAYS of now = hot; an older lower-bound = cold (deep history)."""
        s = cmp.sql().lower()
        if "interval" in s:   # relative interval with a static anchor (not NOW() — that's caught upstream as dynamic)
            if any(u in s for u in ("year", "month", "week")):
                return "cold"
            return "hot"       # day/hour/minute interval = recent
        m = _DATE_RE.search(s)   # absolute date literal: compare to NOW_REF
        if m:
            y, mo, d = (int(g) for g in m.groups())
            try:
                depth_days = (NOW_REF - date(y, mo, d)).days
                return "hot" if 0 <= depth_days <= HOT_WINDOW_DAYS else "cold"
            except ValueError:
                pass
        return "cold"   # no extractable boundary on a recognized time col -> safe default = lakehouse tier

    # ---- R2: shape ----
    def shape(self, tree):
        """Classify the query shape from the AST (Trino-Gateway-style: structural, no data)."""
        # view obfuscation: a single-table SELECT over a known heavy view
        from_tbls = [t.name.lower() for t in tree.find_all(exp.Table)]
        if self.resolve_views:
            for t in from_tbls:
                if t in VIEWS:
                    return VIEWS[t][0]   # router resolved the view to its true shape
        joins = list(tree.find_all(exp.Join))
        tables = set(from_tbls)
        has_agg = bool(list(tree.find_all(exp.AggFunc)) or tree.find(exp.Group))
        has_corr_exists = bool(tree.find(exp.Exists))
        has_distinct = bool(tree.find(exp.Distinct))
        has_having = bool(tree.find(exp.Having))
        has_topn = bool(tree.find(exp.Group) and tree.find(exp.Order) and tree.find(exp.Limit))
        is_topn_agg = has_having or has_topn   # the "agg-join" / top-N aggregation shape (q18)
        limit = tree.find(exp.Limit)
        is_point = bool(limit) and not has_agg and len(joins) == 0
        n_tbl = len(tables)
        # order matters (first match wins), mirroring an ordered rule list
        if has_corr_exists:
            return "correlated_exists"
        if len(joins) >= 4 or n_tbl >= 5:
            return "join_6table"
        if len(joins) == 2 or n_tbl in (3, 4):
            # distinguish the top-N aggregation shape (q18, CH wins) from a plain multi-table join
            # that merely groups (q3, SR wins). A shape-only router CANNOT separate a plain GROUP BY
            # multi-table join from q3 — that residual conflation is a genuine finding, not overfit.
            if is_topn_agg:
                return "aggjoin"
            return "join_3table"
        if len(joins) == 1:
            # one join: dim-enrichment (small dim) vs large-large vs ioc semi vs two-stream agg
            if has_agg and has_distinct:
                return "two_stream_aggjoin"
            if any(t in ("iocs",) for t in tables):
                return "ioc_semijoin"
            if any(t in ("dim_host",) for t in tables):
                return "dim_enrichment"
            return "large_large"
        # no joins
        if is_point:
            return "point_lookup"
        return "scan_aggregation"

    # ---- R3: manifest-stat cost signal (the only cross-engine cost input) ----
    def scan_rows(self, tree):
        """Estimate scan rows from the Iceberg manifest stub. If the router resolves views it sees the
        true underlying scan; otherwise it only sees the thin view's apparent (tiny) scan -> blind."""
        rows = 0
        for t in tree.find_all(exp.Table):
            nm = t.name.lower()
            if nm in VIEWS:
                rows += VIEWS[nm][1] if self.resolve_views else 1  # blind to the hidden join if not resolving
            else:
                rows += TABLE_ROWS.get(nm, 100_000)
        return rows

    # ---- routing decision ----
    def route(self, sql, dialect=None):
        tree = sqlglot.parse_one(sql, dialect=dialect)
        tier = self.time_tier(tree)
        eff_tier = "cold" if tier in ("cold", "default") else "hot"
        shape = self.shape(tree)
        hot_w, cold_w, cliff = WINNERS[shape]
        winners = hot_w if eff_tier == "hot" else cold_w
        pick = winners[0]
        applied = ["R1:%s" % tier, "R2:%s" % shape]
        # R3: the manifest scan-row signal is REPORTED for transparency, but note it does NOT cleanly
        # predict the q5 native cliff — that cliff is a JOIN-CARDINALITY explosion (q5 DNFs on native;
        # q9, a 6-table join with near-identical SCAN size, completes), so scan rows can't separate
        # them. The cliff is avoided STRUCTURALLY: the shape→winner map never routes a join_6table to
        # native. R3's measured value here is the upstream view-resolution (catalog consult) that lets
        # R2 see the true shape in the first place (mode 1) — without it the hidden join is read as a
        # cheap scan and lands on the native cliff.
        if self.use_manifest_stats:
            applied.append("R3:scan=%d" % self.scan_rows(tree))
        else:
            applied.append("R3:off(no-catalog)")
        return {"pick": pick, "tier_decided": tier, "eff_tier": eff_tier, "shape": shape,
                "winners_for_cell": winners, "cliff": cliff, "rules": applied}


def classify(outcome_pick, expected_tier, q):
    """correct / minor_misroute / catastrophic_misroute, vs the recorded winners + cliff."""
    shape = q["shape"]
    hot_w, cold_w, cliff = WINNERS[shape]
    winners = hot_w if expected_tier == "hot" else cold_w
    if outcome_pick in cliff:
        return "catastrophic_misroute"     # routed to an engine that DNFs this shape (the q5 class)
    if outcome_pick in winners:
        return "correct"
    # wrong engine but not a cliff: still answers within the compressed spread (0.07-1.41s SOC)
    return "minor_misroute"


# ── Corpus ──────────────────────────────────────────────────────────────────────────────────────
# Each query: id, mode ('templated' or one of the 5), sql, expected_tier (the GROUND-TRUTH tier the
# query really belongs to), shape (for scoring), and dialect (for the dialect-mismatch mode).
TEMPLATED = [
    # canonical clean forms — clean time bound + plain shape (the >=90% denominator)
    ("t_q3",  "join_3table",       "cold", "SELECT o.k, sum(l.amt) FROM orders o JOIN lineitem l ON o.k=l.k JOIN customer c ON o.c=c.k WHERE o.ts > DATE '2025-01-01' GROUP BY o.k"),
    ("t_q5",  "join_6table",       "cold", "SELECT n.nm, sum(l.amt) FROM orders o JOIN lineitem l ON o.k=l.k JOIN customer c ON o.c=c.k JOIN nation n ON c.n=n.k JOIN region r ON n.r=r.k JOIN supplier s ON l.s=s.k WHERE o.ts > DATE '2025-01-01' GROUP BY n.nm"),
    ("t_q9",  "join_6table",       "cold", "SELECT n.nm, sum(l.amt) FROM lineitem l JOIN supplier s ON l.s=s.k JOIN partsupp ps ON l.p=ps.p JOIN part p ON l.p=p.k JOIN orders o ON l.k=o.k JOIN nation n ON s.n=n.k WHERE o.ts > DATE '2025-01-01' GROUP BY n.nm"),
    ("t_q18", "aggjoin",           "hot",  "SELECT c.nm, sum(l.amt) FROM customer c JOIN orders o ON c.k=o.c JOIN lineitem l ON o.k=l.k WHERE o.ts > DATE '2026-06-10' GROUP BY c.nm HAVING sum(l.amt) > 100 LIMIT 100"),
    ("t_q21", "correlated_exists", "cold", "SELECT s.nm FROM supplier s WHERE EXISTS (SELECT 1 FROM lineitem l WHERE l.s=s.k AND l.ts > DATE '2025-01-01')"),
    ("t_j1",  "dim_enrichment",    "hot",  "SELECT c.orig_h, d.hostname FROM conn c JOIN dim_host d ON c.orig_h=d.ip WHERE c.ts > DATE '2026-06-13'"),
    ("t_j2",  "large_large",       "cold", "SELECT a.orig_h, count(*) FROM conn a JOIN conn b ON a.orig_h=b.resp_h WHERE a.ts > DATE '2025-06-01' GROUP BY a.orig_h"),
    ("t_j3",  "two_stream_aggjoin","cold", "SELECT c.proto, count(DISTINCT c.resp_p) FROM conn c JOIN conn d ON c.orig_h=d.orig_h WHERE c.ts > DATE '2025-06-01' GROUP BY c.proto"),
    ("t_j4",  "ioc_semijoin",      "hot",  "SELECT c.orig_h FROM conn c JOIN iocs i ON c.resp_h=i.ip WHERE c.ts > DATE '2026-06-14'"),
    ("t_scan","scan_aggregation",  "cold", "SELECT proto, count(*) FROM conn WHERE ts > DATE '2025-01-01' GROUP BY proto ORDER BY 2 DESC"),
    ("t_pt",  "point_lookup",      "hot",  "SELECT orig_h, resp_h, ts FROM conn WHERE resp_p = 3389 AND ts > DATE '2026-06-14' LIMIT 100"),
]

# Adversarial: each rewrites a templated query to trigger exactly one mode. expected_tier/shape are
# the TRUE values (what the query really is); the router may now get them wrong.
ADVERSARIAL = [
    # mode 1 — view obfuscation: a thin, recent-looking SELECT over a view that hides a 6-table join.
    # Recent date => an AST-only router sends it to the hot/native cluster, where it hits the
    # join_6table cliff (the DR's OOM scenario). True: join_6table, hot.
    ("m1_view", "view_obfuscation", "hot", "join_6table",
     "SELECT * FROM soc_summary_v WHERE day = DATE '2026-06-14'"),
    # mode 2 — time-predicate masking: CAST wraps the time column -> static extractor fails (true: point_lookup, hot)
    ("m2_mask", "time_predicate_masking", "hot", "point_lookup",
     "SELECT orig_h, resp_h, ts FROM conn WHERE resp_p = 3389 AND CAST(ts AS DATE) = DATE '2026-06-14' LIMIT 100"),
    # mode 3 — literal blindness / skew: same shape as j4 ioc_semijoin but a skewed high-card literal (true: ioc_semijoin, hot)
    ("m3_skew", "literal_skew", "hot", "ioc_semijoin",
     "SELECT c.orig_h FROM conn c JOIN iocs i ON c.resp_h=i.ip WHERE c.ts > DATE '2026-06-14' AND i.ip = '10.0.0.1'"),
    # mode 4 — dynamic function: NOW()-INTERVAL can't be evaluated at routing time (true: scan_aggregation, cold)
    ("m4_dyn", "dynamic_functions", "cold", "scan_aggregation",
     "SELECT proto, count(*) FROM conn WHERE ts < NOW() - INTERVAL '1' YEAR GROUP BY proto"),
    # mode 5 — dialect mismatch: a ClickHouse-only function in a query routed by the common subset (true: scan_aggregation, hot)
    ("m5_dialect", "dialect_mismatch", "hot", "scan_aggregation",
     "SELECT toStartOfDay(ts) d, count(*) FROM conn WHERE ts > DATE '2026-06-14' GROUP BY d"),
]


def run():
    rows = []
    # two routers: the full hypothesis router (consults the catalog: views resolved + manifest read)
    # vs the generic AST-only router (DR-5's "performs syntactic analysis, not semantic execution —
    # never consults the catalog/metastore before routing"). The delta isolates R3 (catalog consult).
    full = Router(use_catalog=True)
    ast_only = Router(use_catalog=False)

    def score(router, qid, mode, exp_tier, shape, sql, dialect=None):
        try:
            r = router.route(sql, dialect=dialect)
        except Exception as e:
            return {"id": qid, "mode": mode, "outcome": "parse_fail", "err": str(e)[:120],
                    "pick": None, "expected_tier": exp_tier, "shape": shape}
        outcome = classify(r["pick"], exp_tier, {"shape": shape})
        # tier correctness (the hot/cold boundary the hypothesis names)
        tier_ok = (r["eff_tier"] == exp_tier)
        return {"id": qid, "mode": mode, "outcome": outcome, "pick": r["pick"],
                "tier_decided": r["tier_decided"], "tier_ok": tier_ok,
                "expected_tier": exp_tier, "shape_true": shape, "shape_router": r["shape"],
                "rules": r["rules"]}

    # templated, full router
    for qid, shape, tier, sql in TEMPLATED:
        rows.append({"router": "full", **score(full, qid, "templated", tier, shape, sql)})

    # adversarial: full (catalog-consulting) vs ast_only (generic AST router) to isolate R3
    for qid, mode, tier, shape, sql in ADVERSARIAL:
        rows.append({"router": "full",     **score(full,     qid, mode, tier, shape, sql)})
        rows.append({"router": "ast_only", **score(ast_only, qid, mode, tier, shape, sql)})

    # ── mode 5 / rec-4: sqlglot dialect round-trip of the templated corpus across the 4 engine dialects ──
    # common-subset contract test: which templated queries parse+transpile cleanly to every engine dialect?
    dialects = {"starrocks": "starrocks", "clickhouse": "clickhouse", "trino": "trino", "dremio": "trino"}  # dremio≈trino/presto proxy
    dialect_report = []
    for qid, shape, tier, sql in TEMPLATED:
        per = {}
        for eng, d in dialects.items():
            try:
                sqlglot.transpile(sql, read=None, write=d)
                per[eng] = "ok"
            except Exception as e:
                per[eng] = "FAIL:%s" % str(e)[:60]
        in_subset = all(v == "ok" for v in per.values())
        dialect_report.append({"id": qid, "in_common_subset": in_subset, "per_dialect": per})
    # the ClickHouse-only function query (mode 5) transpiled to other dialects:
    ch_only = "SELECT toStartOfDay(ts) d, count(*) FROM conn WHERE ts > DATE '2026-06-14' GROUP BY d"
    ch_only_report = {}
    for eng, d in dialects.items():
        try:
            ch_only_report[eng] = "ok:" + sqlglot.transpile(ch_only, read="clickhouse", write=d)[0][:80]
        except Exception as e:
            ch_only_report[eng] = "FAIL:" + str(e)[:60]

    # ── aggregate ──
    def acc(subset):
        n = len(subset)
        c = sum(1 for r in subset if r["outcome"] == "correct")
        cat = sum(1 for r in subset if r["outcome"] == "catastrophic_misroute")
        minor = sum(1 for r in subset if r["outcome"] == "minor_misroute")
        pf = sum(1 for r in subset if r["outcome"] == "parse_fail")
        return {"n": n, "correct": c, "minor_misroute": minor, "catastrophic_misroute": cat,
                "parse_fail": pf, "accuracy": round(c / n, 3) if n else None}

    templated_rows = [r for r in rows if r["mode"] == "templated"]
    full_adv = [r for r in rows if r["router"] == "full" and r["mode"] != "templated"]
    per_mode = {}
    for mode in ["view_obfuscation", "time_predicate_masking", "literal_skew", "dynamic_functions", "dialect_mismatch"]:
        per_mode[mode] = {
            "full":     acc([r for r in rows if r["router"] == "full" and r["mode"] == mode]),
            "ast_only": acc([r for r in rows if r["router"] == "ast_only" and r["mode"] == mode]),
        }

    summary = {
        "bench": "deterministic-routing-sim (H-DETERMINISTIC-ROUTING-01)",
        "tier": "B- / simulation (routing-decision sim, not a live multi-engine measurement)",
        "host": "lab-free; sqlglot %s; ground truth = engine-join-specialization RESULTS (single host, 2026-06-10)" % sqlglot.__version__,
        "honesty": ("Ground-truth winner map is a ~10-shape lookup table from one host. High templated "
                    "accuracy is partly circular (the templated corpus IS the measured shapes) — DR-5's "
                    "denominator-artifact point. The result of interest is the per-mode degradation and "
                    "whether R3/view-resolution closes the catastrophic (cliff) modes."),
        "templated_accuracy": acc(templated_rows),
        "full_router_adversarial_overall": acc(full_adv),
        "per_mode": per_mode,
        "dialect_common_subset": dialect_report,
        "clickhouse_only_func_transpile": ch_only_report,
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "route_sim.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    print(json.dumps(summary, indent=2))
    print("\n-> results/route_sim.json")


if __name__ == "__main__":
    run()
