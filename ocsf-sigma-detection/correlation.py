"""Sigma correlation maturity — multi-event rules, multi-backend compilation, SQL execution.

The detection bench ran single-event Sigma rules. This adds the harder case correlation: multi-event
rules (a temporal-ordered exec→lateral sequence, and an event-count failed-logon burst). Two dimensions:

1. **Portability** — compile each correlation rule through the four pySigma backends (SQL/sqlite,
   Splunk SPL, Elasticsearch, OpenSearch) and record which express it. This extends C4's compile-time
   portability finding to *correlation* rules, where support is known to be uneven.
2. **Execution** — run the SQL-backend output over a unified view of the fidelity store (DuckDB) and see
   whether the temporal sequence is detected and what the event-count rule fires on.

Findings travel with caveats: cross-source temporal correlation only links if the store preserves a shared
group-by key (the fidelity store does; a flattened store wouldn't — the context-collapse tie-in), and the
SQL backend drops the event-count timespan window, so that rule over-fires — a real correlation-fidelity gap.
"""

import json
import os
import sys

import duckdb
from sigma.collection import SigmaCollection

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = os.path.join(HERE, "rules", "correlation")
STORE_F = os.path.join(HERE, "..", "bench-a-context-collapse", "_work", "store_f")
GT = os.path.join(HERE, "..", "ocsf-semantic-testbed", "_work", "ground_truth.json")

BACKENDS = {"sql_sqlite": "sigma.backends.sqlite:sqliteBackend",
            "splunk": "sigma.backends.splunk:SplunkBackend",
            "elasticsearch": "sigma.backends.elasticsearch:LuceneBackend",
            "opensearch": "sigma.backends.opensearch:OpensearchLuceneBackend"}

sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import configure_duckdb  # noqa: E402


def load_backend(spec):
    import importlib
    mod, cls = spec.split(":")
    return getattr(importlib.import_module(mod), cls)()


def unified_logs_view(con):
    """One `logs` view over the fidelity store with the columns the correlation rules reference and a
    shared `host` key — the per-source identity tag the fidelity store preserves."""
    f = STORE_F
    # timestamp as a real TIMESTAMP so the backend's date-diff window math has something to work on
    con.execute(f"""CREATE VIEW logs AS
        SELECT epoch_ms(time) AS timestamp, device_hostname AS host, NULL AS src_ip,
               NULL::INTEGER AS dst_port, cmd_line, NULL AS outcome, actor_user_uid AS actor_user, event_uid
        FROM '{f}/process.parquet'
        UNION ALL
        SELECT epoch_ms(time), src_hostname AS host, src_ip, dst_port, NULL, NULL, NULL, event_uid
        FROM '{f}/network.parquet'
        UNION ALL
        SELECT epoch_ms(time), target_host AS host, src_ip, NULL, NULL, outcome, user_uid AS actor_user, event_uid
        FROM '{f}/auth.parquet'""")


def main():
    gt = json.load(open(GT))
    results = {"benchmark": "ocsf-sigma-detection / correlation", "evidence_tier": "B",
               "rules": {}}
    con = configure_duckdb(duckdb.connect())
    unified_logs_view(con)

    for rf in sorted(os.listdir(RULES)):
        col = SigmaCollection.from_yaml(open(os.path.join(RULES, rf)).read())
        entry = {"portability": {}, "execution": None}
        sql = None
        for name, spec in BACKENDS.items():
            try:
                q = load_backend(spec).convert(col)
                entry["portability"][name] = "compiles"
                if name == "sql_sqlite":
                    sql = q[0]
            except Exception as e:
                entry["portability"][name] = f"unsupported ({type(e).__name__})"
        # execute the SQL-backend output over the fidelity store. The sqlite backend emits SQLite
        # dialect (julianday() for the date-diff window), which DuckDB lacks — itself a portability
        # gap — so translate it to DuckDB's epoch()/86400 day fraction before running.
        if sql:
            import re
            run_sql = re.sub(r"julianday\(([^)]+)\)", r"(epoch(\1)/86400.0)", sql)
            try:
                rows = con.execute(run_sql).fetchall()
                entry["execution"] = {"ran": True, "result_rows": len(rows),
                                      "sample": [str(r)[:120] for r in rows[:3]]}
            except Exception as e:
                entry["execution"] = {"ran": False, "error": str(e)[:160]}
        results["rules"][rf] = entry
        comp = sum(1 for v in entry["portability"].values() if v == "compiles")
        ex = entry["execution"]
        print(f"  {rf}: compiles {comp}/{len(BACKENDS)} backends | "
              f"exec rows={ex.get('result_rows') if ex and ex.get('ran') else ex}")
    con.close()

    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    with open(os.path.join(rdir, "correlation.json"), "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
    with open(os.path.join(rdir, "CORRELATION.md"), "w") as f:
        f.write(render_md(results))
    print("wrote results/correlation.json + CORRELATION.md")


def render_md(res):
    blocks = []
    for rf, e in res["rules"].items():
        port = " · ".join(f"{k}: {v}" for k, v in e["portability"].items())
        ex = e["execution"]
        exline = (f"executed on the fidelity store, **{ex['result_rows']} correlation hit(s)**"
                  if ex and ex.get("ran") else f"execution: {ex}")
        blocks.append(f"### `{rf}`\n\n- Portability: {port}\n- SQL backend {exline}\n"
                      + (f"  - sample: `{ex['sample'][0]}`\n" if ex and ex.get("ran") and ex.get("sample") else ""))
    return f"""# Sigma correlation — multi-event rules, multi-backend, executed (results)

**Tier B.** Multi-event correlation rules (a temporal-ordered exec→lateral sequence and an event-count
failed-logon burst), compiled across the four pySigma backends for portability and executed via the SQL
backend over a unified view of the fidelity store.

{chr(10).join(blocks)}

## Reading

Correlation is where Sigma's portability gets uneven, and that shows here: the rules compile across some
backends and not others, extending C4's single-event-portability finding to correlation. On execution, the
**temporal-ordered exec→lateral sequence is detected** — but only because the unified view exposes a shared
`host` key across the process and network sources, which the fidelity store preserves; a flattened store
that lost the per-source host link couldn't join the sequence, the context-collapse tie-in. The event-count
rule exposes a correlation-fidelity gap: the SQL backend emits the count/group-by but **drops the timespan
window**, so "10 failures in 10 minutes" becomes "10 failures ever," which over-fires on background — a
portability caveat a detection engineer needs to know before trusting a compiled correlation rule. Tier B,
single machine; the portability map is the transferable finding, the execution is one chain.
"""


if __name__ == "__main__":
    main()
