"""T4-interdiction runner. For each seed: build the corpus (gen_corpus.py), load the same rows into SQLite
(stdlib) and DuckDB 1.5.3 (threads=4), compile every Sigma rule with pySigma's sqlite backend, run every
check on both engines, and score each (control, step) as CAUGHT / NOISY / MISSED per PREREGISTRATION.md.
Steps the pre-registration declares MISSED-by-construction are listed, not planted, not scored.

  taskset -c 0-3 nice -n 10 .venv/bin/python -I run.py        # writes results/interdiction.json (+ timings.json)

results/interdiction.json carries no timing field so three identical runs hash identically; monotonic
wall times (under contention, 4 cores) go to results/timings.json.
"""
import hashlib, json, os, re, sqlite3, statistics, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import duckdb  # noqa: E402
from sigma.backends.sqlite import sqliteBackend  # noqa: E402
from sigma.collection import SigmaCollection  # noqa: E402
import checks, gen_corpus  # noqa: E402

T_FLOOR, R_FLOOR = 0.9, 0.5
SEEDS = [20261109, 20261110, 20261111]
STATE_RANK = {"CAUGHT": 2, "NOISY": 1, "MISSED": 0}

# (control, step, set, by_construction) -- transcribed from the PREREGISTRATION.md table
SLOTS = [
    ("AML.M0019", "CS0076[2]", "rule", False), ("AML.M0019", "CS0076[7]", "rule", False), ("AML.M0019", "CS0076[4]", "rule", False),
    ("AML.M0043", "CS0076[2]", "rule", True), ("AML.M0043", "CS0074[22]", "rule", False), ("AML.M0043", "CS0068[23]", "rule", False),
    ("AML.M0005", "CS0076[2]", "rule", True), ("AML.M0005", "CS0074[10]", "rule", True), ("AML.M0005", "CS0076[6]", "rule", True),
    ("AML.M0005", "CS0068[0]", "mech", False), ("AML.M0005", "CS0023[3]", "mech", False),
    ("AML.M0011", "CS0074[13]", "rule", False), ("AML.M0011", "CS0074[2]", "rule", False), ("AML.M0011", "CS0074[24]", "rule", True),
    ("AML.M0011", "CS0031[1]", "mech", False),
    ("AML.M0020", "CS0076[7]", "rule", False), ("AML.M0020", "CS0076[8]", "rule", False), ("AML.M0020", "CS0074[20]", "rule", False),
    ("AML.M0020", "CS0047[2]", "mech", False),
    ("AML.M0024", "CS0034[3]", "rule", False), ("AML.M0024", "CS0076[7]", "rule", False), ("AML.M0024", "CS0076[4]", "rule", False),
    ("AML.M0024", "CS0053[5]", "mech", False), ("AML.M0024", "CS0047[5]", "mech", False),
    ("AML.M0040", "CS0076[11]", "rule", False), ("AML.M0040", "CS0075[7]", "mech", False),
    ("AML.M0013", "CS0073[1]", "rule", False), ("AML.M0013", "CS0069[13]", "rule", True), ("AML.M0013", "CS0023[1]", "rule", False),
    ("AML.M0013", "CS0047[1]", "mech", False),
]


def compile_rule(name):
    sql = sqliteBackend().convert(SigmaCollection.from_yaml(open(os.path.join(HERE, "rules", name)).read()))[-1]
    return sql.replace("SELECT *", "SELECT event_uid", 1)


def case_fold(sql):
    """Supplementary variant: lower() both sides of every LIKE (H5)."""
    return re.sub(r"(\w+) LIKE '([^']*)'", lambda m: f"lower({m.group(1)}) LIKE lower('{m.group(2)}')", sql)


def connections(T):
    sq = sqlite3.connect(":memory:")
    dk = duckdb.connect(":memory:")
    dk.execute("SET threads=4")
    for name, rows in T.items():
        cols = gen_corpus.columns(name)
        data = [[r[c] for c in cols] for r in rows]
        sq.execute(gen_corpus.ddl(name)); sq.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' * len(cols))})", data)
        dk.execute(gen_corpus.ddl(name)); dk.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' * len(cols))})", data)
    return {"sqlite": sq, "duckdb": dk}


def run_check(con, cid, kind, table, unit, src, truth_all, planted_control):
    """Return matched event uids, alert count, TP alert count (and the error if the engine refused the SQL)."""
    try:
        if kind == "sigma":
            sql = compile_rule(src).replace(" FROM logs", f" FROM {table}")
            uids = {r[0] for r in con.execute(sql).fetchall()}
            alerts = len(uids); tp = len(uids & planted_control)
            return {"matched": uids, "alerts": alerts, "tp": tp, "sql": sql}
        sql = checks.SQL[src]
        rows = con.execute(sql).fetchall()
        if unit == "message":
            ents = {r[0] for r in rows}
            uids = {r[1] for r in rows} | {r[2] for r in rows}
            per_ent = {r[0]: {r[1], r[2]} for r in rows}
        else:
            ents = {r[0] for r in rows}
            per_ent = {e: {u[0] for u in con.execute(checks.OWNED[unit], [e]).fetchall()} for e in ents}
            uids = set().union(*per_ent.values()) if per_ent else set()
        tp = sum(1 for e, owned in per_ent.items() if owned & planted_control)
        return {"matched": uids, "alerts": len(ents), "tp": tp, "entities": sorted(ents), "sql": sql}
    except Exception as e:
        return {"matched": set(), "alerts": 0, "tp": 0, "error": f"{type(e).__name__}: {re.sub(r'\\s+', ' ', str(e))[:160]}", "sql": None}


def state(recall, precision, error):
    if error or recall < R_FLOOR:
        return "MISSED"
    return "CAUGHT" if precision >= T_FLOOR else "NOISY"


def run_seed(seed, timings):
    t0 = time.monotonic()
    T, truth = gen_corpus.gen(seed)
    out = os.path.join(HERE, "corpus", str(seed)); gen_corpus.write(T, truth, out)
    truth_sha = hashlib.sha256(open(os.path.join(out, "truth.json"), "rb").read()).hexdigest()
    timings[f"{seed}.gen_write_s"] = round(time.monotonic() - t0, 3)
    cons = connections(T)
    timings[f"{seed}.load_both_engines_s"] = round(time.monotonic() - t0, 3)
    res = {"truth_sha256": truth_sha, "planted_per_step": {k: len(v) for k, v in truth.items()}, "checks": {}, "slots": []}
    check_runs = {}
    for ctrl, clist in checks.CHECKS.items():
        planted_control = set().union(*[set(truth[s]) for (c, s, _, bc) in SLOTS if c == ctrl and not bc])
        for cid, kind, table, unit, src in clist:
            for eng, con in cons.items():
                t1 = time.monotonic()
                r = run_check(con, cid, kind, table, unit, src, truth, planted_control)
                timings[f"{seed}.{ctrl}.{cid}.{eng}_s"] = round(time.monotonic() - t1, 4)
                check_runs[(ctrl, cid, eng)] = r
                prec = round(r["tp"] / r["alerts"], 4) if r["alerts"] else 0.0
                res["checks"][f"{ctrl}|{cid}|{eng}"] = {"kind": kind, "table": table, "unit": unit, "alerts": r["alerts"], "tp_alerts": r["tp"],
                                                         "precision": prec, "matched_events": len(r["matched"]), "error": r.get("error"),
                                                         **({"entities": r["entities"]} if "entities" in r else {})}
                if kind == "sigma" and cid in checks.CASE_SENSITIVE_RULES and r.get("sql"):
                    try:
                        uids = {x[0] for x in con.execute(case_fold(r["sql"])).fetchall()}
                        res["checks"][f"{ctrl}|{cid}|{eng}"]["supplementary_case_folded"] = {
                            "alerts": len(uids), "tp_alerts": len(uids & planted_control), "precision": round(len(uids & planted_control) / len(uids), 4) if uids else 0.0,
                            "matched_events": len(uids)}
                        check_runs[(ctrl, cid, eng, "folded")] = uids
                    except Exception as e:
                        res["checks"][f"{ctrl}|{cid}|{eng}"]["supplementary_case_folded"] = {"error": str(e)[:160]}
    for ctrl, step, sset, bc in SLOTS:
        slot = {"control": ctrl, "step": step, "set": sset, "by_construction": bc}
        if bc:
            slot["state"] = {"sqlite": "MISSED-by-construction", "duckdb": "MISSED-by-construction"}
            res["slots"].append(slot); continue
        suids = set(truth[step]); slot["planted_events"] = len(suids); slot["per_check"] = {}
        for eng in cons:
            best = ("MISSED", -1)
            for cid, kind, table, unit, src in checks.CHECKS[ctrl]:
                r = check_runs[(ctrl, cid, eng)]
                hit = len(r["matched"] & suids); recall = round(hit / len(suids), 4)
                prec = round(r["tp"] / r["alerts"], 4) if r["alerts"] else 0.0
                st = state(recall, prec, r.get("error"))
                slot["per_check"][f"{cid}|{eng}"] = {"recall": recall, "precision": prec, "state": st, **({"error": r["error"]} if r.get("error") else {})}
                if (ctrl, cid, eng, "folded") in check_runs:
                    fu = check_runs[(ctrl, cid, eng, "folded")]
                    slot["per_check"][f"{cid}|{eng}"]["supplementary_case_folded_recall"] = round(len(fu & suids) / len(suids), 4)
                if STATE_RANK[st] > best[1]:
                    best = (st, STATE_RANK[st])
            slot.setdefault("state", {})[eng] = best[0]
        res["slots"].append(slot)
    cons["sqlite"].close(); cons["duckdb"].close()
    timings[f"{seed}.total_s"] = round(time.monotonic() - t0, 3)
    return res


def summarise(per_seed):
    seeds = sorted(per_seed)
    slots = []
    for i, (ctrl, step, sset, bc) in enumerate(SLOTS):
        row = {"control": ctrl, "step": step, "set": sset, "by_construction": bc}
        for eng in ("sqlite", "duckdb"):
            states = [per_seed[s]["slots"][i]["state"][eng] for s in seeds]
            modal = max(set(states), key=states.count)
            row[eng] = {"states": states, "modal": modal, "seeds_agreeing": states.count(modal)}
            if not bc:
                for cid_eng, v in per_seed[seeds[0]]["slots"][i]["per_check"].items():
                    if cid_eng.endswith("|" + eng):
                        recs = [per_seed[s]["slots"][i]["per_check"][cid_eng]["recall"] for s in seeds]
                        precs = [per_seed[s]["slots"][i]["per_check"][cid_eng]["precision"] for s in seeds]
                        row[eng].setdefault("checks", {})[cid_eng.split("|")[0]] = {
                            "states": [per_seed[s]["slots"][i]["per_check"][cid_eng]["state"] for s in seeds],
                            "recall_min_med_max": [min(recs), statistics.median(recs), max(recs)],
                            "precision_min_med_max": [min(precs), statistics.median(precs), max(precs)]}
        slots.append(row)
    counts = {}
    for eng in ("sqlite", "duckdb"):
        for sset in ("rule", "mech"):
            c = {"CAUGHT": 0, "NOISY": 0, "MISSED": 0, "MISSED-by-construction": 0, "slots": 0}
            for row in slots:
                if row["set"] == sset:
                    c[row[eng]["modal"]] += 1; c["slots"] += 1
            counts[f"{sset}|{eng}"] = c
    per_control = {}
    for eng in ("sqlite", "duckdb"):
        for row in slots:
            d = per_control.setdefault(row["control"], {}).setdefault(eng, {"CAUGHT": 0, "NOISY": 0, "MISSED": 0, "MISSED-by-construction": 0})
            d[row[eng]["modal"]] += 1
    return {"slots": slots, "counts": counts, "per_control": per_control}


def main():
    timings = {"note": "monotonic wall seconds, 4 cores under contention with other benches; not a latency claim"}
    per_seed = {s: run_seed(s, timings) for s in SEEDS}
    summary = summarise(per_seed)
    obj = {"benchmark": "t4-interdiction", "precision_floor_T": T_FLOOR, "recall_floor": R_FLOOR, "seeds": SEEDS,
           "versions": {"duckdb": duckdb.__version__, "sqlite": sqlite3.sqlite_version, "python": sys.version.split()[0]},
           "summary": summary, "per_seed": {str(s): per_seed[s] for s in SEEDS},
           "compiled_sql": {f"{c}|{cid}": (compile_rule(src) if kind == "sigma" else checks.SQL[src]) for c, cl in checks.CHECKS.items() for cid, kind, _, _, src in cl}}
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    json.dump(obj, open(os.path.join(HERE, "results", "interdiction.json"), "w"), indent=1, sort_keys=True)
    json.dump(timings, open(os.path.join(HERE, "results", "timings.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(summary["counts"], indent=1))
    for row in summary["slots"]:
        print(f"{row['control']} {row['step']:11} {row['set']:4} sqlite={row['sqlite']['modal']:24} duckdb={row['duckdb']['modal']}")
    for k, v in sorted(per_seed[SEEDS[0]]["checks"].items()):
        print(f"  {k:36} alerts={v['alerts']:5} tp={v['tp_alerts']:5} p={v['precision']:.3f} err={v['error']}")


if __name__ == "__main__":
    main()
