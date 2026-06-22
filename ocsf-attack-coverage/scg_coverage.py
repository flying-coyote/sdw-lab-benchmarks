"""A dependency-free port of security-context-graph/scg_mcp.coverage().

scg_mcp.coverage() is an @mcp.tool() and the MCP server needs `mcp`/`fastmcp`, which the
lab venv does not carry. The coverage logic itself is pure graph bucketing over the SAME
results/nodes.json + results/edges.json the MCP server loads, so this module factors that
bucketing into a plain function the C5 runner can call directly. The TRUST table, the
resolve() prefix logic, the _edge_view shape, and the defenses/curated_mitigations/tactics
bucketing are copied VERBATIM from scg_mcp.py (lines 42-72, 87-137, 154-160, 332-366) so a
lead returned here is identical to what the MCP tool would return -- the gap hop carries the
proxy_quality + trust + weak flags unchanged, and an intent-blind artifact_cooccurrence
edge (trust 0.25) is never laundered into a detection.

Read-only. It loads the prebuilt graph (python3 scg.py -> results/nodes.json + edges.json).
"""

import json
import os
from collections import defaultdict

SCG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "security-context-graph")
RESULTS = os.path.join(SCG_DIR, "results")

# Copied verbatim from scg_mcp.py:42-68.
TRUST = {
    "measured": 1.00, "skos_typed": 0.90, "ontology_axiom": 0.85, "doc_link": 0.80,
    "ontology_curated": 0.70, "curated": 0.65, "ctid_reroute": 0.50, "scf_strm": 0.45,
    "derived": 0.40, "artifact_cooccurrence": 0.25, "unmapped": 0.00,
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


def _trust(pq):
    return TRUST.get(pq, 0.30)


class _Graph:
    def __init__(self, results_dir):
        self.nodes = {}
        self.label_index = defaultdict(list)
        self.adj = defaultdict(list)
        nodes = json.load(open(os.path.join(results_dir, "nodes.json")))
        edges = json.load(open(os.path.join(results_dir, "edges.json")))
        for a in nodes:
            nid = a["id"]
            if nid not in self.nodes:
                self.nodes[nid] = a
                self.label_index[str(a.get("label", "")).lower()].append(nid)
        seen = set()
        for e in edges:
            key = (e["src"], e["dst"], e["rel"], e.get("proxy_quality"))
            if key in seen:
                continue
            seen.add(key)
            pq = e.get("proxy_quality", "")
            fwd = {"to": e["dst"], "rel": e["rel"], "tier": e.get("tier"),
                   "proxy_quality": pq, "dir": "out"}
            rev = {**fwd, "to": e["src"], "dir": "in"}
            self.adj[e["src"]].append(fwd)
            self.adj[e["dst"]].append(rev)

    def resolve(self, q):
        if q in self.nodes:
            return [q]
        for pfx in ("attack:", "d3f:", "ocsf:class/", "ocsf:object/", "ocsf:", "scf:"):
            if (pfx + q) in self.nodes:
                return [pfx + q]
        ql = q.lower()
        if ql in self.label_index:
            return list(self.label_index[ql])
        hits = [nid for lbl, ids in self.label_index.items() if ql in lbl for nid in ids]
        hits += [nid for nid in self.nodes if ql in nid.lower() and nid not in hits]
        return hits[:50]

    def lbl(self, nid):
        a = self.nodes.get(nid, {})
        return a.get("label") or nid.split("/")[-1].split(":")[-1]

    def brief(self, nid):
        a = self.nodes.get(nid, {})
        out = sum(1 for e in self.adj[nid] if e["dir"] == "out")
        return {"id": nid, "ntype": a.get("ntype"), "label": self.lbl(nid),
                "degree_out": out, "degree_in": len(self.adj[nid]) - out}


_G = None


def _graph():
    global _G
    if _G is None:
        _G = _Graph(RESULTS)
    return _G


def _edge_view(g, e):
    pq = e["proxy_quality"]
    return {"to": e["to"], "to_label": g.lbl(e["to"]),
            "to_ntype": g.nodes.get(e["to"], {}).get("ntype"),
            "rel": e["rel"], "dir": e["dir"], "tier": e["tier"],
            "proxy_quality": pq, "trust": _trust(pq), "how": PROXY_NOTE.get(pq, "unknown"),
            "weak": _trust(pq) <= 0.25}


def coverage(attack, min_trust=0.0, limit=40):
    """Verbatim port of scg_mcp.coverage (scg_mcp.py:332-366)."""
    g = _graph()
    ids = g.resolve(attack)
    ids = [i for i in ids if g.nodes.get(i, {}).get("ntype") == "attack"] or ids
    if not ids:
        return {"error": f"no ATT&CK node matches {attack!r}"}
    if ids[0] != attack and len(ids) > 1:
        return {"ambiguous": [g.brief(i) for i in ids[:20]
                              if g.nodes.get(i, {}).get("ntype") == "attack"][:20]}
    nid = ids[0]
    defenses, mitigations, tactics = [], [], []
    for e in g.adj[nid]:
        if _trust(e["proxy_quality"]) < min_trust:
            continue
        v = _edge_view(g, e)
        nt = g.nodes.get(e["to"], {}).get("ntype")
        if e["rel"] == "may_counter" or nt == "defense":
            defenses.append(v)
        elif nt == "attack_mitigation" or e["rel"] == "curated_mitigation":
            mitigations.append(v)
        elif nt == "attack_tactic" or e["rel"] == "in_tactic":
            tactics.append(v)
    defenses.sort(key=lambda v: -v["trust"])
    return {
        "technique": g.brief(nid),
        "tactics": tactics,
        "defenses_may_counter": {"count": len(defenses), "items": defenses[:limit],
                                 "caveat": "most are artifact_cooccurrence (intent-blind, "
                                           "counters!=detects) -- inferred coverage, not proof"},
        "curated_mitigations": {"count": len(mitigations), "items": mitigations[:limit]},
    }
