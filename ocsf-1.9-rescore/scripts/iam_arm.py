"""Arm (e): Okta identity-lifecycle source, OCSF 1.8.0 account_change -> 1.9.0 user_management (H8a-c).

Implements the pre-registered procedure mechanically, so each judgement is the rule's, not ad hoc:
  phase 1 (1.8.0 export only): from OKTA_MAPPING (Authentication 3002) apply the lifecycle role rule
    (actor.* fields that land on user.* move to actor.user.*; target.id/alternateId/displayName/type
    -> user.uid/email_addr/full_name/type), keep paths that resolve strictly in account_change 1.8.0,
    else re-home to a same-named top-level class attribute (the path's leaf), else unmapped.
    Writes iam/okta_account_change_1.8.0.json.
  phase 2 (1.9.0 export): from the 1.8.0 file, keep paths that resolve strictly in user_management 1.9.0
    and are not deprecated; else the replacement the @deprecated message names (tried under the same
    parent, then at class level), else a same-named top-level class attribute, else unmapped.
    Writes iam/okta_user_management_1.9.0.json.
  Activities by enum caption: user.lifecycle.create -> "Create", user.lifecycle.activate -> "Enable".
  Cost metric and outputs as pre-registered; writes results/iam-arm.json.
Source fields come only from ../../ocsf-mapping-fidelity/schemas/okta/inventory.json (50 fields).
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ocsf_full as F  # noqa: E402

C1 = os.path.abspath(os.path.join(F.ROOT, "..", "ocsf-mapping-fidelity"))
sys.path.insert(0, C1)
import mapping as M  # noqa: E402

EVENT_TYPES = {"user.lifecycle.create": "Create", "user.lifecycle.activate": "Enable"}
TARGET_RULE = {"target.id": "user.uid", "target.alternateId": "user.email_addr",
               "target.displayName": "user.full_name", "target.type": "user.type"}
IAM_DIR = os.path.join(F.ROOT, "iam")


def caption_activity(schema, cls, caption):
    enum = schema["classes"][cls]["attributes"]["activity_id"]["enum"]
    hits = [int(k) for k, v in enum.items() if v.get("caption") == caption]
    return (hits[0], "exact caption") if hits else (None, f"no '{caption}' caption; enum={ {k: v['caption'] for k, v in enum.items()} }")


def strict_ok(schema, cls, path, allow_deprecated=True):
    r = F.resolve(schema, cls, path)
    deps = [d for d in r["deprecations"] if not d["where"].startswith("class-itself:")]
    return r["valid"] and (allow_deprecated or not deps), r, deps


def phase1():
    s18, p18 = F.load_export("1.8.0")
    cls = "account_change"
    inv = json.load(open(os.path.join(C1, "schemas", "okta", "inventory.json")))
    out = {}
    for f in (x["field"] for x in inv["fields"]):
        base = M.OKTA_MAPPING[f]
        path, status, note = base["ocsf"], base["status"], []
        if f in TARGET_RULE:
            path, status = TARGET_RULE[f], "typed"
            note.append("role rule: Okta target = the user acted on -> user.*")
        elif f.startswith("actor.") and path.startswith("user."):
            path = "actor." + path
            note.append("role rule: Okta actor = the principal making the change -> actor.user.*")
        if path in F.CATCH_ALLS:
            out[f] = {"ocsf": "unmapped", "status": "unmapped", "note": "; ".join(note + ["unmapped in the Authentication mapping"]),
                      "auth_mapping": base["ocsf"]}
            continue
        ok, r, _ = strict_ok(s18, cls, path)
        if not ok:
            leaf = path.split(".")[-1]
            if leaf in s18["classes"][cls]["attributes"] and strict_ok(s18, cls, leaf)[0]:
                note.append(f"'{path}' invalid in account_change ({r['error']}); re-homed to same-named class attribute '{leaf}'")
                path = leaf
            else:
                note.append(f"'{path}' invalid in account_change ({r['error']}); no same-named class attribute -> unmapped")
                path, status = "unmapped", "unmapped"
        out[f] = {"ocsf": path, "status": status, "note": "; ".join(note) or "kept from the Authentication mapping",
                  "auth_mapping": base["ocsf"]}
    acts = {et: dict(zip(("activity_id", "how"), caption_activity(s18, cls, cap))) for et, cap in EVENT_TYPES.items()}
    doc = {"class": cls, "class_uid": s18["classes"][cls]["uid"], "ocsf_version": "1.8.0", "export_sha256": F.sha256(p18),
           "event_types": acts, "fields": out}
    os.makedirs(IAM_DIR, exist_ok=True)
    with open(os.path.join(IAM_DIR, "okta_account_change_1.8.0.json"), "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
    return doc


def phase2(m18):
    s19, p19 = F.load_export("1.9.0")
    cls = "user_management"
    out = {}
    for f, r18 in m18["fields"].items():
        path, status, note = r18["ocsf"], r18["status"], []
        if path in F.CATCH_ALLS:
            out[f] = {"ocsf": path, "status": status, "note": "unmapped in 1.8.0", "path_change": None}
            continue
        ok, r, deps = strict_ok(s19, cls, path, allow_deprecated=False)
        change = None
        if not ok:
            cand = []
            for d in deps:
                for code in re.findall(r"<code>([^<]+)</code>", d.get("message") or ""):
                    parent = path.rsplit(".", 1)[0] if "." in path else ""
                    if parent:
                        cand.append(parent + "." + code)
                    cand.append(code)
            leaf = path.split(".")[-1]
            cand.append(leaf)
            new = next((c for c in cand if strict_ok(s19, cls, c, allow_deprecated=False)[0]), None)
            if deps and r["valid"]:
                change = "shared_deprecation"
                why = f"'{path}' deprecated in 1.9.0 ({'; '.join(d['where'] + ' since ' + str(d['since']) for d in deps)})"
            else:
                change = "class_move"
                why = f"'{path}' invalid in user_management ({r['error']})"
            if new:
                note.append(f"{why}; re-homed to '{new}'")
                path = new
            else:
                note.append(f"{why}; no valid replacement -> unmapped")
                path, status = "unmapped", "unmapped"
        out[f] = {"ocsf": path, "status": status, "note": "; ".join(note) or "kept", "path_change": change,
                  "path_1.8.0": r18["ocsf"]}
    acts = {et: dict(zip(("activity_id", "how"), caption_activity(s19, cls, cap))) for et, cap in EVENT_TYPES.items()}
    doc = {"class": cls, "class_uid": s19["classes"][cls]["uid"], "ocsf_version": "1.9.0", "export_sha256": F.sha256(p19),
           "class_deprecation_1.9.0_of_account_change": s19["classes"]["account_change"].get("@deprecated"),
           "event_types": acts, "fields": out}
    with open(os.path.join(IAM_DIR, "okta_user_management_1.9.0.json"), "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
    return doc


def tally(doc):
    c = {"typed": 0, "coerced": 0, "unmapped": 0}
    for r in doc["fields"].values():
        c[r["status"]] += 1
    c["total"] = sum(c.values())
    c["coverage"] = round(c["typed"] / c["total"], 4)
    return c


def main():
    m18 = phase1()
    m19 = phase2(m18)
    class_change = int(m18["class_uid"] != m19["class_uid"])
    act_changes = sum(int(m18["event_types"][et]["activity_id"] != m19["event_types"][et]["activity_id"]) for et in EVENT_TYPES)
    tuid_changes = sum(int(m18["class_uid"] * 100 + (m18["event_types"][et]["activity_id"] or 0) !=
                           m19["class_uid"] * 100 + (m19["event_types"][et]["activity_id"] or 0)) for et in EVENT_TYPES)
    moved = [f for f, r in m19["fields"].items() if r["path_change"] == "class_move"]
    shared = [f for f, r in m19["fields"].items() if r["path_change"] == "shared_deprecation"]
    lost = [f for f, r in m19["fields"].items() if m18["fields"][f]["status"] != "unmapped" and r["status"] == "unmapped"]
    six = json.load(open(os.path.join(F.ROOT, "results", "six-source-strict.json")))
    six_drift = len(six["drift_1.8.0_to_1.9.0"])
    total = class_change + act_changes + tuid_changes + len(moved) + len(shared)
    res = {"event_types": list(EVENT_TYPES), "inventory_fields": len(m18["fields"]),
           "account_change_1.8.0": {"class_uid": m18["class_uid"], "activities": m18["event_types"], "tally": tally(m18)},
           "user_management_1.9.0": {"class_uid": m19["class_uid"], "activities": m19["event_types"], "tally": tally(m19)},
           "cost": {"class_uid": class_change, "activity_id": act_changes, "type_uid": tuid_changes,
                    "paths_class_move_i": moved, "paths_shared_deprecation_ii": shared, "total_decisions_changed": total},
           "fields_lost": lost, "six_source_drift_count": six_drift,
           "H8a": total >= max(3, 3 * six_drift), "H8b": len(moved) >= 1, "H8c": len(lost) == 0}
    with open(os.path.join(F.ROOT, "results", "iam-arm.json"), "w") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    print(json.dumps(res, indent=1, sort_keys=True))
    for f, r in m19["fields"].items():
        if r["path_change"] or m18["fields"][f]["note"] != "kept from the Authentication mapping":
            print(f"  {f:46s} 1.8.0 {m18['fields'][f]['ocsf']:34s} | 1.9.0 {r['ocsf']:34s} | {m18['fields'][f]['note']} || {r['note']}")


if __name__ == "__main__":
    main()
