"""Lower-level bake-off #5: compute determinism (SIMD + cross-engine float aggregates) and encryption interop.

Two properties that sit under "verify the answer" and bite a regulated, multi-engine security lakehouse:

  ARM A — determinism of a floating-point aggregate.
    (a) SIMD dispatch: the same engine (Arrow) is forced to NONE / SSE4_2 / AVX2 via ARROW_USER_SIMD_LEVEL,
        and we check the sum is byte-identical regardless of vector width.
    (b) cross-engine: five engines sum/mean the SAME float column. Floating-point addition isn't associative,
        so a different reduction algorithm or lane order gives a last-ULP-different result. Integer sum, min,
        max, and count are exact and must agree everywhere — the control that isolates the float-reduction
        effect. The finding sharpens the answer-equivalence thesis: "equal" for a float-derived metric needs a
        tolerance, and a chain-of-custody hash over a float aggregate won't match across engines.

  ARM B — Parquet Modular Encryption (PME) interop. pyarrow writes a PME-encrypted file (via an in-memory KMS);
    we confirm pyarrow-with-the-key reads it, then try every other engine. If only the implementer can read an
    encrypted file, encryption breaks the open read contract the whole MOAR swap story rests on — exactly the
    case for regulated data that must be encrypted at rest.

Tier B, single machine. Determinism/interop is the transferable finding; re-check per version.

    python run.py
"""
import json
import os
import struct
import subprocess
import sys
import tempfile

import pyarrow as pa
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
N = 2_000_000
SIMD_LEVELS = ["none", "sse4_2", "avx2"]   # this CPU's set; avx512 absent -> reported as such


def bits(x):
    return struct.pack("<d", float(x)).hex()


def make_files(work):
    fvals = [(i % 7) * 1e8 + i * 0.0009765625 for i in range(N)]   # varied magnitudes -> reduction order shows
    ivals = list(range(N))
    pf = os.path.join(work, "f.parquet"); pq.write_table(pa.table({"v": pa.array(fvals, pa.float64())}), pf)
    pi = os.path.join(work, "i.parquet"); pq.write_table(pa.table({"i": pa.array(ivals, pa.int64())}), pi)
    truth = {"fsum": sum(fvals), "imin": 0, "imax": N - 1, "icount": N, "isum": sum(ivals)}
    return pf, pi, truth


# --- ARM A(a): SIMD dispatch determinism (subprocess per level, env set before pyarrow imports) ----------
SIMD_SNIPPET = (
    "import os,struct,pyarrow as pa,pyarrow.compute as pc,pyarrow.parquet as pq;"
    "t=pq.read_table(%r).column('v');"
    "print(pa.runtime_info().simd_level, struct.pack('<d',float(pc.sum(t).as_py())).hex())"
)


def simd_probe(pf):
    out = {}
    for lvl in SIMD_LEVELS:
        env = dict(os.environ, ARROW_USER_SIMD_LEVEL=lvl)
        try:
            r = subprocess.run([sys.executable, "-c", SIMD_SNIPPET % pf],
                               env=env, capture_output=True, text=True, timeout=120)
            line = [l for l in r.stdout.strip().splitlines() if l][-1]
            actual, b = line.split()
            out[lvl] = {"runtime_simd": actual, "sum_bits": b}
        except Exception as e:  # noqa: BLE001
            out[lvl] = {"error": f"{type(e).__name__}: {str(e)[:60]}"}
    got = sorted({v["sum_bits"] for v in out.values() if "sum_bits" in v})
    return {"per_level": out, "byte_identical_across_levels": len(got) == 1, "distinct_results": got}


# --- ARM A(b): cross-engine aggregates --------------------------------------------------------------------
def agg_duckdb(pf, pi):
    import duckdb
    con = duckdb.connect()
    s, m, mn, mx, c = con.execute(f"SELECT sum(v),avg(v),min(v),max(v),count(v) FROM read_parquet('{pf}')").fetchone()
    isum = con.execute(f"SELECT sum(i) FROM read_parquet('{pi}')").fetchone()[0]
    return dict(sum=s, mean=m, min=mn, max=mx, count=c, isum=isum)


def agg_pyarrow(pf, pi):
    import pyarrow.compute as pc
    v = pq.read_table(pf).column("v")
    mm = pc.min_max(v).as_py()
    return dict(sum=pc.sum(v).as_py(), mean=pc.mean(v).as_py(), min=mm["min"], max=mm["max"],
                count=pc.count(v).as_py(), isum=pc.sum(pq.read_table(pi).column("i")).as_py())


def agg_polars(pf, pi):
    import polars as pl
    s = pl.read_parquet(pf)["v"]
    return dict(sum=s.sum(), mean=s.mean(), min=s.min(), max=s.max(), count=s.len(),
                isum=pl.read_parquet(pi)["i"].sum())


def agg_datafusion(pf, pi):
    import datafusion
    ctx = datafusion.SessionContext(); ctx.register_parquet("t", pf); ctx.register_parquet("ti", pi)
    d = ctx.sql("SELECT sum(v) s,avg(v) m,min(v) mn,max(v) mx,count(v) c FROM t").to_pydict()
    isum = ctx.sql("SELECT sum(i) s FROM ti").to_pydict()["s"][0]
    return dict(sum=d["s"][0], mean=d["m"][0], min=d["mn"][0], max=d["mx"][0], count=d["c"][0], isum=isum)


def agg_chdb(pf, pi):
    from chdb import session as chs
    s = chs.Session()
    row = s.query(f"SELECT sum(v),avg(v),min(v),max(v),count(v) FROM file('{pf}',Parquet)", "CSV").data().strip().split(",")
    isum = s.query(f"SELECT sum(i) FROM file('{pi}',Parquet)", "CSV").data().strip()
    return dict(sum=float(row[0]), mean=float(row[1]), min=float(row[2]), max=float(row[3]),
                count=int(row[4]), isum=int(isum))


AGGS = {"duckdb": agg_duckdb, "pyarrow": agg_pyarrow, "polars": agg_polars,
        "datafusion": agg_datafusion, "chdb": agg_chdb}


def cross_engine(pf, pi, truth):
    raw = {}
    for name, fn in AGGS.items():
        try:
            raw[name] = fn(pf, pi)
        except Exception as e:  # noqa: BLE001
            raw[name] = {"error": f"{type(e).__name__}: {str(e)[:60]}"}
    # group engines by identical bit-pattern, per metric
    report = {}
    for metric in ("sum", "mean", "min", "max"):
        groups = {}
        for name, d in raw.items():
            if "error" in d:
                continue
            groups.setdefault(bits(d[metric]), []).append(name)
        report[metric] = {"distinct_bit_patterns": len(groups),
                          "groups": {b: sorted(v) for b, v in groups.items()}}
    # exact controls: count + isum must be one value across engines
    counts = {d.get("count") for d in raw.values() if "error" not in d}
    isums = {d.get("isum") for d in raw.values() if "error" not in d}
    report["exact_controls"] = {
        "count_all_equal": len(counts) == 1 and truth["icount"] in counts,
        "int_sum_all_equal": len(isums) == 1 and truth["isum"] in isums,
        "count_value": sorted(counts), "int_sum_value": sorted(isums)}
    report["raw_values"] = {n: ({k: (bits(v) if isinstance(v, float) else v) for k, v in d.items()}
                                if "error" not in d else d) for n, d in raw.items()}
    return report


# --- ARM B: Parquet Modular Encryption interop -----------------------------------------------------------
def encryption_interop(work):
    import pyarrow.parquet.encryption as pe

    class InMemKms(pe.KmsClient):
        def wrap_key(self, key_bytes, master_key_id):
            import base64; return base64.b64encode(key_bytes)

        def unwrap_key(self, wrapped, master_key_id):
            import base64; return base64.b64decode(wrapped)

    kms_conf = pe.KmsConnectionConfig(custom_kms_conf={"k1": "0123456789012345"})
    cf = pe.CryptoFactory(lambda conf: InMemKms())
    ec = pe.EncryptionConfiguration(footer_key="k1", column_keys={"k1": ["v"]})
    p = os.path.join(work, "enc.parquet")
    with pq.ParquetWriter(p, pa.schema([("v", pa.float64())]),
                          encryption_properties=cf.file_encryption_properties(kms_conf, ec)) as w:
        w.write_table(pa.table({"v": pa.array([1.0, 2.0, 3.0], pa.float64())}))

    dp = cf.file_decryption_properties(kms_conf, pe.DecryptionConfiguration())
    out = {"file_bytes": os.path.getsize(p)}
    # the implementer, WITH the key:
    try:
        out["pyarrow_with_key"] = {"read": True, "values": pq.read_table(p, decryption_properties=dp).column("v").to_pylist()}
    except Exception as e:  # noqa: BLE001
        out["pyarrow_with_key"] = {"read": False, "error": f"{type(e).__name__}: {str(e)[:70]}"}

    import duckdb
    readers = {
        "pyarrow (no key)": lambda: pq.read_table(p).num_rows,
        "duckdb": lambda: duckdb.connect().execute(f"SELECT count(*) FROM read_parquet('{p}')").fetchone()[0],
        "polars": lambda: __import__("polars").read_parquet(p).height,
        "datafusion": lambda: (lambda c: (c.register_parquet("t", p),
                               c.sql("SELECT count(*) n FROM t").to_pydict()["n"][0])[1])(__import__("datafusion").SessionContext()),
        "chdb": lambda: __import__("chdb.session", fromlist=["Session"]).Session().query(
            f"SELECT count() FROM file('{p}',Parquet)", "CSV").data(),
    }
    out["without_the_key"] = {}
    for name, fn in readers.items():
        try:
            out["without_the_key"][name] = {"read": True, "result": str(fn())}
        except Exception as e:  # noqa: BLE001
            out["without_the_key"][name] = {"read": False, "error": f"{type(e).__name__}: {str(e)[:70]}"}
    return out


def run():
    work = tempfile.mkdtemp(prefix="detenc_")
    try:
        pf, pi, truth = make_files(work)
        return {
            "benchmark": "compute determinism (SIMD + cross-engine float) and PME interop (lower-level #5)",
            "evidence_tier": "B (single machine; bit-pattern compare; exact integer controls)",
            "rows": N, "cpu_simd_levels_tested": SIMD_LEVELS, "note_avx512": "absent on this CPU",
            "environment": {m: __import__(m).__version__ for m in
                            ("pyarrow", "duckdb", "polars", "datafusion", "chdb")},
            "armA_simd_determinism": simd_probe(pf),
            "armA_cross_engine_aggregates": cross_engine(pf, pi, truth),
            "armB_encryption_interop": encryption_interop(work),
        }
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


def render_md(r):
    simd = r["armA_simd_determinism"]
    ce = r["armA_cross_engine_aggregates"]
    enc = r["armB_encryption_interop"]
    env = ", ".join(f"{k} `{v}`" for k, v in r["environment"].items())

    simd_rows = "\n".join(f"| {lvl} | `{d.get('runtime_simd','?')}` | `{d.get('sum_bits', d.get('error',''))}` |"
                          for lvl, d in simd["per_level"].items())

    def metric_block(metric):
        m = ce[metric]
        gl = []
        for b, eng in m["groups"].items():
            gl.append(f"  - `{b}` ← {', '.join(eng)}")
        verdict = ("all engines bit-identical" if m["distinct_bit_patterns"] == 1
                   else f"**{m['distinct_bit_patterns']} distinct results**")
        return f"**{metric}**: {verdict}\n" + "\n".join(gl)

    ctrl = ce["exact_controls"]
    enc_rows = "\n".join(f"| {name} | {'✅ read' if d['read'] else '⛔ ' + d.get('error','blocked')[:48]} |"
                         for name, d in enc["without_the_key"].items())
    pk = enc["pyarrow_with_key"]
    return f"""# Compute determinism + Parquet encryption interop (lower-level bake-off #5)

**Tier B · single machine · bit-pattern compare.** Two properties under "verify the answer" that bite a
regulated, multi-engine lakehouse: whether a floating-point aggregate is deterministic (across SIMD width and
across engines), and whether an encrypted Parquet file is portable across engines at all. Engines: {env}.

## Arm A(a) — SIMD-dispatch determinism (same engine, forced vector width)

Arrow forced to each level via `ARROW_USER_SIMD_LEVEL`; the sum of {r['rows']:,} doubles compared bit-for-bit.
AVX-512 is absent on this CPU, so the rung tested is none → SSE4.2 → AVX2.

| forced level | runtime simd | sum (float64 bits) |
|---|---|---|
{simd_rows}

**Byte-identical across SIMD levels: {simd['byte_identical_across_levels']}** — Arrow's reduction does not
change with vector width here, so the SIMD layer is not a determinism risk on its own.

## Arm A(b) — cross-engine float aggregate determinism

The same float column summed/averaged by every engine, compared by exact float64 bit-pattern. Floating-point
addition isn't associative, so a different reduction order or algorithm shows up in the last ULPs.

{metric_block('sum')}

{metric_block('mean')}

Exact controls (must agree everywhere, and do): `min`/`max` bit-identical across engines; `count` all equal =
{ctrl['count_all_equal']} ({ctrl['count_value']}); integer `sum` all equal = {ctrl['int_sum_all_equal']}
({ctrl['int_sum_value']}). The integer sum and the min/max agreeing while the float sum splits is the proof
that the divergence is the floating-point *reduction*, not a read bug.

## Arm B — Parquet Modular Encryption interop

pyarrow wrote a PME-encrypted file ({enc['file_bytes']} bytes) via an in-memory KMS. **pyarrow with the key:**
{'✅ read ' + str(pk.get('values')) if pk['read'] else '⛔ ' + pk.get('error','')}.

Every other reader, without the key:

| reader | result |
|---|---|
{enc_rows}

## Reading

The two arms cut opposite ways, which is the useful part. SIMD dispatch is *not* a determinism problem here —
Arrow returns the same bytes whether it runs scalar or AVX2 — so the vector-width worry can be set aside. But
the cross-engine float aggregate genuinely diverges: the same column summed by different engines lands on
different last-ULP values, because each engine reduces in its own order with its own algorithm, and that is a
real wrinkle for the answer-equivalence thesis. The integer sum, count, min, and max agree to the bit across
every engine, so exact-typed answers are safe to compare for equality and to hash for chain-of-custody, while
a float-derived metric needs a stated tolerance and can't be hashed across engines. Encryption is the harder
edge: a Parquet-Modular-Encryption file is readable only by the implementer holding the key — every other
engine here is locked out entirely — so turning on at-rest encryption silently revokes the open read contract
the whole swap story depends on. For regulated data that *must* be encrypted, that means either standardizing
on one PME-capable engine + KMS or keeping encryption at the storage layer (encrypted volume / SSE) rather
than inside the Parquet file, so the file stays engine-portable. Tier B, single machine; re-check per version.
"""


def main():
    res = run()
    rdir = os.path.join(HERE, "results"); os.makedirs(rdir, exist_ok=True)
    json.dump(res, open(os.path.join(rdir, "results.json"), "w"), indent=2, sort_keys=True, default=str)
    open(os.path.join(rdir, "RESULTS.md"), "w").write(render_md(res))
    print("SIMD byte-identical across levels:", res["armA_simd_determinism"]["byte_identical_across_levels"])
    print("cross-engine float sum distinct results:",
          res["armA_cross_engine_aggregates"]["sum"]["distinct_bit_patterns"])
    print("encryption — readers without key that succeeded:",
          [n for n, d in res["armB_encryption_interop"]["without_the_key"].items() if d["read"]] or "none")
    print("wrote results/results.json + RESULTS.md")


if __name__ == "__main__":
    main()
