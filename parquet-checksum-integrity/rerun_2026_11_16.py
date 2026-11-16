"""Post-hoc version re-check of the 2026-06-06 page-checksum bake-off (run 2026-11-16).

Not a new experiment: it imports the unmodified write/corrupt/reader adapters from run.py and re-runs them on
two build sets (the June pins and current releases), writing ONLY to dated new files. run.py's tracked
results/ files are not touched.

Two additions, both because run.py's CAPABILITY table is hard-coded from June research and so cannot notice a
newly added knob:
  1. probe_knobs(): searches each reader's own settings / signatures for anything named like a checksum or
     verification option, and records what it finds.
  2. extra opt-in readers, tried only if the probe finds a candidate knob on that build.

    <venv>/bin/python -I rerun_2026_11_16.py <label>     # label = june-pins | current
"""
import inspect
import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # -I drops the script dir; add it back explicitly to import the frozen run.py
import run as frozen  # noqa: E402  (unmodified June harness)

PAT = ("checksum", "crc", "verif")


def _match(s):
    s = s.lower()
    return any(p in s for p in PAT)


def probe_knobs():
    out = {}
    import duckdb
    con = duckdb.connect()
    rows = con.execute("SELECT name, value, description FROM duckdb_settings()").fetchall()
    out["duckdb"] = [{"name": n, "value": v, "desc": d} for n, v, d in rows if _match(n) or _match(d or "")]
    try:
        fn = con.execute("SELECT parameters FROM duckdb_functions() WHERE function_name='read_parquet' LIMIT 1").fetchone()
        out["duckdb_read_parquet_params"] = [p for p in (fn[0] if fn else []) if _match(p)]
    except Exception as e:  # noqa: BLE001
        out["duckdb_read_parquet_params"] = f"probe failed: {e}"
    import datafusion
    ctx = datafusion.SessionContext()
    try:
        cfg = ctx.sql("SHOW ALL").to_pydict()
        keys = cfg.get("name") or cfg.get("Name") or []
        out["datafusion"] = [k for k in keys if _match(k)]
    except Exception as e:  # noqa: BLE001
        out["datafusion"] = f"probe failed: {e}"
    import polars as pl
    out["polars_read_parquet_params"] = [p for p in inspect.signature(pl.read_parquet).parameters if _match(p)]
    out["polars_scan_parquet_params"] = [p for p in inspect.signature(pl.scan_parquet).parameters if _match(p)]
    import pyarrow.parquet as pq
    out["pyarrow_read_table_params"] = [p for p in inspect.signature(pq.read_table).parameters if _match(p)]
    from chdb import session as chs
    s = chs.Session()
    try:
        r = s.query("SELECT name, value FROM system.settings WHERE name ILIKE '%parquet%' AND "
                    "(name ILIKE '%checksum%' OR name ILIKE '%crc%' OR name ILIKE '%verif%')", "JSONEachRow").data()
        out["chdb"] = [json.loads(line) for line in r.splitlines() if line.strip()]
    except Exception as e:  # noqa: BLE001
        out["chdb"] = f"probe failed: {e}"
    return out


def run(label):
    knobs = probe_knobs()
    work = tempfile.mkdtemp(prefix="crc_rerun_")
    try:
        crc_file = frozen.make_corrupt(True, work, "crc")
        with_crc = frozen.read_all(crc_file, frozen.READERS)
        opt_in = frozen.read_all(crc_file, frozen.OPT_IN_READERS)
        # chDB stock verifies; also check it is the CRC doing it: the no-checksum control must come back +1.
        no_crc = frozen.read_all(frozen.make_corrupt(False, work, "noc"), frozen.READERS)
        # any newly found knob gets an opt-in try on the SAME corrupted file
        extra = {}
        if isinstance(knobs.get("datafusion"), list) and knobs["datafusion"]:
            import datafusion
            for k in knobs["datafusion"]:
                def r_df(p, k=k):
                    cfg = datafusion.SessionConfig().set(k, "true")
                    ctx = datafusion.SessionContext(cfg); ctx.register_parquet("t", p)
                    return int(ctx.sql("SELECT sum(v) AS s FROM t").to_pydict()["s"][0])
                extra[f"datafusion[{k}=true]"] = r_df
        for name in ("polars_read_parquet_params",):
            for k in knobs.get(name, []) or []:
                import polars as pl
                extra[f"polars[{k}=True]"] = (lambda p, k=k: int(pl.read_parquet(p, **{k: True})["v"].sum()))
        if isinstance(knobs.get("duckdb"), list):
            import duckdb
            for row in knobs["duckdb"]:
                n = row["name"]
                if "debug" in n:
                    continue  # debug_verify_* cover DuckDB's own storage, per the June research
                def r_dk(p, n=n):
                    c = duckdb.connect(); c.execute(f"SET {n}=true")
                    return int(c.execute(f"SELECT sum(v) FROM read_parquet('{p}')").fetchone()[0])
                extra[f"duckdb[{n}=true]"] = r_dk
        extra_res = frozen.read_all(crc_file, extra) if extra else {}
        env = {m: __import__(m).__version__ for m in ("pyarrow", "duckdb", "polars", "datafusion", "chdb")}
        try:
            import importlib.metadata as md
            env["chdb-core"] = md.version("chdb-core")
        except Exception:  # noqa: BLE001
            pass
        return {
            "label": label,
            "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "python": sys.version.split()[0],
            "environment": env,
            "truth_sum": frozen.TRUTH,
            "knob_probe": knobs,
            "with_checksum_stock": with_crc,
            "opt_in_verification": opt_in,
            "extra_opt_in_from_probe": extra_res,
            "no_checksum_control": no_crc,
            "verify_by_default": sorted(k for k, v in with_crc.items() if v["verifies"]),
            "silent_wrong_stock": sorted(k for k, v in with_crc.items() if not v["verifies"]),
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    label = sys.argv[1]
    res = run(label)
    out = os.path.join(HERE, "results", f"rerun-2026-11-16-{label}.json")
    json.dump(res, open(out, "w"), indent=2, sort_keys=True, default=str)
    print(json.dumps({k: res[k] for k in ("environment", "verify_by_default", "silent_wrong_stock")}, indent=1))
    print("opt-in:", {k: v["verdict"] for k, v in res["opt_in_verification"].items()})
    print("extra:", {k: v["verdict"] for k, v in res["extra_opt_in_from_probe"].items()})
    print("knobs:", json.dumps(res["knob_probe"], default=str)[:1500])
    print("wrote", out)
