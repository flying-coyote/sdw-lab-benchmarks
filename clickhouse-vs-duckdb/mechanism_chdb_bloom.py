import os, sys, tempfile, shutil
sys.path.insert(0, "../lib"); sys.path.insert(0, ".")
import duckdb
from common import configure_duckdb
import corpus
from chdb import session as chs

work = tempfile.mkdtemp(prefix="chdiag_", dir="_work")
try:
    p = os.path.join(work, "corpus.parquet")
    con = configure_duckdb(duckdb.connect())
    con.execute(f"COPY ({corpus.gen_select(10_000_000)}) TO '{p}' (FORMAT parquet, ROW_GROUP_SIZE 12288)")
    probes = ["user42","user1337","user256","user1023"]
    truth = {v: con.execute(f"SELECT count(*) FROM ({corpus.gen_select(10_000_000)}) WHERE user_name='{v}'").fetchone()[0] for v in probes}
    con.close()
    sess = chs.Session()
    def ch(where_extra=""):
        out = {}
        for v in probes:
            sql = f"SELECT count(*) FROM file('{p}', Parquet) WHERE user_name='{v}'"
            if where_extra: sql += " SETTINGS " + where_extra
            try:
                out[v] = int(sess.query(sql, "CSV").data().strip().splitlines()[-1].strip('"'))
            except Exception as e:
                out[v] = f"ERR {type(e).__name__}: {str(e)[:80]}"
        return out
    configs = {
        "default (v3 reader, bloom pushdown on)": "",
        "use_native_reader_v3=0 (older reader)": "input_format_parquet_use_native_reader_v3=0",
        "bloom_filter_push_down=0": "input_format_parquet_bloom_filter_push_down=0",
        "filter_push_down=0 (min/max only)": "input_format_parquet_filter_push_down=0",
        "use_native_reader=0": "input_format_parquet_use_native_reader=0",
    }
    print("truth:", truth)
    for label, setting in configs.items():
        res = ch(setting)
        verdict = "ALL CORRECT" if all(res.get(v)==truth[v] for v in probes) else "DIVERGES"
        print(f"\n[{label}]  {verdict}")
        for v in probes:
            mark = "" if res.get(v)==truth[v] else f"  <-- {res.get(v)} vs truth {truth[v]}"
            print(f"   {v}: {res.get(v)}{mark}")
finally:
    shutil.rmtree(work, ignore_errors=True)
