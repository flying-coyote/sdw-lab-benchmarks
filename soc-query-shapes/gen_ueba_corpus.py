#!/usr/bin/env python3
"""Generate a SYNTHETIC UEBA + rare-value corpus with known ground truth (no real telemetry).

The existing soc.conn has no volume-spike hosts and no single-source destinations, so the
ueba_zscore and rare_dest detections returned 0 rows — the 2026-06-15 SOC-shape bench could
measure latency/ranking but NOT detection-correctness or cross-engine answer-equality (the
H-ARCH-02 evidence file flags this explicitly). This builds a self-contained planted table
`soc.conn_ueba_planted` so both detections fire on KNOWN truth:

  UEBA volume Z-score (two-level agg: hourly count per host -> per-host mean/stddev -> Z>3):
    - NORMAL  hosts: ~24 h of steady low volume (~10/h, tight) -> Z ~2, must NOT flag.
    - SPIKE   hosts (GROUND TRUTH): steady baseline + ONE spike hour (~7x) -> Z ~4.5, MUST flag.
    - HIGH-STEADY decoys: high volume every hour (~100/h, low variance) -> Z ~1.6, must NOT flag
      (tests that the detection flags ANOMALY vs its own baseline, not just heavy talkers).
  rare_dest (high-card count-DISTINCT: destinations contacted by exactly one source):
    - common dests: contacted by many sources -> count(DISTINCT orig_h) >> 1, not flagged.
    - RARE dests (GROUND TRUTH): each contacted by exactly ONE source -> flagged.

Spike Z (~4.5) and decoy Z (~1.6) are kept well clear of the 3.0 threshold so the flagged SET
is robust to cross-engine float differences in avg/stddev — answer-equality is scored on the
entity set, not the float-laden rows. Fully synthetic random IPs/timestamps (no injection
surface). Loads to the ejs Nessie catalog. Run in ejs-lab.
"""
import json, random
import pyarrow as pa
from pyiceberg.catalog.rest import RestCatalog

random.seed(1337)  # reproducible
S3 = {"s3.endpoint": "http://minio:9000", "s3.access-key-id": "ejsbench",
      "s3.secret-access-key": "ejsbench123", "s3.path-style-access": "true"}
NESSIE = "http://nessie:19120/iceberg/"
T0 = 1781000000.0
HOURS = 24
HR = 3600.0
N_NORMAL = 3000        # steady low-volume hosts (no spike) -> Z low, must NOT flag
N_SPIKE = 15           # GROUND TRUTH ueba: baseline + one spike hour -> Z>3
N_HIGHSTEADY = 60      # high-volume steady decoys -> Z low, must NOT flag
N_RARE = 15            # GROUND TRUTH rare_dest: each contacted by exactly one source
N_COMMON_DESTS = 60    # shared popular destinations (many sources each)
BASE = 10              # normal per-hour connection count
SPIKE_MULT = 7         # spike hour = BASE * SPIKE_MULT
HIGH = 100             # high-steady per-hour count


def rip(a, b=93):
    return f"{a}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def rows():
    oh = []; rh = []; ts = []; op = []; rp = []; proto = []; ob = []; rbl = []
    common = [f"93.184.{i//256}.{i%256+1}" for i in range(N_COMMON_DESTS)]

    def add(o, r, t):
        oh.append(o); rh.append(r); ts.append(t)
        op.append(random.randint(1024, 65535)); rp.append(random.choice([80, 443, 22, 445, 3389]))
        proto.append("tcp"); ob.append(random.randint(40, 2000)); rbl.append(random.randint(40, 5000))

    def host_hours(host, per_hour_fn):
        """Emit per_hour_fn(h) connections (to common dests) in each of HOURS buckets."""
        for h in range(HOURS):
            c = per_hour_fn(h)
            for _ in range(c):
                add(host, random.choice(common), T0 + h * HR + random.uniform(1, HR - 1))

    # NORMAL: BASE +/- small jitter every hour, no spike
    for i in range(N_NORMAL):
        host_hours(f"10.{i//256}.{i%256}.{random.randint(1,254)}",
                   lambda h: max(1, BASE + random.randint(-2, 2)))

    truth_spike = []
    # SPIKE (ground truth): baseline every hour + ONE hour at BASE*SPIKE_MULT
    for i in range(N_SPIKE):
        host = f"172.16.{i//256}.{i%256}"
        truth_spike.append(host)
        spike_hr = random.randint(2, HOURS - 2)
        host_hours(host, lambda h, sh=spike_hr: (BASE * SPIKE_MULT if h == sh
                                                 else max(1, BASE + random.randint(-2, 2))))

    # HIGH-STEADY decoys: high volume, low variance, no spike -> Z low (must NOT flag)
    for i in range(N_HIGHSTEADY):
        host_hours(f"10.200.{i//256}.{i%256}", lambda h: HIGH + random.randint(-5, 5))

    truth_rare = []
    # RARE dests (ground truth): each a unique source -> a unique dest (disjoint IP range),
    # few connections in 1-2 hours so the source host has <5 active hours (excluded from ueba)
    for i in range(N_RARE):
        src = f"10.250.{i//256}.{i%256}"
        dst = f"198.51.100.{i+1}"
        truth_rare.append(dst)
        for _ in range(random.randint(5, 18)):
            add(src, dst, T0 + random.randint(0, 2) * HR + random.uniform(1, HR - 1))

    tbl = pa.table({"ts": pa.array(ts, pa.float64()), "orig_h": oh, "orig_p": pa.array(op, pa.int32()),
                    "resp_h": rh, "resp_p": pa.array(rp, pa.int32()), "proto": proto,
                    "orig_bytes": pa.array(ob, pa.int64()), "resp_bytes": pa.array(rbl, pa.int64())})
    return tbl, sorted(truth_spike), sorted(truth_rare)


def main():
    tbl, truth_spike, truth_rare = rows()
    cat = RestCatalog("nessie", uri=NESSIE, warehouse="warehouse", **S3)
    cat.create_namespace_if_not_exists("soc")
    try:
        cat.drop_table("soc.conn_ueba_planted")
    except Exception:
        pass
    t = cat.create_table("soc.conn_ueba_planted", schema=tbl.schema)
    t.append(tbl)
    truth = {"ueba_spike_hosts": truth_spike, "n_ueba_true": len(truth_spike),
             "rare_dests": truth_rare, "n_rare_true": len(truth_rare),
             "n_rows": tbl.num_rows, "n_normal": N_NORMAL, "n_highsteady_decoy": N_HIGHSTEADY}
    open("/tmp/ueba_truth.json", "w").write(json.dumps(truth))
    print(f"loaded soc.conn_ueba_planted: {tbl.num_rows} rows | {len(truth_spike)} spike hosts "
          f"(ground truth) | {N_HIGHSTEADY} high-steady decoys | {len(truth_rare)} rare dests (ground truth)")
    print("ground truth -> /tmp/ueba_truth.json")


if __name__ == "__main__":
    main()
