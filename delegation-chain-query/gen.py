"""Seeded generator: synthetic multi-agent delegation chains as delegation-shaped rows.

Shape is modeled on the OCSF 1.9.0 IAM `delegation` object (authorization context per hop), but the
attribute names below are this bench's own and were NOT checked against the 1.9.0 schema JSON, which was
not on disk when the bench was built. One row = one delegation hop: `actor_uid` delegated to `agent_uid`
under `scope_mask` (16-bit authority bitmask), pointing at the previous hop through `parent_uid` (NULL at
the human root).

Chains are linear, so depth is exact: a cell of N rows at depth d holds round(N/d) chains of d hops each.

Normal hops only attenuate (granted = parent_granted & random_keep), so a non-planted chain never
escalates. In PLANT_RATE of chains one hop escalates:
  - class "new": the hop grants bit 15, which no root ever holds;
  - class "reacquire": the hop re-grants a bit the root held but an earlier hop dropped (needs h >= 2;
    at depth 2 every plant is "new"). A root-only check cannot see this class by construction.

Writes <out>/rows{N}_d{d}.parquet and <out>/rows{N}_d{d}.truth.json.
"""
import argparse
import json
import os

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

PLANT_RATE = 0.01
SEED = 20261109
NEW_BIT = 1 << 15


def generate(n_rows: int, depth: int, out_dir: str, seed: int = SEED):
    rng = np.random.default_rng([seed, n_rows, depth])
    C = max(1, round(n_rows / depth))
    # Root authority: bits 0..14 each held with p=0.6; bit 15 never held by a root.
    granted = np.zeros((C, depth), dtype=np.int64)
    granted[:, 0] = (rng.random((C, 15)) < 0.6).astype(np.int64) @ (1 << np.arange(15, dtype=np.int64))
    for h in range(1, depth):
        keep = (rng.random((C, 16)) < 0.85).astype(np.int64) @ (1 << np.arange(16, dtype=np.int64))
        granted[:, h] = granted[:, h - 1] & keep

    n_plant = max(1, int(round(C * PLANT_RATE)))
    planted = rng.choice(C, size=n_plant, replace=False)
    classes = {}
    for c in planted:
        h = int(rng.integers(1, depth))  # hop 1..depth-1
        want_reacq = (h >= 2) and (rng.random() < 0.5)
        if want_reacq:
            # Make sure hop h-1 dropped at least one root bit, then re-grant it at hop h.
            dropped = granted[c, 0] & ~granted[c, h - 1]
            if dropped == 0:
                held = granted[c, h - 1]
                if held == 0:
                    want_reacq = False
                else:
                    low = held & -held
                    granted[c, h - 1] &= ~low  # drop from hop h-1 only; still a subset of hop h-2
                    dropped = low
            if want_reacq:
                bit = dropped & -dropped
                granted[c, h] = granted[c, h - 1] | bit
                cls = "reacquire"
        if not want_reacq:
            granted[c, h] = granted[c, h - 1] | NEW_BIT
            cls = "new"
        # Hops after h attenuate from the escalated grant.
        for k in range(h + 1, depth):
            keep = int((rng.random(16) < 0.85) @ (1 << np.arange(16)))
            granted[c, k] = granted[c, k - 1] & keep
        classes[int(c)] = (cls, h)

    eff = np.zeros_like(granted)
    eff[:, 0] = granted[:, 0]
    for h in range(1, depth):
        eff[:, h] = eff[:, h - 1] & granted[:, h]

    # Identifiers: random, non-sequential int64 so join locality is not handed to either engine.
    total = C * depth
    ev_ids = rng.permutation(np.arange(1, total + 1, dtype=np.int64)) * 7919 + 1_000_000_007
    ev_uid = ev_ids.reshape(C, depth)
    chain_uid = rng.permutation(np.arange(1, C + 1, dtype=np.int64)) * 104729 + 5_000_000_000
    principals = rng.integers(1, 50_000, size=C)  # human root identity
    agents = rng.integers(1_000_000, 1_200_000, size=(C, depth))  # agent identity per hop
    t0 = rng.integers(1_788_000_000_000, 1_788_086_400_000, size=C)  # ms epoch, one day
    gaps = rng.integers(5, 2_000, size=(C, depth)).cumsum(axis=1)

    parent = np.empty((C, depth), dtype=np.int64)
    parent[:, 0] = 0
    parent[:, 1:] = ev_uid[:, :-1]
    actor = np.empty((C, depth), dtype=np.int64)
    actor[:, 0] = principals
    actor[:, 1:] = agents[:, :-1]
    parent_eff = np.empty((C, depth), dtype=np.int64)
    parent_eff[:, 0] = 0
    parent_eff[:, 1:] = eff[:, :-1]

    is_root = np.zeros((C, depth), dtype=bool)
    is_root[:, 0] = True
    tbl = pa.table({
        "event_uid": ev_uid.ravel(),
        "chain_uid": np.repeat(chain_uid, depth),
        "parent_uid": pa.array(parent.ravel(), mask=is_root.ravel()),
        "hop": np.tile(np.arange(depth, dtype=np.int32), C),
        "actor_uid": actor.ravel(),
        "agent_uid": agents.ravel(),
        "time": (t0[:, None] + gaps).ravel(),
        "scope_mask": granted.ravel().astype(np.int32),
        "parent_eff_scope": pa.array(parent_eff.ravel().astype(np.int32), mask=is_root.ravel()),
        "root_scope": np.repeat(granted[:, 0], depth).astype(np.int32),
    })
    # Log-arrival order: sort by time, which interleaves chains.
    tbl = tbl.sort_by("time")
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, f"rows{n_rows}_d{depth}")
    pq.write_table(tbl, base + ".parquet", compression="zstd", row_group_size=1_000_000)
    truth = {
        "n_rows_requested": n_rows, "n_rows": total, "depth": depth, "chains": C, "seed": seed,
        "planted": {str(int(chain_uid[c])): {"class": cls, "hop": h} for c, (cls, h) in classes.items()},
    }
    with open(base + ".truth.json", "w") as f:
        json.dump(truth, f)
    return base


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, required=True)
    ap.add_argument("--depth", type=int, required=True)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "data"))
    a = ap.parse_args()
    print(generate(a.rows, a.depth, a.out))
