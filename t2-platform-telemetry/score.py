#!/usr/bin/env python3
"""Score the Claude Code OTLP export (arm A) against the known session, per trial.

Reads results/claude-<cfg>-t<N>/offsets_{before,after}.txt and slices the collector JSONL files for that
trial, then flattens every log record / metric data point / span to (name, attribute set, values) and
tests each pre-registered field F1..F12 for presence and value-match. Also computes attribute-set variance
across the trials of a configuration (H3). Stdlib only.
"""
import json, os, sys, glob, collections

HERE = os.path.dirname(os.path.abspath(__file__))
SENTINEL = "SDW-T2-SENTINEL-7f3a9c2e"
PROMPT = "Read the file fixtures/known.txt and reply with exactly the sentinel token it contains, nothing else."


def anyval(v):
    """OTLP JSON AnyValue -> python."""
    if not isinstance(v, dict):
        return v
    for k in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if k in v:
            return v[k]
    if "arrayValue" in v:
        return [anyval(x) for x in v["arrayValue"].get("values", [])]
    if "kvlistValue" in v:
        return {kv["key"]: anyval(kv["value"]) for kv in v["kvlistValue"].get("values", [])}
    return v


def attrs(lst):
    return {kv["key"]: anyval(kv.get("value")) for kv in (lst or [])}


def slice_lines(path, a, b):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        lines = f.read().splitlines()
    return [json.loads(l) for l in lines[a:b] if l.strip()]


def flatten_logs(docs):
    out = []
    for d in docs:
        for rl in d.get("resourceLogs", []):
            res = attrs(rl.get("resource", {}).get("attributes"))
            for sl in rl.get("scopeLogs", []):
                for lr in sl.get("logRecords", []):
                    a = attrs(lr.get("attributes"))
                    body = anyval(lr.get("body", {}))
                    name = a.get("event.name") or (body if isinstance(body, str) else "?")
                    out.append({"kind": "log", "name": name, "attrs": a, "resource": res, "body": body,
                                "time": lr.get("timeUnixNano")})
    return out


def flatten_metrics(docs):
    out = []
    for d in docs:
        for rm in d.get("resourceMetrics", []):
            res = attrs(rm.get("resource", {}).get("attributes"))
            for sm in rm.get("scopeMetrics", []):
                for m in sm.get("metrics", []):
                    for kind in ("sum", "gauge", "histogram"):
                        if kind in m:
                            for dp in m[kind].get("dataPoints", []):
                                val = dp.get("asDouble", dp.get("asInt", dp.get("sum")))
                                out.append({"kind": "metric", "name": m["name"], "unit": m.get("unit"),
                                            "attrs": attrs(dp.get("attributes")), "resource": res, "value": val,
                                            "time": dp.get("timeUnixNano")})
    return out


def flatten_traces(docs):
    out = []
    for d in docs:
        for rs in d.get("resourceSpans", []):
            res = attrs(rs.get("resource", {}).get("attributes"))
            for ss in rs.get("scopeSpans", []):
                for sp in ss.get("spans", []):
                    evs = [{"name": e.get("name"), "attrs": attrs(e.get("attributes"))} for e in sp.get("events", [])]
                    out.append({"kind": "span", "name": sp.get("name"), "attrs": attrs(sp.get("attributes")),
                                "resource": res, "events": evs, "time": sp.get("startTimeUnixNano")})
    return out


def walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_strings(v)


def score_trial(items):
    allattrs = {}
    for it in items:
        for k, v in it["attrs"].items():
            allattrs.setdefault(k, []).append(v)
        for k, v in it.get("resource", {}).items():
            allattrs.setdefault("resource." + k, []).append(v)
        for ev in it.get("events", []):
            for k, v in ev["attrs"].items():
                allattrs.setdefault("spanevent." + ev["name"] + "." + k, []).append(v)
    blob = list(walk_strings([it["attrs"] for it in items] + [it.get("events", []) for it in items]))

    def has(*keys):
        return [k for k in keys if k in allattrs]

    def val(k):
        vs = allattrs.get(k, [])
        return vs[0] if vs else None

    f = {}
    f["F1 user identity"] = {"present": bool(has("user.email", "user.account_uuid", "user.id")),
                             "keys": has("user.email", "user.account_uuid", "user.account_id", "user.id", "organization.id"),
                             "email_present": "user.email" in allattrs}
    f["F2 session id"] = {"present": "session.id" in allattrs, "distinct": len(set(allattrs.get("session.id", [])))}
    ptext = [s for s in blob if PROMPT in s]
    f["F3 prompt text"] = {"present": bool(ptext), "keys": has("prompt", "prompt_text", "user_prompt"),
                           "length_only": "prompt_length" in allattrs and not ptext,
                           "redacted_values": sorted(set(str(v) for k in ("prompt", "prompt_text") for v in allattrs.get(k, [])))[:3]}
    tn = [v for v in allattrs.get("tool_name", []) if v]
    f["F4 tool name"] = {"present": bool(tn), "values": sorted(set(map(str, tn)))}
    path_hits = [s for s in blob if "fixtures/known.txt" in s]
    f["F5 tool args (file path)"] = {"present": bool(path_hits) and bool(has("tool_input", "tool_parameters", "file_path")),
                                     "keys": has("tool_input", "tool_parameters", "file_path"),
                                     "path_seen_anywhere": bool(path_hits)}
    sent_hits_out = [k for k, vs in allattrs.items() if any(SENTINEL in str(v) for v in vs)]
    f["F6 tool output / file content"] = {"present": any(k.startswith("spanevent.tool.output") or k in ("tool_output", "output", "new_context") or "tool.output" in k for k in sent_hits_out),
                                          "keys_with_sentinel": sent_hits_out}
    f["F7 model id"] = {"present": "model" in allattrs, "values": sorted(set(map(str, allattrs.get("model", []))))}
    tok_keys = has("input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens")
    tok_metric = any(it["kind"] == "metric" and it["name"] == "claude_code.token.usage" for it in items)
    f["F8 token counts"] = {"present": bool(tok_keys) or tok_metric, "event_keys": tok_keys, "metric": tok_metric,
                            "input_tokens": allattrs.get("input_tokens", [None])[0], "output_tokens": allattrs.get("output_tokens", [None])[0]}
    cost_metric = any(it["kind"] == "metric" and it["name"] == "claude_code.cost.usage" for it in items)
    f["F9 cost"] = {"present": "cost_usd" in allattrs or cost_metric, "event_keys": has("cost_usd", "cost_usd_micros"),
                    "metric": cost_metric, "cost_usd_values": allattrs.get("cost_usd", [])[:3]}
    rtext = [k for k in ("response", "response_text", "response.model_output") if k in allattrs and any(SENTINEL in str(v) for v in allattrs[k])]
    f["F10 response text"] = {"present": bool(rtext), "keys": rtext, "length_only": "response_length" in allattrs and not rtext,
                              "redacted_values": sorted(set(map(str, allattrs.get("response", []))))[:3]}
    f["F11 caller/host identity"] = {"present": bool(has("resource.host.arch", "resource.os.type", "terminal.type", "resource.host.name", "workspace.host_paths")),
                                     "keys": has("resource.host.arch", "resource.os.type", "resource.os.version", "resource.wsl.version", "terminal.type", "resource.host.name", "workspace.host_paths"),
                                     "client_ip": False}
    f["F12 timestamps"] = {"present": any(it.get("time") for it in items)}
    counts = collections.Counter((it["kind"], it["name"]) for it in items)
    return f, allattrs, counts


def main():
    cfgs = sys.argv[1:] or ["A1", "A2"]
    report = {}
    for cfg in cfgs:
        trials = sorted(glob.glob(os.path.join(HERE, "results", f"claude-{cfg}-t*")))
        per_trial = {}
        attr_sets = {}  # (kind,name) -> list of attr-name sets per trial
        for t in trials:
            b = [int(x) for x in open(os.path.join(t, "offsets_before.txt")).read().split()]
            a = [int(x) for x in open(os.path.join(t, "offsets_after.txt")).read().split()]
            items = (flatten_logs(slice_lines(os.path.join(HERE, "collector/out/logs.jsonl"), b[0], a[0]))
                     + flatten_metrics(slice_lines(os.path.join(HERE, "collector/out/metrics.jsonl"), b[1], a[1]))
                     + flatten_traces(slice_lines(os.path.join(HERE, "collector/out/traces.jsonl"), b[2], a[2])))
            f, allattrs, counts = score_trial(items)
            per_name = collections.defaultdict(set)
            for it in items:
                per_name[(it["kind"], it["name"])].update(it["attrs"].keys())
            for k, s in per_name.items():
                attr_sets.setdefault(k, []).append(s)
            with open(os.path.join(t, "events_flat.json"), "w") as fh:
                json.dump(items, fh, indent=1, default=str)
            per_trial[os.path.basename(t)] = {"fields": f, "counts": {f"{k[0]}:{k[1]}": v for k, v in counts.items()},
                                              "n_items": len(items)}
        # H3 variance: attributes present in fewer than all trials for each (kind,name)
        variance = {}
        for k, sets in attr_sets.items():
            n = len(sets)
            union = set().union(*sets)
            inter = set.intersection(*sets) if sets else set()
            unstable = sorted(union - inter)
            variance[f"{k[0]}:{k[1]}"] = {"trials_seen": n, "unstable_attrs": unstable}
        report[cfg] = {"trials": per_trial, "attr_variance": variance}
    out = os.path.join(HERE, "results", "claude_scores.json")
    with open(out, "w") as fh:
        json.dump(report, fh, indent=1, default=str)
    # compact console summary
    for cfg, r in report.items():
        print(f"== {cfg}")
        for t, tr in r["trials"].items():
            pres = {k: v["present"] for k, v in tr["fields"].items()}
            print(f"  {t}: items={tr['n_items']} " + " ".join(f"{k.split()[0]}={'Y' if v else 'n'}" for k, v in pres.items()))
        unstable = {k: v["unstable_attrs"] for k, v in r["attr_variance"].items() if v["unstable_attrs"]}
        print(f"  unstable attrs across trials: {unstable if unstable else 'none'}")
        seen_lt = {k: v["trials_seen"] for k, v in r["attr_variance"].items() if v["trials_seen"] < len(r["trials"])}
        print(f"  event types not seen in every trial: {seen_lt if seen_lt else 'none'}")


if __name__ == "__main__":
    main()
