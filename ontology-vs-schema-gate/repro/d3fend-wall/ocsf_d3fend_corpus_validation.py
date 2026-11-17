#!/usr/bin/env python3
"""
P1-P3 of the corpus-validation plan: run the deductive OCSF->D3FEND gate against the
REAL six-schema crosswalk corpus (ocsf-crosswalk-field-matrix.md) and measure
real-catch vs false-positive.

Design (see ocsf-d3fend-validation-corpus-plan.md): each real mapping gets two
independent groundings -- the OCSF path it maps to (-> target D3FEND artifact) and the
source field's own semantic type (-> source D3FEND artifact). Correct mappings are
type-preserving (groundings agree -> satisfiable); type-crossing mappings disagree under
disjointness -> unsatisfiable -> caught. ELK via ROBOT, one batched reason pass.

Modes:
  selfcheck : reason the grounding+disjointness layer alone -> must be consistent (0 unsat).
              Proves the disjointness layer doesn't make any GROUNDED artifact unsatisfiable
              (the NetworkSession<=Session trap etc.).
  corpus    : false-positive run -- reason over every real mapping, report spurious unsat.
  inject    : real-catch run -- corrupt each correct mapping to a disjoint OCSF object and
              measure how many the gate catches.
Run: python3 ocsf_d3fend_corpus_validation.py [selfcheck|corpus|inject|all]
"""
import subprocess, os, re, json, tempfile, sys
from collections import defaultdict

ROBOT = "/tmp/robot.jar"
D3F = "http://d3fend.mitre.org/ontologies/d3fend.owl#"
OCSF = "https://schema.ocsf.io/align#"
HERE = os.path.dirname(os.path.abspath(__file__))
MATRIX = os.path.join(HERE, "..", "external-engagements", "ocsf-crosswalk-field-matrix.md")
SCHEMAS = ["Splunk CIM", "Google UDM", "Microsoft ASIM", "Elastic ECS", "OpenTelemetry", "Zeek"]

# ---- P1: the grounding map (OCSF path-segment -> D3FEND artifact) -------------------
# resolve a dot-path by its DEEPEST entity-bearing segment (actor.process.file -> File).
SEG_ARTIFACT = {
    "user": "UserAccount", "group": "UserGroup", "owner": "UserAccount",  # owner = a user
    "process": "Process", "file": "File",
    "src_endpoint": "NetworkNode", "dst_endpoint": "NetworkNode",
    "endpoint": "NetworkNode", "device": "NetworkNode",
    "connection_info": "NetworkSession",
    "session": "Session",
    "url": "URL",
    "service": "ServiceApplication", "app_name": "ServiceApplication",
}
WRAPPER_SEGS = {"actor", "evidences[]", "evidences", "observables[]", "observables"}

# ---- P1: the disjointness layer + the ADJUDICATION (the judgment that sets the FP rate)
# pairwise-disjoint at the ENTITY/IDENTITY level (an individual that IS one is not the
# other; "stored-in"/"executed-from"/"locates" are relations, not identity overlaps).
# Session is DELIBERATELY EXCLUDED: NetworkSession <= Session, so disjoint(Session,
# NetworkSession) would make NetworkSession unsatisfiable. UserGroup kept (a group is not
# an account). See disjointness-adjudication.md for the per-pair rationale + caveats.
DISJOINT_SET = ["UserAccount", "UserGroup", "Process", "File",
                "NetworkNode", "NetworkSession", "URL", "ServiceApplication"]
ALL_GROUNDING_ARTIFACTS = sorted(set(SEG_ARTIFACT.values()))   # incl. Session (grounded, not disjoint)

# ---- P2: the source-field typer (independent semantic type, confidence-gated) -------
# v2: type by the DEEPEST semantic token, mirroring ground_path -- the FP analysis (v1)
# showed typing by the leading/container token mis-types `process.owner` (a user) and
# `process.executable` (a file). So we score each dotted segment and let the deepest
# entity-bearing one win. Per-segment rules (specific tokens):
SEG_RULES = [
    ("File",        r"^(executable|image|file|filename|filepath|filehash|md5|sha\d+|dll|binary|exe)$"),
    ("UserAccount", r"^(user|username|userid|owner|principal|account|sam|upn|real_user|effective_user|target_user|src_user)$"),
    ("UserGroup",   r"^(group|groupname|usergroup)$"),
    ("Process",     r"^(process|cmdline|commandline|command_line|pid|proc|parent)$"),
    ("URL",         r"^(url|uri|referer|referrer)$"),
    ("ServiceApplication", r"^(application|service|appname|app)$"),
    ("NetworkSession", r"^(connection|conn|session|sessionid|flow|socket|netflow|communityid|community_id)$"),
    # NOTE: `port` deliberately NOT NetworkSession -- OCSF models port ON the endpoint
    # object (src_endpoint.port), so a port field is endpoint-grained here. v1 typed it
    # NetworkSession and produced 8 grain-mismatch FPs. Align to OCSF's own modeling:
    ("NetworkNode", r"^(ip|ipv4|ipv6|host|hostname|src|dst|dest|destination|source|address|addr|endpoint|device|machine|node|port)$"),
]

def source_type(field):
    """Return (artifact, confident): type the deepest dotted segment by SEG_RULES."""
    f = re.sub(r"[`*~]", "", field).strip().lower()
    if not f or f in ("—", "-", "const"):
        return None, False
    segs = re.split(r"[._ ]", f)
    art = None
    for s in segs:                              # deepest matching segment wins
        for a, pat in SEG_RULES:
            if re.match(pat, s):
                art = a; break
    return (art, True) if art else (None, False)

def ground_path(ocsf_path):
    """Resolve an OCSF dot-path to its D3FEND artifact via the deepest entity segment."""
    segs = [s.replace("[]", "") for s in ocsf_path.split(".")]
    art = None
    for s in segs:                                # deepest entity wins
        key = s
        if key in SEG_ARTIFACT:
            art = SEG_ARTIFACT[key]
        elif (s + "_endpoint") in SEG_ARTIFACT:
            art = SEG_ARTIFACT[s + "_endpoint"]
    return art

# ---- parse the field-matrix into (schema, source_field, ocsf_path) rows ------------
def parse_matrix():
    rows = []
    cols = None
    for line in open(MATRIX):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0].lower().startswith("ocsf attribute"):
            cols = cells; continue
        if not cols or len(cells) < 7 or set("".join(cells)) <= set("- "):
            continue
        m = re.match(r"`([^`]+)`", cells[0])
        if not m:
            continue
        ocsf_path = m.group(1)
        for i, schema in enumerate(SCHEMAS, start=1):
            cell = cells[i] if i < len(cells) else "—"
            # a cell may list several source fields; take each backticked token
            for sf in re.findall(r"`([^`]+)`", cell):
                rows.append({"schema": schema, "source": sf, "ocsf": ocsf_path,
                             "lossy": "~" in cell})
    return rows

# ---- TTL emit + ELK reason ---------------------------------------------------------
PREFIX = (f"@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
          f"@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
          f"@prefix d3f: <{D3F}> .\n@prefix ocsf: <{OCSF}> .\n"
          f"<{OCSF.rstrip('#')}> a owl:Ontology .\n"
          + "".join(f"d3f:{a} a owl:Class .\n" for a in
                    sorted(set(ALL_GROUNDING_ARTIFACTS) | set(DISJOINT_SET) | {"Session"}))
          # the one real subclass fact that matters for the trap: NetworkSession <= Session
          + "d3f:NetworkSession rdfs:subClassOf d3f:Session .\n")

def disjoint_ttl():
    members = " ".join(f"d3f:{c}" for c in DISJOINT_SET)
    return f"[] a owl:AllDisjointClasses ; owl:members ( {members} ) .\n"

def reason(ttl):
    with tempfile.TemporaryDirectory() as td:
        inp, dump, out = (os.path.join(td, x) for x in ("in.ttl", "u.owl", "o.owl"))
        open(inp, "w").write(ttl)
        p = subprocess.run(["java", "-jar", ROBOT, "reason", "--reasoner", "ELK",
                            "--input", inp, "--dump-unsatisfiable", dump, "--output", out],
                           capture_output=True, text=True, timeout=300)
        unsat = sorted(set(re.findall(r"align#([A-Za-z0-9_]+)", open(dump).read()))) if os.path.exists(dump) else []
        return p.returncode, unsat

def cls(schema, source):
    return "M_" + re.sub(r"[^A-Za-z0-9]", "_", f"{schema}__{source}")

# ---- the runs ----------------------------------------------------------------------
def selfcheck():
    ttl = PREFIX + disjoint_ttl()
    for art in ALL_GROUNDING_ARTIFACTS:
        ttl += f"ocsf:probe_{art} a owl:Class ; rdfs:subClassOf d3f:{art} .\n"
    rc, unsat = reason(ttl)
    print(f"[selfcheck] grounding+disjointness consistent? unsat={unsat or '[]'}  (expect [])")
    return not unsat

def corpus():
    rows = parse_matrix()
    typed = ground = both = 0
    ttl = PREFIX + disjoint_ttl(); classes = {}
    for r in rows:
        tart = ground_path(r["ocsf"]); r["target_art"] = tart
        sart, conf = source_type(r["source"]); r["source_art"] = sart; r["conf"] = conf
        if tart: ground += 1
        if conf: typed += 1
        if tart and conf:
            both += 1
            c = cls(r["schema"], r["source"]);
            if c not in classes:
                classes[c] = (sart, tart, r)
    for c, (sart, tart, r) in classes.items():
        ttl += f"ocsf:{c} a owl:Class ; rdfs:subClassOf d3f:{tart} ; rdfs:subClassOf d3f:{sart} .\n"
    rc, unsat = reason(ttl)
    fp = [(c, classes[c]) for c in unsat if c in classes]
    print(f"\n=== CORPUS (false-positive run) ===")
    print(f"rows parsed: {len(rows)} | with target grounding: {ground} | with confident source-type: {typed} | testable (both): {both}")
    print(f"distinct testable mapping-classes: {len(classes)}")
    print(f"gate fired on (would-fail-build): {len(unsat)}  -> these are FALSE POSITIVES if the mapping is actually correct")
    for c in unsat:
        if c in classes:
            sart, tart, r = classes[c]
            print(f"  FP? {r['schema']:14} {r['source'][:28]:30} -> {r['ocsf'][:26]:28} src={sart} vs target={tart}")
    json.dump({"rows": len(rows), "testable": both, "fired": unsat,
               "fired_detail": [{"schema": classes[c][2]['schema'], "source": classes[c][2]['source'],
                                 "ocsf": classes[c][2]['ocsf'], "src_art": classes[c][0],
                                 "target_art": classes[c][1]} for c in unsat if c in classes]},
              open(os.path.join(HERE, "corpus_validation_fp.json"), "w"), indent=1)
    return classes

def inject(classes):
    """Real-catch: corrupt each testable correct mapping to a DISJOINT target artifact."""
    # pick, per mapping, a target artifact disjoint from its source type, and remap.
    ttl = PREFIX + disjoint_ttl(); n = 0; corrupted = {}
    for c, (sart, tart, r) in classes.items():
        if sart not in DISJOINT_SET:
            continue
        wrong = next((a for a in DISJOINT_SET if a != sart), None)   # a disjoint artifact
        cc = "BAD_" + c
        ttl += f"ocsf:{cc} a owl:Class ; rdfs:subClassOf d3f:{wrong} ; rdfs:subClassOf d3f:{sart} .\n"
        corrupted[cc] = (sart, wrong, r); n += 1
    rc, unsat = reason(ttl)
    caught = [c for c in unsat if c in corrupted]
    print(f"\n=== INJECT (real-catch run) ===")
    print(f"injected type-crossing corruptions: {n}")
    print(f"caught by the gate (unsatisfiable): {len(caught)}  ({round(100*len(caught)/max(1,n),1)}%)")
    json.dump({"injected": n, "caught": len(caught)},
              open(os.path.join(HERE, "corpus_validation_catch.json"), "w"), indent=1)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    ok = selfcheck()
    if not ok:
        print("STOP: selfcheck failed — the disjointness layer makes a grounded artifact "
              "unsatisfiable. Fix the adjudication before measuring.")
        sys.exit(1)
    if mode in ("corpus", "inject", "all"):
        cs = corpus()
        if mode in ("inject", "all"):
            inject(cs)
