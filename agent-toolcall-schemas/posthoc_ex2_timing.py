#!/usr/bin/env python3
"""POST-HOC, NOT PRE-REGISTERED (added 2026-11-16 after an external review).

R2 timed AOS example 1 as its L3 layout (tool name, arguments and session inside unmapped.aos), while R2's loss
table primary column and its validator run used AOS example 2 (tool name in api.operation, session in
actor.session.uid). This script adds an example-2-shaped layout, L3b, built from the SAME seeded corpus
(gen_corpus.generate, sub-seed 9202) and timed with the SAME harness settings (lib/common.time_trials, 2 warmups +
7 trials, 3 processes with rotated layout order), so the article can say which AOS example carries the price.

L3b follows extend_ocsf.md example 2 ("Agent with Tool Execution") as R2's map_schemas.AOS does:
  actor.user (agent, type_id 99), actor.session.uid, api.operation = tool name, api.service, status_id,
  unmapped.aos.step.operation.tool.inputs (the arguments document), .outputs, .is_error,
  unmapped.aos.context.agent / .model.
Q2's argument path under L3b is unmapped.aos.step.operation.tool.inputs.sql. R2's map_schemas renders example-2
inputs as a list of {name, value}; this layout keeps the arguments object so the Q2 regex is the same expression in
every layout. That is a simplification in example 2's favour and is stated in RESULTS-EX2-POSTHOC-2026-11-16.md.

Usage: posthoc_ex2_timing.py gen N        -> data/n{N}/ (L1_typed, L2_otel_map, L3_aos_unmapped, L3b_aos_ex2)
       posthoc_ex2_timing.py time N PASS  -> results/timing_ex2posthoc_n{N}_pass{PASS}.json
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lib"))
import duckdb  # noqa: E402
import pyarrow  # noqa: E402

import gen_corpus as g  # noqa: E402
import run_queries as rq  # noqa: E402
from common import configure_duckdb, pin_artifact, time_trials  # noqa: E402

L3B_SQL = """
SELECT make_timestamp(time_ms * 1000) AS time, 6003 AS class_uid, 1 AS activity_id, 'Tool Execution' AS activity_name,
  CASE WHEN is_error THEN 2 ELSE 1 END AS status_id, duration_ms::BIGINT AS duration,
  {'user': {'uid': agent, 'name': agent || '-name', 'type_id': 99, 'type': 'AI Agent'},
   'session': {'uid': session}} AS actor,
  {'operation': tool, 'service': {'name': server, 'version': '1.0.0'},
   'response': {'message': CASE WHEN is_error THEN 'Error executing tool ' || tool END}} AS api,
  {'type_id': 99, 'name': 'AI Agent Endpoint'} AS src_endpoint,
  {'version': '1.0.0', 'correlation_uid': req_id} AS metadata,
  to_json({'aos': {
     'step': {'id': req_id, 'type': 'toolCall',
              'operation': {'type': 'tool_execution',
                            'tool': {'id': tool, 'execution_id': req_id, 'inputs': json(args),
                                     'outputs': json(result), 'is_error': is_error}}},
     'context': {'agent': {'id': agent, 'name': agent || '-name', 'version': '1.0.0'},
                 'model': {'id': 'model-x', 'provider': {'name': 'provider-y'}}}}})::VARCHAR AS unmapped
FROM base ORDER BY time_ms
"""

J, RX = rq.J, rq.RX
Q3B = {
    "Q1_tool_by_agent": "SELECT count(*) FROM L3b WHERE actor.user.uid = 'agent-0042' AND api.operation = 'export_table'",
    "Q2_argument_hunt": f"SELECT count(*) FROM L3b WHERE api.operation = 'run_query' "
                        f"AND regexp_matches({J}(unmapped, '$.aos.step.operation.tool.inputs.sql'), '{RX}')",
    "Q3_tool_breadth_errors": "SELECT actor.user.uid AS agent, count(DISTINCT api.operation) AS n FROM L3b "
                              "WHERE status_id = 2 GROUP BY 1 ORDER BY n DESC, agent LIMIT 10",
    "Q4_failure_bursts": "SELECT count(*) FROM (SELECT actor.session.uid FROM L3b WHERE status_id = 2 "
                         "GROUP BY 1 HAVING count(*) >= 3)",
    "Q5_off_allowlist": "SELECT count(*) FROM L3b c ANTI JOIN allow a "
                        "ON c.api.service.name = a.server AND c.api.operation = a.tool",
}
LAYOUTS = ["L1_typed", "L2_otel_map", "L3_aos_unmapped", "L3b_aos_ex2"]
ALIAS = {"L1_typed": "L1", "L2_otel_map": "L2", "L3_aos_unmapped": "L3", "L3b_aos_ex2": "L3b"}


def gen(n: int) -> None:
    outdir = HERE / "data" / f"n{n}"
    outdir.mkdir(parents=True, exist_ok=True)
    base = g.generate(n)
    con = configure_duckdb(duckdb.connect())
    con.register("base_arrow", base)
    con.execute("CREATE TABLE base AS SELECT * FROM base_arrow")
    con.execute("CREATE TABLE allowlist(server VARCHAR, tool VARCHAR)")
    con.executemany("INSERT INTO allowlist VALUES (?, ?)", g.ALLOWLIST)
    con.execute(f"COPY allowlist TO '{outdir}/allowlist.parquet' (FORMAT parquet)")
    destr = ", ".join(f"'{d}'" for d in sorted(g.DESTRUCTIVE))
    meta = {"n": n, "posthoc": True, "duckdb": duckdb.__version__, "pyarrow": pyarrow.__version__,
            "python": platform.python_version(), "layouts": {}}
    for name, sql in (("L1_typed", g.L1_SQL.replace("{destr}", destr)), ("L2_otel_map", g.L2_SQL),
                      ("L3_aos_unmapped", g.L3_SQL), ("L3b_aos_ex2", L3B_SQL)):
        path = outdir / f"{name}.parquet"
        t1 = time.perf_counter()
        con.execute(f"COPY ({sql}) TO '{path}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 122880)")
        meta["layouts"][name] = {"bytes": path.stat().st_size, "write_s": round(time.perf_counter() - t1, 3),
                                 "pin": pin_artifact(con, str(path))}
        print(name, meta["layouts"][name]["bytes"])
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"corpus_meta_ex2posthoc_n{n}.json").write_text(json.dumps(meta, indent=1, default=str))


def run(n: int, pass_idx: int) -> None:
    d = HERE / "data" / f"n{n}"
    con = configure_duckdb(duckdb.connect())
    for lay in LAYOUTS:
        con.execute(f"CREATE VIEW {ALIAS[lay]} AS SELECT * FROM read_parquet('{d}/{lay}.parquet')")
    con.execute(f"CREATE VIEW allow AS SELECT * FROM read_parquet('{d}/allowlist.parquet')")
    k = pass_idx % len(LAYOUTS)
    order = LAYOUTS[k:] + LAYOUTS[:k]
    out = {"n": n, "pass": pass_idx, "posthoc": True, "layout_order": order, "duckdb": duckdb.__version__,
           "pyarrow": pyarrow.__version__, "threads": con.execute("SELECT current_setting('threads')").fetchone()[0],
           "python": platform.python_version(), "loadavg_start": os.getloadavg(), "queries": {}}
    for qname, per0 in rq.Q.items():
        per = dict(per0, L3b_aos_ex2=Q3B[qname])
        answers, timings = {}, {}
        for lay in order:
            sql = per[lay]
            answers[lay] = con.execute(sql).fetchall()
            timings[lay] = time_trials(lambda s=sql: con.execute(s).fetchall(), warmup=2, trials=7)
        ref = answers["L1_typed"]
        out["queries"][qname] = {"answer": [list(r) for r in ref],
                                 "answers_equal": all(answers[l] == ref for l in LAYOUTS), "timings": timings}
        print(qname, "equal" if out["queries"][qname]["answers_equal"] else f"MISMATCH {answers}",
              {l: timings[l]["median_ms"] for l in LAYOUTS})
    out["loadavg_end"] = os.getloadavg()
    (HERE / "results" / f"timing_ex2posthoc_n{n}_pass{pass_idx}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "gen":
        gen(int(sys.argv[2]))
    else:
        run(int(sys.argv[2]), int(sys.argv[3]))
