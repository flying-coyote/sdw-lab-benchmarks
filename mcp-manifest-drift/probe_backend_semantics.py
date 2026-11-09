"""EXPLORATORY (post-hoc, not pre-registered): two latent differences seen in the emitted SQL.
(i) '_' in a contains value: DuckDB backend emits ILIKE '%id_rsa%' unescaped ('_' = any char); sqlite escapes it.
(ii) NULL in a negated fieldref: DuckDB backend emits NOT (a=b AND c=d); sqlite wraps it in COALESCE(...,0).
Usage: python -I probe_backend_semantics.py a|b   (writes results/probe-<path>.json)"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import sigma_run as S
HERE = Path(__file__).resolve().parent
base = json.loads((HERE / "events/events-D1.jsonl").read_text().splitlines()[0])
probe = []
e1 = dict(base); e1.update({"metadata.uid": "probe-underscore", "activity_id": 8, "unmapped.desc_added_text": "uses idXrsa format"}); probe.append(e1)
e2 = dict(base); e2.update({"metadata.uid": "probe-null-prev", "activity_id": 8, "unmapped.prev_desc_fingerprint": None,
                            "unmapped.prev_input_schema_fingerprint": None}); probe.append(e2)
be, vers = S.backend()
con = S.build(probe, "sqlite" if S.PATH == "b" else "duckdb")
out = {"path": S.PATH, "versions": vers}
for r in ("s3_hidden_instruction", "s2_contract_drift"):
    from sigma.collection import SigmaCollection
    sql = be.convert(SigmaCollection.from_yaml((HERE / f"rules/{r}.yml").read_text()))[0]
    q = '"metadata.uid"' if S.PATH == "a" else "`metadata.uid`"
    out[r] = sorted(x[0] for x in con.execute(sql.replace("SELECT *", f"SELECT {q}", 1)).fetchall())
(HERE / f"results/probe-{S.PATH}.json").write_text(json.dumps(out, indent=1))
print(out)
