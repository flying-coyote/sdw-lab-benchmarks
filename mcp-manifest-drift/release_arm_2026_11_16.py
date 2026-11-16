"""R5 H5 real-release arm, run 2026-11-16 (post-hoc relative to the H4 results; the versions, rules and
metric are the ones frozen in PREREGISTRATION.md on 2026-11-09, but this release-diff code was written
after the H4 results were known, which is why it lives in its own dated file).

Reads snapshots/release.json (written by the unmodified `snapshot.py release`), diffs consecutive published
versions per server with the frozen detector functions (detect.diff), and runs the five frozen Sigma rules
through path (a), pySigma-backend-duckdb 0.1.4 on DuckDB, reusing sigma_run.build/backend unchanged.
Writes only new files: events/release-events-{D0,D1}-2026-11-16.jsonl and results/release-arm-2026-11-16.json.
Usage: .venv/bin/python -I release_arm_2026_11_16.py
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.argv = [sys.argv[0], "a"]            # sigma_run reads its path from argv
sys.path.insert(0, str(HERE))
import detect, sigma_run                  # noqa: E402  (both guard main; importing writes nothing)
from sigma.collection import SigmaCollection  # noqa: E402

TAG = "2026-11-16"
rows = json.loads((HERE / "snapshots/release.json").read_text())
ORDER = {"filesystem": ["2025.8.21", "2025.11.25", "2025.12.18", "2026.1.14", "2026.7.4", "2026.7.10", "2026.8.31"],
         "everything": ["2025.12.18", "2026.1.14", "2026.1.26", "2026.7.4", "2026.8.18", "2026.8.31"]}
snap = {(r["server"], r["version"]): r for r in rows}

events = {"D0": [], "D1": []}
labels, transitions = {}, []
for srv, vers in ORDER.items():
    present = [v for v in vers if (srv, v) in snap]
    for a, b in zip(present, present[1:]):
        t = f"{srv}:{a}->{b}"
        A, B = snap[(srv, a)], snap[(srv, b)]
        transitions.append({"transition": t, "server": srv, "from": a, "to": b,
                            "serverInfo_from": A["serverInfo"], "serverInfo_to": B["serverInfo"],
                            "protocol_from": A["protocolVersion"], "protocol_to": B["protocolVersion"],
                            "tools_from": len(A["tools"]), "tools_to": len(B["tools"])})
        for var, canon in (("D0", False), ("D1", True)):
            evs = detect.diff(srv, B["serverInfo"], A["tools"], B["tools"], canon, f"rel-{var}-{t}")
            for e in evs:
                labels[e["metadata.uid"]] = {"transition": t, "variant": var, "tool": e["ai_capability.name"],
                                             "activity_id": e["activity_id"]}
            events[var] += evs

for var, evs in events.items():
    with open(HERE / f"events/release-events-{var}-{TAG}.jsonl", "w") as f:
        for e in evs:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

be, vers = sigma_run.backend()
vers["duckdb"] = sigma_run.duckdb.__version__
out = {"run": TAG, "path": "a", "versions": vers, "transitions": transitions, "rules": {}, "per_transition": {}}
cons = {var: sigma_run.build(evs, "duckdb") for var, evs in events.items() if evs}
for rf in sorted((HERE / "rules").glob("*.yml")):
    sql = be.convert(SigmaCollection.from_yaml(rf.read_text()))[0]
    sql = sql.replace("SELECT *", 'SELECT "metadata.uid"', 1)
    out["rules"][rf.stem] = {var: sorted(r[0] for r in con.execute(sql).fetchall()) for var, con in cons.items()}

for var in events:
    per = {}
    for tr in transitions:
        t = tr["transition"]
        evs = [e for e in events[var] if labels[e["metadata.uid"]]["transition"] == t]
        hit = {r: sorted(labels[u]["tool"] for u in uids.get(var, []) if labels[u]["transition"] == t)
               for r, uids in out["rules"].items()}
        comp = sorted(set(hit["s3_hidden_instruction"]) | set(hit["s4_description_rewrite"]) | set(hit["s5_schema_widening"]))
        per[t] = {"events": [{"tool": e["ai_capability.name"], "activity_id": e["activity_id"],
                              "desc_similarity": e["unmapped.desc_similarity"],
                              "desc_added_text": e["unmapped.desc_added_text"],
                              "schema_widened": e["unmapped.schema_widened"],
                              "schema_widened_reasons": e["unmapped.schema_widened_reasons"]} for e in evs],
                  "rule_hits": hit, "composite_tools": comp, "composite_fired": bool(comp)}
    out["per_transition"][var] = per

d1 = out["per_transition"]["D1"]
out["summary_D1"] = {
    "transitions": len(transitions),
    "transitions_with_any_event": sum(bool(v["events"]) for v in d1.values()),
    "events": len(events["D1"]),
    "s1_fired_on_every_changed_tool": all(sorted(x["tool"] for x in v["events"]) == v["rule_hits"]["s1_any_manifest_drift"]
                                          for v in d1.values()),
    "composite_fired_transitions": sum(v["composite_fired"] for v in d1.values()),
    "per_rule_transitions_fired": {r: sum(bool(v["rule_hits"][r]) for v in d1.values()) for r in out["rules"]},
    "per_rule_events_fired": {r: len(u.get("D1", [])) for r, u in out["rules"].items()},
}
(HERE / f"results/release-arm-{TAG}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(json.dumps(out["summary_D1"], indent=1))
for t, v in d1.items():
    print(t, len(v["events"]), "events; composite:", v["composite_tools"])
