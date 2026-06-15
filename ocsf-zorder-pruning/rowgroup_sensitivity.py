import sys, os, tempfile
sys.path.insert(0, '/home/USER/sdw-lab-benchmarks/ocsf-zorder-pruning')
import pyarrow.compute  # register pa.compute for run.py
import run as z

def measure(rg_size, n_rows=2_000_000):
    z.ROW_GROUP_SIZE = rg_size
    cols = z._gen_corpus(n_rows)
    queries = z.build_queries(cols)
    work = tempfile.mkdtemp(prefix=f"zrg_{rg_size}_")
    paths = {'unordered': work+'/u.parquet', 'single_sort': work+'/s.parquet', 'zorder': work+'/z.parquet'}
    z.write_unordered(cols, paths['unordered'])
    z.write_single_sort(cols, paths['single_sort'])
    z.write_zorder(cols, paths['zorder'])
    rg = {l: z.row_group_stats(p) for l, p in paths.items()}
    out = {}
    for q in queries:
        out[q['id']] = {l: z.count_prunable_rgs(rg[l], q['predicates']) for l in rg}
    return out

for size in (50_000, 122_880):
    print(f"\n===== ROW_GROUP_SIZE = {size:,} =====")
    r = measure(size)
    for qid, layouts in r.items():
        parts = []
        for l in ('unordered','single_sort','zorder'):
            c = layouts[l]
            parts.append(f"{l}={c['pct_pruned']}%(rg{c['total_rgs']})")
        print(f"  {qid:28} " + "  ".join(parts))
