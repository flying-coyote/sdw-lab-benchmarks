import json,statistics,sys
from pathlib import Path
import os; R=Path(__file__).resolve().parent.parent/"results"
L=["L1_typed","L2_otel_map","L3_aos_unmapped"]
N=os.environ.get("N","1000000")
for tag in sys.argv[1:]:
    D=R if (R/f"timing{tag}_n{N}_pass0.json").exists() else R.parent/"verify"/"rerun"
    ps=[json.loads((D/f"timing{tag}_n{N}_pass{p}.json").read_text()) for p in range(3)]
    print("==",tag, [ (p.get("loadavg_start",[None])[0],p.get("loadavg_end",[None])[0]) for p in ps])
    for q in ps[0]["queries"]:
        m={}
        for l in L:
            s=[x for p in ps for x in p["queries"][q]["timings"][l]["samples_ms"]]
            m[l]=(statistics.median(s),statistics.pstdev(s)/statistics.mean(s)*100,min(s),max(s),len(s))
        eq=all(p["queries"][q]["answers_equal"] for p in ps)
        print(f"{q:24s} L1 {m['L1_typed'][0]:.1f}({m['L1_typed'][1]:.0f}%) L2 {m['L2_otel_map'][0]:.1f} L3 {m['L3_aos_unmapped'][0]:.1f} L3/L1 {m['L3_aos_unmapped'][0]/m['L1_typed'][0]:.1f}x floor {m['L3_aos_unmapped'][2]/m['L1_typed'][3]:.2f} L2/L1 {m['L2_otel_map'][0]/m['L1_typed'][0]:.1f}x n={m['L1_typed'][4]} eq={eq} ans={ps[0]['queries'][q]['answer'][:2]}")
