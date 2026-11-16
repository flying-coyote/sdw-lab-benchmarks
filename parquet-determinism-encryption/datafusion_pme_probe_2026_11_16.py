"""Follow-up probe (2026-11-16) to rerun_pme_with_keys_2026_11_16.py: that script only searched DataFusion's session
config (SHOW ALL) for a decryption key. DataFusion takes Parquet decryption keys as per-table format options, so this
probe hands the key through CREATE EXTERNAL TABLE ... OPTIONS ('format.crypto.file_decryption.footer_key_as_hex' ...)
on a pyarrow-written (explicit-key API, or KMS path on builds without it) and a DuckDB-written uniform PME file.

    <venv>/bin/python -I datafusion_pme_probe_2026_11_16.py <label>
"""
import base64, importlib.metadata as md, json, os, shutil, sys, tempfile, time
import duckdb, datafusion, pyarrow as pa, pyarrow.parquet as pq, pyarrow.parquet.encryption as pe

HERE = os.path.dirname(os.path.abspath(__file__))
K = b"0123456789012345"


class FixedKms(pe.KmsClient):
    def wrap_key(self, key_bytes, master_key_id):
        return base64.b64encode(key_bytes)

    def unwrap_key(self, wrapped, master_key_id):
        return base64.b64decode(wrapped)


def write_files(work):
    files = {}
    p = os.path.join(work, "pyarrow.parquet")
    t = pa.table({"v": pa.array([1.0, 2.0, 3.0], pa.float64())})
    if hasattr(pe, "create_encryption_properties"):
        pq.write_table(t, p, encryption_properties=pe.create_encryption_properties(footer_key=K))
        files["pyarrow (explicit key)"] = (p, K)
    else:  # KMS path; the key handed to DataFusion is then the wrong key, but the error class is what matters
        cf = pe.CryptoFactory(lambda c: FixedKms())
        ec = pe.EncryptionConfiguration(footer_key="k1", uniform_encryption=True, double_wrapping=False)
        pq.write_table(t, p, encryption_properties=cf.file_encryption_properties(
            pe.KmsConnectionConfig(custom_kms_conf={"k1": "x"}), ec))
        files["pyarrow (KMS path; key not handed over)"] = (p, K)
    d = os.path.join(work, "duckdb.parquet")
    c = duckdb.connect(); c.execute(f"PRAGMA add_parquet_key('k', '{K.decode()}')")
    c.execute(f"COPY (SELECT unnest([1.0,2.0,3.0]::DOUBLE[]) AS v) TO '{d}' (FORMAT parquet, ENCRYPTION_CONFIG {{footer_key: 'k'}})")
    files["duckdb"] = (d, K)
    return files


def main(label):
    work = tempfile.mkdtemp(prefix="df_pme_")
    try:
        out = {}
        for name, (p, key) in write_files(work).items():
            try:
                ctx = datafusion.SessionContext()
                ctx.sql(f"CREATE EXTERNAL TABLE t STORED AS PARQUET LOCATION '{p}' "
                        f"OPTIONS ('format.crypto.file_decryption.footer_key_as_hex' '{key.hex()}')").collect()
                out[name] = {"read": True, "values": ctx.sql("SELECT v FROM t").to_pydict()["v"]}
            except Exception as e:  # noqa: BLE001
                out[name] = {"read": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
        res = {"label": label, "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "environment": {m: md.version(m) for m in ("datafusion", "pyarrow", "duckdb")}, "datafusion_table_option": out}
        json.dump(res, open(os.path.join(HERE, "results", f"datafusion-pme-probe-2026-11-16-{label}.json"), "w"), indent=2)
        print(json.dumps(res, indent=1))
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main(sys.argv[1])
