#!/usr/bin/env python3
"""Independent recount of the T8a headline numbers from raw captures (does not import analyze.py).
Usage: indep_check.py <runs-dir>   Prints one line per cell/rep."""
import json, sys
from pathlib import Path
R = Path(sys.argv[1])
PV="io.modelcontextprotocol/protocolVersion"; CI="io.modelcontextprotocol/clientInfo"; SI="io.modelcontextprotocol/serverInfo"
def jl(p): return [json.loads(l) for l in open(p)] if p.exists() else []
rows = []
for cell in sorted(p for p in R.iterdir() if p.is_dir()):
    for rep in sorted(cell.iterdir()):
        d = {"cell": cell.name, "rep": rep.name}
        msgs = []  # (dir, msg, http)
        if (rep/"wire.jsonl").exists():
            for w in jl(rep/"wire.jsonl"): msgs.append((w["dir"], json.loads(w["raw"]), None))
        else:
            ex = jl(rep/"http.jsonl")
            posts = [e for e in ex if e["request"]["method"]=="POST"]
            d["conns"] = len({e["conn"] for e in ex}); d["posts"] = len(posts)
            d["gets"] = sum(e["request"]["method"]=="GET" for e in ex); d["deletes"] = sum(e["request"]["method"]=="DELETE" for e in ex)
            d["sid_req"] = sum("mcp-session-id" in e["request"]["headers"] for e in posts)
            d["sid_resp"] = sum("mcp-session-id" in ((e.get("response") or {}).get("headers") or {}) for e in ex)
            d["mcp_method_hdr"] = sum("mcp-method" in e["request"]["headers"] for e in posts)
            names = []
            for e in posts:
                b = (e["request"].get("body") or {}).get("json") or {}
                if "mcp-name" in e["request"]["headers"]:
                    names.append((b.get("method"), e["request"]["headers"]["mcp-name"], (b.get("params") or {}).get("name") or (b.get("params") or {}).get("uri")))
            d["mcp_name"] = len(names); d["mcp_name_mismatch"] = sum(n[1]!=n[2] for n in names)
            d["status400"] = sum(((e.get("response") or {}).get("status")==400) for e in ex)
            for e in ex:
                q=e["request"]; s=e.get("response") or {}
                b=(q.get("body") or {}).get("json")
                if b is not None: msgs.append(("c2s", b, e))
                sb=s.get("body") or {}
                if sb.get("json") is not None: msgs.append(("s2c", sb["json"], e))
                for ev in sb.get("sse_events", []):
                    if "json" in ev: msgs.append(("s2c", ev["json"], e))
        c2s=[m for dd,m,_ in msgs if dd=="c2s"]; s2c=[m for dd,m,_ in msgs if dd=="s2c"]
        reqs=[m for m in c2s if "id" in m and "method" in m]
        res=[m for m in s2c if "id" in m and ("result" in m or "error" in m)]
        d["req"]=len(reqs); d["init"]=sum(m["method"]=="initialize" for m in reqs); d["discover"]=sum(m["method"]=="server/discover" for m in reqs)
        d["meta_pv_ci"]=sum(PV in ((m.get("params") or {}).get("_meta") or {}) and CI in ((m.get("params") or {}).get("_meta") or {}) for m in reqs)
        d["traceparent"]=sum("traceparent" in ((m.get("params") or {}).get("_meta") or {}) for m in reqs)
        d["results"]=sum("result" in m for m in res); d["meta_si"]=sum(SI in ((m.get("result") or {}).get("_meta") or {}) for m in res if "result" in m)
        d["log_notif"]=sum(m.get("method")=="notifications/message" for m in s2c)
        d["err_codes"]=sorted(m["error"]["code"] for m in res if "error" in m)
        tl=[m["result"] for m in res if "result" in m and "tools" in m["result"]]
        d["ttl"]=[ (r.get("ttlMs"), r.get("cacheScope")) for r in tl]
        se=(rep/"server.stderr").read_text(errors="replace").splitlines() if (rep/"server.stderr").exists() else []
        d["stderr"]=len(se); d["per_req"]=sum(l.startswith("Processing request of type") for l in se)
        d["deprec"]=sum("MCPDeprecationWarning" in l for l in se)
        so=jl(rep/"server.otel.jsonl"); co=jl(rep/"client.otel.jsonl")
        d["sspans"]=sum(s["kind"]=="SERVER" for s in so); d["cspans"]=len(co)
        d["shared_tid"]=len({s["trace_id"] for s in so} & {s["trace_id"] for s in co})
        cl=jl(rep/"client.jsonl")
        d["neg"]=[c.get("protocol_version") for c in cl if c.get("kind")=="negotiated"]
        ft=[c for c in cl if c.get("step")=="tools/call fail_tool"]
        d["fail_text"]=json.dumps(ft[0].get("result",{}).get("content",""))[:90] if ft else None
        rows.append(d)
for d in rows: print(json.dumps(d))
