#!/usr/bin/env python3
"""Text-search/regex bench — SYNTHETIC corpus (approved 2026-06-15; the safe pattern from beaconing).

The owed BM25 arm (batch-2 DR#6) + external-review P4's ranking-inverting shape: does a columnar
engine match an inverted-index search engine on Sigma-style text filtering, and does ClickHouse's
native full-text index + Hyperscan multi-regex close the gap the index is expected to win?

SAFETY: corpus is FULLY SYNTHETIC log-message text (random vocabulary tokens + planted detection
targets at known rates; NO control characters, NO real attacker payloads). Loads + queries entirely
in-engine; only aggregates (latency, match counts vs planted ground truth, index sizes) surface — no
row content reaches the model. See [[feedback_security_telemetry_injection_surface]]. Tier B, single
host. Limitation (P1 corpus-skew): synthetic text is lower-variety than real, which somewhat flatters
both the inverted index and the token index — documented, not hidden.

Arms: OpenSearch 3.7 (analyzed text = inverted-index foil) · ClickHouse 26.5 brute scan (position/
match, no index) · ClickHouse native FTS (token index, hasToken) · ClickHouse Hyperscan
(multiMatchAny multi-regex). Pattern classes: TOKEN (whole token, index-friendly) · SUBSTRING
(sub-token, index-hostile) · REGEX. Run host-side: .venv/bin/python synth_text_bench.py
"""
import json, os, random, statistics, time
from pathlib import Path
import requests
import clickhouse_connect

random.seed(13)
N = int(os.environ.get("N_ROWS", "2000000"))
OS = "http://localhost:9200"
OS_INDEX = "synthmsg"
CH = dict(host="localhost", port=8323, password="ejsbench123")
CH_TABLE = "synthmsg"
OUT = Path(__file__).parent / "results"
TRIALS = 5

VOCAB = (["svchost.exe","explorer.exe","chrome.exe","lsass.exe","services.exe","cmd.exe","winlogon.exe",
          "conhost.exe","taskhostw.exe","dllhost.exe","spoolsv.exe","wininit.exe","csrss.exe"]
         + [f"C:\\\\Windows\\\\System32\\\\{w}" for w in ("kernel32","ntdll","user32","advapi32","ole32")]
         + ["EventID","ProcessId","ParentProcessId","IntegrityLevel","User","NT-AUTHORITY","SYSTEM",
            "TargetImage","SourceImage","GrantedAccess","CallTrace","LogonId","TerminalSessionId"]
         + [f"0x{random.randint(0,0xffffff):06x}" for _ in range(80)]
         + [f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}" for _ in range(60)]
         + [f"tok{i}" for i in range(300)])

# planted targets at known rates -> ground truth. (token / substring-in-token / regex-base64)
PLANT = {
    "powershell":      0.020,   # TOKEN
    "rundll32":        0.010,   # TOKEN
    "FromB64StringDec":0.005,   # SUBSTRING test: search "B64" (sub-token, no token-index hit)
}
B64_RATE = 0.004                 # REGEX test: a 52-char base64 blob
B64RE = "[A-Za-z0-9+/]{40,}"

def b64blob():
    import string
    return "".join(random.choice(string.ascii_letters + string.digits + "+/") for _ in range(52))

def gen():
    truth = {k: 0 for k in PLANT}; truth["__b64"] = 0
    rows = []
    for _ in range(N):
        toks = random.choices(VOCAB, k=random.randint(8, 20))
        for tgt, rate in PLANT.items():
            if random.random() < rate: toks.append(tgt); truth[tgt] += 1
        if random.random() < B64_RATE: toks.append(b64blob()); truth["__b64"] += 1
        rows.append(" ".join(toks))
    return rows, truth

def load_clickhouse(rows):
    c = clickhouse_connect.get_client(**CH)
    c.command("SET allow_experimental_full_text_index = 1")
    c.command(f"DROP TABLE IF EXISTS {CH_TABLE}")
    c.command(f"""CREATE TABLE {CH_TABLE} (id UInt64, message String,
        INDEX msg_tok message TYPE text(tokenizer='splitByNonAlpha') GRANULARITY 1)
        ENGINE=MergeTree ORDER BY id SETTINGS allow_experimental_full_text_index=1""")
    B = 100000
    for i in range(0, len(rows), B):
        chunk = rows[i:i+B]
        c.insert(CH_TABLE, [[i+j, chunk[j]] for j in range(len(chunk))], column_names=["id","message"])
    c.command(f"OPTIMIZE TABLE {CH_TABLE} FINAL")
    size = c.query(f"SELECT sum(bytes_on_disk) FROM system.parts WHERE table='{CH_TABLE}' AND active").result_rows[0][0]
    return c, size

def load_opensearch(rows):
    requests.delete(f"{OS}/{OS_INDEX}", timeout=60)
    requests.put(f"{OS}/{OS_INDEX}", json={"settings":{"number_of_shards":1,"number_of_replicas":0,"refresh_interval":"-1"},
        "mappings":{"properties":{"message":{"type":"text"}}}}, timeout=60).raise_for_status()
    buf=[]
    def flush(b):
        if not b: return
        rr=requests.post(f"{OS}/{OS_INDEX}/_bulk", data="\n".join(b)+"\n", headers={"Content-Type":"application/x-ndjson"}, timeout=300); rr.raise_for_status()
        if rr.json().get("errors"): print("  OS bulk errors", flush=True)
    for i,m in enumerate(rows):
        buf.append('{"index":{"_id":%d}}'%i); buf.append(json.dumps({"message":m}))
        if len(buf)>=20000: flush(buf); buf=[]
    flush(buf)
    requests.post(f"{OS}/{OS_INDEX}/_refresh", timeout=120)
    requests.post(f"{OS}/{OS_INDEX}/_forcemerge?max_num_segments=1", timeout=600)
    size=requests.get(f"{OS}/{OS_INDEX}/_stats/store", timeout=60).json()["indices"][OS_INDEX]["primaries"]["store"]["size_in_bytes"]
    return size

def med(xs): xs=sorted(xs); n=len(xs); return xs[n//2] if n%2 else (xs[n//2-1]+xs[n//2])/2

def time_os(query):
    def once():
        t0=time.perf_counter(); r=requests.post(f"{OS}/{OS_INDEX}/_search", json={"size":0,"track_total_hits":True,"query":query}, timeout=120); r.raise_for_status()
        return time.perf_counter()-t0, r.json()["hits"]["total"]["value"]
    once()
    ds=[]; cnt=0
    for _ in range(TRIALS): d,cnt=once(); ds.append(d)
    return round(med(ds),4), cnt

def time_ch(c, sql):
    c.query(sql)
    ds=[]; cnt=0
    for _ in range(TRIALS):
        t0=time.perf_counter(); cnt=c.query(sql).result_rows[0][0]; ds.append(time.perf_counter()-t0)
    return round(med(ds),4), cnt

def main():
    print(f"generating {N} synthetic messages...", flush=True)
    rows, truth = gen()
    print("planted ground truth:", truth, flush=True)
    print("loading ClickHouse...", flush=True); c, ch_size = load_clickhouse(rows)
    print("loading OpenSearch...", flush=True); os_size = load_opensearch(rows)
    out={"bench":"text-search-regex (synthetic corpus)","tier":"B","host":"single host","n_rows":N,
         "truth":truth,"storage_mb":{"clickhouse":round(ch_size/1e6),"opensearch":round(os_size/1e6)},
         "patterns":{}}
    # (name, class, os_query, ch_brute_sql, ch_fts_sql_or_None, ch_hyperscan_sql_or_None, expected_count)
    T=CH_TABLE
    pats=[
      ("powershell","token",{"match":{"message":"powershell"}},
        f"SELECT count() FROM {T} WHERE position(message,'powershell')>0",
        f"SELECT count() FROM {T} WHERE hasToken(message,'powershell')", None, truth["powershell"]),
      ("rundll32","token",{"match":{"message":"rundll32"}},
        f"SELECT count() FROM {T} WHERE position(message,'rundll32')>0",
        f"SELECT count() FROM {T} WHERE hasToken(message,'rundll32')", None, truth["rundll32"]),
      ("B64_substring","substring",{"wildcard":{"message":"*b64*"}},
        f"SELECT count() FROM {T} WHERE position(message,'B64')>0",
        None, None, truth["FromB64StringDec"]),
      ("base64_blob","regex",{"regexp":{"message":B64RE}},
        f"SELECT count() FROM {T} WHERE match(message,'{B64RE}')",
        None, f"SELECT count() FROM {T} WHERE multiMatchAny(message,['{B64RE}'])", truth["__b64"]),
    ]
    for name,cls,osq,brute,fts,hyper,exp in pats:
        rec={"class":cls,"expected":exp}
        try: rec["opensearch"]=dict(zip(("median_s","count"), time_os(osq)))
        except Exception as e: rec["opensearch"]={"error":str(e)[:120]}
        try: rec["ch_brute"]=dict(zip(("median_s","count"), time_ch(c,brute)))
        except Exception as e: rec["ch_brute"]={"error":str(e)[:120]}
        if fts:
            try: rec["ch_fts"]=dict(zip(("median_s","count"), time_ch(c,fts)))
            except Exception as e: rec["ch_fts"]={"error":str(e)[:120]}
        if hyper:
            try: rec["ch_hyperscan"]=dict(zip(("median_s","count"), time_ch(c,hyper)))
            except Exception as e: rec["ch_hyperscan"]={"error":str(e)[:120]}
        out["patterns"][name]=rec
        def s(k): return f"{rec[k]['median_s']*1000:.0f}ms/{rec[k]['count']}" if k in rec and 'median_s' in rec[k] else (rec[k]['error'][:20] if k in rec else "-")
        print(f"{name:14}[{cls:9}] exp={exp:6} OS={s('opensearch'):>14} brute={s('ch_brute'):>14} fts={s('ch_fts'):>14} hyper={s('ch_hyperscan'):>14}", flush=True)
    out["storage_note"]=f"ClickHouse {out['storage_mb']['clickhouse']}MB vs OpenSearch {out['storage_mb']['opensearch']}MB"
    print("\nstorage:", out["storage_note"], flush=True)
    OUT.mkdir(parents=True, exist_ok=True); (OUT/"synth_text.json").write_text(json.dumps(out, indent=2))
    print("-> results/synth_text.json")

if __name__ == "__main__":
    main()
