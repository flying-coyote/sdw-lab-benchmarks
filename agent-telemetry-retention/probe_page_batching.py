"""EXPLORATORY (not pre-registered): does T3 session-sorted compression depend on pyarrow's write_batch_size?

pyarrow only checks data_page_size after each write batch (default 1024 rows), so with ~200 KB prompt values a
"1 MiB page" can hold a whole session. write_batch_size=1 forces the page-size check per row.
    python probe_page_batching.py > results/probe_page_batching.json
"""
import json, os, tempfile
import numpy as np
import pyarrow.parquet as pq
import measure

out = []
for name in ["coding-real-s0", "chat-real-s0"]:
    t = measure.arm_table(measure.load(name), "T3_full")
    tok = int(t["message_context__total_tokens"].to_numpy().sum())
    perm = np.random.default_rng(4242).permutation(t.num_rows)
    d = tempfile.mkdtemp()
    for order, tt in [("session_sorted", t), ("random", t.take(perm))]:
        for wbs in [1, 1024, 20000]:
            for lvl in [1, 3, 19]:
                p = os.path.join(d, "x.parquet")
                pq.write_table(tt, p, compression="zstd", compression_level=lvl, write_batch_size=wbs,
                               row_group_size=1_048_576, version="2.6")
                out.append(dict(corpus=name, order=order, write_batch_size=wbs, zstd_level=lvl,
                                file_bytes=os.path.getsize(p), bytes_per_mtok=os.path.getsize(p) / tok * 1e6))
                os.remove(p)
print(json.dumps(out, indent=1))
