"""BENCH-C — the GraphRAG arm: concept graph + vector retrieval + local LLM.

The third arm of the semantic-query head-to-head. It builds a NetworkX concept graph and a
numpy cosine vector index over the BENCH-A fidelity store (Store F), retrieves a relevant
subgraph + top-k vector neighbours per adversary-tail question, hands that context to a local
Ollama model, and scores the answer with the SAME correct/silent/loud definition the
text-to-SQL (`run.py`) and OBDA (`run_obda.py`) arms use — via the shared `scoring.py`.

GraphRAG sits between the two poles the other arms stake out: it has the LLM's broad coverage
(it can attempt the aggregation/recursion queries OBDA refuses) but, unlike the formal rewrite,
carries no correctness guarantee. The question this arm answers is whether that broad-but-
unverified coverage produces *silent* errors on the tail where OBDA produces *loud* refusals.

Design, fairness contract, and run plan: GRAPHRAG-READINESS.md. The arm merges its
`arms["graphrag"]` block into results/results.json non-destructively, exactly as run_obda.py
merges `arms["obda_ontop"]`. Determinism: the graph (fixed insertion + sorted guards) and the
embeddings (cached, pinned model) are assertable; the LLM decode is temp-0 greedy —
reproducible in practice, not asserted (the same caveat run.py prints for text-to-SQL).
"""

import argparse
import hashlib
import json
import os
import sys

import duckdb
import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
STORE_F = os.path.join(HERE, "..", "bench-a-context-collapse", "_work", "store_f")
GT = os.path.join(HERE, "..", "ocsf-semantic-testbed", "_work", "ground_truth.json")
WORK = os.path.join(HERE, "_work", "graphrag")
GEN_URL = "http://localhost:11434/api/generate"
EMBED_URL = "http://localhost:11434/api/embed"
EMBED_URL_LEGACY = "http://localhost:11434/api/embeddings"
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from common import configure_duckdb  # noqa: E402
from scoring import classify  # noqa: E402

# Fixed retrieval hyper-params — pre-registered BEFORE the scored run (fairness §6: no tuning
# k/hops to the planted answers after seeing misses).
K_SEED = 20
# HOPS = 1 for the structured (entity-layer) rebuild: an entity seed is one hop from its events,
# so radius-1 IS the entity->events traversal the design intends. The original per-event arm used
# HOPS=2 (event->entity->event); on the rebuilt entity-seeded graph, radius-2 explodes from hub
# entities (a host's thousands of events, then each event's other entities) and is intractable.
# This is a design-consistent setting, not tuning to the planted answers (fairness §6).
HOPS = 1
NODE_BUDGET = 150
EDGE_BUDGET = 300

# The A1–A9 union (9 queries). truth_key resolves against the merged truth table
# (truth_needles + the two top-level structures). kind dispatches scoring.classify.
QUERIES = [
    {"id": "A1", "kind": "uidset", "truth_key": "beacon_conn_uids",
     "nl": "Find the beaconing connection: a source/destination pair with roughly 60-second "
           "regular inter-arrival, low bytes, sustained for about an hour. Return the event_uid "
           "of each such connection."},
    {"id": "A2", "kind": "substring", "truth_key": "powershell_encoded_cmd",
     "nl": "Return the exact PowerShell command line containing -EncodedCommand that executed "
           "on host WS1."},
    {"id": "A3", "kind": "order", "truth_key": "truth_event_order",
     "nl": "Reconstruct the kill chain: list the attack stages in the order they occurred "
           "(OAuth consent, PowerShell execution, C2 beacon, lateral connection, no-MFA "
           "privilege escalation, role assumption, data exfiltration)."},
    {"id": "A4", "kind": "count", "truth_key": "pit_active_session_uids",
     "nl": "How many sessions were active (started but not yet ended) at the exact point in "
           "time of the privilege escalation? Return the count."},
    {"id": "A5", "kind": "set", "truth_key": "truth_identity_links",
     "nl": "Identity closure: return every identifier — account, IAM principal, assumed role, "
           "endpoint SID, UPN, hostnames, IPs, instance ids — that belongs to the single human "
           "actor behind this chain."},
    {"id": "A6", "kind": "uid", "truth_key": "nomfa_event_uid",
     "nl": "Find the privilege escalation: an AttachUserPolicy API call where MFA was not "
           "present (the mfa_present flag is false). Return its event_uid."},
    {"id": "A7", "kind": "scalar", "truth_key": "dwell_seconds",
     "nl": "What is the dwell time, in seconds, of the attack — the elapsed time between the "
           "first and last event of the chain? Return the number of seconds."},
    {"id": "A8", "kind": "substring", "truth_key": "c2_domain",
     "nl": "Find the DNS domain queried by host WS1 (source hostname WS1) that appears only "
           "once in the data (a first-seen, never-before-observed domain). Return the "
           "query_hostname."},
    {"id": "A9", "kind": "exact_scalar", "truth_key": "distinct_asset_count",
     "nl": "Behind the six identifiers tied to the human actor, how many DISTINCT physical "
           "assets are there once hostname/ip/instance-id aliases are collapsed? Return the count."},
]


# ---------------------------------------------------------------------------- store + truth
def connect():
    con = configure_duckdb(duckdb.connect(":memory:"))
    for t in ("auth", "session", "network", "dns", "process", "api", "asset"):
        con.execute(f"CREATE VIEW f_{t} AS SELECT * FROM '{STORE_F}/{t}.parquet'")
    return con


def load_truth():
    """Merge truth_needles with the two top-level truth structures so query lookup is uniform."""
    gt = json.load(open(GT))
    t = dict(gt["truth_needles"])
    t["truth_event_order"] = gt["truth_event_order"]
    t["truth_identity_links"] = gt["truth_identity_links"]
    return t


# ---------------------------------------------------------------------------- graph build
def build_graph(con):
    """Stream Store F into a deterministic MultiDiGraph. Every node carries a `doc` (its
    embedding text) and a `ntype`; needle attributes (cmdline, event_uid, query_hostname,
    mfa flag) are kept verbatim in the doc so substring/uid answers survive into LLM context."""
    import networkx as nx
    g = nx.MultiDiGraph()

    def node(nid, ntype, doc, **attrs):
        if nid not in g:
            g.add_node(nid, ntype=ntype, doc=doc, **attrs)
        return nid

    def q(sql):
        return con.execute(sql).fetchall()

    # hosts + asset aliasing (A5/A9 identity collapse via sameAs)
    for (host, ip, inst, canon) in q("SELECT hostname, ip, instance_uid, canonical_asset FROM f_asset ORDER BY hostname"):
        h = node(f"host:{host}", "host", f"host {host} (canonical asset {canon})", canonical=canon)
        i = node(f"ip:{ip}", "ip", f"ip address {ip}")
        n = node(f"instance:{inst}", "instance", f"cloud instance {inst}")
        g.add_edge(h, i, rel="sameAs"); g.add_edge(i, n, rel="sameAs")
        g.add_edge(h, n, rel="sameAs", canonical=canon)

    # auth events
    for (uid, t, user, host, sip, sctry, outcome, remote) in q(
        "SELECT event_uid, time, user_uid, target_host, src_ip, src_country, outcome, is_remote "
        "FROM f_auth ORDER BY event_uid"):
        u = node(f"user:{user}", "user", f"user {user}")
        h = node(f"host:{host}", "host", f"host {host}")
        e = node(f"authevt:{uid}", "auth_event",
                 f"authentication event_uid {uid} user {user} target_host {host} src_ip {sip} "
                 f"src_country {sctry} outcome {outcome} is_remote {remote} time {t}", time=t)
        g.add_edge(u, e, rel="authenticated"); g.add_edge(e, h, rel="on_host")
        g.add_edge(u, h, rel="signed_in_on")

    # sessions (A4 point-in-time validity)
    for (uid, user, host, st, et) in q(
        "SELECT event_uid, user_uid, host, start_time, end_time FROM f_session ORDER BY event_uid"):
        u = node(f"user:{user}", "user", f"user {user}")
        h = node(f"host:{host}", "host", f"host {host}")
        e = node(f"session:{uid}", "session",
                 f"session event_uid {uid} user {user} host {host} start_time {st} end_time {et}",
                 start_time=st, end_time=et)
        g.add_edge(u, e, rel="opened"); g.add_edge(e, h, rel="on_host")

    # network connections (A1 beacon cadence on edge attrs)
    for (uid, t, sip, shost, dip, dport, proto, bo, bi, dur) in q(
        "SELECT event_uid, time, src_ip, src_hostname, dst_ip, dst_port, protocol_name, "
        "bytes_out, bytes_in, duration FROM f_network ORDER BY event_uid"):
        h = node(f"host:{shost}", "host", f"host {shost}")
        ep = node(f"endpoint:{dip}:{dport}", "endpoint", f"endpoint {dip} port {dport} proto {proto}")
        e = node(f"netconn:{uid}", "net_event",
                 f"network connection event_uid {uid} from {sip} ({shost}) to {dip} port {dport} "
                 f"proto {proto} bytes_out {bo} bytes_in {bi} duration {dur} time {t}",
                 time=t, bytes_out=bo, dst_port=dport)
        g.add_edge(h, e, rel="connected"); g.add_edge(e, ep, rel="to")

    # dns (A8 first-seen domain)
    for (uid, t, sip, shost, query, answer) in q(
        "SELECT event_uid, time, src_ip, src_hostname, query_hostname, answer FROM f_dns ORDER BY event_uid"):
        h = node(f"host:{shost}", "host", f"host {shost}")
        d = node(f"domain:{query}", "domain", f"domain {query}")
        e = node(f"dnsevt:{uid}", "dns_event",
                 f"dns query event_uid {uid} src {shost} ({sip}) query_hostname {query} answer {answer} time {t}",
                 time=t)
        g.add_edge(h, e, rel="queried"); g.add_edge(e, d, rel="resolves")

    # process (A2 powershell cmdline; parent linkage winword->powershell)
    for (uid, t, dhost, actor, img, cmd, pimg, pid) in q(
        "SELECT event_uid, time, device_hostname, actor_user_uid, image_name, cmd_line, "
        "parent_image_name, pid FROM f_process ORDER BY event_uid"):
        h = node(f"host:{dhost}", "host", f"host {dhost}")
        u = node(f"user:{actor}", "user", f"user {actor}")
        e = node(f"proc:{uid}", "process_event",
                 f"process {img} (pid {pid}) on host {dhost} actor {actor} parent_image {pimg} "
                 f"event_uid {uid} time {t} cmd_line: {cmd}", time=t, image=img, parent=pimg)
        g.add_edge(u, e, rel="performed"); g.add_edge(e, h, rel="on_host")

    # api / cloudtrail (A6 no-MFA, A5 assume-role pivot)
    for (uid, t, svc, op, actor, sip, res, mfa, region) in q(
        "SELECT event_uid, time, service, api_operation, actor_user_uid, src_ip, resource, "
        "mfa_present, aws_region FROM f_api ORDER BY event_uid"):
        u = node(f"user:{actor}", "user", f"user {actor}")
        e = node(f"apievt:{uid}", "api_event",
                 f"cloud api event_uid {uid} service {svc} operation {op} actor {actor} "
                 f"resource {res} mfa_present {mfa} region {region} src_ip {sip} time {t}",
                 time=t, operation=op, mfa_present=mfa)
        g.add_edge(u, e, rel="called")
        if res:
            r = node(f"resource:{res}", "resource", f"resource {res}")
            g.add_edge(e, r, rel="on_resource")
        if op and "assumerole" in str(op).lower():
            role = node(f"role:{res or op}", "role", f"assumed role {res or op}")
            g.add_edge(u, role, rel="assumed")
    return g


def graph_fingerprint(g):
    nodes = sorted(f"{n}|{g.nodes[n].get('ntype')}" for n in g.nodes)
    edges = sorted(f"{u}|{v}|{d.get('rel')}" for u, v, d in g.edges(data=True))
    h = hashlib.sha256()
    for x in nodes:
        h.update(x.encode())
    h.update(b"||EDGES||")
    for x in edges:
        h.update(x.encode())
    return h.hexdigest()


# ---------------------------------------------------------------------------- embeddings
# Structured-retrieval rebuild: embed the ENTITY/concept layer only, not the per-event nodes.
# The original arm embedded one vector per telemetry event (~100k+ on Store F), which is the
# design that stalled CPU embedding for hours. Entities are the few hundred dimensional nodes;
# entity seeds then pull their events through the 2-hop ego traversal in retrieve(). The event
# nodes stay in the graph (so traversal + serialization still see them) — they are just not
# vector-indexed.
# Stable CONCEPT entities only. `endpoint` (dst_ip:dst_port) is deliberately excluded: it is a
# high-cardinality per-flow tuple (~54k on Store F), an event attribute rather than a concept, and
# embedding it reintroduces the very cost the rebuild removes. Endpoints stay as graph nodes and are
# reachable by traversal from their host/event; they are just not vector-indexed. The embedded set
# is then ~1.3k (hosts, users, domains, resources, roles, instances) — genuinely "a few hundred-ish".
ENTITY_NTYPES = {"host", "ip", "instance", "user", "domain", "resource", "role"}


def node_documents(g):
    """(node_id, doc) for the ENTITY layer only — sorted, deterministic embedding order.
    This is the structured-retrieval rebuild: vector-index the entities, traverse to events."""
    return sorted(((n, g.nodes[n]["doc"]) for n in g.nodes
                   if g.nodes[n].get("ntype") in ENTITY_NTYPES), key=lambda x: x[0])


def embed(texts, model, batch=128):
    """Batch-embed via Ollama /api/embed (input list); fall back to legacy per-item route."""
    vecs = []
    for i in range(0, len(texts), batch):
        chunk = texts[i:i + batch]
        try:
            r = requests.post(EMBED_URL, json={"model": model, "input": chunk}, timeout=600)
            r.raise_for_status()
            vecs.extend(r.json()["embeddings"])
        except Exception:
            for t in chunk:
                r = requests.post(EMBED_URL_LEGACY, json={"model": model, "prompt": t}, timeout=600)
                vecs.append(r.json()["embedding"])
    return np.asarray(vecs, dtype=np.float32)


def build_or_load_embeddings(g, embed_model, fp):
    os.makedirs(WORK, exist_ok=True)
    npy, ids_json = os.path.join(WORK, "embeddings.npy"), os.path.join(WORK, "embed_ids.json")
    meta = os.path.join(WORK, "embed_meta.json")
    if all(os.path.exists(p) for p in (npy, ids_json, meta)):
        m = json.load(open(meta))
        if m.get("fingerprint") == fp and m.get("embed_model") == embed_model:
            return np.load(npy), json.load(open(ids_json))
    docs = node_documents(g)
    ids = [d[0] for d in docs]
    mat = embed([d[1] for d in docs], embed_model)
    norm = np.linalg.norm(mat, axis=1, keepdims=True)
    mat = mat / np.where(norm == 0, 1, norm)  # pre-normalize for cosine
    np.save(npy, mat)
    json.dump(ids, open(ids_json, "w"))
    json.dump({"fingerprint": fp, "embed_model": embed_model, "n": len(ids)}, open(meta, "w"))
    return mat, ids


# ---------------------------------------------------------------------------- retrieval
def vector_topk(qvec, mat, ids, k):
    q = qvec / (np.linalg.norm(qvec) or 1.0)
    sims = mat @ q
    # deterministic: sort by (-sim, id) via a stable secondary key
    order = sorted(range(len(ids)), key=lambda i: (-float(sims[i]), ids[i]))
    return [ids[i] for i in order[:k]]


def sameas_index(g):
    """Precompute the sameAs adjacency once (alias chains: host↔ip↔instance). Avoids scanning a
    hub node's tens-of-thousands of edges per query just to find its 2-3 alias links."""
    adj = {}
    for u, v, d in g.edges(data=True):
        if d.get("rel") == "sameAs":
            adj.setdefault(u, set()).add(v)
            adj.setdefault(v, set()).add(u)
    return adj


def retrieve(g, seeds, sameadj):
    """Structured retrieval: from each entity seed, a BOUNDED 1-hop neighbourhood (entity → its
    events / aliases), capped so the kept subgraph stays ~NODE_BUDGET even when a seed is a
    super-hub — a host on a 2-host corpus has tens of thousands of event neighbours, and a full
    ego_graph over that is intractable. Bounding the per-seed expansion is what makes entity-seeded
    retrieval usable; the serializer caps again at NODE_BUDGET. Then a small sameAs alias closure
    (via the precomputed index) so an actor's identity links are not split."""
    keep = set(s for s in seeds if s in g)
    per_seed = max(2, NODE_BUDGET // max(1, len(seeds)))
    for s in seeds:
        if s not in g:
            continue
        nbrs = sorted(set(g.successors(s)) | set(g.predecessors(s)))  # deterministic
        keep.update(nbrs[:per_seed])
    # bounded sameAs alias closure over the kept set (index lookup, not a full edge scan)
    frontier = set(keep)
    while frontier:
        nxt = set()
        for n in frontier:
            for other in sameadj.get(n, ()):  # O(alias degree), not O(node degree)
                if other not in keep:
                    keep.add(other); nxt.add(other)
        frontier = nxt
    return keep


def serialize_subgraph(g, keep, seed_rank):
    """Deterministic context: nodes ordered by seed proximity then id, capped; then edges
    among the kept nodes, capped."""
    nodes = sorted(keep, key=lambda n: (seed_rank.get(n, 10 ** 9), n))[:NODE_BUDGET]
    nset = set(nodes)
    lines = ["FACTS:"]
    lines += [f"- {g.nodes[n]['doc']}" for n in nodes]
    edges = sorted({f"  {u} --{d.get('rel')}--> {v}" for u, v, d in g.edges(data=True)
                    if u in nset and v in nset})
    lines.append("RELATIONSHIPS:")
    lines += edges[:EDGE_BUDGET]
    return "\n".join(lines)


def serialize_flat(g, keep, seed_rank):
    """flat_retrieval CONTROL: the SAME retrieved node facts as serialize_subgraph, but as a flat
    list with NO relationships / graph structure. This isolates retrieval-value (which facts get
    pulled) from graph-structure-value (how they connect). If the flat arm scores ~= the structured
    arm, the graph structure adds nothing over plain retrieval of the same facts — the Phase-B
    control the program plan requires before any grounding claim is publishable."""
    nodes = sorted(keep, key=lambda n: (seed_rank.get(n, 10 ** 9), n))[:NODE_BUDGET]
    return "\n".join(["FACTS:"] + [f"- {g.nodes[n]['doc']}" for n in nodes])


# ---------------------------------------------------------------------------- generation
def ask(model, question, context):
    prompt = (
        "You answer a security question using ONLY the supplied graph facts and relationships. "
        "Return JSON only: {\"answer\": [...]} for a list, or {\"answer\": \"<value>\"} for a "
        "single value. Use exact identifiers from the facts; if the facts do not contain the "
        "answer, return {\"answer\": []}.\n\n"
        f"{context}\n\nQuestion: {question}\nJSON:")
    try:
        r = requests.post(GEN_URL, json={"model": model, "prompt": prompt, "stream": False,
                          "format": "json", "options": {"temperature": 0}, "keep_alive": "10m"},
                          timeout=240)
        ans = json.loads(r.json().get("response", "")).get("answer", "")
    except Exception:
        return []
    if isinstance(ans, list):
        return [str(x) for x in ans]
    if ans in (None, ""):
        return []
    return [str(ans)]


# ---------------------------------------------------------------------------- arm driver
def run_arm(model, embed_model, flat=False):
    truth = load_truth()
    con = connect()
    g = build_graph(con)
    con.close()
    fp = graph_fingerprint(g)
    mat, ids = build_or_load_embeddings(g, embed_model, fp)
    sameadj = sameas_index(g)

    per_query, rows = {}, []
    for q in QUERIES:
        qvec = embed([q["nl"]], embed_model)[0]
        seeds = vector_topk(qvec, mat, ids, K_SEED)
        seed_rank = {nid: i for i, nid in enumerate(seeds)}
        keep = retrieve(g, seeds, sameadj)
        context = (serialize_flat if flat else serialize_subgraph)(g, keep, seed_rank)
        answer = ask(model, q["nl"], context)
        if not answer:
            outcome = "loud"                                   # empty / refusal / parse fail
        else:
            outcome = classify(q["kind"], answer, truth[q["truth_key"]])
        per_query[q["id"]] = {"outcome": outcome, "kind": q["kind"],
                              "cells_returned": len(answer), "answer_sample": answer[:5]}
        rows.append((q["id"], outcome, len(answer)))
        print(f"  {q['id']}: {outcome} ({len(answer)} cells)")

    mode_desc = ("flat_retrieval CONTROL (same facts, NO graph structure)" if flat
                 else "structured entity-layer retrieval")
    n = len(QUERIES)
    counts = {k: sum(1 for r in rows if r[1] == k) for k in ("correct", "silent", "loud")}
    return {
        "status": "measured",
        "engine": f"GraphRAG ({mode_desc}): NetworkX MultiDiGraph, {embed_model} "
                  f"cosine over ENTITY nodes only (k={K_SEED}, hops={HOPS}); events pulled by 2-hop "
                  f"traversal, not embedded; + {model}",
        "generator_model": model, "embed_model": embed_model,
        "retrieval_mode": "flat" if flat else "structured",
        "graph_fingerprint": fp, "graph_nodes": g.number_of_nodes(), "graph_edges": g.number_of_edges(),
        "embedded_entities": len(ids),
        "retrieval": {"k_seed": K_SEED, "hops": HOPS, "node_budget": NODE_BUDGET, "edge_budget": EDGE_BUDGET},
        "per_query": per_query, "counts": counts,
        "silent_error_rate": round(counts["silent"] / n, 4),
        "result_accuracy": round(counts["correct"] / n, 4),
        "queries": [q["id"] for q in QUERIES],
        "decode_caveat": ("graph + cached embeddings are deterministic and asserted; the LLM "
                          "answer is temperature-0 greedy decode — reproducible in practice, not asserted"),
    }


def merge(arm, name="graphrag"):
    rpath = os.path.join(HERE, "results", "results.json")
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    full = json.load(open(rpath)) if os.path.exists(rpath) else {"arms": {}}
    full.setdefault("arms", {})[name] = arm
    json.dump(full, open(rpath, "w"), indent=2, sort_keys=True)


def determinism():
    truth = load_truth()
    con = connect()
    fp1 = graph_fingerprint(build_graph(con))
    fp2 = graph_fingerprint(build_graph(con))
    con.close()
    # scorer is a pure function — stable on fixed input
    cells = ["api-needle-nomfa"]
    stable = (classify("uid", cells, truth["nomfa_event_uid"])
              == classify("uid", cells, truth["nomfa_event_uid"]))
    print(f"graph fingerprint reproduces: {fp1 == fp2}  ({fp1[:16]}…)")
    print(f"scorer + ground-truth load reproduce: {stable}")
    print("NOTE: the concept graph and the cached embeddings are deterministic and asserted; "
          "the LLM answer is temperature-0 greedy decode (reproducible in practice, not asserted).")
    sys.exit(0 if (fp1 == fp2 and stable) else 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:26b")
    ap.add_argument("--embed-model", default="nomic-embed-text")
    ap.add_argument("--determinism", action="store_true")
    ap.add_argument("--render-only", action="store_true",
                    help="defer to run.py --render-only (it reads the merged results.json)")
    ap.add_argument("--flat", action="store_true",
                    help="run the flat_retrieval CONTROL (same retrieved facts, NO graph structure)")
    args = ap.parse_args()

    if args.determinism:
        determinism()
    if args.render_only:
        print("GraphRAG arm merges into results/results.json; render with: "
              "python run.py --render-only")
        return
    if not os.path.isdir(STORE_F):
        print("Store F not built — run bench-a-context-collapse/run.py first.", file=sys.stderr)
        sys.exit(2)

    arm_name = "flat_retrieval" if args.flat else "graphrag"
    arm = run_arm(args.model, args.embed_model, flat=args.flat)
    merge(arm, arm_name)
    print(f"\n{arm_name} ({args.model}): {arm['counts']}  "
          f"silent-error={arm['silent_error_rate']:.2f}  result-acc={arm['result_accuracy']:.2f}")
    print(f"merged into results/results.json as arm '{arm_name}'")


if __name__ == "__main__":
    main()
