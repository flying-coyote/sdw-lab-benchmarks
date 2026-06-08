"""Deterministic Zeek-conn-shaped NDJSON corpus for the SDPP ingest-throughput bench.

This is a *throughput* corpus, not a normalization-fidelity one: the point is to
hand every pipeline engine the same bytes off disk and time how fast it can read,
lightly transform, and emit them. So the records are realistic Zeek `conn.log`
JSON (the field names Zeek's JSON logger actually writes — `id.orig_h`,
`conn_state`, `history`, …), sized like real conn records (~370 bytes), with
enough field variety that a JSON parser does real work per line.

Determinism: every field is a pure function of the row index via Python's
``hashlib``-free arithmetic on a per-row seed derived from ``lib.common``'s master
seed. No ``random()`` without a seed, no wall-clock — the same ``n`` regenerates
byte-identical output, and the content fingerprint (below) proves it. That matters
here because the input bytes are the one thing held equal across engines; if the
corpus shifted between the Vector run and the Tenzir run, the comparison would be
meaningless.

The light filter the bench applies downstream keys off ``conn_state``: roughly
38% of records are the low-value short-lived/rejected states (``S0``, ``REJ``,
``RSTO``) that a route-by-value pipeline would drop before paying to store them,
so the filter selectivity is realistic and stated, not arbitrary.
"""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from common import BASE_EPOCH, MASTER_SEED  # noqa: E402

# Sub-seed for this corpus, so it's independent of every other bench's corpus but
# still fully determined by the master seed.
SUB_SEED = 4407
WINDOW_S = 86_400  # one UTC day of traffic

# Conn states, weighted to look like a real estate: ~62% "interesting"
# (SF/established/etc.), ~38% low-value short/rejected. The downstream filter
# drops the low-value class, so this weighting *is* the filter selectivity.
# (state, weight, is_low_value)
_CONN_STATES = [
    ("SF", 40, False),    # normal establish+teardown
    ("S1", 8, False),     # established, not terminated
    ("RSTR", 6, False),   # responder reset
    ("OTH", 4, False),    # no SYN, midstream
    ("SH", 4, False),     # orig SYN then FIN, no SYN-ACK
    ("S0", 22, True),     # connection attempt, no reply  <- low value
    ("REJ", 10, True),    # rejected                       <- low value
    ("RSTO", 6, True),    # originator reset (often scan)   <- low value
]
LOW_VALUE_STATES = {s for s, _, lv in _CONN_STATES if lv}
_STATE_TABLE = []
for _s, _w, _ in _CONN_STATES:
    _STATE_TABLE.extend([_s] * _w)
_STATE_MOD = len(_STATE_TABLE)  # == 100

_PROTOS = ["tcp", "tcp", "tcp", "udp", "udp", "icmp"]
_SERVICES = ["ssl", "dns", "http", "ssh", "-", "smtp", "ntp", "-", "dhcp", "-"]
_PORTS = [443, 53, 80, 22, 3389, 445, 8080, 25, 123, 67]
_HISTORIES = ["ShADadFf", "Dd", "S", "ShADadfF", "R", "ShR", "ShAfF", "C"]


def _h(i: int, salt: str) -> int:
    """Deterministic non-negative int from (row, salt). Uses the master+sub seed
    folded into a fast multiplicative mix — reproducible, thread-independent (it's
    pure arithmetic on i), and avoids per-row hashlib cost so a 10M corpus writes
    in a sane time."""
    x = (i * 0x9E3779B1) ^ (MASTER_SEED + SUB_SEED)
    for c in salt:
        x = (x * 1000003) ^ ord(c)
        x &= 0xFFFFFFFFFFFF
    return x & 0x7FFFFFFFFFFF


def _record(i: int) -> dict:
    state = _STATE_TABLE[_h(i, "st") % _STATE_MOD]
    orig_h = "10.%d.%d.%d" % (_h(i, "o1") % 256, _h(i, "o2") % 256, _h(i, "o3") % 256)
    resp_h = "10.0.%d.%d" % (_h(i, "r1") % 256, _h(i, "r2") % 256)
    proto = _PROTOS[_h(i, "p") % len(_PROTOS)]
    dur = round((_h(i, "du") % 600000) / 1000.0, 6)
    ob = _h(i, "ob") % 200000
    rb = _h(i, "rb") % 2000000
    op = 1 + _h(i, "op") % 200
    rp = 1 + _h(i, "rp") % 200
    return {
        "ts": round(BASE_EPOCH + (i % WINDOW_S) + (_h(i, "tf") % 1000) / 1000.0, 6),
        "uid": "C" + format(_h(i, "u1"), "x") + format(_h(i, "u2"), "x"),
        "id.orig_h": orig_h,
        "id.orig_p": 1024 + _h(i, "sp") % 64000,
        "id.resp_h": resp_h,
        "id.resp_p": _PORTS[_h(i, "dp") % len(_PORTS)],
        "proto": proto,
        "service": _SERVICES[_h(i, "sv") % len(_SERVICES)],
        "duration": dur,
        "orig_bytes": ob,
        "resp_bytes": rb,
        "conn_state": state,
        "local_orig": True,
        "local_resp": (_h(i, "lr") % 2 == 0),
        "missed_bytes": 0,
        "history": _HISTORIES[_h(i, "hi") % len(_HISTORIES)],
        "orig_pkts": op,
        "orig_ip_bytes": ob + op * 40,
        "resp_pkts": rp,
        "resp_ip_bytes": rb + rp * 40,
    }


def write_ndjson(n: int, path: str) -> str:
    """Write n deterministic Zeek-conn NDJSON records to path. Buffered in chunks
    so a 10M write doesn't hold the whole corpus in memory."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    buf = []
    with open(path, "w") as f:
        for i in range(n):
            buf.append(json.dumps(_record(i), separators=(",", ":")))
            if len(buf) >= 50_000:
                f.write("\n".join(buf) + "\n")
                buf = []
        if buf:
            f.write("\n".join(buf) + "\n")
    return path


def content_fingerprint(n: int) -> str:
    """Order-dependent SHA-256 over the generated records (the file is written in
    row order, so byte order is stable). Two generations of the same n must hash
    identically; this is the determinism gate the harness asserts."""
    h = hashlib.sha256()
    for i in range(n):
        h.update(json.dumps(_record(i), separators=(",", ":")).encode())
        h.update(b"\n")
    return h.hexdigest()


def low_value_fraction(n: int) -> float:
    """The exact fraction of records the downstream filter will drop, computed from
    the corpus (not assumed). Reported so the filter selectivity is a measured
    property of the input, identical for every engine."""
    low = sum(1 for i in range(n) if _record(i)["conn_state"] in LOW_VALUE_STATES)
    return low / n if n else 0.0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--out", default="/tmp/conn_sample.ndjson")
    a = ap.parse_args()
    write_ndjson(a.n, a.out)
    print("wrote", a.n, "->", a.out)
    print("low_value_fraction:", round(low_value_fraction(a.n), 4))
    print("fingerprint:", content_fingerprint(a.n))
