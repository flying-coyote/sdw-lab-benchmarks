"""Why a DuckDB-written PME file fails in pyarrow and Polars with the correct key (post-hoc check, 2026-11-16).

Follow-up to RESULTS-PME-WITH-KEYS-2026-11-16.md direction 2, prompted by an adversarial review that found the
cause. This script reproduces it independently: it writes uniform-PME files with the same 16-byte key from DuckDB
and from pyarrow's explicit-key API, reads each with every reader that has a key path, then parses the file tail
(`... [FileCryptoMetaData][len4][nonce12][ciphertext+tag16] [footer_len4] PARE`) and decrypts the footer by hand
with AES-GCM under three AAD candidates: empty, and `aad_file_unique || 0x00` (the footer module AAD the Parquet
encryption spec describes for module type Footer = 0, no AAD prefix) where an identifier is present.

Two stages, because the engines live in the venv and `cryptography` in the system Python:
    <venv>/bin/python -I footer_aad_check_2026_11_16.py write <label>     # writes, reads, then calls stage 2
    /usr/bin/python3 -I footer_aad_check_2026_11_16.py check <dir>         # footer decrypts (called automatically)
"""
import json
import os
import struct
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KEY = b"0123456789012345"
WRONG = b"5432109876543210"


def _try(fn):
    try:
        return {"read": True, "values": fn()}
    except Exception as e:  # noqa: BLE001
        return {"read": False, "error": f"{type(e).__name__}: {str(e)[:150]}"}


def stage_write(label):
    import importlib.metadata as md
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    import pyarrow.parquet.encryption as pe
    work = tempfile.mkdtemp(prefix="aad_")
    d = os.path.join(work, "duckdb.parquet")
    c = duckdb.connect(); c.execute(f"PRAGMA add_parquet_key('k', '{KEY.decode()}')")
    c.execute(f"COPY (SELECT unnest([1.0,2.0,3.0]::DOUBLE[]) AS v) TO '{d}' (FORMAT parquet, ENCRYPTION_CONFIG {{footer_key: 'k'}})")
    files = {"duckdb": d}
    if hasattr(pe, "create_encryption_properties"):
        p = os.path.join(work, "pyarrow.parquet")
        pq.write_table(pa.table({"v": pa.array([1.0, 2.0, 3.0], pa.float64())}), p,
                       encryption_properties=pe.create_encryption_properties(footer_key=KEY))
        files["pyarrow_explicit_key"] = p
    reads = {}
    for name, f in files.items():
        r = {}
        def ddb(k):
            c2 = duckdb.connect(); c2.execute(f"PRAGMA add_parquet_key('k', '{k.decode()}')")
            return [x[0] for x in c2.execute(f"SELECT v FROM read_parquet('{f}', encryption_config={{footer_key: 'k'}})").fetchall()]
        r["duckdb (key)"] = _try(lambda: ddb(KEY))
        r["duckdb (wrong key, control)"] = _try(lambda: ddb(WRONG))
        if hasattr(pe, "create_decryption_properties"):
            r["pyarrow (key)"] = _try(lambda: pq.read_table(f, decryption_properties=pe.create_decryption_properties(footer_key=KEY)).column("v").to_pylist())
        try:
            import polars as pl
            if hasattr(pl, "ParquetDecryptionProperties"):
                r["polars (key)"] = _try(lambda: pl.read_parquet(f, decryption=pl.ParquetDecryptionProperties(footer_key=KEY))["v"].to_list())
        except ImportError:
            pass
        reads[name] = r
    chk = subprocess.run(["/usr/bin/python3", "-I", os.path.abspath(__file__), "check", work],
                         capture_output=True, text=True)
    footer = json.loads(chk.stdout) if chk.returncode == 0 else {"error": chk.stderr[-400:]}
    env = {m: md.version(m) for m in ("duckdb", "pyarrow", "polars")}
    res = {"label": label, "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "environment": env,
           "reads": reads, "footer_check": footer}
    out = os.path.join(HERE, "results", f"footer-aad-check-2026-11-16-{label}.json")
    json.dump(res, open(out, "w"), indent=2)
    print(json.dumps(res, indent=1))


def footer_parts(path):
    b = open(path, "rb").read()
    assert b[-4:] == b"PARE", "not an encrypted-footer file"
    n = struct.unpack("<I", b[-8:-4])[0]
    tail = b[-8 - n:-8]
    for off in range(0, min(len(tail) - 32, 200)):
        if off + 4 + struct.unpack("<I", tail[off:off + 4])[0] == len(tail):
            return tail[:off], tail[off + 4:off + 16], tail[off + 16:]
    raise RuntimeError("footer layout not found")


def stage_check(work):
    from cryptography import __version__ as cv
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    out = {"cryptography": cv}
    for fn in sorted(os.listdir(work)):
        crypto, nonce, ct = footer_parts(os.path.join(work, fn))
        r = {"FileCryptoMetaData_hex": crypto.hex()}
        # aad_file_unique: thrift binary field inside AesGcmV1; pyarrow writes 8 bytes after a 0x28 0x08 header
        i = crypto.find(b"\x28\x08")
        uniq = crypto[i + 2:i + 10] if i >= 0 else b""
        r["aad_file_unique_hex"] = uniq.hex() or None
        cands = {"empty AAD": b""}
        if uniq:
            cands["aad_file_unique||0x00"] = uniq + b"\x00"
        for name, aad in cands.items():
            for kn, k in (("key", KEY), ("wrong key", WRONG)):
                try:
                    r[f"{name}, {kn}"] = f"decrypts ({len(AESGCM(k).decrypt(nonce, ct, aad))} bytes)"
                except Exception as e:  # noqa: BLE001
                    r[f"{name}, {kn}"] = f"fails ({type(e).__name__})"
        out[fn] = r
    print(json.dumps(out))


if __name__ == "__main__":
    {"write": stage_write, "check": stage_check}[sys.argv[1]](sys.argv[2])
