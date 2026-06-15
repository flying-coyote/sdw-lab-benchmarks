#!/usr/bin/env python3
"""§9 / H-SPEC-INTEGRITY-01 — the spec-as-defective-contract failure, generalized off the PAN-OS n=1.

The hypothesis: when a vendor's PUBLISHED field spec disagrees with the data the product actually emits,
a spec-faithful parser inherits the misalignment silently, and in POSITIONAL formats one disagreement
cascades to corrupt every downstream field (present-but-wrong, no null, no error — nothing fires). This
harness measures the MECHANISM across format CLASSES on synthetic records (we author both the spec and the
controlled divergence — so this demonstrates + quantifies the structural failure's *blast radius* by format
class; it is NOT a measurement of real vendors' disagreement rates, which needs real specs + emitted samples).

For each (format class × disagreement type): generate N records from ground truth, serialize them with the
divergence, parse by the SPEC, and classify every field — correct / SILENT-wrong (present, ≠ truth, no
null/error) / loud-miss (null/error). Blast radius = mean SILENT-wrong fields per record. Synthetic,
deterministic. Tier B.
"""
import json, random

random.seed(7)
N = 5000
# a PAN-OS-TRAFFIC-shaped schema (positions matter for the positional format)
SPEC = ["receive_time", "serial", "type", "subtype", "src", "dst", "src_user", "dst_user", "app", "action", "bytes", "session_id"]


def truth_record(i):
    return {
        "receive_time": f"2026/06/15 12:00:{i%60:02d}", "serial": f"0123456-{i%9999}", "type": "TRAFFIC",
        "subtype": "end", "src": f"10.0.{i%255}.{(i*7)%255}", "dst": f"93.184.{i%255}.{(i*3)%255}",
        "src_user": f"corp\\u{i%2000}", "dst_user": "", "app": random.choice(["ssl", "dns", "web-browsing", "smb"]),
        "action": random.choice(["allow", "deny"]), "bytes": str(random.randint(64, 90000)), "session_id": str(100000 + i),
    }


def classify(parsed, truth):
    """correct / silent_wrong (present but != truth) / loud_miss (None/empty-where-truth-nonempty)."""
    c = s = lm = 0
    for f in SPEC:
        pv = parsed.get(f, None); tv = truth.get(f, "")
        if pv == tv:
            c += 1
        elif pv is None:
            lm += 1            # field absent/null -> a null-check or schema validator CAN fire
        else:
            s += 1             # present but wrong -> nothing fires; only ground truth catches it
    return c, s, lm


# ---- serializers + spec-faithful parsers per format class, with the controlled divergence ----
def run_positional(disagreement):
    """Positional CSV. Parser reads by SPEC index. Divergence shifts/omits -> cascade."""
    sw = lm = cor = 0
    for i in range(N):
        t = truth_record(i)
        vals = [t[f] for f in SPEC]
        if disagreement == "field_omission":      # product omits src_user (idx 6) -> everything after shifts left
            emitted = vals[:6] + vals[7:]
        elif disagreement == "tail_append":        # product appends a corrected hi-res-ts field at the tail (not in spec)
            emitted = vals + [f"2026-06-15T12:00:{i%60:02d}.123-04:00"]
        elif disagreement == "type_drift":         # product emits app+port composite at the app slot (idx 8)
            emitted = vals[:8] + [vals[8] + "/443"] + vals[9:]
        else:
            emitted = vals
        line = ",".join(emitted)
        toks = line.split(",")
        parsed = {SPEC[j]: (toks[j] if j < len(toks) else None) for j in range(len(SPEC))}
        c, s, l = classify(parsed, t); cor += c; sw += s; lm += l
    return {"correct": cor, "silent_wrong": sw, "loud_miss": lm}


def run_selfdescribing(fmt, disagreement):
    """KV or JSON. Parser reads by KEY. Divergence renames/omits a key -> localized loud null."""
    sw = lm = cor = 0
    for i in range(N):
        t = truth_record(i)
        emitted = dict(t)
        if disagreement == "key_rename":           # spec key 'src_user' but product emits 'srcuser'
            emitted["srcuser"] = emitted.pop("src_user")
        elif disagreement == "field_omission":     # product omits src_user entirely
            emitted.pop("src_user")
        # serialize + reparse by the SAME format (self-describing), then read by SPEC keys
        if fmt == "kv":
            s_ = " ".join(f'{k}="{v}"' for k, v in emitted.items())
            got = dict(__import__("re").findall(r'(\w+)="([^"]*)"', s_))
        else:  # json
            got = json.loads(json.dumps(emitted))
        parsed = {f: got.get(f, None) for f in SPEC}
        c, s, l = classify(parsed, t); cor += c; sw += s; lm += l
    return {"correct": cor, "silent_wrong": sw, "loud_miss": lm}


def main():
    out = {"bench": "spec-vs-emitted-integrity (H-SPEC-INTEGRITY-01 §9)", "tier": "B", "n_records": N,
           "n_fields": len(SPEC), "cases": {}}
    cases = [
        ("positional_csv", "field_omission", lambda: run_positional("field_omission")),
        ("positional_csv", "tail_append", lambda: run_positional("tail_append")),
        ("positional_csv", "type_drift", lambda: run_positional("type_drift")),
        ("kv_pairs", "key_rename", lambda: run_selfdescribing("kv", "key_rename")),
        ("kv_pairs", "field_omission", lambda: run_selfdescribing("kv", "field_omission")),
        ("json", "key_rename", lambda: run_selfdescribing("json", "key_rename")),
    ]
    for fmt, dis, fn in cases:
        r = fn()
        r["silent_per_record"] = round(r["silent_wrong"] / N, 2)
        r["loud_per_record"] = round(r["loud_miss"] / N, 2)
        out["cases"][f"{fmt}:{dis}"] = r
        print(f"  {fmt:14} {dis:14} -> SILENT-wrong/rec={r['silent_per_record']:>5}  loud-miss/rec={r['loud_per_record']:>4}  "
              f"(of {len(SPEC)} fields)", flush=True)
    # headline: positional silent blast radius vs self-describing
    pos = [v["silent_per_record"] for k, v in out["cases"].items() if k.startswith("positional")]
    sd = [v["silent_per_record"] for k, v in out["cases"].items() if not k.startswith("positional")]
    out["positional_max_silent_blast"] = max(pos)
    out["selfdescribing_max_silent_blast"] = max(sd)
    json.dump(out, open("/home/USER/sdw-lab-benchmarks/spec-vs-emitted-integrity/results/spec_vs_emitted.json", "w"), indent=2)
    print(f"\npositional SILENT blast radius up to {max(pos)} fields/record (cascade); "
          f"self-describing up to {max(sd)} (localized, mostly loud-null). "
          f"-> the spec-defect failure is a property of POSITIONAL formats, not a PAN-OS quirk.")


if __name__ == "__main__":
    main()
