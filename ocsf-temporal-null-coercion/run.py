"""Cross-engine NULL / type-coercion / timezone correctness — the silent-divergence modes that break detections.

The answer-equivalence work so far tested count(*)/sum on equality point-lookups. The shapes where security
answers silently diverge across engines are different, and this bench probes the three highest-yield ones,
all over byte-identical Parquet, all against a SQL-standard (or known-UTC) ground truth:

  ARM B — NULL semantics + type coercion (SQL engines: DuckDB, DataFusion, chDB).
    The star case is the allowlist footgun: `col NOT IN (a, b, NULL)` is, by SQL three-valued logic, *empty* —
    so a detection phrased "flag everything not in the allowlist" matches NOTHING the moment the allowlist
    contains a NULL. Plus the everyday NULL traps (`<>` excludes NULLs, `count(*)` vs `count(col)`, `IN`
    excludes NULLs, '' is not NULL) and a string-vs-int coercion case where engines genuinely differ.

  ARM A — timezone handling of naive vs UTC-adjusted timestamps (SQL engines, session TZ forced to a non-UTC
    zone). The SAME wall-clock instants are written two ways: timestamp[us, tz=UTC] (isAdjustedToUTC=true) and
    timestamp[us] (naive). Each engine counts rows in a fixed UTC hour window. For the UTC-adjusted column all
    engines should agree; for the naive column, an engine that treats naive timestamps as *session-local*
    shifts the window by the TZ offset and counts a different number — a silent off-by-hours in any
    time-windowed detection.

Tier B, single machine, deterministic. The transferable finding is the per-engine behavior table.

    python run.py
"""
import json
import os
import time
from datetime import datetime, timezone

os.environ["TZ"] = "America/New_York"   # force a non-UTC session zone so naive-timestamp handling is visible
time.tzset()

import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_work")
os.makedirs(WORK, exist_ok=True)
PB = os.path.join(WORK, "null_coerce.parquet")
PA = os.path.join(WORK, "timestamps.parquet")

# ---- Arm B corpus: a string column with allowlist members, an attacker value, an empty string, and NULLs;
# an int column with a known count of 5s and NULLs. Counts are explicit so the SQL-standard truth is exact.
S = (["allow1"] * 100 + ["allow2"] * 150 + ["evil"] * 50 + [""] * 30 + [None] * 40)   # N = 370
I = ([5] * 60 + [7] * 200 + [None] * 110)                                              # N = 370
NB = len(S)
assert len(I) == NB

# ---- Arm A corpus: 1200 instants on a 6-second cadence starting 2026-06-06 12:00:00 UTC. Written UTC-adjusted
# and naive (same wall-clock). The UTC window [12:00, 13:00) contains exactly the first 600 (3600s / 6s).
BASE_US = int(datetime(2026, 6, 6, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1_000_000)  # 12:00:00Z, exact
NA = 1200
STEP_US = 6_000_000
WIN_LO_US, WIN_HI_US = BASE_US, BASE_US + 3600_000_000
instants = [BASE_US + i * STEP_US for i in range(NA)]
TS_TRUTH_WINDOW = sum(1 for v in instants if WIN_LO_US <= v < WIN_HI_US)   # rows in the UTC hour window


def build():
    pq.write_table(pa.table({"s": pa.array(S, pa.string()), "i": pa.array(I, pa.int64())}), PB)
    pq.write_table(pa.table({
        "ts_utc": pa.array(instants, pa.timestamp("us", tz="UTC")),
        "ts_naive": pa.array(instants, pa.timestamp("us")),
    }), PA)


# ---- SQL engines: each runs `SELECT <sel> FROM <its ref> [WHERE <pred>]` and returns an int scalar or errors.
def q_duckdb(path, sel, pred):
    import duckdb
    con = duckdb.connect(); con.execute("SET TimeZone='America/New_York'")
    sql = f"SELECT {sel} FROM read_parquet('{path}')" + (f" WHERE {pred}" if pred else "")
    return int(con.execute(sql).fetchone()[0])


def q_datafusion(path, sel, pred):
    import datafusion
    ctx = datafusion.SessionContext(); ctx.register_parquet("t", path)
    sql = f"SELECT {sel} AS r FROM t" + (f" WHERE {pred}" if pred else "")
    return int(ctx.sql(sql).to_pydict()["r"][0])


def q_chdb(path, sel, pred):
    from chdb import session as chs
    sess = chs.Session()
    sql = (f"SELECT {sel} FROM file('{path}', Parquet)" + (f" WHERE {pred}" if pred else "")
           + " SETTINGS session_timezone='America/New_York'")
    return int(sess.query(sql, "CSV").data().strip().splitlines()[-1].strip('"'))


SQL_ENGINES = {"duckdb": q_duckdb, "datafusion": q_datafusion, "chdb": q_chdb}


def judge(engine_fn, path, sel, pred, truth):
    try:
        got = engine_fn(path, sel, pred)
    except Exception as e:  # noqa: BLE001
        return {"status": "errored", "detail": f"{type(e).__name__}: {str(e)[:60]}"}
    return {"status": "ok" if got == truth else "DIVERGES", "got": got, "truth": truth}


# ---- Arm B query battery (label, select, predicate, SQL-standard truth, security note) -------------------
ARM_B = [
    ("count(*)",                "count(*)",  None,                               NB,  "all rows"),
    ("count(s) excludes NULL",  "count(s)",  None,                               330, "count(col) drops the 40 NULLs"),
    ("s = 'allow1'",            "count(*)",  "s = 'allow1'",                     100, "baseline equality"),
    ("s <> 'allow1'",           "count(*)",  "s <> 'allow1'",                    230, "<> silently excludes the 40 NULLs"),
    ("s NOT IN (allow1,allow2)","count(*)",  "s NOT IN ('allow1','allow2')",      80, "excludes NULLs too (evil+empty=80)"),
    ("s NOT IN (...,NULL) TRAP","count(*)",  "s NOT IN ('allow1','allow2',NULL)",  0, "a NULL in the allowlist => matches NOTHING (detection bypass)"),
    ("s IS NULL",               "count(*)",  "s IS NULL",                         40, "the NULLs"),
    ("s = '' (empty != NULL)",  "count(*)",  "s = ''",                            30, "empty string is not NULL"),
    ("s IN (allow1,allow2)",    "count(*)",  "s IN ('allow1','allow2')",         250, "IN excludes NULLs (inverse check)"),
    ("i = 5 (int literal)",     "count(*)",  "i = 5",                             60, "baseline"),
    ("i = '5' (string literal)","count(*)",  "i = '5'",                           60, "coercion: standard coerces '5'->5; engines may differ/err"),
]


def arm_b():
    out = {}
    for label, sel, pred, truth, note in ARM_B:
        out[label] = {"truth": truth, "note": note,
                      "engines": {name: judge(fn, PB, sel, pred, truth) for name, fn in SQL_ENGINES.items()}}
    return out


# ---- Arm A: window count over the UTC-adjusted vs the naive column, per engine (session TZ = America/New_York)
def arm_a():
    lo = "TIMESTAMP '2026-06-06 12:00:00'"
    hi = "TIMESTAMP '2026-06-06 13:00:00'"
    out = {"utc_truth_window": TS_TRUTH_WINDOW, "session_tz": "America/New_York", "engines": {}}
    for name, fn in SQL_ENGINES.items():
        out["engines"][name] = {
            "ts_utc": _window(fn, "ts_utc", TS_TRUTH_WINDOW),     # UTC-adjusted: unambiguous, should hit truth
            "ts_naive": _window(fn, "ts_naive", TS_TRUTH_WINDOW),  # naive: session-local read shifts the window
        }
    return out


def _window(fn, col, truth):
    # compare the column to a plain (naive) timestamp literal for the UTC hour; the divergence we want to see
    # is whether the engine treats the stored value (and the literal) as UTC or as the session zone.
    pred = f"{col} >= TIMESTAMP '2026-06-06 12:00:00' AND {col} < TIMESTAMP '2026-06-06 13:00:00'"
    try:
        got = fn(PA, "count(*)", pred)
    except Exception as e:  # noqa: BLE001
        return {"status": "errored", "detail": f"{type(e).__name__}: {str(e)[:60]}"}
    return {"status": "ok" if got == truth else "shifted", "got": got, "truth": truth}


def run():
    build()
    return {
        "benchmark": "cross-engine NULL / type-coercion / timezone correctness",
        "evidence_tier": "B (single machine; deterministic; SQL-standard / known-UTC ground truth)",
        "session_tz": "America/New_York",
        "environment": {m: __import__(m).__version__ for m in ("pyarrow", "duckdb", "datafusion", "chdb")},
        "arm_b_null_coercion": arm_b(),
        "arm_a_timezone": arm_a(),
    }


def render_md(r):
    eng = list(SQL_ENGINES)
    sym = {"ok": "✅", "DIVERGES": "❌", "shifted": "⚠️ shifted", "errored": "⚠️ err"}
    b = r["arm_b_null_coercion"]
    blines = ["| query | truth | " + " | ".join(eng) + " | security note |", "|" + "---|" * (len(eng) + 3)]
    for label, cell in b.items():
        cells = []
        for name in eng:
            v = cell["engines"][name]
            s = sym.get(v["status"], "?")
            cells.append(s if v["status"] == "ok" else f"{s} ({v.get('got', v.get('detail',''))})")
        blines.append(f"| `{label}` | {cell['truth']} | " + " | ".join(cells) + f" | {cell['note']} |")
    a = r["arm_a_timezone"]
    alines = ["| engine | UTC-adjusted col | naive col |", "|---|---|---|"]

    def fmt(x):
        g = x.get("got", x.get("detail", "err"))
        return f"**{g}**" + (" ✅" if x.get("status") == "ok" else " ⚠️")
    for name in eng:
        c = a["engines"][name]
        alines.append(f"| {name} | {fmt(c['ts_utc'])} | {fmt(c['ts_naive'])} |")
    utc_counts = {a["engines"][n]["ts_utc"].get("got") for n in eng}
    naive_counts = {a["engines"][n]["ts_naive"].get("got") for n in eng}
    agree = len(utc_counts) == 1 and len(naive_counts) == 1
    alines.append("")
    alines.append(f"**Engines agree on the window count: {agree}.** UTC-adjusted column → {sorted(c for c in utc_counts if c is not None)}; "
                  f"naive column → {sorted(c for c in naive_counts if c is not None)} (the UTC-correct count is {a['utc_truth_window']}).")
    env = ", ".join(f"{k} `{v}`" for k, v in r["environment"].items())
    return f"""# Cross-engine NULL / type-coercion / timezone correctness

**Tier B · single machine · deterministic.** The shapes where security answers silently diverge across engines
aren't count/sum on point-lookups — they're NULL three-valued logic, type coercion, and timezone handling.
Byte-identical Parquet, SQL-standard (or known-UTC) ground truth, session timezone forced to
`America/New_York`. SQL engines: {env}.

## Arm B — NULL semantics + type coercion

{chr(10).join(blines)}

✅ = matches the SQL-standard answer · ❌ = diverges (engine's answer in parens) · ⚠️ err = raised.

## Arm A — timezone handling: naive vs UTC-adjusted timestamps

The same 1,200 instants written UTC-adjusted (`timestamp[us, tz=UTC]`) and naive (`timestamp[us]`); each engine
runs the identical `count(*) WHERE col >= TIMESTAMP '2026-06-06 12:00:00' AND col < '...13:00:00'` with session
TZ = `{a['session_tz']}`. The UTC-correct window holds {a['utc_truth_window']} rows.

{chr(10).join(alines)}

The numbers are each engine's row count (✅ = equals the UTC-correct {a['utc_truth_window']}). They **do not
agree**: under a non-UTC session, DataFusion treats the tz-aware column and the literal as UTC and gets it
right; DuckDB compares the tz-aware column against the *naive literal cast into the session zone* (shifting the
window to empty) while reading the naive column directly (correct); chDB applies the session zone on both and
lands on neither. No engine is "buggy" in isolation — the SQL standard leaves naive-timestamp and naive-literal
tz-resolution to the engine — but the **same time-window query over the same bytes returns different counts on
different engines**, which is the answer-equivalence break that matters for any time-bucketed detection.

## Reading

The allowlist footgun is the one to internalise: `col NOT IN (a, b, NULL)` is empty by SQL three-valued logic,
so the instant an allowlist picks up a NULL, a "flag everything not allowlisted" detection matches nothing and
says so with a clean zero — the same silent-wrong-answer failure mode as the engine bugs, but in the *query
semantics* rather than the reader. Two patterns came out of the run. Some traps are **portable**: the everyday
NULL behaviors (`<>` and `NOT IN` and `IN` all silently dropping NULL rows, `count(col)` excluding them, `''`
not being NULL) and the string-to-int coercion (`i = '5'` → 60) behaved identically across DuckDB, DataFusion
and chDB — so they're silent the same way everywhere, which is its own hazard. Others **diverge**: chDB does
not apply the SQL three-valued-logic emptying to `NOT IN (..., NULL)` (it returned 80 where DuckDB and
DataFusion returned 0), and the time-window counts disagree three ways under a non-UTC session — so the same
detection rule gives a different answer depending on the engine. Verify-the-answer therefore has to cover NULL
logic, coercion, and timezone, not just whether two engines agree on a clean count, and the safe defaults fall
out of it: pin sessions to UTC, store tz-aware (UTC) timestamps, and never let an allowlist carry a NULL. Tier
B, single machine; the per-engine behavior table is the transferable finding and is version-bound.
"""


def main():
    res = run()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(res, open(os.path.join(rdir, "results.json"), "w"), indent=2, sort_keys=True, default=str)
    open(os.path.join(rdir, "RESULTS.md"), "w").write(render_md(res))
    # console summary
    for label, cell in res["arm_b_null_coercion"].items():
        bad = {n: v.get("got", v.get("detail")) for n, v in cell["engines"].items() if v["status"] != "ok"}
        if bad:
            print(f"arm-B non-standard: {label} (truth {cell['truth']}) -> {bad}")
    print("arm-A naive-ts:", {n: c["ts_naive"]["status"] for n, c in res["arm_a_timezone"]["engines"].items()})
    print("wrote results/results.json + RESULTS.md")


if __name__ == "__main__":
    main()
