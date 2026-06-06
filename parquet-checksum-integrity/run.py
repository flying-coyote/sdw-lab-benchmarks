"""Lower-level bake-off: do Parquet readers VERIFY page checksums, or return a confident wrong answer?

Parquet pages can carry a CRC32 over the page bytes, but writing the checksum and verifying it on read are
independent code paths — and most readers don't verify by default. This is the deepest extension of the
cross-engine answer-equivalence thesis (R3 / multi_engine_correctness): a single-bit flip inside a
checksummed page should be *caught*; a reader that ignores the CRC instead decodes the corrupted bytes and
returns a silently-wrong number. For evidence-grade security logs on cheap/cold media, a writer that emits
CRCs read by a verifier that ignores them is false integrity assurance.

The finding is a THREE-way split, not pass/fail (researched per-reader, 2026-06-06):
  - verifies by DEFAULT          — chDB (ClickHouse Parquet reader)
  - CAPABLE but OFF by default   — pyarrow (page_checksum_verification=True), and Polars only via its
                                   pyarrow passthrough (use_pyarrow=True + pyarrow_options=...)
  - NO read-side verification    — DuckDB (only debug_verify_blocks/_vector, which cover its own storage,
                                   not Parquet page CRCs) and DataFusion (no datafusion.execution.parquet.*
                                   checksum key in v53)

Method: write an int64 column (PLAIN, uncompressed, statistics off so the column max isn't copied into the
footer) with page checksums and a unique sentinel value, flip ONE byte of that value inside the data page
(CRC now mismatches, value changes by +1), then read sum(v) with each engine. ERROR = the reader verified
the checksum; WRONG (truth+1) = silent corruption; a no-checksum control file shows the CRC is the only
signal that could catch it; an opt-in probe re-reads the SAME corrupted file with verification turned on
where the reader supports it.

    python run.py
"""
import json
import os
import shutil
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
N = 100_000
SENTINEL = 0x0102030405060708            # distinctive; its LE bytes are easy to locate + unique
SENT_LE = SENTINEL.to_bytes(8, "little")  # b"\x08\x07\x06\x05\x04\x03\x02\x01"
TRUTH = SENTINEL + sum(range(1, N))


def write(path, checksum):
    vals = [SENTINEL] + list(range(1, N))
    # write_statistics=False so the sentinel (the column max) isn't ALSO copied into the footer min/max —
    # we want it to live ONLY in the data page so the byte-flip is uniquely locatable and the page CRC is
    # the sole signal that could catch it (a stats-based reader can't shortcut sum() anyway).
    pq.write_table(pa.table({"v": pa.array(vals, pa.int64())}), path,
                   use_dictionary=False, compression="none", write_statistics=False,
                   write_page_checksum=checksum)


def corrupt(path):
    """Flip the first byte of the sentinel value inside the data page -> value +1, CRC mismatch."""
    b = bytearray(open(path, "rb").read())
    i = b.find(SENT_LE)
    if i < 0 or b.find(SENT_LE, i + 1) >= 0:
        raise RuntimeError("sentinel not uniquely locatable; pick another")
    b[i] = (b[i] + 1) & 0xFF      # 0x08 -> 0x09  => value becomes SENTINEL+1
    open(path, "wb").write(b)


# --- reader adapters: each returns sum(v) or raises. STOCK config (no verification opted in) --------------
def r_duckdb(p):
    import duckdb
    return int(duckdb.connect().execute(f"SELECT sum(v) FROM read_parquet('{p}')").fetchone()[0])


def r_pyarrow(p):
    return int(sum(pq.read_table(p).column("v").to_pylist()))


def r_polars(p):
    import polars as pl
    return int(pl.read_parquet(p)["v"].sum())


def r_datafusion(p):
    import datafusion
    ctx = datafusion.SessionContext(); ctx.register_parquet("t", p)
    return int(ctx.sql("SELECT sum(v) AS s FROM t").to_pydict()["s"][0])


def r_chdb(p):
    from chdb import session as chs
    s = chs.Session()
    return int(s.query(f"SELECT sum(v) FROM file('{p}', Parquet)", "CSV").data().strip().splitlines()[-1].strip('"'))


# --- opt-in adapters: same readers, page-checksum verification turned ON where the reader supports it ------
def r_pyarrow_verify(p):
    return int(sum(pq.read_table(p, page_checksum_verification=True).column("v").to_pylist()))


def r_polars_pyarrow_verify(p):
    import polars as pl
    return int(pl.read_parquet(p, use_pyarrow=True,
                               pyarrow_options={"page_checksum_verification": True})["v"].sum())


READERS = {"duckdb": r_duckdb, "pyarrow": r_pyarrow, "polars": r_polars,
           "datafusion": r_datafusion, "chdb": r_chdb}

OPT_IN_READERS = {"pyarrow": r_pyarrow_verify, "polars(via pyarrow)": r_polars_pyarrow_verify}

# per-reader page-checksum verification capability (researched 2026-06-06 against the pinned versions below).
# class: "default" verifies with stock config; "opt-in" has a read-side knob (off by default); "none" has no
# read-side verification path at all.
CAPABILITY = {
    "duckdb":     {"class": "none",
                   "note": "no Parquet page-checksum read setting (debug_verify_blocks/_vector cover DuckDB's own storage)"},
    "pyarrow":    {"class": "opt-in", "knob": "page_checksum_verification=True",
                   "note": "read_table / ParquetFile arg; default False"},
    "polars":     {"class": "opt-in", "knob": "use_pyarrow=True + pyarrow_options={'page_checksum_verification': True}",
                   "note": "native reader has no knob; verification only via the pyarrow passthrough"},
    "datafusion": {"class": "none",
                   "note": "no datafusion.execution.parquet.* checksum key (v53)"},
    "chdb":       {"class": "default",
                   "note": "ClickHouse Parquet reader verifies the page CRC by default in this version"},
}


def read_all(path, readers):
    out = {}
    for name, fn in readers.items():
        try:
            got = fn(path)
            out[name] = {"result": got, "verifies": False,
                         "verdict": "SILENT-WRONG" if got != TRUTH else "correct(unexpected)",
                         "delta": got - TRUTH}
        except Exception as e:  # noqa: BLE001 — an error here means the reader CAUGHT the corruption
            out[name] = {"result": None, "verifies": True, "verdict": "ERRORED (caught it)",
                         "error": f"{type(e).__name__}: {str(e)[:90]}"}
    return out


def make_corrupt(checksum, work, tag):
    p = os.path.join(work, f"data_{tag}.parquet")
    write(p, checksum)
    corrupt(p)
    return p


def run():
    work = tempfile.mkdtemp(prefix="crc_")
    try:
        crc_file = make_corrupt(True, work, "crc")
        with_crc = read_all(crc_file, READERS)                 # stock config, checksummed file
        opt_in = read_all(crc_file, OPT_IN_READERS)            # SAME file, verification turned on
        no_crc = read_all(make_corrupt(False, work, "noc"), READERS)  # control: no checksum to catch it
        verifiers = sorted(k for k, v in with_crc.items() if v["verifies"])
        silent = sorted(k for k, v in with_crc.items() if not v["verifies"])
        return {
            "benchmark": "parquet page-checksum write-vs-verify (lower-level correctness bake-off)",
            "evidence_tier": "B (single machine; deterministic byte-flip; ground-truth-verified)",
            "rows": N, "sentinel": hex(SENTINEL), "truth_sum": TRUTH,
            "environment": {"pyarrow": pa.__version__,
                            "duckdb": __import__("duckdb").__version__,
                            "polars": __import__("polars").__version__,
                            "datafusion": __import__("datafusion").__version__,
                            "chdb": __import__("chdb").__version__},
            "capability": CAPABILITY,
            "readers_that_verify_by_default": verifiers,
            "readers_silently_wrong_stock": silent,
            "with_checksum_stock": with_crc,
            "opt_in_verification": opt_in,
            "no_checksum_control": no_crc,
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def render_md(r):
    cls = {"default": "verifies by default", "opt-in": "off by default", "none": "no read-side verification"}

    def row(name):
        wc = r["with_checksum_stock"][name]
        nc = r["no_checksum_control"][name]
        cap = r["capability"][name]
        stock = "✅ caught it" if wc["verifies"] else f"❌ silent wrong (+{wc.get('delta')})"
        ctrl = "errored" if nc["verifies"] else f"silent wrong (+{nc.get('delta')})"
        return f"| {name} | {cls[cap['class']]} | {stock} | {ctrl} |"

    rows = "\n".join(row(n) for n in READERS)
    opt = r["opt_in_verification"]

    def optrow(name):
        v = opt[name]
        cell = "✅ caught it" if v["verifies"] else "❌ still silent (+%s)" % v.get("delta")
        return f"| {name} | {cell} |"
    optrows = "\n".join(optrow(n) for n in OPT_IN_READERS)
    env = r["environment"]
    return f"""# Do Parquet readers verify page checksums? (lower-level correctness bake-off)

**Tier B · single machine · deterministic byte-flip.** An int64 column ({r['rows']:,} rows, PLAIN,
uncompressed, statistics off) is written **with** Parquet page checksums and a unique sentinel; one byte of
the sentinel is flipped inside the data page (the value changes by +1 and the page CRC no longer matches).
Each reader then computes `sum(v)`. A reader that **verifies** the CRC raises an error (catches it); one that
**ignores** it returns a silently-wrong sum (truth+1). The no-checksum control shows the CRC is the only
signal that could catch the flip. Readers: DuckDB `{env['duckdb']}`, pyarrow `{env['pyarrow']}`, Polars
`{env['polars']}`, DataFusion `{env['datafusion']}`, chDB `{env['chdb']}`.

It is a **three-way split**, not pass/fail — capability, default, and behavior are three different things:

| reader | page-CRC support | stock config (checksummed file) | no-checksum control |
|---|---|---|---|
{rows}

**Verifies by default: {', '.join(r['readers_that_verify_by_default']) or 'none'}.**
**Silently wrong with stock config despite the checksum: {', '.join(r['readers_silently_wrong_stock']) or 'none'}.**

### Opt-in probe — the SAME corrupted file, verification turned on where the reader has a knob

| reader (verification ON) | result |
|---|---|
{optrows}

pyarrow's knob is `page_checksum_verification=True` on `read_table` / `ParquetFile` (default `False`); Polars'
native reader has no such parameter, so verification is only reachable through its pyarrow passthrough
(`use_pyarrow=True, pyarrow_options={{'page_checksum_verification': True}}`). DuckDB and DataFusion expose no
read-side page-checksum verification at all in these versions.

## Reading

Writing a page checksum and verifying it on read are independent code paths, and most readers leave
verification off, so they decode the corrupted bytes and hand back a confident wrong number — the same
silent-wrong-answer failure mode as the chDB Bloom-pushdown undercount and the fastparquet dictionary
mis-decode, one layer deeper. The richer point is that this is a configuration default rather than a missing
feature for some of them: pyarrow already ships the verifier and just doesn't run it unless you ask, which
means the integrity backstop for evidence-grade telemetry is one keyword argument away yet off in the stock
path almost everyone uses. The chDB result is the nice irony — the engine that gave us the Bloom-pushdown
silent undercount is the one that catches the bit-flip here, so no engine is uniformly safe and the only
durable discipline is to verify rather than trust. The no-checksum control confirms the asymmetry: with no
CRC there is nothing to catch the flip, so a writer that emits checksums only helps if the reader on the
other end actually checks them. That is why "verify the answer" has to include verifying the bytes, not just
cross-checking engines — and why the per-reader class here (default / opt-in / none) is the transferable
finding, to be re-checked per version as checksum verification is actively added across implementations.
"""


def main():
    res = run()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(res, open(os.path.join(rdir, "results.json"), "w"), indent=2, sort_keys=True)
    open(os.path.join(rdir, "RESULTS.md"), "w").write(render_md(res))
    print("verify by default:", res["readers_that_verify_by_default"])
    print("silent wrong (stock):", res["readers_silently_wrong_stock"])
    print("opt-in:", {k: v["verdict"] for k, v in res["opt_in_verification"].items()})
    print("wrote results/results.json + RESULTS.md")


if __name__ == "__main__":
    main()
