#!/usr/bin/env python3
"""Dry run on a SYNTHETIC fixture (not a scored run; PREREGISTRATION.md section 1).

Every fixture source field is invented (`fx.*`, schema "Fixture"), and the script asserts that no
fixture (schema, source, ocsf) triple is a corpus triple, so no arm touches a corpus row. OCSF
classes and paths are real 1.8.0. Shows that S1, S3, O0, O1, O2, the injector and the scorer
execute end to end. S2 runs here only with FIXTURE_TYPER, a stub over the invented `fx.<object>.*`
names that is test scaffolding, not the S2 typer (that is written by a separate author).
Outputs: results/dryrun/.
Usage: python3 -I dryrun.py
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arms as A  # noqa: E402
import common as C  # noqa: E402
import inject as I  # noqa: E402
import score as S  # noqa: E402

OUT = os.path.join(C.G, "results", "dryrun")

FIXTURE = [  # (source, ocsf, cls, expected-truth note)
    ("fx.user.name", "user.name", "authentication", "correct"),
    ("fx.user.name", "process.name", "process_activity", "kind crossing"),
    ("fx.src.ip", "src_endpoint.ip", "network_activity", "correct"),
    ("fx.src.ip", "time", "network_activity", "type crossing"),
    ("fx.process.pid", "process.pid", "process_activity", "correct"),
    ("fx.file.path", "process.file.path", "process_activity", "correct (process's file)"),
    ("fx.session.uid", "session.uid", "authentication", "Session target"),
    ("fx.user.name", "src_endpoint.no_such_attr", "network_activity", "invalid path"),
    ("fx.conn.uid", "connection_info.uid", "network_activity", "correct"),
    ("fx.evt.action", "activity_id", "authentication", "correct (declared enum cast)"),
    ("fx.flow.duration", "duration", "network_activity", "correct (float onto long)"),
    ("Elastic ECS|fx.zzz.ip", "src_endpoint.ip", "network_activity", "correct (real S1 table row)"),
]
FIXTURE_TABLE = {("Fixture", "name"): "string", ("Fixture", "ip"): "ip", ("Fixture", "pid"): "integer",
                 ("Fixture", "path"): "string", ("Fixture", "uid"): "string", ("Fixture", "action"): "string",
                 ("Fixture", "duration"): "float"}
FIXTURE_CLASS_PATHS = {
    "authentication": ("user.name", "user.uid", "session.uid", "src_endpoint.ip", "dst_endpoint.ip",
                       "actor.user.name", "time"),
    "network_activity": ("src_endpoint.ip", "dst_endpoint.ip", "src_endpoint.port", "connection_info.uid",
                         "time", "src_endpoint.hostname"),
    "process_activity": ("process.name", "process.pid", "process.file.path", "actor.process.name",
                         "actor.user.name", "device.ip", "time"),
}


class FIXTURE_TYPER:  # scaffolding for the dry run only
    @staticmethod
    def source_kind(schema, field):
        seg = field.split(".")[1] if field.startswith("fx.") else None
        return {"user": "user", "src": "network_endpoint", "process": "process", "file": "file",
                "session": "session", "conn": "network_connection_info", "zzz": "network_endpoint"}.get(seg)


def main():
    C.verify_pins()
    os.makedirs(os.path.join(OUT, "arms"), exist_ok=True)
    corpus_keys = {(t["schema"], t["source"], t["ocsf"]) for t in C.triples()}
    items = []
    for i, (src, path, cls, note) in enumerate(FIXTURE):
        schema, src = src.split("|") if "|" in src else ("Fixture", src)
        assert (schema, src, path) not in corpus_keys
        assert not any(s == src for _, s, _ in corpus_keys), "fixture source collides with a corpus source"
        cell = f"`{src}` (enum)~" if "enum" in note else f"`{src}`"
        items.append({"item_id": f"FX{i:02d}", "tid": f"FX{i:02d}", "schema": schema, "source": src,
                      "ocsf": path, "cls": cls, "cell": cell, "note": note})
    C.write_jsonl(os.path.join(OUT, "fixture-items.jsonl"), items)

    # injector on the fixture triples, with a fixture candidate pool
    e1, counts = I.generate(items, class_paths=lambda c: FIXTURE_CLASS_PATHS[c])
    C.write_jsonl(os.path.join(OUT, "e1-items.jsonl"), e1)
    json.dump(counts, open(os.path.join(OUT, "e1-counts.json"), "w"), indent=1)

    table = {**A.load_s1_table(), **FIXTURE_TABLE}  # the real frozen table plus fixture rows
    summary = {"_note": "SYNTHETIC FIXTURE ONLY: these counts and the verdict below exercise the code "
                        "path and carry no evidential weight", "e1_counts": counts}
    for arm in A.ARMS if hasattr(A, "ARMS") else ["S1", "S2", "S3", "O0", "O1", "O2"]:
        for name, its in (("corpus", items), ("e1", e1)):
            recs, meta = A.run_arm(arm, its, s1_table=table, s2_typer=FIXTURE_TYPER)
            C.write_jsonl(os.path.join(OUT, "arms", f"{arm}-{name}.jsonl"), recs)
            summary[f"{arm}-{name}"] = {"meta": meta, **{v: sum(r["verdict"] == v for r in recs)
                                                        for v in ("flag", "pass", "abstain")}}
    # per-item verdict grid for the fixture rows
    grid = {}
    for arm in ["S1", "S2", "S3", "O0", "O1", "O2"]:
        for r in C.read_jsonl(os.path.join(OUT, "arms", f"{arm}-corpus.jsonl")):
            grid.setdefault(r["item_id"], {})[arm] = r["verdict"]
    summary["fixture_grid"] = {it["item_id"]: dict(note=it["note"], **grid[it["item_id"]]) for it in items}

    # synthetic labels for the scorer (fixture only)
    truth = {"correct": ("correct", "no"), "kind crossing": ("wrong", "yes"), "type crossing": ("wrong", "no"),
             "correct (process's file)": ("correct", "no"), "Session target": ("correct", "no"),
             "invalid path": ("wrong", "unclear"), "correct (declared enum cast)": ("correct", "no"),
             "correct (float onto long)": ("correct", "no"), "correct (real S1 table row)": ("correct", "no")}
    with open(os.path.join(OUT, "key-batch1.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "tid", "origin", "kappa_subset"])
        for it in items:
            w.writerow([it["item_id"], it["tid"], "fixture", True])
    for name in ("labels-batch1.csv", "labels-kappa.csv"):
        with open(os.path.join(OUT, name), "w", newline="") as f:
            f.write("# fixture labels\n")
            w = csv.writer(f)
            w.writerow(["item_id", "label", "kind_crossing", "source_kind_adjudicated"])
            for it in items:
                lab, kc = truth[it["note"]]
                w.writerow([it["item_id"], lab, kc, ""])
    res = S.score(OUT)
    json.dump(res, open(os.path.join(OUT, "score.json"), "w"), indent=1)
    summary["score_decision"] = res["decision"]
    summary["score_e1_O1"] = res["e1"].get("O1")
    json.dump(summary, open(os.path.join(OUT, "dryrun-summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
