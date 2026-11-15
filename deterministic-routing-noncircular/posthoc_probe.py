#!/usr/bin/env python3
"""POST-HOC engine probes (not pre-registered), run after the scored passes, in drn-lab:
  sr_rerun   : re-run corpus join_3to4_04 on StarRocks 3 times (did the memory-limit DNF reproduce?) and
               join_3to4_09 once for contrast; writes results/posthoc_sr_rerun.json
  ch_order   : run corpus join_3to4_04 / join_3to4_09 on native MergeTree with
               query_plan_optimize_join_order_limit=0 (June's diagnostic) and with the default, 1 run each,
               plus EXPLAIN of the default plan; writes results/posthoc_ch_order.json
"""
import json, sys, time
from pathlib import Path
import run_engines as R
from ejs_queries import render, normalize, answers_equal

HERE = Path(__file__).parent
corpus = {q["id"]: q["sql"] for q in json.loads((HERE / "queries/corpus.json").read_text())["queries"]}
oracle = json.loads((HERE / "results/oracle.json").read_text())["answers"]


def timed(client, sql, qid):
    la = R.loadavg(); t0 = time.perf_counter()
    try:
        rows = client.run(sql); dt = time.perf_counter() - t0
        return {"s": round(dt, 3), "load": la, "matches_oracle": answers_equal(normalize(rows), oracle[qid])}
    except Exception as e:
        return {"s": round(time.perf_counter() - t0, 3), "load": la, "err": str(e)[:300]}


mode = sys.argv[1]
out = {"mode": mode, "runs": []}
if mode == "sr_rerun":
    refs = R.table_refs("starrocks")
    for qid, n in (("join_3to4_04", 3), ("join_3to4_09", 1)):
        for i in range(n):
            c = R.make_client("starrocks")
            out["runs"].append({"id": qid, "i": i, **timed(c, render(corpus[qid], refs), qid)})
            print(out["runs"][-1], flush=True)
    out["version"] = R.make_client("starrocks").version()
else:
    refs = R.table_refs("clickhouse_native")
    c = R.make_client("clickhouse_native")
    for qid in ("join_3to4_04", "join_3to4_09"):
        q = render(corpus[qid], refs)
        out.setdefault("explain", {})[qid] = [r[0] for r in c.run("EXPLAIN " + q)]
        for lim in (0, None):
            sql = q + (" SETTINGS query_plan_optimize_join_order_limit = 0" if lim == 0 else "")
            out["runs"].append({"id": qid, "join_order_limit": "0" if lim == 0 else "default", **timed(c, sql, qid)})
            print(out["runs"][-1], flush=True)
(HERE / f"results/posthoc_{mode}.json").write_text(json.dumps(out, indent=1))
