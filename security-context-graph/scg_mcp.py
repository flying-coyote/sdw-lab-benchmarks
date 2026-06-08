#!/usr/bin/env python3
"""Security Context Graph — read-only MCP server (Phase B).

Exposes the concept-only Security Context Graph (built by scg.py) over MCP/stdio so an
agent can ground a security-context question in the real OCSF<->D3FEND<->ATT&CK<->control
chain instead of inventing one. The whole point of this server is the transparency
discipline from the mapping-rigor review: EVERY edge carries its `proxy_quality`, and a
multi-hop answer is only as trustworthy as its WEAKEST edge. The server never hides a weak
join -- it surfaces it and labels it, so a model (or a reader) can see exactly how a claim
is supported and refuse to overclaim where the support is an intent-blind inference.

READ-ONLY. It loads results/nodes.json + results/edges.json (the public spine). The
ND-gated SCF layer (results-scf-local/) loads only when SCG_WITH_SCF=1 is set, so the
default server ships nothing under CC-BY-ND.

Empirical context (do not overstate the graph's value): the SDW Lab field-mapping and
nl2sql benchmarks (2026-06-08) found that conceptual grounding prose is ~inert versus a
plain schema-validity check, and that graph STRUCTURE changed a retrieval answer on only
1 of 9 incident-reconstruction queries (the identity-collapse case). So this graph's job
is honest navigation-with-provenance, not a claim that grounding makes a model smarter.

Run: python3 scg_mcp.py     (registered in project1/.claude/mcp.json as `scg`)
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict, deque
from pathlib import Path

from mcp.server.fastmcp import FastMCP

HERE = Path(__file__).resolve().parent
RESULTS = Path(os.environ.get("SCG_RESULTS_DIR", HERE / "results"))
WITH_SCF = os.environ.get("SCG_WITH_SCF", "") not in ("", "0", "false", "False")
SCF_DIR = Path(os.environ.get("SCG_SCF_DIR", HERE / "results-scf-local"))

# Trust ranking of the proxy_quality taxonomy: how defensible is an edge as grounding,
# from empirically-measured down to intent-blind inference. A path's trust is the MIN over
# its edges (weakest link). These ranks are a deliberate, documented judgement, not a
# measurement -- they encode "how was this join actually established."
TRUST = {
    "measured": 1.00,            # (1) first-party measured field->OCSF mapping
    "skos_typed": 0.90,          # (5) D3FEND->800-53/CCI typed SKOS relation
    "ontology_axiom": 0.85,      # (3) ontology subclass / restriction axiom (logical)
    "doc_link": 0.80,            # (2) OCSF<->D3FEND maintainer hyperlink (seeAlso)
    "ontology_curated": 0.70,    # (3) ontology-authored artifact tag
    "curated": 0.65,             # (4') hand-authored ATT&CK mitigation / in-tactic
    "ctid_reroute": 0.50,        # (5') SCF->ATT&CK = CTID 800-53->ATT&CK re-routed
    "scf_strm": 0.45,            # SCF->framework STRM crosswalk
    "derived": 0.40,             # rollup / derived statistic
    "artifact_cooccurrence": 0.25,  # (4) offense<->defense INFERRED, intent-blind -- WEAK
    "unmapped": 0.00,            # explicit honest gap (a null mapping), not traversable
}
PROXY_NOTE = {
    "measured": "first-party measured mapping",
    "skos_typed": "formal typed SKOS mapping in the D3FEND ontology",
    "ontology_axiom": "ontology subclass/restriction axiom (logical entailment)",
    "doc_link": "maintainer-authored cross-reference hyperlink",
    "ontology_curated": "ontology-authored artifact relationship",
    "curated": "hand-authored (MITRE/CTID) mitigation or tactic assignment",
    "ctid_reroute": "re-routed through CTID's 800-53->ATT&CK mapping (one inference hop)",
    "scf_strm": "SCF STRM framework crosswalk (vendor-authored)",
    "derived": "derived rollup statistic",
    "artifact_cooccurrence": "INFERRED from shared digital artifact, intent-blind -- do "
                             "NOT state as an established relationship; counters!=detects",
    "unmapped": "explicit gap: no mapping exists (honest null, not a link)",
}


def _trust(pq: str) -> float:
    return TRUST.get(pq, 0.30)  # unknown proxy -> conservative low-ish


class Graph:
    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.label_index: dict[str, list[str]] = defaultdict(list)
        self.adj: dict[str, list[dict]] = defaultdict(list)  # undirected, annotated
        self.edge_pq = Counter()
        self.loaded_scf = False
        self._load(RESULTS, scf=False)
        if WITH_SCF and SCF_DIR.exists():
            self._load(SCF_DIR, scf=True)
            self.loaded_scf = True

    def _load(self, d: Path, scf: bool) -> None:
        nodes = json.load(open(d / "nodes.json"))
        edges = json.load(open(d / "edges.json"))
        for a in nodes:
            nid = a["id"]
            if nid not in self.nodes:
                self.nodes[nid] = a
                self.label_index[str(a.get("label", "")).lower()].append(nid)
        seen = set()
        for e in edges:
            key = (e["src"], e["dst"], e["rel"], e.get("proxy_quality"))
            if key in seen:
                continue  # raw edges.json has duplicates; the fingerprint dedups, so do we
            seen.add(key)
            pq = e.get("proxy_quality", "")
            self.edge_pq[pq] += 1
            fwd = {"to": e["dst"], "rel": e["rel"], "tier": e.get("tier"),
                   "proxy_quality": pq, "proxy_note": e.get("proxy_note", ""),
                   "dir": "out", "scf": scf}
            rev = {**fwd, "to": e["src"], "dir": "in"}
            self.adj[e["src"]].append(fwd)
            self.adj[e["dst"]].append(rev)

    def resolve(self, q: str) -> list[str]:
        """Return node ids matching q: exact id, then a prefixed exact id (so a bare
        'T1059' resolves uniquely to 'attack:T1059' and not its sub-techniques), then
        exact label, then substring on label or id."""
        if q in self.nodes:
            return [q]
        for pfx in ("attack:", "d3f:", "ocsf:class/", "ocsf:object/", "ocsf:", "scf:"):
            if (pfx + q) in self.nodes:
                return [pfx + q]
        ql = q.lower()
        if ql in self.label_index:
            return list(self.label_index[ql])
        hits = [nid for lbl, ids in self.label_index.items() if ql in lbl for nid in ids]
        # also allow substring on id (e.g. "T1059")
        hits += [nid for nid in self.nodes if ql in nid.lower() and nid not in hits]
        return hits[:50]

    def lbl(self, nid: str) -> str:
        """A display label: the node's own label, or a cleaned id when the label is empty
        (many D3FEND defense nodes carry an empty label but a self-descriptive id)."""
        a = self.nodes.get(nid, {})
        return a.get("label") or nid.split("/")[-1].split(":")[-1]

    def brief(self, nid: str) -> dict:
        a = self.nodes.get(nid, {})
        out = sum(1 for e in self.adj[nid] if e["dir"] == "out")
        return {"id": nid, "ntype": a.get("ntype"), "label": self.lbl(nid),
                "degree_out": out, "degree_in": len(self.adj[nid]) - out}


G = Graph()
mcp = FastMCP(
    "security-context-graph",
    instructions=(
        "Concept-only Security Context Graph (OCSF schema <-> digital artifact <-> D3FEND "
        "defense <-> ATT&CK offense <-> 800-53/SCF control). READ-ONLY. Every edge carries "
        "a proxy_quality saying HOW the join was established; a multi-hop answer is only as "
        "trustworthy as its weakest edge (see `legend` and the path_trust each tool "
        "returns). Treat `artifact_cooccurrence` edges as intent-blind inferences, not "
        "established facts. Call `legend` first if unsure how to read the trust labels."
    ),
)


def _edge_view(e: dict) -> dict:
    pq = e["proxy_quality"]
    return {"to": e["to"], "to_label": G.lbl(e["to"]),
            "to_ntype": G.nodes.get(e["to"], {}).get("ntype"),
            "rel": e["rel"], "dir": e["dir"], "tier": e["tier"],
            "proxy_quality": pq, "trust": _trust(pq), "how": PROXY_NOTE.get(pq, "unknown"),
            "weak": _trust(pq) <= 0.25, **({"scf": True} if e.get("scf") else {})}


@mcp.tool()
def legend() -> dict:
    """The proxy_quality + tier vocabulary and trust ranking. Read this to interpret every
    other tool's `proxy_quality`/`trust`/`weak` fields. Trust is a documented judgement of
    how an edge was established, not a measurement; a path's trust is its weakest edge."""
    return {
        "evidence_tiers": {
            "A": "peer-reviewed research / official standard",
            "B": "first-party SDW lab measurement / practitioner field source",
            "C": "vendor doc or marketing (bias-flagged)",
            "D": "speculation / unverified inference",
        },
        "proxy_quality": {k: {"trust": TRUST[k], "meaning": PROXY_NOTE[k]} for k in TRUST},
        "weakest_link_rule": "A multi-hop chain is only as sound as its least-trustworthy "
                             "edge. Every path tool returns path_trust = min(edge trust) "
                             "and names the weakest hop. Do not state a chain that crosses "
                             "an artifact_cooccurrence (intent-blind) edge as established.",
        "scf_layer_loaded": G.loaded_scf,
    }


@mcp.tool()
def stats() -> dict:
    """Graph size and composition: node counts by type, edge counts by proxy_quality, and
    the headline reconciliation figures locked by scg.py (so you can trust the corpus)."""
    nt = Counter(a.get("ntype") for a in G.nodes.values())
    recon = {}
    rp = RESULTS / "reconcile.json"
    if rp.exists():
        try:
            data = json.load(open(rp))
            checks = data.get("checks", data if isinstance(data, list) else [])
            recon = {c["check"]: {"got": c.get("got"), "pass": c.get("pass")}
                     for c in checks if isinstance(c, dict) and "check" in c}
        except Exception:
            pass
    return {"nodes": len(G.nodes), "edges_deduped": sum(G.edge_pq.values()),
            "nodes_by_type": dict(nt), "edges_by_proxy_quality": dict(G.edge_pq),
            "scf_layer_loaded": G.loaded_scf, "reconcile": recon}


@mcp.tool()
def find_node(query: str, ntype: str = "", limit: int = 20) -> dict:
    """Resolve a node by id (e.g. 'attack:T1059'), exact label, or substring. Optionally
    filter by ntype (attack, attack_tactic, attack_mitigation, defense, artifact,
    d3fend_event, ocsf_class, ocsf_object, ocsf_field, source_field, control). Returns
    candidates -- when more than one matches, pick the intended id before traversing."""
    ids = G.resolve(query)
    if ntype:
        ids = [i for i in ids if G.nodes.get(i, {}).get("ntype") == ntype]
    return {"query": query, "match_count": len(ids),
            "matches": [G.brief(i) for i in ids[:limit]]}


@mcp.tool()
def node(id: str) -> dict:
    """Full record for one node id, including its raw attributes and out/in degree. Use
    find_node first if you only have a name."""
    ids = G.resolve(id)
    if not ids:
        return {"error": f"no node matches {id!r}"}
    if ids[0] != id and len(ids) > 1:
        return {"ambiguous": True, "candidates": [G.brief(i) for i in ids[:20]]}
    nid = ids[0]
    return {"node": G.nodes[nid], **G.brief(nid)}


@mcp.tool()
def neighbors(id: str, direction: str = "both", rel_prefix: str = "",
              min_trust: float = 0.0, limit: int = 60) -> dict:
    """Adjacent nodes with full edge provenance. direction = out|in|both. rel_prefix filters
    relations (e.g. 'observes', 'produces', 'skos', 'may_counter', 'in_tactic', 'seeAlso',
    'curated_mitigation'). min_trust drops edges below a proxy-trust threshold (set e.g. 0.6
    to see only well-supported links; default shows everything, weak links flagged)."""
    ids = G.resolve(id)
    if not ids:
        return {"error": f"no node matches {id!r}"}
    if ids[0] != id and len(ids) > 1:
        return {"ambiguous": True, "candidates": [G.brief(i) for i in ids[:20]]}
    nid = ids[0]
    out = []
    for e in G.adj[nid]:
        if direction != "both" and e["dir"] != direction:
            continue
        if rel_prefix and not e["rel"].startswith(rel_prefix):
            continue
        if _trust(e["proxy_quality"]) < min_trust:
            continue
        out.append(_edge_view(e))
    out.sort(key=lambda v: (-v["trust"], v["rel"]))
    return {"node": G.brief(nid), "neighbor_count": len(out),
            "neighbors": out[:limit],
            "weak_links_present": any(v["weak"] for v in out)}


@mcp.tool()
def paths(src: str, dst: str, max_hops: int = 5, min_trust: float = 0.0,
          limit: int = 8) -> dict:
    """Find concept chains between two nodes (e.g. an OCSF class and an 800-53 control), the
    core grounded-reasoning primitive. Traverses edges in either direction but records each
    hop's real orientation, relation, and proxy_quality. For every path it returns
    path_trust = the MINIMUM edge trust (weakest link) and names the weakest hop, so you can
    see whether the connection rests on a measured mapping or an intent-blind inference.
    min_trust prunes edges below a threshold during search (find only well-supported chains).
    Paths are ranked by trust, then length."""
    si = G.resolve(src)
    di = G.resolve(dst)
    if not si:
        return {"error": f"no node matches src {src!r}"}
    if not di:
        return {"error": f"no node matches dst {dst!r}"}
    if si[0] != src and len(si) > 1:
        return {"ambiguous_src": [G.brief(i) for i in si[:20]]}
    if di[0] != dst and len(di) > 1:
        return {"ambiguous_dst": [G.brief(i) for i in di[:20]]}
    start, goal = si[0], di[0]
    max_hops = max(1, min(int(max_hops), 6))
    found: list[dict] = []
    budget = [250_000]  # expansion guard against hub explosion

    def dfs(cur: str, on_path: list[str], hops: list[dict]) -> None:
        if len(found) >= limit or budget[0] <= 0:
            return
        if cur == goal and hops:
            tr = min(h["trust"] for h in hops)
            weakest = min(hops, key=lambda h: h["trust"])
            found.append({
                "hops": hops,
                "length": len(hops),
                "path_trust": round(tr, 3),
                "weakest_hop": {"from": weakest["from"], "to": weakest["to"],
                                "rel": weakest["rel"], "proxy_quality": weakest["proxy_quality"],
                                "how": weakest["how"]},
                "crosses_inference": any(h["weak"] for h in hops),
                "node_chain": on_path,
            })
            return
        if len(hops) >= max_hops:
            return
        for e in G.adj[cur]:
            budget[0] -= 1
            if budget[0] <= 0:
                return
            nxt = e["to"]
            if nxt in on_path:
                continue
            t = _trust(e["proxy_quality"])
            if t < min_trust:
                continue
            hop = {"from": cur, "from_label": G.lbl(cur),
                   "to": nxt, "to_label": G.lbl(nxt),
                   "to_ntype": G.nodes.get(nxt, {}).get("ntype"),
                   "rel": e["rel"], "dir": e["dir"], "proxy_quality": e["proxy_quality"],
                   "trust": t, "how": PROXY_NOTE.get(e["proxy_quality"], "unknown"),
                   "weak": t <= 0.25}
            dfs(nxt, on_path + [nxt], hops + [hop])

    dfs(start, [start], [])
    found.sort(key=lambda p: (-p["path_trust"], p["length"]))
    return {
        "src": G.brief(start), "dst": G.brief(goal),
        "path_count": len(found), "paths": found[:limit],
        "note": ("path_trust is the weakest edge in the chain; crosses_inference=true means "
                 "the chain relies on an intent-blind artifact_cooccurrence edge -- treat as "
                 "a lead, not an established fact."),
        "truncated": budget[0] <= 0,
    }


@mcp.tool()
def coverage(attack: str, min_trust: float = 0.0, limit: int = 40) -> dict:
    """For an ATT&CK technique, what counters/addresses it and how soundly. Returns the
    D3FEND defenses that may_counter it (mostly intent-blind artifact_cooccurrence -- flagged),
    the curated ATT&CK mitigations (hand-authored), and its tactic. Each entry carries its
    proxy_quality + trust so you can separate measured/curated coverage from inferred coverage.
    Pass min_trust=0.6 to see only well-supported coverage."""
    ids = G.resolve(attack)
    ids = [i for i in ids if G.nodes.get(i, {}).get("ntype") == "attack"] or ids
    if not ids:
        return {"error": f"no ATT&CK node matches {attack!r}"}
    if ids[0] != attack and len(ids) > 1:
        return {"ambiguous": [G.brief(i) for i in ids[:20] if G.nodes.get(i, {}).get("ntype") == "attack"][:20]}
    nid = ids[0]
    defenses, mitigations, tactics = [], [], []
    for e in G.adj[nid]:
        if _trust(e["proxy_quality"]) < min_trust:
            continue
        v = _edge_view(e)
        nt = G.nodes.get(e["to"], {}).get("ntype")
        if e["rel"] == "may_counter" or nt == "defense":
            defenses.append(v)
        elif nt == "attack_mitigation" or e["rel"] == "curated_mitigation":
            mitigations.append(v)
        elif nt == "attack_tactic" or e["rel"] == "in_tactic":
            tactics.append(v)
    defenses.sort(key=lambda v: -v["trust"])
    return {
        "technique": G.brief(nid),
        "tactics": tactics,
        "defenses_may_counter": {"count": len(defenses), "items": defenses[:limit],
                                 "caveat": "most are artifact_cooccurrence (intent-blind, "
                                           "counters!=detects) -- inferred coverage, not proof"},
        "curated_mitigations": {"count": len(mitigations), "items": mitigations[:limit]},
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
