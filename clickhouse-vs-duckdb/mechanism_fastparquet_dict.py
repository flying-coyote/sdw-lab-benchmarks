import os, sys, tempfile, shutil
sys.path.insert(0, "../lib"); sys.path.insert(0, ".")
import duckdb
from common import configure_duckdb
import corpus
import pyarrow as pa, pyarrow.parquet as pq, fastparquet

work = tempfile.mkdtemp(prefix="fp2_", dir="_work")
try:
    con = configure_duckdb(duckdb.connect())
    duckf = os.path.join(work, "duck.parquet")
    con.execute(f"COPY ({corpus.gen_select(1_000_000)}) TO '{duckf}' (FORMAT parquet, ROW_GROUP_SIZE 12288)")
    truth_u7 = con.execute(f"SELECT count(*) FROM ({corpus.gen_select(1_000_000)}) WHERE user_name='user7'").fetchone()[0]
    con.close()
    tbl = pq.read_table(duckf)   # byte-content into arrow, then rewrite with pyarrow
    paf_dict = os.path.join(work, "pa_dict.parquet"); paf_nodict = os.path.join(work, "pa_nodict.parquet")
    pq.write_table(tbl, paf_dict, row_group_size=12288, use_dictionary=True)
    pq.write_table(tbl, paf_nodict, row_group_size=12288, use_dictionary=False)
    print("truth user7 =", truth_u7)
    for label, f in [("duckdb-written", duckf), ("pyarrow dict", paf_dict), ("pyarrow no-dict", paf_nodict)]:
        col = fastparquet.ParquetFile(f).to_pandas(columns=["user_name"])["user_name"]
        n = int((col=="user7").sum())
        # also: does fastparquet read the SAME value pyarrow does, row by row? find mismatch count vs pyarrow
        pacol = pq.read_table(f, columns=["user_name"]).column(0).to_pylist()
        fpcol = col.tolist()
        mism = sum(1 for a,b in zip(pacol, fpcol) if a!=b)
        print(f"  {label:16} user7={n} {'OK' if n==truth_u7 else 'MISDECODE '+str(n-truth_u7)}  | rows where fastparquet!=pyarrow: {mism}")
    md = pq.ParquetFile(duckf).metadata
    idx = pq.ParquetFile(duckf).schema_arrow.names.index("user_name")
    cc = md.row_group(0).column(idx)
    print("DuckDB user_name encodings:", cc.encodings, "| dict_page:", cc.dictionary_page_offset is not None)
    print("fastparquet", fastparquet.__version__, "| pyarrow", pa.__version__)
finally:
    shutil.rmtree(work, ignore_errors=True)
