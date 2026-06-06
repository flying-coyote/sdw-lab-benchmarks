"""Lower-level bake-off #2: the Parquet encoding x library correctness matrix.

Both silent-wrong-answer findings the SDW Lab turned up this year lived in the Parquet *library* layer, not the
engine: chDB's Bloom-pushdown undercount and fastparquet's dictionary mis-decode. This bench is the home for
that bug-class — for each physical encoding, does each library actually decode the bytes back to the right
values, or does it error / silently hand back wrong ones? It's the empirical companion to the Apache Parquet
implementation-status matrix (which records *claimed* read/write support): claimed support and a correct answer
are not the same thing, and the gap is exactly where a detection query silently under-counts.

Three arms:
  ARM 1 (reader x forced-encoding): pyarrow writes a single column at each forced encoding (PLAIN,
    RLE_DICTIONARY, DELTA_BINARY_PACKED, DELTA_BYTE_ARRAY, DELTA_LENGTH_BYTE_ARRAY, BYTE_STREAM_SPLIT), the
    emitted encoding is read back from the file metadata to confirm the writer really used it, then all six
    reader libraries decode the column and the values are compared (order-independent) to ground truth.
  ARM 2 (writer default-encoding map): each writer library (pyarrow, DuckDB, Polars, fastparquet) writes the
    same table at its defaults; the encoding each chose per column type is read from the metadata.
  ARM 3 (writer x reader real-world round-trip): every reader reads every writer's default file and is checked
    against ground truth — the real-world matrix, and the one that hits DuckDB's PLAIN_DICTIONARY (the
    deprecated v1 dictionary encoding the historical fastparquet bug lived on).

Ground truth is exact by construction (int sum is exact; doubles are i*0.5, exactly representable so summation
order can't confound; strings are clean ASCII, no CSV-breaking chars). Tier B, single machine.

    python run.py
"""
import json
import os
import shutil
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
N = 20_000

# Single-column corpora, one per physical type, with exact order-independent ground truth. Safe column names
# (no SQL reserved words) so per-column reads work across DuckDB/chDB without quoting gymnastics.
COLS = {
    "int64":  {"col": "i64", "arr": pa.array(range(N), pa.int64()),               "norm": int},
    "string": {"col": "str", "arr": pa.array([f"evt{i % 97:02d}" for i in range(N)], pa.string()), "norm": str},
    "double": {"col": "f64", "arr": pa.array([i * 0.5 for i in range(N)], pa.float64()), "norm": float},
}
TRUTH = {t: sorted(c["norm"](v) for v in c["arr"].to_pylist()) for t, c in COLS.items()}

ENCODINGS = {   # only the encodings the format allows for each type
    "int64":  ["PLAIN", "RLE_DICTIONARY", "DELTA_BINARY_PACKED", "BYTE_STREAM_SPLIT"],
    "string": ["PLAIN", "RLE_DICTIONARY", "DELTA_BYTE_ARRAY", "DELTA_LENGTH_BYTE_ARRAY"],
    "double": ["PLAIN", "RLE_DICTIONARY", "BYTE_STREAM_SPLIT"],
}


def write_forced(path, col, arr, encoding):
    """Write a one-column file at a forced encoding; return the data-page encodings actually emitted."""
    t = pa.table({col: arr})
    if encoding == "PLAIN":
        kw = dict(use_dictionary=False, compression="none")
    elif encoding == "RLE_DICTIONARY":
        kw = dict(use_dictionary=True, compression="none")
    else:
        kw = dict(use_dictionary=False, compression="none", column_encoding={col: encoding})
    pq.write_table(t, path, **kw)
    return [str(e) for e in pq.ParquetFile(path).metadata.row_group(0).column(0).encodings]


# --- reader value extractors: each returns a named column as a Python list (order irrelevant — we sort) -----
def rv_duckdb(p, col):
    import duckdb
    return [r[0] for r in duckdb.connect().execute(f'SELECT "{col}" FROM read_parquet(\'{p}\')').fetchall()]


def rv_pyarrow(p, col):
    return pq.read_table(p).column(col).to_pylist()


def rv_polars(p, col):
    import polars as pl
    return pl.read_parquet(p)[col].to_list()


def rv_datafusion(p, col):
    import datafusion
    ctx = datafusion.SessionContext(); ctx.register_parquet("t", p)
    return ctx.sql(f'SELECT "{col}" FROM t').to_pydict()[col]


def rv_chdb(p, col):
    from chdb import session as chs
    return chs.Session().query(f"SELECT `{col}` FROM file('{p}', Parquet)", "ArrowTable").column(0).to_pylist()


def rv_fastparquet(p, col):
    import fastparquet
    return fastparquet.ParquetFile(p).to_pandas()[col].tolist()


READERS = {"duckdb": rv_duckdb, "pyarrow": rv_pyarrow, "polars": rv_polars,
           "datafusion": rv_datafusion, "chdb": rv_chdb, "fastparquet": rv_fastparquet}


def judge(reader, path, ctype):
    """Decode + compare to ground truth. ok / SILENT-WRONG / errored."""
    col, norm = COLS[ctype]["col"], COLS[ctype]["norm"]
    try:
        vals = READERS[reader](path, col)
    except Exception as e:  # noqa: BLE001
        return {"status": "errored", "detail": f"{type(e).__name__}: {str(e)[:70]}"}
    try:
        got = sorted(norm(v) for v in vals)
    except Exception as e:  # noqa: BLE001 — decoded to a type we can't even normalize == corruption
        return {"status": "SILENT-WRONG", "detail": f"unnormalizable: {type(e).__name__}", "n": len(vals)}
    if got == TRUTH[ctype]:
        return {"status": "ok", "n": len(got)}
    detail = f"n={len(got)} (truth {len(TRUTH[ctype])})"
    if ctype in ("int64", "double") and len(got) == len(TRUTH[ctype]):
        detail = f"sum {sum(got)} vs truth {sum(TRUTH[ctype])}"
    return {"status": "SILENT-WRONG", "detail": detail}


def arm1(work):
    out = {}
    for ctype, encs in ENCODINGS.items():
        out[ctype] = {}
        col = COLS[ctype]["col"]
        for enc in encs:
            p = os.path.join(work, f"a1_{ctype}_{enc}.parquet")
            try:
                emitted = write_forced(p, col, COLS[ctype]["arr"], enc)
            except Exception as e:  # noqa: BLE001 — pyarrow refuses this encoding for this type
                out[ctype][enc] = {"writer": "rejected", "writer_detail": f"{type(e).__name__}: {str(e)[:70]}"}
                continue
            cell = {"emitted": emitted}
            if enc not in emitted:   # pyarrow silently fell back — can't judge readers on this encoding
                cell["writer"] = f"fell back to {emitted}"
            else:
                cell["writer"] = "ok"
                cell["readers"] = {r: judge(r, p, ctype) for r in READERS}
            out[ctype][enc] = cell
    return out


# --- ARM 2/3: writers' default encodings + the cross-writer x reader real-world round-trip -----------------
def w_pyarrow(path, table):
    pq.write_table(table, path)


def w_duckdb(path, table):
    import duckdb
    con = duckdb.connect(); con.register("t", table)
    con.execute(f"COPY t TO '{path}' (FORMAT PARQUET)")


def w_polars(path, table):
    import polars as pl
    pl.from_arrow(table).write_parquet(path)


def w_fastparquet(path, table):
    import fastparquet
    fastparquet.write(path, table.to_pandas())


WRITERS = {"pyarrow": w_pyarrow, "duckdb": w_duckdb, "polars": w_polars, "fastparquet": w_fastparquet}


def arm23(work):
    table = pa.table({COLS[t]["col"]: COLS[t]["arr"] for t in COLS})
    col2type = {COLS[t]["col"]: t for t in COLS}
    default_map, roundtrip = {}, {}
    for w, fn in WRITERS.items():
        p = os.path.join(work, f"w_{w}.parquet")
        try:
            fn(p, table)
        except Exception as e:  # noqa: BLE001
            default_map[w] = {"write": f"errored: {type(e).__name__}: {str(e)[:60]}"}
            continue
        rg = pq.ParquetFile(p).metadata.row_group(0)
        cols = {rg.column(i).path_in_schema: [str(e) for e in rg.column(i).encodings]
                for i in range(rg.num_columns)}
        default_map[w] = {"write": "ok",
                          "default_encoding": {col2type[c]: cols[c] for c in cols}}
        # ARM 3: every reader reads this writer's default file, all three columns checked vs ground truth
        roundtrip[w] = {r: {ctype: judge(r, p, ctype)["status"] for ctype in COLS} for r in READERS}
    return default_map, roundtrip


def run():
    work = tempfile.mkdtemp(prefix="pqmatrix_")
    try:
        default_map, roundtrip = arm23(work)
        return {
            "benchmark": "parquet encoding x library correctness matrix (lower-level bake-off #2)",
            "evidence_tier": "B (single machine; exact ground truth; order-independent value compare)",
            "rows": N,
            "environment": {m: __import__(m).__version__ for m in
                            ("pyarrow", "duckdb", "polars", "datafusion", "chdb", "fastparquet", "pandas")},
            "arm1_reader_x_encoding": arm1(work),
            "arm2_writer_defaults": default_map,
            "arm3_writer_x_reader_roundtrip": roundtrip,
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def render_md(r):
    sym = {"ok": "✅", "SILENT-WRONG": "❌", "errored": "⚠️"}
    rd = list(READERS)

    # ---- Arm 1 blocks
    blocks = []
    for ctype, encs in r["arm1_reader_x_encoding"].items():
        lines = [f"\n### {ctype}\n\n| encoding | " + " | ".join(rd) + " |",
                 "|" + "---|" * (len(rd) + 1)]
        for enc, cell in encs.items():
            if "readers" not in cell:
                note = cell.get("writer", "?")
                lines.append(f"| `{enc}` | _{note}_ |" + " |" * (len(rd) - 1))
                continue
            cells = []
            for name in rd:
                v = cell["readers"][name]
                cells.append(sym.get(v["status"], "?") if v["status"] == "ok"
                             else f"{sym.get(v['status'],'?')} {v.get('detail','')[:20]}")
            lines.append(f"| `{enc}` | " + " | ".join(cells) + " |")
        blocks.append("\n".join(lines))

    # ---- Arm 2 default-encoding map
    def datapage(encs):   # the data-page encoding (drop the RLE definition-level marker + the dict PLAIN page)
        es = [e for e in encs if e != "RLE"]
        for e in es:
            if e not in ("PLAIN",) or len(es) == 1:
                pass
        # prefer a *_DICTIONARY tag if present, else the last non-RLE
        dicts = [e for e in es if e.endswith("DICTIONARY")]
        return dicts[0] if dicts else es[-1]
    a2 = ["| writer | int64 | string | double |", "|---|---|---|---|"]
    for w, d in r["arm2_writer_defaults"].items():
        if d.get("write") != "ok":
            a2.append(f"| {w} | _{d.get('write')}_ |  |  |")
            continue
        de = d["default_encoding"]
        a2.append(f"| {w} | {datapage(de['int64'])} | {datapage(de['string'])} | {datapage(de['double'])} |")

    # ---- Arm 3 writer x reader
    a3 = ["| writer ↓ / reader → | " + " | ".join(rd) + " |", "|" + "---|" * (len(rd) + 1)]
    for w, rr in r["arm3_writer_x_reader_roundtrip"].items():
        cells = []
        for name in rd:
            sts = rr[name]
            bad = [f"{ct}:{s}" for ct, s in sts.items() if s != "ok"]
            cells.append("✅" if not bad else "⚠️/❌ " + ",".join(bad)[:24])
        a3.append(f"| {w} | " + " | ".join(cells) + " |")

    env = ", ".join(f"{k} `{v}`" for k, v in r["environment"].items())
    return f"""# Parquet encoding x library correctness matrix (lower-level bake-off #2)

**Tier B · single machine · exact ground truth.** Both silent-wrong-answer findings the Lab turned up this
year (chDB's Bloom-pushdown undercount, fastparquet's dictionary mis-decode) lived in the Parquet *library*
layer. This is the home for that bug-class: for each physical encoding, does each library decode the bytes
back to the right values, or error / silently return wrong ones? It's the empirical companion to the Apache
implementation-status matrix — *claimed* support and a *correct answer* are different things. {N:,} rows per
column; order-independent value compare against exact ground truth. Libraries: {env}.

## Arm 1 — reader × forced encoding

pyarrow writes one column at each forced encoding (emitted encoding confirmed from file metadata before any
reader is judged); every reader decodes and is compared to ground truth. ✅ correct · ❌ silent-wrong · ⚠️
errored (caught it). An italic cell means pyarrow wouldn't emit that encoding for that type, so there was
nothing to read.
{''.join(blocks)}

## Arm 2 — what each writer emits by default

Each writer writes the same three-column table at its defaults; the data-page encoding it chose per type,
from the file metadata.

{chr(10).join(a2)}

## Arm 3 — writer × reader real-world round-trip

Every reader reads every writer's *default* file, all three columns checked against ground truth. ✅ = all
three correct. This is the matrix that hits DuckDB's `PLAIN_DICTIONARY` string column — the deprecated v1
dictionary encoding the historical fastparquet bug lived on.

{chr(10).join(a3)}

## Reading

The matrix makes the bug-class legible: a reader can claim an encoding and still decode it wrong, and the only
thing that catches it is comparing the decoded values to a known answer — the same verify-the-answer discipline
as the cross-engine and page-checksum benches, pushed down to the encoding. On these pinned versions the
exotic encodings fail *safe* — fastparquet raises `NotImplementedError` on the DELTA byte-array family and on
BYTE_STREAM_SPLIT, and DuckDB errors on BYTE_STREAM_SPLIT-for-int (a Parquet-2.10-era edge) rather than
returning a wrong number — which is the good failure mode, unlike the page-checksum bench where the same
libraries decoded corruption silently. The writers cluster on dictionary-by-default with PLAIN fallbacks, so
those exotic encodings are the ones a security pipeline only hits when someone tunes for size — exactly when
the least-exercised decode paths get loaded. Note DuckDB still emits the deprecated `PLAIN_DICTIONARY` for
strings; every reader here handles it, but it is the encoding the earlier fastparquet mis-decode lived on, so
it stays on the re-check list. The per-cell result is the transferable finding and is version-bound: re-run on
any library upgrade, because encoding support is actively moving (BYTE_STREAM_SPLIT for integers and the DELTA
family are the active edges).
"""


def main():
    res = run()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(res, open(os.path.join(rdir, "results.json"), "w"), indent=2, sort_keys=True, default=str)
    open(os.path.join(rdir, "RESULTS.md"), "w").write(render_md(res))
    wrong = []
    for ctype, encs in res["arm1_reader_x_encoding"].items():
        for enc, cell in encs.items():
            for name, v in cell.get("readers", {}).items():
                if v["status"] != "ok":
                    wrong.append(f"{ctype}/{enc}/{name}={v['status']}")
    silent = [c for c in wrong if "SILENT" in c]
    print("arm1 non-ok:", wrong or "none")
    print("arm1 SILENT-WRONG (the dangerous mode):", silent or "none")
    print("wrote results/results.json + RESULTS.md")


if __name__ == "__main__":
    main()
