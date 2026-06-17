"""SPEC-INTEGRITY real-vendor leg — the mechanism, grounded off the synthetic n=1 onto THREE named real
vendor formats (PAN-OS / Zeek / CloudTrail). Companion to spec_vs_emitted.py (which authored both the spec
and the divergence synthetically). This one uses the **real published field specs** (fetched verbatim from
the vendor docs, high-confidence; source URLs below) and applies each vendor's **real documented cross-version
schema change** under a spec-faithful parser pinned to the OLD version, scoring silent-vs-loud BY FORMAT CLASS.

Boundary: pure code diff, no LLM, no real telemetry — the specs are public vendor documentation, the parser
is deterministic. Cleared 2026-06-16 (public-vendor-doc-samples only; code-only diff, injection boundary does
not bind). Tier B/C: real published specs + each vendor's documented field-evolution; existence/format-class
result, NOT a prevalence rate (a rate needs a real-log corpus, which stays out of scope).

WHAT IS REAL HERE vs MODELED:
- REAL: the field specs (verbatim from the docs), the format class of each, and the FACT that each vendor adds
  fields across versions (PAN-OS field growth 8.x->10.1/11.0; Zeek ip_proto in 7.1.0; CloudTrail additive
  eventVersion history). Sources cited per vendor.
- MODELED (deterministically, from the real change): we apply the two real change SHAPES — a mid-record
  insertion and a tail append — to the real spec and run a spec-faithful (old-version-pinned) parser. The
  outcome is fully determined by the format class; nothing is invented beyond replaying the documented change.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))

# --- REAL published field specs (verbatim from the vendor docs; fetch wf26jdpmh, high-confidence) ---
VENDORS = {
    "PAN-OS TRAFFIC": {
        "format_class": "positional-delimited", "self_describing": False,
        "src": "https://docs.paloaltonetworks.com/pan-os/10-1/pan-os-admin/monitoring/use-syslog-for-monitoring/syslog-field-descriptions/traffic-log-fields",
        "real_change": "PAN-OS adds/shifts TRAFFIC fields across releases (8.x -> 10.1/11.0 grew the record substantially; the PR-294 src_user-area shift is the documented mid-record case).",
        "spec": ["FUTURE_USE","Receive Time","Serial Number","Type","Threat/Content Type","FUTURE_USE","Generated Time","Source Address","Destination Address","NAT Source IP","NAT Destination IP","Rule Name","Source User","Destination User","Application","Virtual System","Source Zone","Destination Zone","Inbound Interface","Outbound Interface","Log Action","FUTURE_USE","Session ID","Repeat Count","Source Port","Destination Port","NAT Source Port","NAT Destination Port","Flags","Protocol","Action","Bytes","Bytes Sent","Bytes Received","Packets","Start Time","Elapsed Time","Category","FUTURE_USE","Sequence Number","Action Flags","Source Country","Destination Country","FUTURE_USE","Packets Sent","Packets Received","Session End Reason"],
        # mid-record insertion point modeling the real PR-294-class change (a field inserted at the Source User area)
        "mid_insert_at": 12,  # index of "Source User"
    },
    "Zeek conn.log": {
        "format_class": "self-describing-header", "self_describing": True,
        "src": "https://docs.zeek.org/en/lts/logs/conn.html",
        "real_change": "Zeek 7.1.0 added the ip_proto column; 8.0.0 optional policy scripts add columns. Each emitted file carries a #fields header naming every column in order.",
        "spec": ["ts","uid","id.orig_h","id.orig_p","id.resp_h","id.resp_p","proto","service","duration","orig_bytes","resp_bytes","conn_state","local_orig","local_resp","missed_bytes","history","orig_pkts","orig_ip_bytes","resp_pkts","resp_ip_bytes","tunnel_parents","ip_proto"],
        "mid_insert_at": 7,  # e.g. a column added among the early fields
    },
    "AWS CloudTrail": {
        "format_class": "self-describing-json", "self_describing": True,
        "src": "https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html",
        "real_change": "CloudTrail record contents are additive across eventVersion (requestID/eventID 1.01; vpcEndpointId 1.04; tlsDetails/addendum later). Fields are JSON keys.",
        "spec": ["eventTime","eventVersion","userIdentity","eventSource","eventName","awsRegion","sourceIPAddress","userAgent","errorCode","errorMessage","requestParameters","responseElements","additionalEventData","requestID","eventID"],
        "mid_insert_at": 5,  # JSON has no positional contract; insertion index is irrelevant to the outcome
    },
}


def parse_positional(emitted_values, old_spec):
    """A spec-faithful positional parser pinned to OLD_SPEC: field i := emitted[i] by POSITION.
    Returns (silent_wrong, loud_missing, undelivered_new) vs the emitted record's TRUE field->value map."""
    # emitted_values is a list of (true_field_name, value); the parser assigns by index against old_spec
    silent_wrong = loud = 0
    for i, fname in enumerate(old_spec):
        if i >= len(emitted_values):
            loud += 1  # ran short -> null/missing (loud)
            continue
        true_field, _ = emitted_values[i]
        if true_field != fname:
            silent_wrong += 1  # present-but-WRONG: read a value that belongs to a different field, no error
    undelivered_new = max(0, len(emitted_values) - len(old_spec))  # emitted fields the old spec never reads
    return silent_wrong, loud, undelivered_new


def parse_self_describing(emitted_values, old_spec):
    """A consumer keyed by NAME (Zeek #fields header / JSON keys): reads each old field by its name wherever
    it sits; a renamed/dropped field is a visible miss (loud), a new field is announced (visible), never a
    silent positional shift."""
    emitted_by_name = {f: v for f, v in emitted_values}
    silent_wrong = 0
    loud = sum(1 for f in old_spec if f not in emitted_by_name)  # dropped/renamed -> visible null
    undelivered_new = sum(1 for f, _ in emitted_values if f not in set(old_spec))  # new fields, but NAMED/visible
    return silent_wrong, loud, undelivered_new


def emit(old_spec, change, insert_at):
    """Produce the NEW-version emitted record (list of (field,value)) after applying a real change SHAPE."""
    base = [(f, f"<{f}>") for f in old_spec]
    if change == "mid_insert":
        return base[:insert_at] + [("NEW_MIDFIELD", "<NEW_MIDFIELD>")] + base[insert_at:]
    if change == "tail_append":
        return base + [("NEW_TAILFIELD", "<NEW_TAILFIELD>")]
    return base


def main():
    results = {"benchmark": "spec-vs-emitted-integrity / real-vendor leg (H-SPEC-INTEGRITY-01)",
               "evidence_tier": "B/C (real published specs + documented field-evolution; format-class/existence result, not a prevalence rate)",
               "boundary": "public vendor-doc specs only; pure code diff, no LLM, no real telemetry",
               "vendors": {}}
    for name, v in VENDORS.items():
        spec = v["spec"]; parser = parse_positional if not v["self_describing"] else parse_self_describing
        rows = {}
        for change in ("mid_insert", "tail_append"):
            emitted = emit(spec, change, v["mid_insert_at"])
            sw, loud, undel = parser(emitted, spec)
            rows[change] = {"silent_wrong": sw, "loud_missing": loud, "undelivered_new_field": undel,
                            "of_fields": len(spec)}
        results["vendors"][name] = {
            "format_class": v["format_class"], "self_describing": v["self_describing"],
            "spec_fields": len(spec), "src": v["src"], "real_change": v["real_change"],
            "mid_insert": rows["mid_insert"], "tail_append": rows["tail_append"],
            "silent_cascade_exposed": rows["mid_insert"]["silent_wrong"] > 0,
        }
        m, t = rows["mid_insert"], rows["tail_append"]
        print(f"  {name:16s} [{v['format_class']:22s}] mid-insert: silent={m['silent_wrong']:2d}/{m['of_fields']} loud={m['loud_missing']} "
              f"| tail-append: silent={t['silent_wrong']} undelivered={t['undelivered_new_field']}", flush=True)

    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    with open(os.path.join(rdir, "realvendor_spec_vs_emitted.json"), "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
    print("  wrote results/realvendor_spec_vs_emitted.json", flush=True)


if __name__ == "__main__":
    main()
