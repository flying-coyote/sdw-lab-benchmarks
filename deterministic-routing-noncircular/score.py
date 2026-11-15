#!/usr/bin/env python3
"""Score the UNCHANGED deterministic-routing-sim rule stack against measured winners on the frozen corpus.

The Router class, WINNERS table and shape rules are imported from ../deterministic-routing-sim/route_sim.py
by path, unmodified (its sha256 is recorded in the output). Three scorings (pre-registered):
  S1 verbatim  : Router(use_catalog=True).route(sql) on the executed text with bare table names; the
                 router's own R1 decides the tier. Scored in both cells.
  S2 forced    : unchanged Router.shape() + WINNERS[shape][cell][0], scored in the hot and cold cell.
                 Headline for the cliff question (the hot cell is where native MergeTree is eligible).
  S3 vocab     : S2 after renaming tables to the sim's vocabulary (ioc->iocs, assets->dim_host).
                 Secondary, labelled; it is a deployment binding, not a rule change.
Cells: hot = {starrocks, clickhouse_iceberg, clickhouse_native}; cold = {starrocks, clickhouse_iceberg}.
Secondary universe adds trino to both cells.
  ../.venv/bin/python score.py   -> results/scores.json + printed summary
"""
import hashlib
import sys

sys.dont_write_bytecode = True  # do not leave a .pyc in ../deterministic-routing-sim (write scope)
import importlib.util
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import sqlglot

HERE = Path(__file__).parent
SIM = HERE.parent / "deterministic-routing-sim" / "route_sim.py"
spec = importlib.util.spec_from_file_location("route_sim", SIM)
route_sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route_sim)
Router, WINNERS = route_sim.Router, route_sim.WINNERS

RESULTS = HERE / "results"
ARMS = ["starrocks", "clickhouse_iceberg", "clickhouse_native", "trino"]
CELLS = {"hot": ["starrocks", "clickhouse_iceberg", "clickhouse_native"],
         "cold": ["starrocks", "clickhouse_iceberg"]}
CELLS_T = {k: v + ["trino"] for k, v in CELLS.items()}
SOFT_X, SOFT_ABS = 10.0, 5.0
DNF_PRICE = 300.0
VOCAB = {"$ioc ": "$iocs ", "$assets ": "$dim_host "}


def load_raw():
    raw = {}
    for arm in ARMS:
        p = RESULTS / f"raw_{arm}.json"
        if p.exists():
            raw[arm] = json.loads(p.read_text())
    return raw


def cell_view(raw, key, engines):
    """Per engine: ('ok', median, cv) | ('dnf', reason) | ('wrong', median) | ('missing',)."""
    v = {}
    for e in engines:
        rec = raw.get(e, {}).get("queries", {}).get(key)
        if rec is None:
            v[e] = ("missing",)
        elif "median_s" in rec:
            v[e] = ("ok", rec["median_s"], rec.get("cv_pct") or 0.0) if rec.get("matches_oracle") \
                else ("wrong", rec["median_s"], rec.get("cv_pct") or 0.0)
        else:
            v[e] = ("dnf", rec.get("dnf", "?"))
    ok = {e: x for e, x in v.items() if x[0] == "ok"}
    if not ok:
        return v, None
    best = min(ok, key=lambda e: ok[e][1])
    mb, cvb = ok[best][1], ok[best][2]
    accept = [e for e, x in ok.items() if (x[1] - mb) / mb * 100 <= max(cvb, x[2])]
    cliffs = {}
    for e, x in v.items():
        if x[0] == "dnf":
            cliffs[e] = "dnf:" + x[1]
        elif x[0] in ("ok", "wrong") and x[1] >= SOFT_X * mb and x[1] >= SOFT_ABS:
            cliffs[e] = "soft"
    wrong = [e for e, x in v.items() if x[0] == "wrong"]
    return v, {"best": best, "best_s": mb, "accept": sorted(accept), "cliffs": cliffs, "wrong": wrong}


def outcome(pick, v, truth):
    if pick in truth["cliffs"]:
        return "catastrophic"
    if pick in truth["wrong"]:
        return "silent_wrong"
    if pick not in v:
        return "ineligible"
    if pick in truth["accept"]:
        return "correct"
    return "minor"


def regret(pick, v, truth):
    x = v.get(pick)
    if x is None or x[0] in ("missing",):
        return None
    if x[0] == "dnf":
        return DNF_PRICE - truth["best_s"]
    return x[1] - truth["best_s"]


def picks_for(sql_bare, mode):
    r = Router(use_catalog=True)
    if mode == "S3":
        s = sql_bare
        for a, b in VOCAB.items():
            s = s.replace(a, b)
        sql = s.replace("$", "")
    else:
        sql = sql_bare.replace("$", "")
    tree = sqlglot.parse_one(sql)
    if mode == "S1":
        d = r.route(sql)
        return {"hot": d["pick"], "cold": d["pick"], "shape": d["shape"], "tier": d["tier_decided"]}
    shape = r.shape(tree)
    hot_w, cold_w, _ = WINNERS[shape]
    return {"hot": hot_w[0], "cold": cold_w[0], "shape": shape}


def summarise(rows):
    out = {}
    for cell in ("hot", "cold"):
        rs = [r for r in rows if r["cell"] == cell]
        c = Counter(r["outcome"] for r in rs)
        n = len(rs)
        regs = [r["regret_s"] for r in rs if r["regret_s"] is not None]
        with_cliff = [r for r in rs if r["cliff_engines"]]
        out[cell] = {"n": n, **dict(c),
                     "accuracy_tie_tolerant": round(c.get("correct", 0) / n, 3) if n else None,
                     "accuracy_strict": round(sum(r["strict"] for r in rs) / n, 3) if n else None,
                     "decisions_with_a_cliff_present": len(with_cliff),
                     "cliff_avoided": sum(1 for r in with_cliff if r["outcome"] != "catastrophic"),
                     "regret_total_s": round(sum(regs), 3), "regret_mean_s": round(statistics.mean(regs), 3) if regs else None}
    return out


def main():
    raw = load_raw()
    corpus = json.loads((HERE / "queries" / "corpus.json").read_text())["queries"]
    from ejs_queries import QUERIES as ANCHORS
    items = [("corpus", q["id"], q["family"], q["sql"]) for q in corpus] + \
            [("anchor", qid, "anchor", sql) for qid, sql in ANCHORS.items()]
    res = {"route_sim_sha256": hashlib.sha256(SIM.read_bytes()).hexdigest(),
           "corpus_sha256": hashlib.sha256((HERE / "queries" / "corpus.json").read_bytes()).hexdigest(),
           "engine_versions": {a: raw[a].get("engine_version") for a in raw},
           "excluded": [], "scorings": {}, "baselines": {}, "truth": {}, "families": {}}
    for universe, cells in (("primary", CELLS), ("with_trino", CELLS_T)):
        for mode in ("S1", "S2", "S3"):
            rows = []
            for setname, qid, fam, sql in items:
                key = f"{setname}:{qid}"
                p = picks_for(sql, mode)
                for cell, engines in cells.items():
                    v, truth = cell_view(raw, key, engines)
                    if truth is None:
                        if universe == "primary" and mode == "S2":
                            res["excluded"].append({"key": key, "cell": cell, "view": v})
                        continue
                    if universe == "primary" and mode == "S2":
                        res["truth"][f"{key}|{cell}"] = {"view": v, **truth}
                    pick = p[cell]
                    rows.append({"set": setname, "id": qid, "family": fam, "cell": cell, "shape": p["shape"],
                                 "tier": p.get("tier"), "pick": pick, "outcome": outcome(pick, v, truth),
                                 "strict": pick == truth["best"], "best": truth["best"], "accept": truth["accept"],
                                 "cliff_engines": truth["cliffs"], "regret_s": regret(pick, v, truth)})
            corpus_rows = [r for r in rows if r["set"] == "corpus"]
            fam = defaultdict(list)
            for r in corpus_rows:
                fam[r["family"]].append(r)
            res["scorings"][f"{universe}:{mode}"] = {
                "corpus": summarise(corpus_rows),
                "anchor": summarise([r for r in rows if r["set"] == "anchor"]),
                "by_family": {f: summarise(rs) for f, rs in sorted(fam.items())},
                "misclassified": [r for r in corpus_rows if r["outcome"] != "correct"],
                "rows": rows}
        # one-front-engine baselines (corpus only)
        for eng in ("starrocks", "clickhouse_iceberg", "clickhouse_native"):
            rows = []
            for setname, qid, fam, sql in items:
                if setname != "corpus":
                    continue
                for cell, engines in cells.items():
                    if eng not in engines:
                        continue
                    v, truth = cell_view(raw, f"{setname}:{qid}", engines)
                    if truth is None:
                        continue
                    rows.append({"cell": cell, "outcome": outcome(eng, v, truth), "strict": eng == truth["best"],
                                 "cliff_engines": truth["cliffs"], "regret_s": regret(eng, v, truth)})
            res["baselines"][f"{universe}:always_{eng}"] = summarise(rows)
    # shape-class vs family confusion + within-shape winner stability (H5), primary S2 cold+hot
    s2 = res["scorings"]["primary:S2"]["rows"]
    conf = Counter((r["family"], r["shape"]) for r in s2 if r["set"] == "corpus" and r["cell"] == "cold")
    res["shape_confusion"] = {f"{f} -> {s}": n for (f, s), n in sorted(conf.items())}
    stab = {}
    for cell in ("hot", "cold"):
        by = defaultdict(list)
        for r in s2:
            if r["set"] == "corpus" and r["cell"] == cell:
                by[r["shape"]].append(r["best"])
        stab[cell] = {s: {"n": len(b), "winners": dict(Counter(b)),
                          "modal_share": round(Counter(b).most_common(1)[0][1] / len(b), 3)}
                      for s, b in sorted(by.items())}
    res["within_shape_winner_stability"] = stab
    (RESULTS / "scores.json").write_text(json.dumps(res, indent=1, sort_keys=True, default=str))
    for k, s in res["scorings"].items():
        print(k, "corpus", json.dumps(s["corpus"]))
    for k, s in res["baselines"].items():
        print(k, json.dumps(s))
    print("excluded:", len(res["excluded"]))


if __name__ == "__main__":
    main()
