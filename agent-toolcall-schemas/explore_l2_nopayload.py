#!/usr/bin/env python3
"""EXPLORATORY, not pre-registered (added after the formal run). L2b = the L2 OTel map layout with the opt-in
gen_ai.tool.call.arguments / .result keys left out, which is the OTel default (both are opt_in). Q1, Q3, Q4, Q5
only, since Q2 has no arguments to search in L2b. Same codec/row group, 3 passes x (2 warmup + 7 trials)."""
import json, statistics, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
from common import configure_duckdb, time_trials
import duckdb
from run_queries import Q
d = HERE / "data" / "n1000000"
con = configure_duckdb(duckdb.connect())
p = d / "L2b_otel_map_nopayload.parquet"
con.execute(f"""COPY (SELECT * REPLACE (map_from_entries(list_filter(map_entries(attributes),
    e -> e.key NOT IN ('gen_ai.tool.call.arguments', 'gen_ai.tool.call.result'))) AS attributes)
    FROM read_parquet('{d}/L2_otel_map.parquet') ORDER BY start_time_unix_nano)
    TO '{p}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 122880)""")
con.execute(f"CREATE VIEW L2 AS SELECT * FROM read_parquet('{p}')")
con.execute(f"CREATE VIEW L1 AS SELECT * FROM read_parquet('{d}/L1_typed.parquet')")
con.execute(f"CREATE VIEW allow AS SELECT * FROM read_parquet('{d}/allowlist.parquet')")
out = {"bytes": p.stat().st_size, "queries": {}}
for q in ("Q1_tool_by_agent", "Q3_tool_breadth_errors", "Q4_failure_bursts", "Q5_off_allowlist"):
    eq = con.execute(Q[q]["L2_otel_map"]).fetchall() == con.execute(Q[q]["L1_typed"]).fetchall()
    s = []
    for _ in range(3):
        s += time_trials(lambda: con.execute(Q[q]["L2_otel_map"]).fetchall(), 2, 7)["samples_ms"]
    out["queries"][q] = {"answers_equal_L1": eq, "median_ms": round(statistics.median(s), 2),
                         "cv_pct": round(statistics.pstdev(s) / statistics.mean(s) * 100, 1),
                         "min_ms": min(s), "max_ms": max(s)}
    print(q, out["queries"][q])
print("bytes", out["bytes"])
(HERE / "results" / "exploratory_l2b_nopayload.json").write_text(json.dumps(out, indent=1))
