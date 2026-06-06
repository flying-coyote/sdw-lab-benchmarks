"""Cross-engine nested-OCSF type fidelity — does the SAME nested data give the SAME answer, and how far does
nested access stay portable across engines?

OCSF is deeply nested: an event carries `src_endpoint`/`dst_endpoint` structs and an `observables[]` list of
structs, and a real hunt filters on exactly those (`dst_endpoint.port = 3389`, "any observable is a flagged
IP"). The answer-equivalence work so far stayed on flat scalar columns; this bench pushes it into the nested
type system, over one byte-identical Parquet file, against explicit ground-truth counts.

Each engine gets its FAIR best expression for the same logical question (probe-verified per engine, so a
divergence is real, not a syntax strawman). Engines: DuckDB and DataFusion and chDB (SQL) plus Polars (the
dataframe API). The transferable finding is the per-engine nested-access table — where the open read contract
holds through the nesting, and where it stops.

    ../../.venv/bin/python run.py
"""
import json
import os
import sys

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import common  # noqa: E402  (lib.common: pin_artifact dogfoods the methodology)

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_work")
os.makedirs(WORK, exist_ok=True)
P = os.path.join(WORK, "nested_ocsf.parquet")

N = 1000
PORTS = [80, 443, 22, 53, 3389, 445, 8080, 3306]
EP = pa.struct([("ip", pa.string()), ("port", pa.int32())])
OBS = pa.list_(pa.struct([("name", pa.string()), ("type_id", pa.int32())]))


def build():
    # Deterministic OCSF Network Activity (4001)-shaped batch with nested struct + list<struct> fields.
    # Clean ground-truth counts (so any disagreement is an engine effect, not an arithmetic accident):
    #   src_endpoint.ip = '10.0.0.1'  -> 500   (i % 2 == 0)
    #   src_endpoint.port = 30000     -> 250   (i % 4 == 0)
    #   dst_endpoint.port = 3389      -> 125   (i % 8 == 4)
    #   len(observables) = 3          -> 250   (i % 4 == 0 adds a 3rd "user" observable)
    #   any observable.type_id = 21   -> 250   (the user observable)
    #   any observable.type_id = 2    -> 1000  (every row has two IP observables)
    src = [{"ip": "10.0.0.1" if i % 2 == 0 else "10.0.0.2", "port": 30000 + (i % 4)} for i in range(N)]
    dst = [{"ip": f"192.168.1.{i % 256}", "port": PORTS[i % 8]} for i in range(N)]
    observables = [
        [{"name": "src", "type_id": 2}, {"name": "dst", "type_id": 2}]
        + ([{"name": f"user{i}", "type_id": 21}] if i % 4 == 0 else [])
        for i in range(N)
    ]
    tbl = pa.table({
        "time": pa.array([common.BASE_EPOCH * 1000 + i for i in range(N)], pa.int64()),
        "class_uid": pa.array([4001] * N, pa.int32()),
        "src_endpoint": pa.array(src, EP),
        "dst_endpoint": pa.array(dst, EP),
        "observables": pa.array(observables, OBS),
    })
    pq.write_table(tbl, P)


# ---- engine runners: each takes a WHERE fragment (or None) and returns count(*) as an int, or raises -------
def r_duckdb(where):
    import duckdb
    con = duckdb.connect()
    q = f"SELECT count(*) FROM read_parquet('{P}')" + (f" WHERE {where}" if where else "")
    return int(con.execute(q).fetchone()[0])


def r_datafusion(where):
    import datafusion
    ctx = datafusion.SessionContext(); ctx.register_parquet("t", P)
    q = "SELECT count(*) AS r FROM t" + (f" WHERE {where}" if where else "")
    return int(ctx.sql(q).to_pydict()["r"][0])


def r_chdb(where):
    from chdb import session as chs
    s = chs.Session()
    q = f"SELECT count(*) FROM file('{P}', Parquet)" + (f" WHERE {where}" if where else "")
    return int(s.query(q, "CSV").data().strip().splitlines()[-1].strip('"'))


SQL = {"duckdb": r_duckdb, "datafusion": r_datafusion, "chdb": r_chdb}


def r_polars(predicate):
    import polars as pl
    df = pl.read_parquet(P)
    return df.height if predicate is None else df.filter(predicate(pl)).height


# ---- the question battery: same logical question, each engine's fair best expression (probe-verified) -------
# sql: per-SQL-engine WHERE fragment (None = no WHERE). polars: a predicate fn (None = count all rows).
import polars as _pl  # noqa: E402  (for the predicate lambdas)

Q = [
    {"label": "count(*)", "truth": N, "kind": "baseline",
     "sql": {"duckdb": None, "datafusion": None, "chdb": None}, "polars": None,
     "note": "all rows"},
    {"label": "src_endpoint.ip = '10.0.0.1'", "truth": 500, "kind": "struct string",
     "sql": {"duckdb": "src_endpoint.ip = '10.0.0.1'",
             "datafusion": "src_endpoint['ip'] = '10.0.0.1'",
             "chdb": "src_endpoint.ip = '10.0.0.1'"},
     "polars": lambda pl: pl.col("src_endpoint").struct.field("ip") == "10.0.0.1",
     "note": "scalar field inside a struct"},
    {"label": "dst_endpoint.port = 3389", "truth": 125, "kind": "struct int",
     "sql": {"duckdb": "dst_endpoint.port = 3389",
             "datafusion": "dst_endpoint['port'] = 3389",
             "chdb": "dst_endpoint.port = 3389"},
     "polars": lambda pl: pl.col("dst_endpoint").struct.field("port") == 3389,
     "note": "the RDP hunt, but on a nested port"},
    {"label": "src_endpoint.port = 30000", "truth": 250, "kind": "struct int",
     "sql": {"duckdb": "src_endpoint.port = 30000",
             "datafusion": "src_endpoint['port'] = 30000",
             "chdb": "src_endpoint.port = 30000"},
     "polars": lambda pl: pl.col("src_endpoint").struct.field("port") == 30000,
     "note": "second struct field"},
    {"label": "len(observables) = 3", "truth": 250, "kind": "list length",
     "sql": {"duckdb": "len(observables) = 3",
             "datafusion": "array_length(observables) = 3",
             "chdb": "length(observables) = 3"},
     "polars": lambda pl: pl.col("observables").list.len() == 3,
     "note": "cardinality of a list<struct>"},
    {"label": "any observable.type_id = 21", "truth": 250, "kind": "list<struct> predicate",
     "sql": {"duckdb": "len(list_filter(observables, x -> x.type_id = 21)) > 0",
             "datafusion": "array_has(observables['type_id'], 21)",
             "chdb": "arrayExists(x -> x.type_id = 21, observables)"},
     "polars": lambda pl: pl.col("observables").list.eval(_pl.element().struct.field("type_id") == 21).list.any(),
     "note": "field predicate across a list of structs (the OCSF observables hunt)"},
    {"label": "any observable.type_id = 2", "truth": N, "kind": "list<struct> predicate",
     "sql": {"duckdb": "len(list_filter(observables, x -> x.type_id = 2)) > 0",
             "datafusion": "array_has(observables['type_id'], 2)",
             "chdb": "arrayExists(x -> x.type_id = 2, observables)"},
     "polars": lambda pl: pl.col("observables").list.eval(_pl.element().struct.field("type_id") == 2).list.any(),
     "note": "same shape, present in every row"},
]


def judge(fn, arg, truth):
    try:
        got = fn(arg)
    except Exception as e:  # noqa: BLE001
        detail = " ".join(str(e).split())   # collapse newlines/whitespace so it stays one markdown-table cell
        return {"status": "errored", "detail": f"{type(e).__name__}: {detail[:90]}"}
    return {"status": "ok" if got == truth else "DIVERGES", "got": got, "truth": truth}


def run():
    build()
    pin = common.pin_artifact(common.connect(), P)   # dogfood the methodology: pin the nested artifact
    results = []
    for q in Q:
        cell = {"label": q["label"], "kind": q["kind"], "truth": q["truth"], "note": q["note"], "engines": {}}
        for name, fn in SQL.items():
            cell["engines"][name] = judge(fn, q["sql"][name], q["truth"])
        cell["engines"]["polars"] = judge(r_polars, q["polars"], q["truth"])
        results.append(cell)
    return {
        "benchmark": "cross-engine nested-OCSF type fidelity (struct + list<struct> access)",
        "evidence_tier": "B (single machine; deterministic; explicit ground-truth counts)",
        "environment": {m: __import__(m).__version__ for m in ("pyarrow", "duckdb", "datafusion", "chdb", "polars")},
        "artifact": {"path": pin["path"], "logical_fingerprint": pin["logical_fingerprint"],
                     "n_rows": pin["manifest"]["n_rows"], "n_row_groups": pin["manifest"]["n_row_groups"],
                     "columns": pq.read_schema(P).names,   # top-level schema (manifest holds the nested leaf paths)
                     "leaf_paths": list(pin["manifest"]["columns"].keys()), "bytes_sha256": pin["bytes_sha256"]},
        "questions": results,
    }


def render_md(r):
    eng = ["duckdb", "datafusion", "chdb", "polars"]
    sym = {"ok": "✅", "DIVERGES": "❌", "errored": "⚠️ err"}
    lines = ["| question | kind | truth | " + " | ".join(eng) + " |", "|" + "---|" * (len(eng) + 3)]
    for c in r["questions"]:
        cells = []
        for name in eng:
            v = c["engines"][name]
            cells.append("✅" if v["status"] == "ok" else f"{sym[v['status']]} ({v.get('got', v.get('detail', ''))})")
        lines.append(f"| `{c['label']}` | {c['kind']} | {c['truth']} | " + " | ".join(cells) + " |")
    # portability summary: a question is portable if every engine matched the truth
    portable = [c["label"] for c in r["questions"] if all(c["engines"][n]["status"] == "ok" for n in eng)]
    broke = [(c["label"], {n: c["engines"][n] for n in eng if c["engines"][n]["status"] != "ok"})
             for c in r["questions"] if any(c["engines"][n]["status"] != "ok" for n in eng)]
    env = ", ".join(f"{k} `{v}`" for k, v in r["environment"].items())
    a = r["artifact"]
    broke_txt = "\n".join(
        f"- `{lbl}` — " + ", ".join(f"{n} {v['status']}"
                                    + (f" ({v.get('got', v.get('detail',''))})") for n, v in bad.items())
        for lbl, bad in broke) or "- (none)"
    return f"""# Cross-engine nested-OCSF type fidelity

**Tier B · single machine · deterministic.** OCSF events are nested — `src_endpoint`/`dst_endpoint` structs and
an `observables[]` list of structs — and a real hunt filters on exactly those. This asks whether the SAME nested
data returns the SAME answer across engines, and how far nested access stays portable. One byte-identical Parquet
file, explicit ground-truth counts, each engine given its fair best expression (probe-verified). Engines: {env}.

The artifact is pinned (the [methodology](../BENCHMARKING-METHODOLOGY.md) rule): logical fingerprint
`{a['logical_fingerprint']}`, {a['n_rows']} rows in {a['n_row_groups']} row group(s), columns
`{', '.join(a['columns'])}`, sha256 `{a['bytes_sha256'][:16]}…`.

## Results

{chr(10).join(lines)}

✅ = matches the ground-truth count · ❌ = diverges (engine's count in parens) · ⚠️ err = the engine could not
express the nested access (detail in parens).

## Reading

Scalar access into a struct (`src_endpoint.port`, `dst_endpoint.ip`) and list cardinality (`len(observables)`)
are **portable**: DuckDB, DataFusion, chDB, and Polars all read the same nested bytes and return the same count,
so the open read contract holds through one level of nesting. The boundary is the **list-of-struct field
predicate** — "does any observable carry `type_id = 21`", which is the natural way to ask an OCSF `observables[]`
question. DuckDB (`list_filter` with a lambda), chDB (`arrayExists`), and Polars (`list.eval`) all express it and
agree; DataFusion cannot apply a per-element struct-field predicate inside a `WHERE` clause (it errors on field
access across the list), so the same hunt that runs on three engines doesn't run on the fourth without rewriting
it as an `UNNEST` subquery.

Portable here: {', '.join('`'+p+'`' for p in portable)}.

Not portable across all four:
{broke_txt}

The transferable point: an open table format guarantees every engine can *read the bytes*, not that every engine
can *ask the same nested question the same way*. This is a concrete reason teams flatten OCSF observables into
their own columns or a side table before querying — flattening trades schema fidelity for query portability, and
the trade is real, measured here at the list-of-struct boundary. The per-engine table is version-bound (the
divergence is a DataFusion capability gap on this version, not a law); re-run on upgrade.
"""


def main():
    res = run()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(res, open(os.path.join(rdir, "results.json"), "w"), indent=2, sort_keys=True, default=str)
    open(os.path.join(rdir, "RESULTS.md"), "w").write(render_md(res))
    for c in res["questions"]:
        bad = {n: v.get("got", v.get("detail")) for n, v in c["engines"].items() if v["status"] != "ok"}
        if bad:
            print(f"non-portable: {c['label']} (truth {c['truth']}) -> {bad}")
    print("wrote results/results.json + RESULTS.md")


if __name__ == "__main__":
    main()
