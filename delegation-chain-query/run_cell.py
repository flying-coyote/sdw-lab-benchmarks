"""Run one (rows, depth) cell: load the same Parquet into DuckDB and chDB, check every arm's flagged-chain
set against generator ground truth (untimed warmup), then time 5 round-robin rounds interleaving
engine x arm so shared host noise lands on both sides of every within-cell ratio.

Arms (escalation = a hop whose scope_mask is not a subset of the authority it was delegated from):
  A_recursive  recursive CTE walks each chain from its root, carrying effective scope (bitwise AND).
  B_selfjoin   one non-recursive child->parent self-join, per-hop subset check.
  C_materialized  filter on parent_eff_scope, a column the generator (standing in for ingest) wrote.
  D_rootonly   filter on root_scope only; cheaper, and blind to the "reacquire" class by construction.
All durations use time.perf_counter_ns (monotonic). Hot/warm only: tables are in memory.
"""
import json
import os
import sys
import threading
import time

import chdb
import duckdb
from chdb import session as chs

TIMEOUT_S = 300
ROUNDS = 5
SLOW_WARMUP_MS = 60_000  # engine-arms whose warmup exceeds this get 3 timed trials, not 5
MEM_BYTES = 16 * 1024**3

DUCK = {
    "A_recursive": """
WITH RECURSIVE walk(event_uid, chain_uid, eff, esc) AS (
  SELECT event_uid, chain_uid, scope_mask, 0 FROM delegation WHERE parent_uid IS NULL
  UNION ALL
  SELECT d.event_uid, w.chain_uid, w.eff & d.scope_mask,
         CASE WHEN (d.scope_mask | w.eff) <> w.eff THEN 1 ELSE 0 END
  FROM walk w JOIN delegation d ON d.parent_uid = w.event_uid
)
SELECT DISTINCT chain_uid FROM walk WHERE esc = 1""",
    "B_selfjoin": """
SELECT DISTINCT c.chain_uid FROM delegation c JOIN delegation p ON c.parent_uid = p.event_uid
WHERE (c.scope_mask | p.scope_mask) <> p.scope_mask""",
    "C_materialized": """
SELECT DISTINCT chain_uid FROM delegation
WHERE parent_eff_scope IS NOT NULL AND (scope_mask | parent_eff_scope) <> parent_eff_scope""",
    "D_rootonly": """
SELECT DISTINCT chain_uid FROM delegation WHERE (scope_mask | root_scope) <> root_scope""",
}
CH = {
    "A_recursive": """
WITH RECURSIVE walk AS (
  SELECT event_uid, chain_uid, scope_mask AS eff, toUInt8(0) AS esc FROM delegation WHERE parent_uid IS NULL
  UNION ALL
  SELECT d.event_uid AS event_uid, w.chain_uid AS chain_uid, bitAnd(w.eff, d.scope_mask) AS eff,
         toUInt8(bitOr(d.scope_mask, w.eff) != w.eff) AS esc
  FROM walk AS w INNER JOIN delegation AS d ON d.parent_uid = w.event_uid
)
SELECT DISTINCT chain_uid FROM walk WHERE esc = 1""",
    "B_selfjoin": """
SELECT DISTINCT c.chain_uid FROM delegation AS c INNER JOIN delegation AS p ON c.parent_uid = p.event_uid
WHERE bitOr(c.scope_mask, p.scope_mask) != p.scope_mask""",
    "C_materialized": """
SELECT DISTINCT chain_uid FROM delegation
WHERE parent_eff_scope IS NOT NULL AND bitOr(scope_mask, parent_eff_scope) != parent_eff_scope""",
    "D_rootonly": """
SELECT DISTINCT chain_uid FROM delegation WHERE bitOr(scope_mask, root_scope) != root_scope""",
}
AGG = "SELECT count(*) AS n, sum(chain_uid) AS s FROM ({q}) AS t"
CH_SETTINGS = f" SETTINGS max_execution_time={TIMEOUT_S}, max_memory_usage={MEM_BYTES}"


class Duck:
    name = "duckdb"

    def __init__(self, path):
        self.con = duckdb.connect()
        self.con.execute(f"SET memory_limit='{MEM_BYTES // 1024**3}GB'")
        t = time.perf_counter_ns()
        self.con.execute(f"CREATE TABLE delegation AS SELECT * FROM read_parquet('{path}')")
        self.load_ns = time.perf_counter_ns() - t
        self.meta = {"version": duckdb.__version__,
                     "threads": self.con.execute("SELECT current_setting('threads')").fetchone()[0],
                     "table": "in-memory DuckDB table (default)"}

    def run(self, sql):
        timer = threading.Timer(TIMEOUT_S, self.con.interrupt)
        timer.start()
        try:
            return self.con.execute(sql).fetchall()
        finally:
            timer.cancel()


class CH_:
    name = "chdb"

    def __init__(self, path):
        self.s = chs.Session()
        t = time.perf_counter_ns()
        self.s.query(f"CREATE TABLE delegation ENGINE = Memory AS SELECT * FROM file('{path}', Parquet)")
        self.load_ns = time.perf_counter_ns() - t
        v = self.s.query("SELECT version(), getSetting('max_threads')", "TabSeparated").bytes().decode().split("\t")
        self.meta = {"version": f"chdb {chdb.__version__} / ClickHouse {v[0]}", "threads": v[1].strip(),
                     "table": "ENGINE = Memory (no ORDER BY / index)"}

    def run(self, sql):
        out = self.s.query(sql + CH_SETTINGS, "TabSeparated").bytes().decode()
        return [tuple(int(x) if x not in ("", "\\N") else None for x in ln.split("\t"))
                for ln in out.splitlines() if ln]


def main(path, truth_path, out_path):
    truth = json.load(open(truth_path))
    planted = {int(k): v["class"] for k, v in truth["planted"].items()}
    planted_reacq = {k for k, c in planted.items() if c == "reacquire"}
    engines = []
    meta = {"loadavg_start": os.getloadavg(), "cell": {k: truth[k] for k in ("n_rows", "depth", "chains")},
            "planted": len(planted), "planted_reacquire": len(planted_reacq)}
    for cls in (Duck, CH_):
        e = cls(path)
        engines.append(e)
        meta[e.name] = dict(e.meta, load_ms=e.load_ns / 1e6)
    sqls = {"duckdb": DUCK, "chdb": CH}
    res = {}
    # Warmup + correctness (untimed for the reported statistics; duration recorded).
    for arm in DUCK:
        for e in engines:
            key = f"{e.name}|{arm}"
            t = time.perf_counter_ns()
            try:
                rows = e.run(sqls[e.name][arm])
                ok = True
                err = None
            except Exception as ex:  # timeout, OOM, or SQL error -> DNF for this engine-arm in this cell
                rows, ok, err = [], False, repr(ex)[:400]
            dt = (time.perf_counter_ns() - t) / 1e6
            got = {r[0] for r in rows}
            r = {"warmup_ms": dt, "status": "OK" if ok else "DNF", "error": err}
            if ok:
                tp = len(got & planted.keys())
                r.update(flagged=len(got), true_pos=tp, false_pos=len(got - planted.keys()),
                         recall=tp / len(planted), missed_reacquire=len(planted_reacq - got),
                         exact_match=(got == set(planted)), checksum=[len(got), sum(got)])
            res[key] = r
    # Timed rounds, round-robin engine x arm.
    for rnd in range(ROUNDS):
        for arm in DUCK:
            for e in engines:
                key = f"{e.name}|{arm}"
                if res[key]["status"] != "OK":
                    continue
                if res[key]["warmup_ms"] > SLOW_WARMUP_MS and rnd >= 3:
                    continue
                q = AGG.format(q=sqls[e.name][arm])
                la = os.getloadavg()[0]
                t = time.perf_counter_ns()
                try:
                    out = e.run(q)
                except Exception as ex:
                    res[key]["status"] = "DNF"
                    res[key]["error"] = f"round {rnd}: " + repr(ex)[:400]
                    continue
                dt = (time.perf_counter_ns() - t) / 1e6
                n, s = int(out[0][0]), int(out[0][1] or 0)
                res[key].setdefault("trials_ms", []).append(dt)
                res[key].setdefault("loadavg_1m", []).append(la)
                if [n, s] != res[key]["checksum"]:
                    res[key]["checksum_mismatch"] = True
    meta["loadavg_end"] = os.getloadavg()
    with open(out_path, "w") as f:
        json.dump({"meta": meta, "results": res}, f, indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:4])
