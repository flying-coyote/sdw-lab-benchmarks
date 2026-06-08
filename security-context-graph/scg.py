#!/usr/bin/env python3
"""Security Context Graph — concept-only backing graph (Phase A-minimal).

A concept/entity graph (NO telemetry-event nodes) that merges the scattered
OCSF <-> D3FEND <-> ATT&CK <-> NIST 800-53 / CCI / SCF crosswalks into ONE queryable
structure whose differentiator is honesty about its own joints: every edge is tagged
`{rel, source_file, tier, proxy_quality, proxy_note}` so a consumer can see how cheap
each join's proxy is rather than treating a documentation hyperlink and a measured field
map as the same kind of fact.

This is the evidence behind the controls-layer essay
(securitydataworks.com/writing/ocsf/controls-layer-crosswalk), not an owned product. It
backs the essay + the Sankey; the per-vendor scoring stays in the paid Capability Matrix.

Design constraints (from the reshaped program plan):
  * concept-only, NO event nodes -> a few thousand nodes, not the 234k that stalled BENCH-C.
  * new per-hop loaders; only graph_fingerprint ports from run_graphrag.py (extended here
    to fold tier + proxy_quality into the edge hash).
  * no embeddings -- the map render needs structure, not vectors.
  * SCF layer (CC-BY-ND) loads ONLY behind --with-scf from a local, un-redistributed file;
    the public spine (OCSF/D3FEND/ATT&CK/NIST-800-53) carries no ND content.

proxy_quality taxonomy (the tag that is the whole point):
  measured            field-level crosswalk, read from a mapping table          (hop 1)
  doc_link            OCSF<->D3FEND reciprocal hyperlinks, not axioms           (hop 2)
  ontology_curated    D3FEND technique observes artifact (hand-tagged)          (hop 3)
  artifact_cooccurrence  offense<->defense inferred from a SHARED artifact;
                         intent-blind (D3FEND #520), counters=0/detects=1       (hop 4)
  curated             D3FEND's hand-authored ATT&CK-mitigation edges            (hop 4')
  skos_typed          D3FEND -> 800-53/CCI, SKOS broader/narrower/exactly/related (hop 5)
  ctid_reroute        SCF -> ATT&CK is CTID's 800-53->ATT&CK re-routed via SCF's
                      own 800-53 crosswalk (uniform Intersects-With/strength-3) (hop 5')
  scf_strm            SCF control -> external framework (NIST IR 8477 STRM)     (hop 5')
  derived             rollups computed across hops (e.g. defense->control via ATT&CK)

Run:
  python3 scg.py                 # public spine only
  python3 scg.py --with-scf      # + the ND-gated SCF layer (local file)
Outputs land in results/: nodes.json, edges.json, fingerprint.txt, reconcile.json.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import os
import sys
from pathlib import Path

# --------------------------------------------------------------------------- source paths
# Defaults point at the local project1 working copies. The ontology + wall are public and
# can be vendored into ./sources/ for a self-contained public run; the SCF file is NOT
# (CC-BY-ND) and is loaded only with --with-scf. Override any path with an env var.
P1 = Path(os.environ.get("SCG_PROJECT1", str(Path.home() / "project1" / "02-projects")))
SRC = {
    "ontology": Path(os.environ.get("SCG_ONTOLOGY", P1 / "d3fend-wall" / "cache" / "d3fend_ontology.json")),
    "edges": Path(os.environ.get("SCG_WALL_EDGES", P1 / "d3fend-wall" / "data" / "edges.csv")),
    "matrix_long": Path(os.environ.get("SCG_WALL_MATRIX", P1 / "d3fend-wall" / "data" / "matrix_long.csv")),
    "wall_columns": Path(os.environ.get("SCG_WALL_COLUMNS", P1 / "d3fend-wall" / "data" / "wall_columns.csv")),
    "table_b": Path(os.environ.get("SCG_TABLE_B", P1 / "d3fend-wall" / "data" / "table_b_off_artifacts.csv")),
    "cim_bridge": Path(os.environ.get("SCG_CIM_BRIDGE", P1 / "d3fend-wall" / "c1-fieldmapping" / "cim_ocsf_bridge.json")),
    "scf_sankey": Path(os.environ.get("SCG_SCF_SANKEY", P1 / "scf-mapping" / "data" / "scf_sankey.json")),
}

# Published reconciliation targets (the numbers the essay/crosswalks cite). The build
# asserts the spine ones hard; SCF/reach ones assert only under --with-scf.
EXPECT = {
    "skos_edges": 606, "skos_controls": 402, "skos_controls_800-53": 111,
    "skos_controls_cci": 291, "skos_def_techniques": 79,
    # ocsf_distinct_classes: the build CORRECTS the stale "25" carried in robustness-map.md and
    # the controls-layer essay. The v1.4.0 ontology's 28 event-class seeAlso links resolve to 27
    # distinct OCSF classes (only module_activity is a shared target: Load+Unload library events).
    # The earlier 25 came from an older extraction with different entity->class names.
    "ocsf_seealso_pairs": 69, "ocsf_event_class_links": 28, "ocsf_distinct_classes": 27,
    "scf_controls_attack": 108, "scf_attack_ids": 511,
    "wall_defenses": 120, "wall_defenses_reaching_scf": 118,
    "scf_controls_reached": 104, "wall_attack_gaps": 33,
}

EVENT_NTYPES = {  # forbidden in a concept graph -- the 234k-node stall came from these
    "auth_event", "session", "net_event", "dns_event", "process_event", "api_event", "event",
}

# --------------------------------------------------------------------------- ontology helpers
SKOS_PREDS = ("d3f:broader", "d3f:narrower", "d3f:exactly", "d3f:related")


def is_control(nid):
    s = str(nid)
    if "NIST_SP_800-53" in s or "800-53" in s:
        return "800-53"
    if "CCI-" in s or s.startswith("d3f:CCI"):
        return "CCI"
    return None


def classify_d3f(node):
    t = node.get("@type", [])
    types = t if isinstance(t, list) else [t]
    ts = " ".join(str(x) for x in types)
    if "ATTACKEnterpriseMitigation" in ts:
        return "attack_mitigation"
    if "ATTACKEnterpriseDataSource" in ts:
        return "attack_datasource"
    if "owl:Class" in ts:
        return "defensive_technique"
    return "other"


def _label(node):
    l = node.get("rdfs:label")
    if isinstance(l, dict):
        return str(l.get("@value", ""))
    if isinstance(l, list) and l:
        return _label({"rdfs:label": l[0]})
    return l or ""


def _refs(val):
    """Normalize an ontology value into a list of @id / literal strings."""
    out = []
    for v in (val if isinstance(val, list) else [val]):
        if isinstance(v, dict):
            if "@id" in v:
                out.append(v["@id"])
        elif v is not None:
            out.append(v)
    return out


class Ontology:
    def __init__(self, path):
        self.graph = json.load(open(path))["@graph"]
        self.byid = {n.get("@id"): n for n in self.graph if isinstance(n, dict)}
        self.label2id = {}
        self.d3fendid2id = {}
        self.attackid2ids = collections.defaultdict(set)
        for n in self.graph:
            if not isinstance(n, dict):
                continue
            nid = n.get("@id")
            lab = _label(n).strip().lower()
            if lab and lab not in self.label2id:
                self.label2id[lab] = nid
            for d in _refs(n.get("d3f:d3fend-id")):
                self.d3fendid2id[d] = nid
            for a in _refs(n.get("d3f:attack-id")):
                self.attackid2ids[a].add(nid)
        self._artifact_leaves = None

    def subclass_descendants(self, root):
        kids = collections.defaultdict(set)
        for n in self.graph:
            if not isinstance(n, dict):
                continue
            cid = n.get("@id")
            for p in _refs(n.get("rdfs:subClassOf")):
                kids[p].add(cid)
        seen, stack = set(), [root]
        while stack:
            cur = stack.pop()
            for c in kids[cur]:
                if c not in seen:
                    seen.add(c)
                    stack.append(c)
        return seen, kids

    def digital_artifact_leaves(self):
        if self._artifact_leaves is None:
            desc, kids = self.subclass_descendants("d3f:DigitalArtifact")
            leaves = {c for c in desc if not (kids[c] & desc)}
            self._artifact_leaves = (desc, leaves)
        return self._artifact_leaves


# --------------------------------------------------------------------------- graph scaffold
class SCG:
    """Self-contained concept graph: a node dict (id -> attrs) and an edge list. No external
    graph library, so the build is reproducible from a stock Python."""

    def __init__(self):
        self.nodes = {}   # id -> {ntype, label, **attrs}
        self.edges = []   # list of {src, dst, rel, tier, proxy_quality, source_file, proxy_note}

    def node(self, nid, ntype, label="", **attrs):
        if nid not in self.nodes:           # first write wins (like add_node-if-absent)
            self.nodes[nid] = {"ntype": ntype, "label": label, **attrs}
        return nid

    def edge(self, src, dst, rel, tier, proxy_quality, source_file, proxy_note=""):
        self.edges.append({"src": src, "dst": dst, "rel": rel, "tier": tier,
                           "proxy_quality": proxy_quality, "source_file": source_file,
                           "proxy_note": proxy_note})


# --------------------------------------------------------------------------- loaders (per hop)
def hop1_fields(scg, recon):
    """Hop 1: source field -> OCSF field -> OCSF class. measured, Tier A. Loaded from the one
    structured crosswalk on disk (the PAN-OS firewall CIM->OCSF network_activity bridge) as a
    worked sample of the field layer; the other five schemas live as markdown tables
    (ocsf-crosswalk-field-matrix.md) and are a documented extension at class grain. The
    null-OCSF fields are kept as honest `unmapped` edges -- the silent-failure surface."""
    p = SRC["cim_bridge"]
    if not p.exists():
        recon["hop1_cim_fields"] = 0
        return
    data = json.load(open(p))
    bridge = data.get("bridge", {})
    cls = (data.get("_target_class", "") or "unknown").split("(")[0].strip() or "unknown"
    src_file = "d3fend-wall/c1-fieldmapping/cim_ocsf_bridge.json"
    cnode = scg.node(f"ocsf:class/{cls}", "ocsf_class", cls)
    n_mapped = n_unmapped = 0
    for cim_field, spec in bridge.items():
        if not isinstance(spec, dict):
            continue
        ocsf_path = spec.get("ocsf")
        note = f"basis={spec.get('basis', '')}; {spec.get('note', '')}"[:240]
        s = scg.node(f"src:cim/{cim_field}", "source_field", cim_field, schema="splunk_cim")
        if ocsf_path:
            f = scg.node(f"ocsf:field/{cls}.{ocsf_path}", "ocsf_field", ocsf_path)
            scg.edge(s, f, "normalizes", "A", "measured", src_file, note)
            scg.edge(f, cnode, "field_of", "A", "measured", src_file)
            n_mapped += 1
        else:
            scg.edge(s, cnode, "unmapped", "A", "measured", src_file, note)  # a CIM field with no OCSF home
            n_unmapped += 1
    recon["hop1_cim_fields"] = n_mapped
    recon["hop1_cim_unmapped"] = n_unmapped


def hop2_ocsf_d3fend(scg, ont, recon):
    """Hop 2: OCSF class/object <-> D3FEND entity, reciprocal seeAlso/references hyperlinks.
    doc_link, Tier A. Documentation-level, NOT equivalentClass axioms, NOT per-record fields."""
    src_file = "d3fend-wall/cache/d3fend_ontology.json (rdfs:seeAlso -> schema.ocsf.io)"
    pairs = 0
    event_class_links = 0
    distinct_classes = set()
    note = "reciprocal hyperlink, not an owl:equivalentClass axiom and not a per-record field"
    for n in ont.graph:
        if not isinstance(n, dict):
            continue
        nid = n.get("@id")
        for tgt in _refs(n.get("rdfs:seeAlso")):
            if "schema.ocsf.io" not in str(tgt):
                continue
            pairs += 1
            d = scg.node(nid, "d3fend_event", _label(n))
            kind = ("class" if "/classes/" in tgt else "object" if "/objects/" in tgt
                    else "category" if "/categories/" in tgt else "other")
            if kind == "class":
                event_class_links += 1
                cls = tgt.rstrip("/").split("/")[-1]
                distinct_classes.add(cls)
                o = scg.node(f"ocsf:class/{cls}", "ocsf_class", cls, ocsf_url=tgt)
            elif kind == "object":
                obj = tgt.rstrip("/").split("/")[-1]
                o = scg.node(f"ocsf:object/{obj}", "ocsf_object", obj, ocsf_url=tgt)
            else:
                o = scg.node(f"ocsf:other/{tgt}", "ocsf_other", tgt)
            scg.edge(o, d, "references", "A", "doc_link", src_file, note)
            scg.edge(d, o, "seeAlso", "A", "doc_link", src_file, note)
    # leaf-orphan: of the DigitalArtifact leaves, how many carry an OCSF seeAlso
    desc, leaves = ont.digital_artifact_leaves()
    leaf_with_ocsf = 0
    for lid in leaves:
        node = ont.byid.get(lid, {})
        if any("schema.ocsf.io" in str(t) for t in _refs(node.get("rdfs:seeAlso"))):
            leaf_with_ocsf += 1
    recon["ocsf_seealso_pairs"] = pairs
    recon["ocsf_event_class_links"] = event_class_links
    recon["ocsf_distinct_classes"] = len(distinct_classes)
    recon["digital_artifact_leaves"] = len(leaves)
    recon["leaves_with_ocsf_seealso"] = leaf_with_ocsf


def hop2b_event_artifact(scg, ont, recon):
    """Hop 2b: D3FEND event -> digital artifact, via the ontology's own event-class restrictions
    (e.g. FileEvent `has-participant` File, AuthenticationEvent `caused-by` Authentication).
    ontology_axiom, Tier A. This is the join that connects an OCSF-linked event to the artifact a
    defense observes -- it closes the schema->defense path end-to-end through real edges."""
    art_desc = ont.digital_artifact_leaves()[0]  # full DigitalArtifact descendant set
    src_file = "d3fend-wall/cache/d3fend_ontology.json (event subClassOf restriction)"
    note = "D3FEND event-class restriction linking the event-occurrent to its digital-artifact participant"
    n = 0
    event_ids = [nid for nid, a in scg.nodes.items() if a.get("ntype") == "d3fend_event"]
    for eid in event_ids:
        node = ont.byid.get(eid, {})
        for sc in _refs(node.get("rdfs:subClassOf")):
            r = ont.byid.get(sc, {})
            if r.get("@type") != "owl:Restriction":
                continue
            prop = (_refs(r.get("owl:onProperty")) or [""])[0].replace("d3f:", "").replace("-", "_")
            for tgt in _refs(r.get("owl:someValuesFrom")):
                if tgt in art_desc:
                    a = scg.node(tgt, "artifact", _label(ont.byid.get(tgt, {})))
                    scg.edge(eid, a, f"event_{prop or 'involves'}", "A", "ontology_axiom", src_file, note)
                    n += 1
    recon["hop2b_event_artifact_edges"] = n


def _resolve_defense(ont, scg, d3fend_id=None, label=None):
    nid = None
    if d3fend_id and d3fend_id in ont.d3fendid2id:
        nid = ont.d3fendid2id[d3fend_id]
    elif label and label.strip().lower() in ont.label2id:
        nid = ont.label2id[label.strip().lower()]
    if nid is None:
        nid = f"d3f:defense/{(d3fend_id or label or 'unknown')}"
    return scg.node(nid, "defense", label or "", d3fend_id=d3fend_id or "")


def _resolve_artifact(ont, scg, label):
    nid = ont.label2id.get(label.strip().lower(), f"d3f:artifact/{label.replace(' ', '')}")
    return scg.node(nid, "artifact", label)


def _attack(scg, tid, name=""):
    return scg.node(f"attack:{tid}", "attack", name or tid, base=tid.split(".")[0])


def hop34_artifacts(scg, ont, recon):
    """Hop 3 (artifact -> defense, technique observes artifact: ontology_curated, A) and
    hop 4 (artifact -> ATT&CK offense, attack produces artifact: artifact_cooccurrence, A),
    from the wall's artifact-mediated edge detail."""
    src_file = "d3fend-wall/data/edges.csv"
    note3 = "D3FEND ontology: defensive technique hand-tagged to the artifact it observes/touches"
    note4 = "inferred from a SHARED artifact; intent-blind (D3FEND #520), a POSSIBILITY of coverage not a guarantee"
    n_obs = n_prod = 0
    for r in csv.DictReader(open(SRC["edges"])):
        dfn = _resolve_defense(ont, scg, label=r["def_tech"])
        d_art = _resolve_artifact(ont, scg, r["def_artifact"])
        scg.edge(dfn, d_art, f"observes:{r['def_artifact_rel']}", "A", "ontology_curated", src_file, note3)
        n_obs += 1
        atk = _attack(scg, r["off_tech_id"], r["off_tech"])
        o_art = _resolve_artifact(ont, scg, r["off_artifact"])
        scg.edge(atk, o_art, f"produces:{r['off_artifact_rel']}", "A", "artifact_cooccurrence", src_file, note4)
        n_prod += 1
        if r.get("off_tactic"):
            tac = scg.node(f"attack:tactic/{r['off_tactic']}", "attack_tactic", r["off_tactic"])
            scg.edge(atk, tac, "in_tactic", "A", "curated", src_file)
    recon["hop3_observes_edges"] = n_obs
    recon["hop4_produces_edges"] = n_prod


def hop4_inferred_matrix(scg, ont, recon):
    """Hop 4' rolled-up: defense -[may_counter]-> ATT&CK, the inferred offense-defense edge
    materialized over the SHARED artifact (subclass-walked). artifact_cooccurrence; Tier A
    for the reproduction of D3FEND's own join, Tier B for any coverage interpretation."""
    src_file = "d3fend-wall/data/matrix_long.csv"
    note = ("reproduces D3FEND's own artifact-overlap inference (subclass-walked); coverage != detection: "
            "an inferred edge means a defense COULD observe the artifact, not that it counters the attack in a deployment")
    n = 0
    defenses = set()
    def2attacks = collections.defaultdict(set)
    for r in csv.DictReader(open(SRC["matrix_long"])):
        d3id = r["d3fend_id"]
        dfn = _resolve_defense(ont, scg, d3fend_id=d3id)
        atk = _attack(scg, r["off_tech_id"], r.get("off_tech", ""))
        scg.edge(dfn, atk, "may_counter", "A", "artifact_cooccurrence", src_file, note)
        defenses.add(d3id)
        def2attacks[d3id].add(r["off_tech_id"])
        n += 1
    recon["hop4_inferred_edges"] = n
    recon["wall_defenses"] = len(defenses)
    return def2attacks


def hop4prime_curated(scg, ont, recon):
    """Hop 4' curated: D3FEND <-> ATT&CK-mitigation (M####), the hand-authored mapping
    (excluded from the SKOS control count, included here as the curated offense leg). Tier A."""
    src_file = "d3fend-wall/cache/d3fend_ontology.json (ATTACKEnterpriseMitigation d3f:related)"
    n = 0
    for node in ont.graph:
        if classify_d3f(node) != "attack_mitigation":
            continue
        mid = node.get("@id")
        m = scg.node(mid, "attack_mitigation", _label(node))
        for pred in SKOS_PREDS:
            for tgt in _refs(node.get(pred)):
                if is_control(tgt):
                    continue
                tnode = ont.byid.get(tgt, {})
                if classify_d3f(tnode) == "defensive_technique":
                    dfn = scg.node(tgt, "defense", _label(tnode))
                    scg.edge(dfn, m, "curated_mitigation", "A", "curated", src_file,
                             "D3FEND's hand-authored ATT&CK-mitigation relation")
                    n += 1
    recon["hop4prime_curated_edges"] = n


def hop5_skos(scg, ont, recon):
    """Hop 5: D3FEND defensive technique -> NIST 800-53 R5 / CCI control, SKOS-typed.
    skos_typed, Tier A. Reuses verify_skos_counts.py's exact definition so the graph matches
    the locked 606/402/79 BY CONSTRUCTION."""
    src_file = "d3fend-wall/cache/d3fend_ontology.json (SKOS, exactly-one-control-endpoint)"
    triples = set()
    for n in ont.graph:
        if not isinstance(n, dict):
            continue
        sid = n.get("@id")
        for pred in SKOS_PREDS:
            for oid in _refs(n.get(pred)):
                if sid and oid:
                    triples.add((sid, pred, oid))
    dt_edges, controls, c8053, ccci, techs = set(), set(), set(), set(), set()
    for sid, pred, oid in triples:
        cs, co = is_control(sid), is_control(oid)
        if bool(cs) == bool(co):
            continue
        if cs:
            ctl, kind, d3f = sid, cs, oid
        else:
            ctl, kind, d3f = oid, co, sid
        if classify_d3f(ont.byid.get(d3f, {})) != "defensive_technique":
            continue
        dt_edges.add((ctl, d3f, pred))
        controls.add(ctl)
        (c8053 if kind == "800-53" else ccci).add(ctl)
        techs.add(d3f)
        dfn = scg.node(d3f, "defense", _label(ont.byid.get(d3f, {})))
        cnode = scg.node(ctl, "control", _label(ont.byid.get(ctl, {})) or ctl,
                         control_kind=("nist_800-53" if kind == "800-53" else "cci"))
        scg.edge(dfn, cnode, pred.replace("d3f:", "skos_"), "A", "skos_typed", src_file)
    recon["skos_edges"] = len(dt_edges)
    recon["skos_controls"] = len(controls)
    recon["skos_controls_800-53"] = len(c8053)
    recon["skos_controls_cci"] = len(ccci)
    recon["skos_def_techniques"] = len(techs)


def hop5prime_scf(scg, ont, recon, def2attacks):
    """Hop 5' (ND-GATED): ATT&CK -> SCF control (ctid_reroute) + SCF control -> framework
    (scf_strm). Loaded only with --with-scf from the local, un-redistributed scf_sankey.json."""
    p = SRC["scf_sankey"]
    if not p.exists():
        recon["scf_loaded"] = False
        return
    d = json.load(open(p))
    src_file = "scf-mapping/data/scf_sankey.json (LOCAL, CC-BY-ND -- not redistributed)"
    fw_by_fid = {str(f["fid"]): f for f in d["frameworks"]}
    domains = d.get("domains", [])
    attack_note = ("SCF's ATT&CK layer is CTID's NIST 800-53->ATT&CK mapping re-routed through SCF's own "
                   "800-53 crosswalk (uniform Intersects-With/strength-3); SCF adds no independent ATT&CK signal")
    scf_attack_controls = 0
    scf_attack_ids = set()
    scf_attack_set = set()           # all ATT&CK ids any SCF control maps (exact)
    ctl_to_attacks = {}
    for c in d["controls"]:
        scf_code = c.get("scf") or f"cid{c['cid']}"
        did = c.get("did")
        cnode = scg.node(f"scf:{scf_code}", "scf_control", c.get("name", ""),
                         consensus=c.get("cons"), consensus_w=c.get("consw"),
                         domain=(domains[did] if isinstance(did, int) and did < len(domains) else None))
        mp = c.get("map") or {}
        # SCF control -> external framework (STRM); ND-gated derived edges
        for fid, codes in mp.items():
            if fid == "36":
                continue  # the ATT&CK leg handled below
            fw = fw_by_fid.get(fid)
            if not fw:
                continue
            fnode = scg.node(f"scf:framework/{fid}", "framework", fw.get("label", fid),
                             curated=fw.get("curated"))
            scg.edge(cnode, fnode, "maps_to", "A", "scf_strm", src_file,
                     "NIST IR 8477 Set Theory Relationship Mapping")
        # ATT&CK leg
        atks = mp.get("36")
        if atks:
            scf_attack_controls += 1
            ctl_to_attacks[scf_code] = set(atks)
            for tid in atks:
                scf_attack_ids.add(tid)
                scf_attack_set.add(tid)
                atk = _attack(scg, tid)
                scg.edge(atk, cnode, "mitigated_by", "A", "ctid_reroute", src_file, attack_note)
    recon["scf_loaded"] = True
    recon["scf_controls_attack"] = scf_attack_controls
    recon["scf_attack_ids"] = len(scf_attack_ids)

    # ---- derived reach (the essay's 118/120, 104, 33) ----
    def base(t):
        return t.split(".")[0]
    scf_exact = scf_attack_set
    scf_base = {base(t) for t in scf_attack_set}

    reached_def = 0
    for d3id, atks in def2attacks.items():
        if any((a in scf_exact) or (base(a) in scf_base) for a in atks):
            reached_def += 1
    # defenses with a derived governance edge: mark on the graph as well
    wall_attacks = set()
    for atks in def2attacks.values():
        wall_attacks |= atks
    wall_exact = wall_attacks
    wall_base = {base(t) for t in wall_attacks}
    controls_reached = 0
    for scf_code, atks in ctl_to_attacks.items():
        if any((a in wall_exact) or (base(a) in wall_base) for a in atks):
            controls_reached += 1
    gaps = sum(1 for a in wall_attacks
               if not ((a in scf_exact) or (base(a) in scf_base)))
    recon["wall_defenses_reaching_scf"] = reached_def
    recon["scf_controls_reached"] = controls_reached
    recon["wall_attack_gaps"] = gaps


# --------------------------------------------------------------------------- fingerprint
def graph_fingerprint(scg):
    """Ported from ocsf-semantic-query/run_graphrag.py and EXTENDED: the edge hash now folds
    in tier + proxy_quality, so a change in how honest a joint is changes the fingerprint."""
    nodes = sorted(f"{nid}|{a.get('ntype')}" for nid, a in scg.nodes.items())
    edges = sorted(
        f"{e['src']}|{e['dst']}|{e['rel']}|{e['tier']}|{e['proxy_quality']}"
        for e in scg.edges
    )
    h = hashlib.sha256()
    for x in nodes:
        h.update(x.encode())
    h.update(b"||EDGES||")
    for x in edges:
        h.update(x.encode())
    return h.hexdigest()


# --------------------------------------------------------------------------- reconcile
def reconcile(scg, recon, with_scf):
    node_types = collections.Counter(a["ntype"] for a in scg.nodes.values())
    recon["total_nodes"] = len(scg.nodes)
    recon["total_edges"] = len(scg.edges)
    recon["node_types"] = dict(node_types)
    recon["proxy_quality_dist"] = dict(collections.Counter(
        e.get("proxy_quality") for e in scg.edges))

    checks = []

    def chk(name, got, exp, hard=True):
        ok = got == exp
        checks.append({"check": name, "got": got, "expected": exp, "pass": ok, "hard": hard})
        return ok

    # invariants
    chk("node_count_under_10k", recon["total_nodes"] < 10000, True)
    event_nodes = sorted(t for t in node_types if t in EVENT_NTYPES)
    chk("no_event_nodes", event_nodes, [])

    # spine asserts (no SCF needed)
    chk("skos_edges", recon["skos_edges"], EXPECT["skos_edges"])
    chk("skos_controls", recon["skos_controls"], EXPECT["skos_controls"])
    chk("skos_controls_800-53", recon["skos_controls_800-53"], EXPECT["skos_controls_800-53"])
    chk("skos_controls_cci", recon["skos_controls_cci"], EXPECT["skos_controls_cci"])
    chk("skos_def_techniques", recon["skos_def_techniques"], EXPECT["skos_def_techniques"])
    chk("ocsf_seealso_pairs", recon["ocsf_seealso_pairs"], EXPECT["ocsf_seealso_pairs"])
    chk("ocsf_event_class_links", recon["ocsf_event_class_links"], EXPECT["ocsf_event_class_links"])
    chk("ocsf_distinct_classes", recon["ocsf_distinct_classes"], EXPECT["ocsf_distinct_classes"])
    chk("wall_defenses", recon["wall_defenses"], EXPECT["wall_defenses"])
    # leaf-orphan reproduced as a SOFT report (leaf definition is sensitive)
    chk("digital_artifact_leaves~607", recon.get("digital_artifact_leaves"), 607, hard=False)
    chk("leaves_with_ocsf_seealso~14", recon.get("leaves_with_ocsf_seealso"), 14, hard=False)

    if with_scf:
        chk("scf_controls_attack", recon["scf_controls_attack"], EXPECT["scf_controls_attack"])
        chk("scf_attack_ids", recon["scf_attack_ids"], EXPECT["scf_attack_ids"])
        chk("wall_defenses_reaching_scf", recon["wall_defenses_reaching_scf"], EXPECT["wall_defenses_reaching_scf"])
        chk("scf_controls_reached", recon["scf_controls_reached"], EXPECT["scf_controls_reached"])
        chk("wall_attack_gaps", recon["wall_attack_gaps"], EXPECT["wall_attack_gaps"])

    recon["checks"] = checks
    recon["hard_failures"] = [c for c in checks if c["hard"] and not c["pass"]]
    recon["soft_failures"] = [c for c in checks if not c["hard"] and not c["pass"]]
    return checks


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Build the concept-only Security Context Graph.")
    ap.add_argument("--with-scf", action="store_true",
                    help="load the ND-gated SCF layer from the local scf_sankey.json (CC-BY-ND)")
    ap.add_argument("--out", default=str(Path(__file__).parent / "results"))
    ap.add_argument("--strict", action="store_true", help="exit non-zero on any soft failure too")
    args = ap.parse_args()

    missing = [k for k in ("ontology", "edges", "matrix_long") if not SRC[k].exists()]
    if missing:
        sys.exit(f"missing required source(s): {[str(SRC[k]) for k in missing]}")

    print("loading ontology ...", file=sys.stderr)
    ont = Ontology(SRC["ontology"])
    scg = SCG()
    recon = {"with_scf": args.with_scf, "sources": {k: str(v) for k, v in SRC.items()}}

    hop1_fields(scg, recon)
    hop2_ocsf_d3fend(scg, ont, recon)
    hop2b_event_artifact(scg, ont, recon)
    hop34_artifacts(scg, ont, recon)
    def2attacks = hop4_inferred_matrix(scg, ont, recon)
    hop4prime_curated(scg, ont, recon)
    hop5_skos(scg, ont, recon)
    if args.with_scf:
        hop5prime_scf(scg, ont, recon, def2attacks)

    fp = graph_fingerprint(scg)
    recon["fingerprint"] = fp
    reconcile(scg, recon, args.with_scf)

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    nodes = [{"id": nid, **scg.nodes[nid]} for nid in sorted(scg.nodes)]
    edges = sorted(scg.edges, key=lambda e: (e["src"], e["dst"], e["rel"], e["proxy_quality"]))
    json.dump(nodes, open(outdir / "nodes.json", "w"), indent=2)
    json.dump(edges, open(outdir / "edges.json", "w"), indent=2)
    (outdir / "fingerprint.txt").write_text(fp + "\n")
    json.dump(recon, open(outdir / "reconcile.json", "w"), indent=2, sort_keys=True)

    # ---- report ----
    print(f"\nSecurity Context Graph  (with_scf={args.with_scf})")
    print(f"  nodes: {recon['total_nodes']}   edges: {recon['total_edges']}")
    print(f"  node types: {recon['node_types']}")
    print(f"  proxy_quality: {recon['proxy_quality_dist']}")
    print(f"  fingerprint: {fp[:16]}...")
    print("\n  reconciliation:")
    for c in recon["checks"]:
        mark = "OK " if c["pass"] else ("XX " if c["hard"] else "~~ ")
        print(f"    {mark}{c['check']}: got={c['got']} expected={c['expected']}")
    hard = recon["hard_failures"]
    soft = recon["soft_failures"]
    print(f"\n  {len(hard)} hard failure(s), {len(soft)} soft failure(s).")
    if hard:
        sys.exit(f"HARD reconciliation failure: {[c['check'] for c in hard]}")
    if soft and args.strict:
        sys.exit(f"soft reconciliation failure (strict): {[c['check'] for c in soft]}")
    print("  OK -- all hard asserts pass.")


if __name__ == "__main__":
    main()
