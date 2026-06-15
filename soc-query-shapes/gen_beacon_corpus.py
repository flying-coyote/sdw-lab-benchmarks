#!/usr/bin/env python3
"""Generate a SYNTHETIC beacon-detection corpus with known ground truth (no real telemetry).

soc.conn (the existing corpus) has max 3 connections per (orig_h,resp_h) pair — no beacon structure
to detect. This builds a self-contained synthetic table `soc.conn_beacontest` = background random TCP
flow + PLANTED regular-interval beacons (the ground truth) + high-variance decoy heavy-talkers, so
the beaconing detection is real and answer-equality across engines can be checked against known
truth. Fully synthetic (random IPs/timestamps), so no adversarial-text / injection surface.

Ground truth = the planted beacon (orig_h,resp_h) pairs (low gap-CV). Loads to the ejs Nessie
catalog as soc.conn_beacontest. Run in ejs-lab.
"""
import json, random
import pyarrow as pa
from pyiceberg.catalog.rest import RestCatalog

random.seed(42)   # reproducible
S3 = {"s3.endpoint": "http://minio:9000", "s3.access-key-id": "ejsbench",
      "s3.secret-access-key": "ejsbench123", "s3.path-style-access": "true"}
NESSIE = "http://nessie:19120/iceberg/"
T0 = 1781000000.0          # base epoch
N_BACKGROUND = 800_000
N_BEACONS = 120            # planted regular beacons (ground truth)
N_DECOYS = 30             # high-volume but irregular pairs (must NOT be flagged)

def ip(a=10): return f"{a}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"

def rows():
    orig_h=[]; resp_h=[]; ts=[]; orig_p=[]; resp_p=[]; proto=[]; ob=[]; rb=[]
    def add(oh, rh, t, rp):
        orig_h.append(oh); resp_h.append(rh); ts.append(t); orig_p.append(random.randint(1024,65535))
        resp_p.append(rp); proto.append("tcp"); ob.append(random.randint(40,2000)); rb.append(random.randint(40,5000))
    # background: random unique-ish flow
    for _ in range(N_BACKGROUND):
        add(ip(10), ip(93), T0 + random.uniform(0, 86400), random.choice([80,443,22,445,3389]))
    truth=[]
    # planted beacons: regular interval + small jitter, 25-45 callbacks each
    for b in range(N_BEACONS):
        oh=f"172.16.{b//256}.{b%256}"; rh=f"203.0.113.{b%254+1}"; rp=random.choice([443,8443,53])
        interval=random.choice([30.0,60.0,300.0]); n=random.randint(25,45); start=T0+random.uniform(0,3600)
        for k in range(n):
            add(oh, rh, start + k*interval + random.uniform(-0.08,0.08)*interval, rp)
        truth.append((oh, rh))
    # decoys: heavy pairs with IRREGULAR gaps (high CV) — should rank LOW (not beacons)
    for d in range(N_DECOYS):
        oh=f"192.168.{d//256}.{d%256}"; rh=f"198.51.100.{d%254+1}"
        t=T0+random.uniform(0,3600)
        for k in range(random.randint(25,45)):
            t += random.uniform(1, 600)   # wildly irregular
            add(oh, rh, t, 443)
    tbl = pa.table({"ts":pa.array(ts,pa.float64()),"orig_h":orig_h,"orig_p":pa.array(orig_p,pa.int32()),
                    "resp_h":resp_h,"resp_p":pa.array(resp_p,pa.int32()),"proto":proto,
                    "orig_bytes":pa.array(ob,pa.int64()),"resp_bytes":pa.array(rb,pa.int64())})
    return tbl, truth

def main():
    tbl, truth = rows()
    cat = RestCatalog("nessie", uri=NESSIE, warehouse="warehouse", **S3)
    cat.create_namespace_if_not_exists("soc")
    try: cat.drop_table("soc.conn_beacontest")
    except Exception: pass
    t = cat.create_table("soc.conn_beacontest", schema=tbl.schema)
    t.append(tbl)
    open("/tmp/beacon_truth.json","w").write(json.dumps({"truth_pairs":sorted(truth),"n_truth":len(truth),
        "n_rows":tbl.num_rows,"n_decoys":N_DECOYS}))
    print(f"loaded soc.conn_beacontest: {tbl.num_rows} rows, {len(truth)} planted beacons, {N_DECOYS} decoys")
    print("ground truth -> /tmp/beacon_truth.json")

if __name__ == "__main__":
    main()
