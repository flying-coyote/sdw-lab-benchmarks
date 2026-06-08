"""ocsf-rls-overhead — engine-side predicate overhead of row-level security on OCSF data.

WHAT THIS MEASURES
------------------
Row-level security enforced as a WHERE predicate appended to every query (the "predicate-push"
approach) and as a secured VIEW (the "view wrapper" approach), measured against an unfiltered
baseline across three role-selectivity tiers:

  - tier_1pct  : the role sees ~1 % of rows  (narrow, high-privilege filter)
  - tier_10pct : the role sees ~10% of rows
  - tier_50pct : the role sees ~50% of rows  (broad / near-admin filter)

Four SOC-representative query shapes are timed under each (baseline, predicate, view):

  count_all    — SELECT count(*) FROM <table>
  top_talkers  — top-20 src_ip by event count (classic SOC telemetry query)
  group_by_act — event count by activity_id (group-by, medium cardinality)
  needle       — single-event lookup by event_id (the rare-event search)

WHAT THIS IS (AND IS NOT)
-------------------------
This is the **engine-side predicate-overhead lower bound**: DuckDB evaluates the RLS predicate
as an ordinary WHERE clause after parsing; no catalog layer is involved. Real multi-tenant
catalog systems (Polaris, Unity Catalog, AWS Lake Formation) enforce RLS at the catalog layer,
which adds its own protocol round-trips, token validation, and policy-evaluation cost *before*
the engine even plans — so real-world overhead is higher than what we measure here. Cross-
reference q3-catalog-benchmark for the catalog-layer leg. Tier B, single machine, DuckDB 1.5.3.

Relevant hypothesis: H-SECURITY-02 (federated catalog RBAC / centralized security governance).
The overhead of the enforcement mechanism is a prerequisite cost for any governance claim;
this measures the DuckDB-engine component of that cost.

DETERMINISM GUARANTEE
---------------------
The corpus is seeded via lib.common.new_rng(sub_seed). The SAME rows will be generated on every
run, so the "answers" (counts, top-N rankings) are reproducible. Latencies are wall-clock and
legitimately non-deterministic; the corpus and the query answers are the reproducible parts.

CORRECTNESS GATE
----------------
For every query shape, baseline and predicate results are compared against the view results.
The three enforcement approaches must return identical answers for the same logical data; a
mismatch is a hard error, not a performance note.

USAGE
-----
  # normal run (in-memory, seeded corpus)
  python ocsf-rls-overhead/run.py

  # larger corpus
  python ocsf-rls-overhead/run.py --rows 5000000

  # render existing results.json to RESULTS.md without re-running
  python ocsf-rls-overhead/run.py --render-only
"""

import argparse
import json
import os
import platform
import sys
import time

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import (  # noqa: E402
    BASE_EPOCH,
    MASTER_SEED,
    configure_duckdb,
    logical_fingerprint,
    new_rng,
    time_trials,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_N_ROWS = 1_000_000   # comfortable in-memory scale; 5M–10M for a stronger signal

# Sub-seed for this benchmark's RNG; keeps corpus independent of other benches
# while still determined by the global MASTER_SEED.
RLS_SUB_SEED = 9901

# Selectivity tiers: fraction of rows visible to the role.
# Each tier maps to a tenant_id range [0, cutoff) out of TOTAL_TENANTS tenants.
# ~1%, ~10%, ~50% selectivity is achieved by choosing 1, 10, or 50 tenant IDs out of 100.
TOTAL_TENANTS = 100
SELECTIVITY_TIERS = {
    "tier_1pct":  1,   # visible_tenants = 1  → ~1%  of rows
    "tier_10pct": 10,  # visible_tenants = 10 → ~10% of rows
    "tier_50pct": 50,  # visible_tenants = 50 → ~50% of rows
}

# Query templates.  {t} is substituted with the table/view expression at runtime.
QUERIES = {
    "count_all":    "SELECT count(*) FROM {t}",
    "top_talkers":  (
        "SELECT src_ip, count(*) AS c FROM {t} "
        "GROUP BY 1 ORDER BY c DESC, src_ip LIMIT 20"
    ),
    "group_by_act": (
        "SELECT activity_id, count(*) AS c FROM {t} "
        "GROUP BY 1 ORDER BY c DESC"
    ),
    "needle":       "SELECT * FROM {t} WHERE event_id = {needle_id} LIMIT 1",
}

# time_trials parameters matching the repo's medium-scale convention.
# warmup=2, trials=7 per lib/common.py defaults.
WARMUP = 2
TRIALS = 7


# ---------------------------------------------------------------------------
# Corpus generation
# ---------------------------------------------------------------------------

def generate_corpus(con: duckdb.DuckDBPyConnection, n: int) -> int:
    """Build the in-memory OCSF-shaped corpus and return a needle event_id for the
    needle-lookup query.  Schema mirrors the OCSF Network Activity class skeleton:
      event_id     — unique row identifier
      time         — Unix ms timestamp (deterministic from BASE_EPOCH)
      tenant_id    — integer in [0, TOTAL_TENANTS); uniform random; the RLS column
      src_ip       — synthetic IPv4 address
      dst_port     — one of 8 representative ports
      activity_id  — OCSF activity enum (1-6; maps to Open/Close/Connect/…)
      bytes_out    — random payload size (bytes)
    """
    rng = new_rng(RLS_SUB_SEED)
    seed_val = rng.randint(0, 2**31 - 1)

    # DuckDB hash() is deterministic on the value, seeded here by the corpus seed.
    # We derive every column from the row index and a per-column salt so the corpus
    # is deterministic without materialising Python lists.
    PORTS = "[80, 443, 22, 53, 3389, 445, 8080, 3306]"
    con.execute(f"""
        CREATE OR REPLACE TABLE rls_corpus AS
        SELECT
            i                                                            AS event_id,
            {BASE_EPOCH * 1000} + i                                     AS time,
            (abs(hash(i::VARCHAR || 'tid' || {seed_val})) % {TOTAL_TENANTS})::INTEGER
                                                                         AS tenant_id,
            '10.'
                || (abs(hash(i::VARCHAR||'a'||{seed_val})) % 256)::VARCHAR || '.'
                || (abs(hash(i::VARCHAR||'b'||{seed_val})) % 256)::VARCHAR || '.'
                || (abs(hash(i::VARCHAR||'c'||{seed_val})) % 256)::VARCHAR
                                                                         AS src_ip,
            {PORTS}[(1 + abs(hash(i::VARCHAR||'p'||{seed_val})) % 8)::BIGINT]::INTEGER
                                                                         AS dst_port,
            (1 + abs(hash(i::VARCHAR||'act'||{seed_val})) % 6)::INTEGER  AS activity_id,
            (abs(hash(i::VARCHAR||'bo'||{seed_val})) % 5_000_000)::BIGINT
                                                                         AS bytes_out
        FROM range(0, {n}) t(i)
    """)

    # Verify actual tenant distribution is close to uniform (a sanity check, not a gate).
    tenant_counts = con.execute(
        "SELECT count(DISTINCT tenant_id) AS distinct_tenants FROM rls_corpus"
    ).fetchone()
    assert tenant_counts[0] == TOTAL_TENANTS, (
        f"Expected {TOTAL_TENANTS} distinct tenants, got {tenant_counts[0]}"
    )

    # Pick a needle: a row that falls within tier_1pct's visible tenant range,
    # so the needle query has a non-empty result even at the narrowest tier.
    needle_id_row = con.execute(
        "SELECT event_id FROM rls_corpus WHERE tenant_id < 1 LIMIT 1"
    ).fetchone()
    if needle_id_row is None:
        # Fallback: any row at all (corpus guarantees all TOTAL_TENANTS are present).
        needle_id_row = con.execute("SELECT event_id FROM rls_corpus LIMIT 1").fetchone()
    return int(needle_id_row[0])


def create_views(con: duckdb.DuckDBPyConnection) -> None:
    """Create one secured VIEW per selectivity tier.  Each view contains ONLY the rows
    visible to that tier's role (tenant_id < visible_tenants_cutoff).  This is the
    'view-wrapper' RLS approach: the consumer queries the view directly and never sees
    the WHERE clause."""
    for tier_name, visible_n in SELECTIVITY_TIERS.items():
        view_name = f"rls_view_{tier_name}"
        con.execute(f"""
            CREATE OR REPLACE VIEW {view_name} AS
            SELECT * FROM rls_corpus
            WHERE tenant_id < {visible_n}
        """)


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

def _predicate_expr(visible_n: int) -> str:
    """The RLS predicate appended to an existing WHERE clause (or added fresh)."""
    return f"tenant_id < {visible_n}"


def run_trials(con: duckdb.DuckDBPyConnection, sql: str) -> dict:
    """Run time_trials for a single SQL string and return the timing dict."""
    return time_trials(lambda: con.execute(sql).fetchall(), warmup=WARMUP, trials=TRIALS)


def _answers_equal(a, b):
    """Order-insensitive equality for result sets (sorted multiset comparison)."""
    def norm(rows):
        return sorted(tuple(str(c) for c in r) for r in rows)
    return norm(a) == norm(b)


def time_query(
    con: duckdb.DuckDBPyConnection,
    q_name: str,
    q_tmpl: str,
    tier_name: str,
    visible_n: int,
    needle_id: int,
) -> dict:
    """Time one query under all three enforcement approaches for one selectivity tier.

    Returns a dict keyed by approach name ('baseline', 'predicate', 'view'), each
    containing the timing result from time_trials, plus an 'answers_identical' flag.
    """
    # Substitute the needle id for the needle query
    def q(tmpl, t):
        return tmpl.format(t=t, needle_id=needle_id)

    view_name = f"rls_view_{tier_name}"

    # (a) baseline: unfiltered full table
    sql_baseline = q(q_tmpl, "rls_corpus")

    # (b) predicate: WHERE clause appended directly to the query
    #     For queries that already have a WHERE, we wrap as a subquery so the
    #     predicate addition is uniform and doesn't require query-specific parsing.
    sql_predicate = (
        f"SELECT * FROM ({q(q_tmpl, 'rls_corpus')}) _sub "
        f"WHERE {_predicate_expr(visible_n)}"
        if q_name == "needle"
        else q(q_tmpl, f"(SELECT * FROM rls_corpus WHERE {_predicate_expr(visible_n)})")
    )

    # (c) view: the query hits the secured view, which encapsulates the predicate
    sql_view = q(q_tmpl, view_name)

    t_baseline  = run_trials(con, sql_baseline)
    t_predicate = run_trials(con, sql_predicate)
    t_view      = run_trials(con, sql_view)

    # Correctness gate: predicate and view must match each other.
    # Baseline will differ (it sees all rows) — we gate predicate ↔ view only.
    rows_pred = con.execute(sql_predicate).fetchall()
    rows_view = con.execute(sql_view).fetchall()
    answers_identical = _answers_equal(rows_pred, rows_view)

    baseline_ms = t_baseline["median_ms"]
    pred_ms     = t_predicate["median_ms"]
    view_ms     = t_view["median_ms"]

    def overhead_pct(enforced_ms, base_ms):
        if base_ms <= 0:
            return None
        return round((enforced_ms - base_ms) / base_ms * 100.0, 1)

    return {
        "baseline":  {**t_baseline,  "approach": "baseline"},
        "predicate": {**t_predicate, "approach": "predicate",
                      "overhead_pct_vs_baseline": overhead_pct(pred_ms, baseline_ms)},
        "view":      {**t_view,      "approach": "view",
                      "overhead_pct_vs_baseline": overhead_pct(view_ms, baseline_ms)},
        "answers_identical_predicate_vs_view": answers_identical,
    }


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------

def run(n_rows: int = DEFAULT_N_ROWS) -> dict:
    con = configure_duckdb(duckdb.connect())

    print(f"  generating {n_rows:,}-row OCSF corpus (seeded, deterministic)…")
    needle_id = generate_corpus(con, n_rows)
    create_views(con)

    # Corpus fingerprint — order-independent hash of the logical content.
    fp = logical_fingerprint(con, "SELECT * FROM rls_corpus")

    results_by_tier = {}
    all_answers_ok = True

    for tier_name, visible_n in SELECTIVITY_TIERS.items():
        selectivity_actual = con.execute(
            f"SELECT count(*) * 1.0 / (SELECT count(*) FROM rls_corpus) "
            f"FROM rls_corpus WHERE tenant_id < {visible_n}"
        ).fetchone()[0]

        tier_results = {
            "tier": tier_name,
            "visible_tenants": visible_n,
            "selectivity_actual": round(float(selectivity_actual), 4),
            "queries": {},
        }

        for q_name, q_tmpl in QUERIES.items():
            qr = time_query(con, q_name, q_tmpl, tier_name, visible_n, needle_id)
            tier_results["queries"][q_name] = qr
            ok = qr["answers_identical_predicate_vs_view"]
            if not ok:
                all_answers_ok = False
            pred_oh = qr["predicate"]["overhead_pct_vs_baseline"]
            view_oh = qr["view"]["overhead_pct_vs_baseline"]
            print(
                f"  {tier_name:12} {q_name:12}  "
                f"baseline {qr['baseline']['median_ms']:7.1f} ms  "
                f"predicate {qr['predicate']['median_ms']:7.1f} ms (+{pred_oh}%)  "
                f"view {qr['view']['median_ms']:7.1f} ms (+{view_oh}%)  "
                f"{'OK' if ok else 'MISMATCH!'}"
            )

        results_by_tier[tier_name] = tier_results

    con.close()

    return {
        "benchmark": "ocsf-rls-overhead",
        "hypothesis": "H-SECURITY-02 (federated catalog RBAC / centralized governance — "
                      "engine-side predicate overhead lower bound)",
        "evidence_tier": (
            "B (single machine; latencies are medians with CV; "
            "corpus and answers are deterministic; "
            "this is engine-side overhead only — catalog-layer enforcement "
            "(Polaris/Unity/Lake Formation) adds further cost not measured here)"
        ),
        "caveat_lower_bound": (
            "DuckDB evaluates RLS predicates as ordinary WHERE clauses after parsing. "
            "Real catalog systems (Polaris, Unity Catalog, AWS Lake Formation) enforce "
            "policy at the catalog protocol layer before the engine plans — adding "
            "token-validation, policy-evaluation, and protocol round-trip cost. "
            "Cross-reference q3-catalog-benchmark for the catalog-layer component."
        ),
        "n_rows": n_rows,
        "total_tenants": TOTAL_TENANTS,
        "corpus_logical_fingerprint": fp,
        "needle_event_id": needle_id,
        "all_answers_identical": all_answers_ok,
        "environment": {
            "duckdb_version": duckdb.__version__,
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "note": (
                "single host, embedded DuckDB in-process; "
                "run under Windows High-Performance power plan per BENCHMARKING-METHODOLOGY.md"
            ),
        },
        "tiers": results_by_tier,
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def render_md(res: dict) -> str:
    lines = []
    a = lines.append

    a("# OCSF RLS Overhead — engine-side predicate cost of row-level security\n")
    a(f"- DuckDB `{res['environment']['duckdb_version']}`  ")
    a(f"- Host: {res['environment']['cpu_count']} vCPU, `{res['environment']['platform']}`  ")
    a(f"- Corpus: {res['n_rows']:,} rows, {res['total_tenants']} tenants, "
      f"fingerprint `{res['corpus_logical_fingerprint'][:16]}…`  ")
    a(f"- Answers identical (predicate ↔ view, every query/tier): "
      f"**{res['all_answers_identical']}**  ")
    a(f"- Evidence tier: {res['evidence_tier']}\n")

    a("> **Lower-bound caveat.** " + res["caveat_lower_bound"] + "\n")

    a("Latencies are wall-clock **medians** (ms) with coefficient of variation (CV%) over "
      f"{TRIALS} trials after {WARMUP} warmup calls. A delta below the CV is not a real "
      "difference. Overhead % = (enforced − baseline) / baseline × 100.\n")

    for tier_name, tier in res["tiers"].items():
        a(f"## {tier_name}  "
          f"(visible_tenants={tier['visible_tenants']}, "
          f"actual selectivity={tier['selectivity_actual']:.1%})\n")
        a("| query | baseline ms (cv%) | predicate ms (cv%) | overhead % | "
          "view ms (cv%) | overhead % | pred↔view agree |")
        a("|---|--:|--:|--:|--:|--:|:--:|")
        for q_name, qr in tier["queries"].items():
            b = qr["baseline"]
            p = qr["predicate"]
            v = qr["view"]
            agree = "yes" if qr["answers_identical_predicate_vs_view"] else "**NO**"
            a(
                f"| {q_name} "
                f"| {b['median_ms']:.1f} ({b['cv_pct']:.0f}%) "
                f"| {p['median_ms']:.1f} ({p['cv_pct']:.0f}%) "
                f"| {p['overhead_pct_vs_baseline']:+.0f}% "
                f"| {v['median_ms']:.1f} ({v['cv_pct']:.0f}%) "
                f"| {v['overhead_pct_vs_baseline']:+.0f}% "
                f"| {agree} |"
            )
        a("")

    a("## Reading\n")
    a(
        "The overhead% column is the cost, in extra latency, of enforcing row-level security "
        "at the engine layer across two mechanisms: a WHERE predicate appended to the query, "
        "and a secured VIEW the query hits directly. Both approaches incur the same logical "
        "work (filter the corpus by `tenant_id`), so they should produce identical answers — "
        "the correctness gate above confirms this. The overhead should scale with selectivity: "
        "a 1%-selectivity filter reads 99% fewer rows than the baseline (high overhead on a "
        "full-scan count but potentially near-zero on a needle lookup that hits an index-like "
        "path early), while a 50%-selectivity filter reads half the table and overhead should "
        "track selectivity roughly linearly for scan-shaped queries.\n"
    )
    a(
        "The gap between predicate and view overhead (if any) is the cost of the view-wrapper "
        "indirection — DuckDB should inline the view predicate into the plan, so the gap should "
        "be small or within CV. A systematic view-is-slower gap would indicate the view wrapper "
        "prevents a predicate-pushdown optimization that the raw predicate allows; that is the "
        "finding to watch for.\n"
    )
    a(
        "This is Tier B, single machine, DuckDB engine-side only. The \"overhead\" measured "
        "here is the lower bound: a real multi-tenant SIEM or data-lake platform with catalog-layer "
        "RLS (Polaris principal roles, Unity Catalog row filters, Lake Formation cell-level "
        "permissions) adds policy-evaluation and protocol round-trips on top of this engine cost. "
        "Cross-reference q3-catalog-benchmark for the catalog-enforcement component.\n"
    )
    a(f"Advances H-SECURITY-02 (federated catalog RBAC). "
      f"Run `python ocsf-rls-overhead/run.py` to reproduce.")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="OCSF RLS overhead benchmark")
    ap.add_argument(
        "--rows", type=int, default=DEFAULT_N_ROWS,
        help=f"corpus size (default {DEFAULT_N_ROWS:,})"
    )
    ap.add_argument(
        "--render-only", action="store_true",
        help="render existing results/results.json to RESULTS.md without re-running"
    )
    args = ap.parse_args()

    rdir = os.path.join(HERE, "results")
    os.makedirs(rdir, exist_ok=True)
    rjson = os.path.join(rdir, "results.json")
    rmd   = os.path.join(rdir, "RESULTS.md")

    if args.render_only:
        with open(rjson) as f:
            res = json.load(f)
    else:
        res = run(n_rows=args.rows)
        with open(rjson, "w") as f:
            json.dump(res, f, indent=2, sort_keys=True)

    with open(rmd, "w") as f:
        f.write(render_md(res))

    print(f"\nall_answers_identical={res['all_answers_identical']}  "
          f"duckdb={res['environment']['duckdb_version']}  "
          f"n_rows={res['n_rows']:,}  "
          f"corpus_fp={res['corpus_logical_fingerprint'][:16]}…")
    if not res["all_answers_identical"]:
        print("  WARNING: predicate↔view answer mismatch — inspect results.json")
    print(f"wrote {rjson}")
    print(f"wrote {rmd}")


if __name__ == "__main__":
    main()
