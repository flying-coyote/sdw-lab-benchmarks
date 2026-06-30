"""Materialize the ATT&CK-tagged OCSF corpus for the C5 ocsf-attack-coverage bench.

This bench does NOT generate new synthetic rows. The synthetic source of truth is the
ocsf-semantic-testbed (generate.py, build-once, fingerprint 46af223b...), normalized into
the OCSF-shaped Store F by bench-a-context-collapse. Re-rolling a second corpus here would
fork determinism and invite a tuned-to-the-rules artifact. So instead this script PROJECTS
a ground-truth-tagged OCSF view of the EXISTING Store F into corpus/: every event keeps its
Store F event_uid + class_uid, and gains two columns derived purely from the planted
ground_truth.json --

  * is_malicious : True iff the event's uid is one of the planted needle uids (scalar
                   needles, beacon_conn_uids[], exfil_event_uids[]) or carries the C2 IOC
                   value; benign background otherwise.
  * att_ck       : the ATT&CK technique id the needle realizes (NULL for benign rows),
                   from the same needle->technique map the runner scores against.

Because the tags are a pure function of ground_truth.json (itself a pure function of
MASTER_SEED via the testbed), this projection is deterministic and inherits the testbed
fingerprint -- a re-run produces byte-identical corpus parquet given an unchanged Store F.
No new randomness is introduced (no new_rng draw, no datetime.now); the corpus is the same
synthetic, aggregate-safe telemetry, only re-keyed by ground truth. Synthetic only.

Run: ~/sdw-lab-benchmarks/.venv/bin/python gen_corpus.py
"""

import json
import os
import sys

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
STORE_F = os.path.join(HERE, "..", "bench-a-context-collapse", "_work", "store_f")
GT = os.path.join(HERE, "..", "ocsf-semantic-testbed", "_work", "ground_truth.json")
MANIFEST = os.path.join(HERE, "..", "ocsf-semantic-testbed", "_work", "manifest.json")
CORPUS = os.path.join(HERE, "corpus")
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import MASTER_SEED, canonical, configure_duckdb  # noqa: E402

# Store F table -> OCSF class. Mirrors the measured class bindings (process=1007 ...).
TABLES = {"process": 1007, "network": 4001, "api": 6003, "dns": 4003}

# Which planted needle uids (and the C2 IOC value) realize which ATT&CK technique, per
# Store F table. This is the SAME needle->technique pairing the runner scores against;
# it is the ground-truth tag, not a detection. Keys map to ground_truth["truth_needles"].
NEEDLE_TECHNIQUE = {
    "process": [("powershell_proc_uid", "T1059.001")],          # scalar needle uid
    "network": [("lateral_conn_uid", "T1021"),                  # scalar needle uid
                ("beacon_conn_uids", "T1071")],                 # uid-list needle (C2 beacons)
    "api":     [("nomfa_event_uid", "T1098"),                   # scalar needle uid
                ("exfil_event_uids", "T1048")],                 # uid-list needle (exfil)
    # dns: the C2 needle is an IOC VALUE (query_hostname == c2_domain), not a uid.
}


def _malicious_map(gt):
    """uid -> att_ck for every planted needle uid, per table (deterministic, from GT)."""
    out = {t: {} for t in TABLES}
    for table, pairs in NEEDLE_TECHNIQUE.items():
        for key, tech in pairs:
            v = gt.get(key)
            if v is None:
                continue
            if isinstance(v, list):
                for uid in v:
                    out[table][uid] = tech
            else:
                out[table][v] = tech
    return out


def main():
    if not os.path.isdir(STORE_F):
        print("Store F not built -- run bench-a-context-collapse/run.py first.", file=sys.stderr)
        sys.exit(2)
    gt = json.load(open(GT))["truth_needles"]
    c2_domain = gt.get("c2_domain")
    mal = _malicious_map(gt)
    os.makedirs(CORPUS, exist_ok=True)
    con = configure_duckdb(duckdb.connect(":memory:"))

    summary = {"benchmark": "ocsf-attack-coverage", "corpus_source": "projection of Store F (no new rows)",
               "master_seed": MASTER_SEED, "tables": {}}
    for table, class_uid in TABLES.items():
        src = f"{STORE_F}/{table}.parquet"
        # Build a deterministic tag relation (uid, att_ck) from ground truth, register it,
        # left-join so every existing Store F row keeps its event_uid + class_uid and gains
        # is_malicious + att_ck. ORDER BY event_uid makes the projection order-stable.
        tags = [{"event_uid": uid, "att_ck": tech} for uid, tech in sorted(mal[table].items())]
        con.register("tags", _df_tags(con, tags))
        if table == "dns" and c2_domain is not None:
            mal_expr = (f"CASE WHEN s.query_hostname = '{c2_domain}' THEN TRUE "
                        f"WHEN t.att_ck IS NOT NULL THEN TRUE ELSE FALSE END")
            tech_expr = (f"CASE WHEN s.query_hostname = '{c2_domain}' THEN 'T1071' "
                         f"ELSE t.att_ck END")
        else:
            mal_expr = "CASE WHEN t.att_ck IS NOT NULL THEN TRUE ELSE FALSE END"
            tech_expr = "t.att_ck"
        out = f"{CORPUS}/{table}.parquet"
        con.execute(f"""
            COPY (
              SELECT s.*, {mal_expr} AS is_malicious, {tech_expr} AS att_ck
              FROM '{src}' s
              LEFT JOIN tags t ON s.event_uid = t.event_uid
              ORDER BY s.event_uid
            ) TO '{out}' (FORMAT PARQUET)
        """)
        con.unregister("tags")
        nrow, nmal = con.execute(
            f"SELECT count(*), count(*) FILTER (WHERE is_malicious) FROM '{out}'").fetchone()
        techs = sorted({r[0] for r in con.execute(
            f"SELECT DISTINCT att_ck FROM '{out}' WHERE att_ck IS NOT NULL").fetchall()})
        summary["tables"][table] = {"class_uid": class_uid, "rows": int(nrow),
                                    "malicious": int(nmal), "att_ck_tags": techs}
        print(f"  {table:8} class_uid={class_uid}  rows={nrow}  malicious={nmal}  tags={techs}")
    con.close()

    summary["ground_truth_fingerprint"] = _fingerprint()
    with open(os.path.join(CORPUS, "_corpus_manifest.json"), "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    print(f"\nwrote tagged OCSF corpus to {CORPUS}/ (projection of Store F, no new rows)")
    print(f"canonical: {canonical(summary['tables'])[:80]}...")


def _df_tags(con, tags):
    """A small DuckDB relation (uid, att_ck) from the tag list, typed even when empty."""
    if not tags:
        return con.sql("SELECT NULL::VARCHAR AS event_uid, NULL::VARCHAR AS att_ck WHERE 1=0")
    vals = ", ".join(f"('{t['event_uid']}', '{t['att_ck']}')" for t in tags)
    return con.sql(f"SELECT * FROM (VALUES {vals}) AS v(event_uid, att_ck)")


def _fingerprint():
    try:
        return json.load(open(MANIFEST)).get("fingerprint_sha256", "")
    except Exception:
        return ""


if __name__ == "__main__":
    main()
