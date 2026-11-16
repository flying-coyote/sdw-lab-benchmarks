"""Arm B extension, post-hoc (run 2026-11-16): can the other engines read a PME file when they ARE given the key?

The 2026-06-06 Arm B (run.py, unmodified) only showed that readers WITHOUT the key fail, which is what encryption
is supposed to do. The open question the essay needs is whether in-file Parquet Modular Encryption keeps the
multi-engine read contract when each engine gets the key through its own mechanism. This script asks that, in
both directions, and writes only to dated new files (run.py's tracked results/ are untouched).

Harness note (the trap the June arm could not hit but this one could): pyarrow's KMS path generates a random data
key (DEK) and stores it wrapped. Handing another engine the KMS *master* key would fail for a harness reason, not an
interop reason. So the pyarrow file is written with uniform encryption and double_wrapping=False, and the in-memory
KMS records the DEK it is asked to wrap; that DEK is the actual AES key on the footer and every column, and it is what
each other engine is given.

Direction 1: pyarrow writes (uniform PME, AES_GCM_V1 default), readers given the DEK.
Direction 3: pyarrow writes through its explicit-key API with the same known key (only builds that ship it).
Direction 2: DuckDB writes with a known 16-byte footer key (if the build supports it), readers given that key
             (pyarrow through a KMS whose unwrap returns the known key whatever the key metadata says).

    <venv>/bin/python -I rerun_pme_with_keys_2026_11_16.py <label>
"""
import base64
import importlib.metadata as md
import json
import os
import shutil
import sys
import tempfile
import time

import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.parquet.encryption as pe

HERE = os.path.dirname(os.path.abspath(__file__))
VALUES = [1.0, 2.0, 3.0]
KNOWN_KEY = b"0123456789012345"  # 128-bit, used only for direction 2
CAPTURED = []


def _try(fn):
    try:
        v = fn()
        return {"read": True, "values": v, "correct": v == VALUES}
    except Exception as e:  # noqa: BLE001
        return {"read": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}


class CapturingKms(pe.KmsClient):
    def wrap_key(self, key_bytes, master_key_id):
        CAPTURED.append(bytes(key_bytes))
        return base64.b64encode(key_bytes)

    def unwrap_key(self, wrapped, master_key_id):
        return base64.b64decode(wrapped)


class FixedKeyKms(pe.KmsClient):
    """For a file pyarrow did not write: ignore the wrapped material and return the known key."""
    def wrap_key(self, key_bytes, master_key_id):
        return base64.b64encode(key_bytes)

    def unwrap_key(self, wrapped, master_key_id):
        return KNOWN_KEY


def pyarrow_write(p):
    kms_conf = pe.KmsConnectionConfig(custom_kms_conf={"k1": "0123456789012345"})
    cf = pe.CryptoFactory(lambda conf: CapturingKms())
    ec = pe.EncryptionConfiguration(footer_key="k1", uniform_encryption=True, double_wrapping=False,
                                  data_key_length_bits=256)
    with pq.ParquetWriter(p, pa.schema([("v", pa.float64())]),
                          encryption_properties=cf.file_encryption_properties(kms_conf, ec)) as w:
        w.write_table(pa.table({"v": pa.array(VALUES, pa.float64())}))
    assert len(CAPTURED) == 1, f"expected exactly one DEK wrap, got {len(CAPTURED)}"
    return CAPTURED[0], (cf, kms_conf)


def r_pyarrow_kms(p, cf, kms_conf):
    dp = cf.file_decryption_properties(kms_conf, pe.DecryptionConfiguration())
    return pq.read_table(p, decryption_properties=dp).column("v").to_pylist()


def r_duckdb(p, key):
    import duckdb
    # add_parquet_key takes a VARCHAR. Per the DuckDB 2.0 docs (read 2026-11-16) it accepts a raw 16/24/32-char key
    # or base64. Probe 2026-11-16: base64 of a 16-byte key is 24 chars, which DuckDB takes as a literal AES-192 key
    # (a file written under base64('0123456789012345') does not open with the raw string). So printable keys go in
    # raw, and binary keys go in as base64 only when the base64 length (44 for 256-bit) is not itself a key length.
    try:
        ks = key.decode("ascii")
        assert ks.isprintable() and "'" not in ks and len(ks) in (16, 24, 32)
    except Exception:  # noqa: BLE001
        ks = base64.b64encode(key).decode()
        if len(ks) in (16, 24, 32):
            raise RuntimeError("UNTESTABLE: binary key whose base64 length is itself a valid key length")
    c = duckdb.connect()
    c.execute(f"PRAGMA add_parquet_key('k', '{ks}')")
    return [r[0] for r in c.execute(
        f"SELECT v FROM read_parquet('{p}', encryption_config={{footer_key: 'k'}})").fetchall()]


def r_polars(p, key):
    import polars as pl
    if not hasattr(pl, "ParquetDecryptionProperties"):
        raise RuntimeError("no Parquet decryption API in this Polars build (no pl.ParquetDecryptionProperties)")
    dp = pl.ParquetDecryptionProperties(footer_key=key)
    return pl.read_parquet(p, decryption=dp)["v"].to_list()


def r_datafusion(p, key):
    import datafusion
    ctx = datafusion.SessionContext()
    keys = ctx.sql("SHOW ALL").to_pydict()["name"]
    crypto = [k for k in keys if "crypt" in k]
    if not crypto:
        raise RuntimeError("no parquet crypto/decryption config key in this Python build (SHOW ALL lists none)")
    cfg = datafusion.SessionConfig().set("datafusion.execution.parquet.crypto.file_decryption.footer_key_as_hex",
                                         key.hex())
    ctx = datafusion.SessionContext(cfg); ctx.register_parquet("t", p)
    return ctx.sql("SELECT v FROM t").to_pydict()["v"]


def r_chdb(p, key):
    import chdb
    rows = chdb.query("SELECT name FROM system.settings WHERE name ILIKE '%parquet%' AND "
                      "(name ILIKE '%encrypt%' OR name ILIKE '%decrypt%')", "CSV").data().strip()
    if not rows:
        raise RuntimeError("no Parquet decryption setting in this chDB build (system.settings lists none)")
    raise RuntimeError(f"settings exist but harness has no adapter: {rows}")


def duckdb_write(p):
    import duckdb
    c = duckdb.connect()
    c.execute(f"PRAGMA add_parquet_key('k', '{KNOWN_KEY.decode()}')")
    c.execute(f"COPY (SELECT unnest([1.0, 2.0, 3.0]::DOUBLE[]) AS v) TO '{p}' "
              f"(FORMAT parquet, ENCRYPTION_CONFIG {{footer_key: 'k'}})")


def r_pyarrow_fixed(p):
    kms_conf = pe.KmsConnectionConfig()
    cf = pe.CryptoFactory(lambda conf: FixedKeyKms())
    dp = cf.file_decryption_properties(kms_conf, pe.DecryptionConfiguration())
    return pq.read_table(p, decryption_properties=dp).column("v").to_pylist()


def pyarrow_write_explicit(p):
    if not hasattr(pe, "create_encryption_properties"):
        raise RuntimeError("no explicit-key encryption API in this pyarrow build")
    props = pe.create_encryption_properties(footer_key=KNOWN_KEY)
    pq.write_table(pa.table({"v": pa.array(VALUES, pa.float64())}), p, encryption_properties=props)


def r_pyarrow_explicit(p):
    if not hasattr(pe, "create_decryption_properties"):
        raise RuntimeError("no explicit-key decryption API in this pyarrow build")
    return pq.read_table(p, decryption_properties=pe.create_decryption_properties(footer_key=KNOWN_KEY)).column("v").to_pylist()


def r_duckdb_plain(p):
    import duckdb
    return [r[0] for r in duckdb.connect().execute(f"SELECT v FROM read_parquet('{p}')").fetchall()]


def run(label):
    work = tempfile.mkdtemp(prefix="pme_keys_")
    try:
        p1 = os.path.join(work, "pyarrow_pme.parquet")
        dek, (cf, kms_conf) = pyarrow_write(p1)
        d1 = {
            "writer": "pyarrow KMS path (uniform PME, double_wrapping=False, 256-bit DEK, default algorithm)",
            "dek_bits": len(dek) * 8,
            "readers_given_the_dek": {
                "pyarrow (KMS control)": _try(lambda: r_pyarrow_kms(p1, cf, kms_conf)),
                "duckdb": _try(lambda: r_duckdb(p1, dek)),
                "polars": _try(lambda: r_polars(p1, dek)),
                "datafusion": _try(lambda: r_datafusion(p1, dek)),
                "chdb": _try(lambda: r_chdb(p1, dek)),
            },
            "duckdb_without_key": _try(lambda: r_duckdb_plain(p1)),
        }
        p2 = os.path.join(work, "duckdb_pme.parquet")
        w2 = _try(lambda: (duckdb_write(p2), VALUES)[1])
        d2 = {"writer": "duckdb (ENCRYPTION_CONFIG footer_key, 128-bit)", "write": w2}
        if w2["read"]:
            d2["readers_given_the_key"] = {
                "duckdb (control)": _try(lambda: r_duckdb(p2, KNOWN_KEY)),
                "pyarrow (KMS returning the known key)": _try(lambda: r_pyarrow_fixed(p2)),
                "pyarrow (explicit-key API)": _try(lambda: r_pyarrow_explicit(p2)),
                "polars": _try(lambda: r_polars(p2, KNOWN_KEY)),
                "datafusion": _try(lambda: r_datafusion(p2, KNOWN_KEY)),
                "chdb": _try(lambda: r_chdb(p2, KNOWN_KEY)),
            }
            d2["pyarrow_without_key"] = _try(lambda: pq.read_table(p2).column("v").to_pylist())
        p3 = os.path.join(work, "pyarrow_explicit_pme.parquet")
        w3 = _try(lambda: (pyarrow_write_explicit(p3), VALUES)[1])
        d3 = {"writer": "pyarrow explicit-key API (uniform, 128-bit known key, AES_GCM_V1)", "write": w3}
        if w3["read"]:
            d3["readers_given_the_key"] = {
                "pyarrow (explicit-key control)": _try(lambda: r_pyarrow_explicit(p3)),
                "duckdb": _try(lambda: r_duckdb(p3, KNOWN_KEY)),
                "polars": _try(lambda: r_polars(p3, KNOWN_KEY)),
                "datafusion": _try(lambda: r_datafusion(p3, KNOWN_KEY)),
                "chdb": _try(lambda: r_chdb(p3, KNOWN_KEY)),
            }
        env = {m: md.version(m) for m in ("pyarrow", "duckdb", "polars", "datafusion", "chdb")}
        return {"label": label, "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "python": sys.version.split()[0], "environment": env,
                "direction1_pyarrow_writes": d1, "direction2_duckdb_writes": d2,
                "direction3_pyarrow_explicit_key_writes": d3}
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    label = sys.argv[1]
    res = run(label)
    out = os.path.join(HERE, "results", f"rerun-pme-with-keys-2026-11-16-{label}.json")
    json.dump(res, open(out, "w"), indent=2, sort_keys=True, default=str)
    print(json.dumps(res, indent=1, default=str))
    print("wrote", out)
