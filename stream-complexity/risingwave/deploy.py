"""R arm deploy: wait for the SQL port, run the edition probe, then create the table, the
materialized view and the subscription from detection.sql. Env: SMX_RW_DSN."""
import json, os, sys, time
import psycopg

HERE = os.path.dirname(os.path.abspath(__file__))
DSN = os.environ.get("SMX_RW_DSN", "host=localhost port=14566 user=root dbname=dev")
PROBE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "edition-probe.json")

for _ in range(120):
    try:
        conn = psycopg.connect(DSN, autocommit=True)
        break
    except psycopg.OperationalError:
        time.sleep(1)
else:
    sys.exit("RisingWave SQL port did not answer")

probe = {}
with conn.cursor() as cur:
    cur.execute("SELECT version()")
    probe["version"] = cur.fetchone()[0]
    cur.execute("SHOW PARAMETERS")
    probe["license_before"] = [r for r in cur.fetchall() if "license" in str(r[0]).lower()]
    try:
        cur.execute("ALTER SYSTEM SET license_key TO ''")
        probe["clear_trial"] = "accepted"
    except psycopg.Error as e:
        probe["clear_trial"] = f"refused: {e}".strip()
    cur.execute("SHOW PARAMETERS")
    probe["license_after"] = [r for r in cur.fetchall() if "license" in str(r[0]).lower()]
    probe["rw_features"] = cur.execute("SELECT * FROM rw_catalog.rw_features").fetchall()
    with open(PROBE, "w") as f:
        json.dump(probe, f, indent=2, default=str)
    sql = "\n".join(l for l in open(os.path.join(HERE, "detection.sql")) if not l.strip().startswith("--"))
    for stmt in sql.split(";"):
        if stmt.strip():
            cur.execute(stmt)
print("R arm deployed:", probe["version"][:60])
