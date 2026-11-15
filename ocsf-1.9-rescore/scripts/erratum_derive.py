"""Re-derive the four points of the pipeline-normalization-fidelity erratum (draft 12 item 1)
from the saved inputs, over all 100,000 zeek_conn records. Read-only: writes one JSON file
to ocsf-1.9-rescore/results/erratum-derivation.json and nothing else.

Inputs (all inside ../pipeline-normalization-fidelity/):
  _work/zeek_conn.corpus.jsonl, _work/zeek_conn.gold.jsonl  (gen_corpus.py output, sha256 in manifest)
  results/tenzir_zeek_conn.emitted.jsonl                     (Tenzir 6.0.0 / library 671e049)
  ../ocsf-mapping-fidelity/schemas/ocsf/ocsf_1.8.0_subset.json + schemas/ocsf/ocsf_1.8.0_ext_subset.json

Points:
  1. conn_state x activity_id cross-tab (gold vs Tenzir) and the gold's pinned activity_id.
  2. What sits in `unmapped` on every emitted record.
  3. Where Tenzir put uid / service / history, and whether those paths (and the gold's) resolve
     in the merged 1.8.0 subset, "full" or "deep".
  4. `ts`: emitted `time` type, and whether parsing it back reproduces the corpus value
     (at ms, us and ns precision); `duration` differences characterised.
"""
import collections
import datetime as dt
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.abspath(os.path.join(HERE, "..", ".."))
PNF = os.path.join(LAB, "pipeline-normalization-fidelity")
sys.path.insert(0, os.path.join(LAB, "ocsf-mapping-fidelity"))
from map_fidelity import resolve_ocsf_path  # noqa: E402  (read-only import)

CORPUS = os.path.join(PNF, "_work", "zeek_conn.corpus.jsonl")
GOLD = os.path.join(PNF, "_work", "zeek_conn.gold.jsonl")
EMITTED = os.path.join(PNF, "results", "tenzir_zeek_conn.emitted.jsonl")
C1 = os.path.join(LAB, "ocsf-mapping-fidelity", "schemas", "ocsf", "ocsf_1.8.0_subset.json")
EXT = os.path.join(PNF, "schemas", "ocsf", "ocsf_1.8.0_ext_subset.json")
OUT = os.path.join(LAB, "ocsf-1.9-rescore", "results", "erratum-derivation.json")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(p):
    out = {}
    with open(p) as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                out[r["_id"]] = r
    return out


def get(o, dotted):
    for s in dotted.split("."):
        if isinstance(o, dict) and s in o:
            o = o[s]
        else:
            return False, None
    return True, o


def parse_rfc3339_ns(s):
    """'2026-01-06T14:33:05.181363968Z' -> integer ns since epoch (exact, no float)."""
    assert s.endswith("Z")
    base, frac = s[:-1].split(".") if "." in s else (s[:-1], "0")
    secs = int(dt.datetime.strptime(base, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp())
    frac = (frac + "000000000")[:9]
    return secs * 10**9 + int(frac)


def main():
    schema = json.load(open(C1))
    ext = json.load(open(EXT))
    schema["classes"].update(ext.get("classes", {}))
    schema["objects"].update(ext.get("objects", {}))

    corpus, gold, emitted = load(CORPUS), load(GOLD), load(EMITTED)
    n = len(gold)
    assert n == len(corpus) == len(emitted) == 100000, (n, len(corpus), len(emitted))

    # 1. cross-tab
    xt = collections.Counter()
    gold_acts = collections.Counter()
    for k, g in gold.items():
        gold_acts[g["activity_id"]] += 1
        xt[(corpus[k]["conn_state"], g["activity_id"], emitted[k].get("activity_id"))] += 1
    agree = sum(c for (st, ga, ta), c in xt.items() if ga == ta)

    # 2. unmapped contents
    unmapped_keysets = collections.Counter()
    for e in emitted.values():
        unmapped_keysets[tuple(sorted((e.get("unmapped") or {}).keys()))] += 1

    # 3. where uid/service/history landed
    probes = {
        "uid": ["connection_info.uid", "metadata.original_event_uid", "metadata.correlation_uid", "metadata.uid"],
        "service": ["app_protocol_name", "app_name"],
        "history": ["connection_info.flag_history", "connection_info.tcp_flags"],
    }
    landing = {}
    for field, paths in probes.items():
        landing[field] = {}
        for p in paths:
            eq = present = 0
            for k, e in emitted.items():
                ok, v = get(e, p)
                if ok and v is not None:
                    present += 1
                    if v == corpus[k][field]:
                        eq += 1
            try:
                res = resolve_ocsf_path(schema, "network_activity", p)
            except ValueError as ex:
                res = f"INVALID: {ex}"
            landing[field][p] = {"present_non_null": present, "equals_source_value": eq,
                                 "resolves_in_merged_1.8.0_subset": res}
    # service '-' handling
    svc_dash = sum(1 for k in corpus if corpus[k]["service"] == "-")
    svc_dash_emitted = collections.Counter()
    for k in corpus:
        if corpus[k]["service"] == "-":
            ok, v = get(emitted[k], "app_protocol_name")
            svc_dash_emitted[repr(v) if ok else "<absent>"] += 1

    # 4. ts / time
    time_types = collections.Counter(type(e.get("time")).__name__ for e in emitted.values())
    ms_ok = us_ok = ns_ok = 0
    max_ns_err = 0
    for k, e in emitted.items():
        ns = parse_rfc3339_ns(e["time"])
        ts = corpus[k]["ts"]  # float seconds, 6 decimals as generated
        # exact decimal reading of the corpus value as written (6 dp)
        src_us = round(ts * 10**6)
        src_ms_gold = gold[k]["fields"]["ts"]["value"]  # int(ts*1000), the gold's own coercion
        if ns // 10**6 == src_ms_gold:
            ms_ok += 1
        if round(ns / 1000) == src_us:
            us_ok += 1
        err = abs(ns - src_us * 1000)
        max_ns_err = max(max_ns_err, err)
        if err == 0:
            ns_ok += 1
    # duration
    dur_diffs = collections.Counter()
    dur_rule = collections.Counter()
    for k, e in emitted.items():
        gv = gold[k]["fields"]["duration"]["value"]
        tv = e.get("duration")
        if tv != gv:
            dur_diffs[tv - gv] += 1
            s = corpus[k]["duration"] * 1000
            import math
            dur_rule["emitted==floor(s*1000)" if tv == math.floor(s) else
                     "emitted==ceil" if tv == math.ceil(s) else "other"] += 1

    out = {
        "generated_by": "ocsf-1.9-rescore/scripts/erratum_derive.py",
        "inputs_sha256": {"corpus": sha(CORPUS), "gold": sha(GOLD), "emitted": sha(EMITTED),
                          "c1_subset": sha(C1), "ext_subset": sha(EXT)},
        "records": n,
        "gold_activity_id_distribution": dict(gold_acts),
        "crosstab_conn_state_gold_tenzir": sorted([[st, ga, ta, c] for (st, ga, ta), c in xt.items()]),
        "activity_agreement_records": agree,
        "emitted_metadata_version": dict(collections.Counter(e.get("metadata", {}).get("version") for e in emitted.values())),
        "unmapped_keysets": {"|".join(k) or "<empty>": c for k, c in unmapped_keysets.items()},
        "landing": landing,
        "service_dash_records": svc_dash,
        "service_dash_app_protocol_name_values": dict(svc_dash_emitted),
        "time_json_types": dict(time_types),
        "time_parse_back": {"ms_equals_gold_int_ms": ms_ok, "us_equals_corpus_6dp": us_ok,
                            "ns_exact_vs_corpus_6dp": ns_ok, "max_abs_err_ns": max_ns_err},
        "duration_diffs_emitted_minus_gold_ms": {str(k): v for k, v in dur_diffs.items()},
        "duration_diff_rule": dict(dur_rule),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
