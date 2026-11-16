#!/usr/bin/env python3
"""QUIET REPLICATION 2026-11-16 data gate 1: count() of all 13 tables through icebergS3 (pinned metadata) and
native bench.* on ClickHouse, against the 11-15 row counts. Writes results/quiet-2026-11-16/data_gate_counts.json."""
import json, sys
sys.dont_write_bytecode = True
import run_engines_quiet  # noqa
import run_engines as R
locs = json.loads((R.WORK / "table_locations.json").read_text())
c = R.make_client("clickhouse_iceberg")
out, ok = {}, True
for arm in ("clickhouse_iceberg", "clickhouse_native"):
    refs = R.table_refs(arm)
    for ident, meta in locs.items():
        name = ident.split(".")[1]
        n = c.run(f"SELECT count() FROM {refs[name]}")[0][0]
        out[f"{arm}:{ident}"] = {"count": n, "rows_1115": meta["rows"], "match": n == meta["rows"]}
        ok &= n == meta["rows"]
        print(arm, ident, n, meta["rows"], n == meta["rows"], flush=True)
(R.RESULTS / "data_gate_counts.json").write_text(json.dumps({"all_match": ok, "counts": out}, indent=1))
print("GATE1", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
