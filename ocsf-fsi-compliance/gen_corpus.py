"""BENCH-F — synthetic FSI compliance corpus (scaffold).

A deterministic, OCSF-shaped security-telemetry corpus spanning a compressed multi-year
retention window (monthly partitions simulating six years of §1005/17a-4 retention, not
real elapsed time), with a planted intrusion whose timeline is known. This is the data the
two substrates (a schema-on-read SIEM stack and an Iceberg + catalog + time-travel
lakehouse) would each be built over so the §1003(b) report can be produced on each and the
human-hours compared.

Entirely synthetic — no real FSI data — which is what keeps this publishable and inside the
regulatory-compliance constraint that retired the customer-data benchmark offering. Seeded
off lib/common.py, so the corpus and the planted-intrusion ground truth reproduce exactly.

The human-hours headline is the operator's to measure (see REPORT-SPEC.md); this generator
builds the substrate-independent corpus and ground truth that both substrates share.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from common import BASE_EPOCH, canonical, new_rng  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_work")
MONTH_S = 30 * 86_400
RETENTION_MONTHS = 72            # six years of monthly partitions
EVENTS_PER_MONTH = 500           # modest synthetic volume per partition

SERVICES = ["s3", "iam", "ec2", "sts", "kms", "rds", "lambda"]
SYSTEMS = ["trading-gateway", "order-mgmt", "market-data", "clearing", "risk-engine"]


def _month_epoch(m):
    # anchor six years before BASE_EPOCH so the window ends "recently"
    return BASE_EPOCH - RETENTION_MONTHS * MONTH_S + m * MONTH_S


def generate():
    rng = new_rng(601)
    rows = []
    uid = 0
    for m in range(RETENTION_MONTHS):
        base = _month_epoch(m)
        for _ in range(EVENTS_PER_MONTH):
            t = base + rng.randint(0, MONTH_S - 1)
            svc = rng.choice(SERVICES)
            rows.append({
                "event_uid": f"fsi-{uid:07d}", "time": t * 1000,
                "logged_time": (t + rng.randint(1, 30)) * 1000,
                "year": 2020 + m // 12, "month": (m % 12) + 1,
                "class_uid": 6003, "service": svc, "system": rng.choice(SYSTEMS),
                "actor": f"svc-{rng.randint(0,40):02d}@fsi.example",
                "api_operation": rng.choice(["GetObject", "PutObject", "AssumeRole", "Decrypt", "DescribeInstances"]),
                "src_ip": f"10.20.{rng.randint(0,255)}.{rng.randint(1,254)}",
                "needle": None,
            })
            uid += 1

    # Planted intrusion: a known multi-step timeline in month 60 (for §1003(b) section b).
    intr_month = 60
    t0 = _month_epoch(intr_month) + 9 * 3600
    chain = [
        (0,    "sts", "AssumeRole",   "intruder-principal"),
        (420,  "s3",  "ListBucket",   "intruder-principal"),
        (900,  "kms", "Decrypt",      "intruder-principal"),
        (1500, "s3",  "GetObject",    "intruder-principal"),
        (2100, "s3",  "GetObject",    "intruder-principal"),
    ]
    timeline = []
    for off, svc, op, actor in chain:
        u = f"fsi-needle-{off}"
        rows.append({"event_uid": u, "time": (t0 + off) * 1000,
                     "logged_time": (t0 + off + 5) * 1000, "year": 2020 + intr_month // 12,
                     "month": (intr_month % 12) + 1, "class_uid": 6003, "service": svc,
                     "system": "clearing", "actor": actor, "api_operation": op,
                     "src_ip": "203.0.113.55", "needle": "intrusion"})
        timeline.append({"event_uid": u, "true_event_time_ms": (t0 + off) * 1000,
                         "service": svc, "operation": op})

    rows.sort(key=lambda r: (r["time"], r["event_uid"]))
    ground_truth = {
        "retention": {
            "first_partition_year": 2020, "months": RETENTION_MONTHS,
            "sec_1005_floor_years": 5, "rule_17a4_floor_years": 6,
            "readily_accessible_years": 2,
        },
        "intrusion_timeline": timeline,         # section (b) answer key
        "lineage_sample_uids": [r["event_uid"] for r in rows[::5000]][:10],  # section (c) sample
        "point_in_time_ms": (t0 + 1200) * 1000,  # section (d): re-run a query as of this instant
        "total_events": len(rows),
    }
    return rows, ground_truth


def write(rows, gt):
    os.makedirs(WORK, exist_ok=True)
    with open(os.path.join(WORK, "corpus.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    with open(os.path.join(WORK, "ground_truth.json"), "w") as f:
        json.dump(gt, f, indent=2, sort_keys=True)
    # convenience parquet for whichever substrate wants it
    try:
        import duckdb
        con = duckdb.connect()
        src = os.path.join(WORK, "corpus.jsonl").replace("'", "''")
        con.execute(f"COPY (SELECT * FROM read_json_auto('{src}', sample_size=-1)) "
                    f"TO '{os.path.join(WORK, 'corpus.parquet')}' (FORMAT parquet)")
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()
    r1, g1 = generate()
    r2, g2 = generate()
    det = canonical([r1, g1]) == canonical([r2, g2])
    print(f"FSI corpus: {len(r1)} events over {RETENTION_MONTHS} monthly partitions, "
          f"{len(g1['intrusion_timeline'])}-step planted intrusion. determinism: {'OK' if det else 'FAIL'}")
    if det and not args.no_write:
        write(r1, g1)
        print(f"wrote _work/corpus.jsonl + ground_truth.json (+ parquet)")
    return r1, g1


if __name__ == "__main__":
    main()
