#!/usr/bin/env python3
"""QUIET REPLICATION 2026-11-16 (new file; 11-15 files untouched). Nessie runs IN_MEMORY, so its catalog was lost
when drn-nessie stopped; the Iceberg data and metadata files survive in the drn-minio-data volume. Instead of
re-appending the parquet (which would write new data files at new locations), register each table in Nessie from
the exact metadata file recorded in the 11-15 _work/table_locations.json, then verify row counts against the
11-15 record and the pinned parquet. Writes _work_quiet_2026-11-16/table_locations.json (same shape as 11-15's).
Falls back to nothing: if registration fails, it reports and exits non-zero (load.py reload is the next step)."""
import json, sys
from pathlib import Path
import pyarrow.parquet as pq
import load as L

HERE = Path(__file__).parent
src = json.loads((HERE / "_work" / "table_locations.json").read_text())
out_dir = HERE / "_work_quiet_2026-11-16"
cat = L.catalog()
ok = True
report = {}
for ns in ("tpch", "soc"):
    try:
        cat.create_namespace(ns)
    except Exception as e:
        print("namespace", ns, type(e).__name__)
for ident, meta in src.items():
    ns, name = ident.split(".")
    parquet_rows = pq.ParquetFile(L.TABLES[ns][name]).metadata.num_rows
    try:
        try:
            tbl = cat.load_table(ident)
        except Exception:
            tbl = cat.register_table(ident, meta["metadata_location"])
        n = sum(f.file.record_count for f in tbl.scan().plan_files())
        same_meta = tbl.metadata_location == meta["metadata_location"]
        report[ident] = {"rows_now": n, "rows_1115": meta["rows"], "parquet_rows": parquet_rows,
                         "location_same": tbl.location() == meta["location"], "metadata_location_same": same_meta,
                         "snapshot_id": tbl.current_snapshot().snapshot_id if tbl.current_snapshot() else None}
        if not (n == meta["rows"] == parquet_rows and same_meta):
            ok = False
    except Exception as e:
        ok = False
        report[ident] = {"error": f"{type(e).__name__}: {str(e)[:300]}"}
    print(ident, report[ident], flush=True)
new = {k: dict(v) for k, v in src.items()}
(out_dir / "table_locations.json").write_text(json.dumps(new, indent=2))
(out_dir / "register_report.json").write_text(json.dumps({"all_match": ok, "tables": report}, indent=1))
print("ALL_MATCH" if ok else "MISMATCH")
sys.exit(0 if ok else 1)
