#!/usr/bin/env python3
"""BENCH-C v2 — A9 asset-population enlargement (committed BEFORE the scored re-run).

Why (pre-reg §3 / addendum §5): v1's A9 advantage was a materialized-sameAs-index artifact —
the structured context handed the model 2 precomputed `--sameAs-->` collapse edges over a 2-asset
corpus, so it counted pre-collapsed pairs instead of *computing* an alias closure. v2 enlarges the
asset population to EXACTLY 12 assets, each with hostname + IP + instance_id (3 alias nodes), with
>=3 assets carrying a MULTI-HOP alias chain (a reassigned IP linking two hostnames), so the alias
closure is >= 2 hops and must be computed, not read off a 2-edge freebie.

The "distinct physical asset" gold is the number of connected components of the alias graph
(hostname/ip/instance_id nodes joined by sameAs edges), COMPUTED here from the population — never
hand-set — so the gold is a function of the committed corpus, not a planted constant.

FAIRNESS / cross-bench scoping: this writes a BENCH-C-LOCAL overlay (_work/v2/asset_v2.parquet +
_work/v2/ground_truth_v2.json). It does NOT touch the shared store_f/asset.parquet or the shared
ocsf-semantic-testbed ground_truth.json, because BENCH-A (bench.py) and validate.py assert the v1
`distinct_asset_count == 2` against the shared artifacts. See bench_c_v2_config.py for the rationale.

Deterministic: a fixed asset list (no RNG); re-running reproduces byte-identical output.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bench_c_v2_config as CFG  # noqa: E402

# --------------------------------------------------------------------------- #
# The committed 12-asset population. Each asset = (hostname, ip, instance_id). #
# A "reassigned IP" is an IP that appears on TWO hostnames: under transitive   #
# sameAs closure (host -- ip -- host) that links the two hostnames into one    #
# physical-asset component over a >=2-hop chain (host1 -> ip -> host2).        #
#                                                                              #
# Layout (committed, deterministic):                                          #
#   - 12 hostnames WS1..WS12, each with its own instance_id.                  #
#   - 3 reassigned-IP chains (>=3 assets carrying a multi-hop chain, per       #
#     addendum §5): IPs 10.20.0.50 / .51 / .52 are each shared by a pair of    #
#     hostnames, collapsing 6 hostnames into 3 physical assets.               #
#   - the remaining 6 hostnames each have a unique IP (singleton components).  #
#   => connected components after closure = 3 (merged pairs) + 6 (singletons) #
#      = 9 distinct physical assets.  The gold is computed below, not asserted.#
# --------------------------------------------------------------------------- #
ASSETS = [
    # --- 3 reassigned-IP chains: each IP shared by two hostnames (>=2-hop closure) ---
    ("WS1",  "10.20.0.50", "i-0a00000000000001"),   # WS1 & WS2 share 10.20.0.50 (reassigned)
    ("WS2",  "10.20.0.50", "i-0a00000000000002"),
    ("WS3",  "10.20.0.51", "i-0a00000000000003"),   # WS3 & WS4 share 10.20.0.51 (reassigned)
    ("WS4",  "10.20.0.51", "i-0a00000000000004"),
    ("WS5",  "10.20.0.52", "i-0a00000000000005"),   # WS5 & WS6 share 10.20.0.52 (reassigned)
    ("WS6",  "10.20.0.52", "i-0a00000000000006"),
    # --- 6 singleton assets: unique IP each ---
    ("WS7",  "10.20.0.57", "i-0a00000000000007"),
    ("WS8",  "10.20.0.58", "i-0a00000000000008"),
    ("WS9",  "10.20.0.59", "i-0a00000000000009"),
    ("WS10", "10.20.0.60", "i-0a0000000000000a"),
    ("WS11", "10.20.0.61", "i-0a0000000000000b"),
    ("WS12", "10.20.0.62", "i-0a0000000000000c"),
]
assert len(ASSETS) == 12, "addendum §5 fixes the population at EXACTLY 12 assets"


def alias_edges(assets):
    """sameAs edges of the alias graph: hostname -- ip -- instance_id per row. A shared IP node is
    where two hostnames meet (the reassigned-IP multi-hop chain)."""
    edges = []
    for host, ip, inst in assets:
        edges.append((f"host:{host}", f"ip:{ip}"))
        edges.append((f"ip:{ip}", f"instance:{inst}"))
    return edges


def connected_components(nodes, edges):
    """Union-find over the alias graph -> number of distinct physical-asset components."""
    parent = {n: n for n in nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    for a, b in edges:
        union(a, b)
    roots = {find(n) for n in nodes}
    # group hostnames by component so we can report the alias-chain structure
    comp = {}
    for host, ip, inst in ASSETS:
        comp.setdefault(find(f"host:{host}"), []).append(host)
    return len(roots), sorted(sorted(v) for v in comp.values())


def closure_hops(assets):
    """Max alias-chain length for any merged component (host1 -> ip -> host2 is 2 hops)."""
    # the shared-IP pairs are exactly the >=2-hop chains; report the count and the depth.
    ip_to_hosts = {}
    for host, ip, inst in assets:
        ip_to_hosts.setdefault(ip, []).append(host)
    multi = {ip: hs for ip, hs in ip_to_hosts.items() if len(hs) > 1}
    return multi


def build():
    nodes = set()
    for host, ip, inst in ASSETS:
        nodes.update((f"host:{host}", f"ip:{ip}", f"instance:{inst}"))
    edges = alias_edges(ASSETS)
    n_distinct, components = connected_components(nodes, edges)
    multi = closure_hops(ASSETS)

    # gold is COMPUTED from the population (never hand-set)
    distinct_assets = [{"hostname": h, "ip": ip, "instance_id": inst} for (h, ip, inst) in ASSETS]
    gold = {
        "distinct_asset_count": n_distinct,          # connected components after alias closure
        "n_asset_rows": len(ASSETS),                 # 12 alias-bearing rows
        "asset_components": components,               # which hostnames collapse together
        "reassigned_ip_chains": multi,               # the >=2-hop chains (shared IPs)
        "distinct_assets_rows": distinct_assets,      # the raw 12-row population
        "note": ("distinct_asset_count is the connected-component count of the hostname/ip/"
                 "instance alias graph; gold computed from the committed population, not asserted."),
    }
    return gold


def write_overlay(gold):
    os.makedirs(CFG.WORK_V2, exist_ok=True)
    # asset_v2.parquet — same columns as the v1 asset table so run_graphrag.build_graph reads it
    # unchanged: hostname, ip, instance_uid, canonical_asset. canonical_asset is left as the
    # hostname (the v1 convention); closure is COMPUTED by the arms, not read from canonical_asset.
    import duckdb
    rows = ",\n            ".join(
        f"('{h}','{ip}','{inst}','{h}')" for (h, ip, inst) in ASSETS)
    con = duckdb.connect()
    con.execute(f"""COPY (
        SELECT * FROM (VALUES
            {rows}
        ) AS t(hostname, ip, instance_uid, canonical_asset)
    ) TO '{CFG.STORE_F_V2_ASSET}' (FORMAT parquet)""")
    con.close()

    # ground_truth_v2.json — BENCH-C-local; merges the v1 shared truth, overriding ONLY the
    # A9 asset block. (A4 stays as-is in the shared truth but is EXCLUDED at scoring time.)
    shared = json.load(open(CFG.GT))
    v2 = dict(shared)
    tn = dict(v2["truth_needles"])
    tn["distinct_asset_count"] = gold["distinct_asset_count"]
    tn["distinct_assets"] = gold["distinct_assets_rows"]
    v2["truth_needles"] = tn
    v2["_bench_c_v2_a9"] = gold      # full computed structure for audit
    json.dump(v2, open(CFG.GT_V2, "w"), indent=2, sort_keys=True)


def main():
    gold = build()
    write_overlay(gold)
    print("=== BENCH-C v2 A9 asset population (committed) ===")
    print(f"  asset rows (alias-bearing): {gold['n_asset_rows']}  (addendum §5 fixes this at 12)")
    print(f"  distinct physical assets after closure (GOLD, computed): {gold['distinct_asset_count']}")
    print(f"  reassigned-IP multi-hop chains (>=2 hops): {len(gold['reassigned_ip_chains'])}")
    for ip, hs in gold["reassigned_ip_chains"].items():
        print(f"    {ip}  shared by  {hs}   (host1 -> ip -> host2 = 2-hop closure)")
    print(f"  components: {gold['asset_components']}")
    print(f"  wrote {CFG.STORE_F_V2_ASSET}")
    print(f"  wrote {CFG.GT_V2}")


if __name__ == "__main__":
    main()
