"""Arm (b): the six-source C1 mapping corpus on the strict full-schema validator,
OCSF 1.8.0 then 1.9.0 (H2, H3). Imports ../../ocsf-mapping-fidelity/mapping.py read-only.

Writes results/six-source-strict.json and results/proposed-mapping-changes.md.
Coverage arithmetic (pre-registered): invalid path -> counted unmapped; deprecated-but-valid
keeps its status and is reported. coverage = typed/total; lossy = (coerced+unmapped)/total.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ocsf_full as F  # noqa: E402

C1 = os.path.abspath(os.path.join(F.ROOT, "..", "ocsf-mapping-fidelity"))
sys.path.insert(0, C1)
import mapping as M  # noqa: E402

SOURCES = {
    "okta": ("authentication", M.OKTA_MAPPING),
    "crowdstrike": ("detection_finding", M.CROWDSTRIKE_MAPPING),
    "palo_alto": ("network_activity", M.PALO_ALTO_MAPPING),
    "cisco_asa": ("network_activity", M.CISCO_ASA_MAPPING),
    "cisco_umbrella": ("dns_activity", M.CISCO_UMBRELLA_MAPPING),
    "zscaler": ("http_activity", M.ZSCALER_MAPPING),
}


def run_version(version, profiles):
    schema, path = F.load_export(version, profiles=profiles)
    per = {}
    tot = {"total": 0, "typed": 0, "coerced": 0, "unmapped": 0, "invalid": 0, "deprecated": 0}
    for src, (cls, mp) in SOURCES.items():
        recs = []
        c = {"total": 0, "typed": 0, "coerced": 0, "unmapped": 0, "invalid": 0, "deprecated": 0,
             "published_typed": 0, "published_coerced": 0, "published_unmapped": 0}
        for field, r in mp.items():
            c["total"] += 1
            c["published_" + r["status"]] += 1
            status = r["status"]
            res = F.resolve(schema, cls, r["ocsf"])
            # class-level deprecation is not a mapping-path finding; keep attribute/object ones
            deps = [d for d in res["deprecations"] if not d["where"].startswith("class-itself:")]
            row = {"field": field, "ocsf": r["ocsf"], "published_status": r["status"],
                   "valid": res["valid"], "error": res["error"], "deprecations": deps,
                   "leaf_type": res["leaf_type"]}
            if not res["valid"]:
                status = "unmapped"
                c["invalid"] += 1
            if deps and res["valid"] and r["ocsf"] not in F.CATCH_ALLS:
                c["deprecated"] += 1
            row["strict_status"] = status
            c[status] += 1
            recs.append(row)
        c["coverage"] = round(c["typed"] / c["total"], 4)
        c["lossy"] = round((c["coerced"] + c["unmapped"]) / c["total"], 4)
        c["published_coverage"] = round(c["published_typed"] / c["total"], 4)
        per[src] = {"class": cls, "summary": c, "records": recs}
        for k in tot:
            tot[k] += c[k]
    tot["coverage"] = round(tot["typed"] / tot["total"], 4)
    tot["lossy"] = round((tot["coerced"] + tot["unmapped"]) / tot["total"], 4)
    return {"export": os.path.relpath(path, F.ROOT), "sha256": F.sha256(path), "per_source": per, "total": tot}


def findings(run):
    out = []
    for src, s in run["per_source"].items():
        for r in s["records"]:
            if r["ocsf"] in F.CATCH_ALLS:
                if not r["valid"]:
                    out.append((src, r["field"], r["ocsf"], "CATCH-ALL MISSING", r["error"]))
                continue
            if not r["valid"]:
                out.append((src, r["field"], r["ocsf"], "INVALID", r["error"]))
            for d in r["deprecations"]:
                out.append((src, r["field"], r["ocsf"], f"DEPRECATED since {d['since']}",
                            f"{d['where']}: {d['message']}"))
    return out


def main():
    res = {}
    for v in ("1.8.0", "1.9.0"):
        res[v] = {"profiles": run_version(v, True), "noprofile": run_version(v, False)}
    # paths valid only with profiles
    for v in res:
        only = []
        for src in SOURCES:
            for a, b in zip(res[v]["profiles"]["per_source"][src]["records"],
                            res[v]["noprofile"]["per_source"][src]["records"]):
                if a["valid"] and not b["valid"]:
                    only.append({"source": src, "field": a["field"], "ocsf": a["ocsf"]})
        res[v]["valid_only_with_profiles"] = only
    # drift 1.8.0 -> 1.9.0 (typed+coerced paths only, profiles export)
    drift = []
    for src in SOURCES:
        for a, b in zip(res["1.8.0"]["profiles"]["per_source"][src]["records"],
                        res["1.9.0"]["profiles"]["per_source"][src]["records"]):
            if a["published_status"] == "unmapped":
                continue
            became_invalid = a["valid"] and not b["valid"]
            new_dep = [d for d in b["deprecations"] if d["since"] == "1.9.0"]
            if became_invalid or new_dep:
                drift.append({"source": src, "field": a["field"], "ocsf": a["ocsf"],
                              "became_invalid": became_invalid, "new_deprecations": new_dep})
    res["drift_1.8.0_to_1.9.0"] = drift
    res["typed_plus_coerced_paths"] = sum(1 for s in SOURCES.values() for r in s[1].values() if r["status"] != "unmapped")
    # detections affected by any record needing change on 1.9.0 (invalid or deprecated)
    need = {}
    for src in SOURCES:
        for r in res["1.9.0"]["profiles"]["per_source"][src]["records"]:
            if r["ocsf"] in F.CATCH_ALLS:
                continue
            if (not r["valid"]) or r["deprecations"]:
                need[(src, r["field"])] = r
    dets = []
    for d in M.DETECTIONS:
        hit = [f for f in d["fields"] if (d["source"], f) in need]
        if hit:
            dets.append({"name": d["name"], "source": d["source"], "fields": hit})
    res["detections_depending_on_changed_records"] = dets
    with open(os.path.join(F.ROOT, "results", "six-source-strict.json"), "w") as f:
        json.dump(res, f, indent=1, sort_keys=True)

    # report
    for v in ("1.8.0", "1.9.0"):
        for k in ("profiles", "noprofile"):
            t = res[v][k]["total"]
            print(f"{v} {k:9s} typed={t['typed']} coerced={t['coerced']} unmapped={t['unmapped']} "
                  f"invalid={t['invalid']} deprecated={t['deprecated']} cov={t['coverage']} lossy={t['lossy']}")
        for fnd in findings(res[v]["profiles"]):
            print("   ", v, *fnd)
        print("   valid only with profiles:", res[v]["valid_only_with_profiles"])
    print("per-source 1.8.0 strict vs 1.9.0 strict (profiles):")
    for src in SOURCES:
        a = res["1.8.0"]["profiles"]["per_source"][src]["summary"]
        b = res["1.9.0"]["profiles"]["per_source"][src]["summary"]
        print(f"  {src:15s} published cov={a['published_coverage']} 1.8.0 cov={a['coverage']} lossy={a['lossy']}  "
              f"1.9.0 cov={b['coverage']} lossy={b['lossy']}")
    print("drift:", json.dumps(drift, indent=1))
    print("detections:", json.dumps(dets, indent=1))

    # proposed changes file
    lines = ["# Proposed mapping.py changes (NOT applied)", "",
             "Generated by `scripts/validate_six_source.py` from the strict validator on the pinned OCSF exports. "
             "Each row is a `mapping.py` record that would have to change to reach zero invalid and zero deprecated "
             "targets. The replacement is the one the schema's `@deprecated` message names, or `untyped` where the path "
             "has no valid home under the rule pre-registered in `PREREGISTRATION.md`. Remap versus untyped moves "
             "published figures and is the owner's call, so `mapping.py` is untouched.", "",
             "| version | source | field | current target | finding | proposed |", "|---|---|---|---|---|---|"]
    for v in ("1.8.0", "1.9.0"):
        for src, field, ocsf, kind, msg in findings(res[v]["profiles"]):
            prop = "untyped (status unmapped), unless the owner picks a valid home" if kind == "INVALID" else \
                "per message: " + msg.split(": ", 1)[-1]
            lines.append(f"| {v} | {src} | `{field}` | `{ocsf}` | {kind}: {msg} | {prop} |")
    with open(os.path.join(F.ROOT, "results", "proposed-mapping-changes.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
