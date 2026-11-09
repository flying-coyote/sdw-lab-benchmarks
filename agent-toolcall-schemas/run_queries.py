#!/usr/bin/env python3
"""Time the five pre-registered hunt queries over the three layouts. One process = one pass.

Usage: run_queries.py N PASS_INDEX   -> writes results/timing_n{N}_pass{PASS}.json
Layout order rotates with the pass index so no layout always runs first. Warm/hot only (no root cache purge).
"""
from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
from common import configure_duckdb, time_trials  # noqa: E402

import duckdb  # noqa: E402

RX = r"(?i)copy\s.+\sto\s"
J = "json_extract_string"
Q = {
    "Q1_tool_by_agent": {
        "L1_typed": "SELECT count(*) FROM L1 WHERE ai_capability.name = 'export_table' AND ai_agent.uid = 'agent-0042'",
        "L2_otel_map": "SELECT count(*) FROM L2 WHERE attributes['gen_ai.tool.name'] = 'export_table' "
                       "AND attributes['gen_ai.agent.id'] = 'agent-0042'",
        "L3_aos_unmapped": f"SELECT count(*) FROM L3 WHERE actor.user.uid = 'agent-0042' "
                           f"AND {J}(unmapped, '$.aos.tool_call.name') = 'export_table'",
    },
    "Q2_argument_hunt": {
        "L1_typed": f"SELECT count(*) FROM L1 WHERE ai_capability.name = 'run_query' "
                    f"AND regexp_matches({J}(api.request.data, '$.sql'), '{RX}')",
        "L2_otel_map": f"SELECT count(*) FROM L2 WHERE attributes['gen_ai.tool.name'] = 'run_query' "
                       f"AND regexp_matches({J}(attributes['gen_ai.tool.call.arguments'], '$.sql'), '{RX}')",
        "L3_aos_unmapped": f"SELECT count(*) FROM L3 WHERE {J}(unmapped, '$.aos.tool_call.name') = 'run_query' "
                           f"AND regexp_matches({J}(unmapped, '$.aos.tool_call.arguments.sql'), '{RX}')",
    },
    "Q3_tool_breadth_errors": {
        "L1_typed": "SELECT ai_agent.uid AS agent, count(DISTINCT ai_capability.name) AS n FROM L1 "
                    "WHERE status_id = 2 GROUP BY 1 ORDER BY n DESC, agent LIMIT 10",
        "L2_otel_map": "SELECT attributes['gen_ai.agent.id'] AS agent, count(DISTINCT attributes['gen_ai.tool.name']) AS n "
                       "FROM L2 WHERE status_code = 'ERROR' GROUP BY 1 ORDER BY n DESC, agent LIMIT 10",
        "L3_aos_unmapped": f"SELECT actor.user.uid AS agent, count(DISTINCT {J}(unmapped, '$.aos.tool_call.name')) AS n "
                           f"FROM L3 WHERE status_id = 2 GROUP BY 1 ORDER BY n DESC, agent LIMIT 10",
    },
    "Q4_failure_bursts": {
        "L1_typed": "SELECT count(*) FROM (SELECT actor.session.uid FROM L1 WHERE status_id = 2 "
                    "GROUP BY 1 HAVING count(*) >= 3)",
        "L2_otel_map": "SELECT count(*) FROM (SELECT attributes['gen_ai.conversation.id'] FROM L2 "
                       "WHERE status_code = 'ERROR' GROUP BY 1 HAVING count(*) >= 3)",
        "L3_aos_unmapped": f"SELECT count(*) FROM (SELECT {J}(unmapped, '$.aos.context.session.id') FROM L3 "
                           f"WHERE status_id = 2 GROUP BY 1 HAVING count(*) >= 3)",
    },
    "Q5_off_allowlist": {
        "L1_typed": "SELECT count(*) FROM L1 c ANTI JOIN allow a "
                    "ON c.ai_capability.service.name = a.server AND c.ai_capability.name = a.tool",
        "L2_otel_map": "SELECT count(*) FROM L2 c ANTI JOIN allow a "
                       "ON c.attributes['sdw.mcp.server.name'] = a.server AND c.attributes['gen_ai.tool.name'] = a.tool",
        "L3_aos_unmapped": f"SELECT count(*) FROM L3 c ANTI JOIN allow a "
                           f"ON c.api.service.name = a.server AND {J}(c.unmapped, '$.aos.tool_call.name') = a.tool",
    },
}
LAYOUTS = ["L1_typed", "L2_otel_map", "L3_aos_unmapped"]


def main(n: int, pass_idx: int) -> None:
    d = HERE / "data" / f"n{n}"
    con = configure_duckdb(duckdb.connect())
    for lay, alias in zip(LAYOUTS, ("L1", "L2", "L3")):
        con.execute(f"CREATE VIEW {alias} AS SELECT * FROM read_parquet('{d}/{lay}.parquet')")
    con.execute(f"CREATE VIEW allow AS SELECT * FROM read_parquet('{d}/allowlist.parquet')")
    order = LAYOUTS[pass_idx % 3:] + LAYOUTS[:pass_idx % 3]
    out = {"n": n, "pass": pass_idx, "layout_order": order, "duckdb": duckdb.__version__,
           "threads": con.execute("SELECT current_setting('threads')").fetchone()[0],
           "python": platform.python_version(), "loadavg_start": os.getloadavg(), "queries": {}}
    for qname, per in Q.items():
        answers, timings = {}, {}
        for lay in order:
            sql = per[lay]
            answers[lay] = con.execute(sql).fetchall()
            timings[lay] = time_trials(lambda s=sql: con.execute(s).fetchall(), warmup=2, trials=7)
        ref = answers["L1_typed"]
        out["queries"][qname] = {"answer": [list(r) for r in ref],
                                 "answers_equal": all(answers[l] == ref for l in LAYOUTS),
                                 "timings": timings}
        print(qname, "equal" if out["queries"][qname]["answers_equal"] else f"MISMATCH {answers}",
              {l: timings[l]["median_ms"] for l in LAYOUTS})
    out["loadavg_end"] = os.getloadavg()
    tag = os.environ.get("R2_TAG", "")
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"timing{tag}_n{n}_pass{pass_idx}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
