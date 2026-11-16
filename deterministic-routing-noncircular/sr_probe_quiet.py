#!/usr/bin/env python3
"""QUIET REPLICATION 2026-11-16, StarRocks join_3to4_04 attempt probe (pre-registered in
PREREGISTRATION-ADDENDUM-QUIET-2026-11-16.md, not post-hoc). Runs in drn-lab right after the StarRocks
main pass, engine still up. Exactly 5 executions of corpus join_3to4_04, each on a fresh client connection,
no retries. Writes results/quiet-2026-11-16/sr_attempts_probe.json (new file)."""
import json, sys, time
sys.dont_write_bytecode = True
from pathlib import Path
import run_engines_quiet  # noqa: F401  (patches paths + stamp)
import run_engines as R
from ejs_queries import render, normalize, answers_equal

HERE = Path(__file__).parent
Q = HERE / "results" / "quiet-2026-11-16"
corpus = {q["id"]: q["sql"] for q in json.loads((HERE / "queries/corpus.json").read_text())["queries"]}
oracle = json.loads((Q / "oracle.json").read_text())["answers"]
qid = "join_3to4_04"
refs = R.table_refs("starrocks")
out = {"mode": "sr_attempts_probe", "id": qid, "runs": []}
for i in range(5):
    c = R.make_client("starrocks")
    la = R.loadavg(); t0 = time.perf_counter()
    try:
        rows = c.run(render(corpus[qid], refs))
        rec = {"i": i, "s": round(time.perf_counter() - t0, 3), "load": la,
               "matches_oracle": answers_equal(normalize(rows), oracle[qid])}
    except Exception as e:
        rec = {"i": i, "s": round(time.perf_counter() - t0, 3), "load": la, "err": str(e)[:300]}
    out["runs"].append(rec); print(rec, flush=True)
out["version"] = R.make_client("starrocks").version()
(Q / "sr_attempts_probe.json").write_text(json.dumps(out, indent=1))
