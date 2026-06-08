#!/usr/bin/env python3
"""Offline smoke test for the Security Context Graph MCP server.

Exercises the graph load + every tool's underlying function directly (no MCP client needed),
asserting the invariants that make the server trustworthy: the dedup runs, the SKOS counts
reconcile, proxy_quality + trust ride every edge, and the weakest-link path discipline holds
(a chain through an intent-blind artifact_cooccurrence edge reports low path_trust and
crosses_inference=true, while a typed SKOS hop reports high trust).

Run: python3 test_scg_mcp.py   (needs the `mcp` package on the active python)
"""
import scg_mcp as M


def _fn(name):
    fn = getattr(M, name)
    return getattr(fn, "fn", fn)  # unwrap FastMCP FunctionTool if wrapped


def main() -> int:
    G = M.G
    assert len(G.nodes) > 1000, f"too few nodes: {len(G.nodes)}"
    assert not G.loaded_scf, "default server must be spine-only (no SCF without env)"

    st = _fn("stats")()
    assert st["edges_deduped"] < 20000, "dedup did not run"
    pq = st["edges_by_proxy_quality"]
    assert pq.get("skos_typed") == 606, f"SKOS edges drifted: {pq.get('skos_typed')}"
    assert pq.get("artifact_cooccurrence", 0) > pq.get("measured", 0), \
        "expected inferred edges to dominate measured"
    rec = st["reconcile"]
    if rec:  # reconcile.json present
        assert rec.get("ocsf_distinct_classes", {}).get("got") == 27, "OCSF class count != 27"

    leg = _fn("legend")()
    assert leg["proxy_quality"]["measured"]["trust"] == 1.0
    assert leg["proxy_quality"]["artifact_cooccurrence"]["trust"] == 0.25

    # bare technique id resolves to the parent, not its sub-techniques
    nd = _fn("node")("T1059")
    assert not nd.get("ambiguous"), "T1059 should resolve uniquely to the parent"
    assert nd["id"] == "attack:T1059", nd.get("id")

    cov = _fn("coverage")("T1059")
    assert cov["technique"]["id"] == "attack:T1059"
    defs = cov["defenses_may_counter"]["items"]
    assert defs and all(d["proxy_quality"] == "artifact_cooccurrence" and d["weak"] for d in defs), \
        "T1059 defenses should all be intent-blind artifact_cooccurrence"

    # a typed SKOS hop: defense -> 800-53/CCI control, high trust, not an inference
    src = next(n for n, a in G.nodes.items() if a.get("ntype") == "defense"
               and any(e["rel"].startswith("skos") for e in G.adj[n]))
    dst = next(e["to"] for e in G.adj[src] if e["rel"].startswith("skos"))
    p = _fn("paths")(src, dst, max_hops=2, limit=1)
    assert p["path_count"] >= 1, "expected a defense->control SKOS path"
    top = p["paths"][0]
    assert top["path_trust"] >= 0.85 and not top["crosses_inference"], \
        f"SKOS path should be high-trust, got {top['path_trust']}"

    # min_trust prunes weak edges: high threshold should drop the intent-blind coverage
    cov_strong = _fn("coverage")("T1059", min_trust=0.6)
    assert cov_strong["defenses_may_counter"]["count"] == 0, \
        "min_trust=0.6 must hide intent-blind defense coverage"

    print(f"OK  nodes={len(G.nodes)} edges={st['edges_deduped']} "
          f"skos_typed={pq.get('skos_typed')} "
          f"T1059_inferred_defenses={cov['defenses_may_counter']['count']} "
          f"(0 survive min_trust=0.6) | SKOS path_trust={top['path_trust']}")
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
