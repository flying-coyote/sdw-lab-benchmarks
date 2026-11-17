#!/usr/bin/env python3
"""E1 seeded path-level injector (PREREGISTRATION.md section 5, E1). Seed 20261117.

For every triple and every stratum, draw one replacement OCSF path uniformly from that stratum's
eligible candidates. Candidates are the OCSF paths in the same class's first column of the matrix
(class = the first section the triple appears in), plus generated non-paths for E1-INV only.
A triple with no eligible candidate in a stratum is ineligible there and counted.

Strata (decisions D8-D12 in HARNESS-ADDENDUM.md):
  K1  same OCSF type family; both paths ground to artifacts under the gate's ground_path() and the
      artifacts differ; both have an OCSF root kind and the roots differ.        (deciding stratum)
  K2  same type family; a root-kind crossing where a gate grounding is missing, or a gate-artifact
      crossing where a root kind is missing.                                     (vocabulary coverage)
      Same-family pairs where both systems type both sides but disagree on whether it is a
      crossing are in neither stratum and are counted as `k_disagree`.
  T   both type families known and different.
  R   role swap src_endpoint<->dst_endpoint, actor.user<->user, actor.process<->process (prefix).
  INV an attribute name carried by some OCSF 1.8.0 object or class, appended to the original path's
      deepest object-typed prefix whose object does not carry it (confirmed invalid by the walk).

Per-(triple, stratum) RNG: random.Random(int(sha256(f"{seed}|{stratum}|{tid}"), 16)), so the draw
for one triple does not depend on the order or the eligibility of any other.
Usage: python3 -I inject.py <out_items.jsonl> <out_counts.json>
"""
import hashlib
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

STRATA = ["K1", "K2", "T", "R", "INV"]
ROLE_SWAPS = [("actor.user", "user"), ("actor.process", "process"), ("src_endpoint", "dst_endpoint")]


def rng(stratum, tid, seed=C.SEED):
    return random.Random(int(hashlib.sha256(f"{seed}|{stratum}|{tid}".encode()).hexdigest(), 16))


def features(path, cls):
    g = C.gate()
    k = C.ocsf_kind(path, cls)
    return {"valid": C.path_valid(path, cls), "fam": C.leaf_family(path, cls),
            "art": g.ground_path(path), "root": C.root_kind(k) if k else None}


def k_class(a, b):
    """K1 / K2 / disagree / None for a same-family pair of feature dicts."""
    arts = a["art"] is not None and b["art"] is not None
    roots = a["root"] is not None and b["root"] is not None
    art_x = arts and a["art"] != b["art"]
    root_x = roots and a["root"] != b["root"]
    if art_x and root_x:
        return "K1"
    if (root_x and not arts) or (art_x and not roots):
        return "K2"
    if arts and roots and (art_x != root_x):
        return "disagree"
    return None


def role_swap(path):
    segs = path.split(".")
    for a, b in ROLE_SWAPS:
        for x, y in ((a, b), (b, a)):
            xs = x.split(".")
            if segs[:len(xs)] == xs:
                return ".".join(y.split(".") + segs[len(xs):])
    return None


def all_attr_names():
    names = set()
    for o in C.all_objects():
        names |= set((C.ocsf_object(o) or {}).get("attributes", {}))
    for cls in C.SECTION_CLASS.values():
        names |= set(C.ocsf_class(cls)["attributes"])
    return sorted(names)


def inv_candidates(path, cls, vocab):
    w = C.walk(path, cls)
    if not w or len(C.expand_notation(path)) > 1:
        return []
    segs = C.norm_path(C.expand_notation(path)[0])
    last = None
    for i, (_, a) in enumerate(w):
        if a.get("object_type"):
            last = (i, a["object_type"])
    if last is None:
        return []
    i, obj = last
    carried = set((C.ocsf_object(obj) or {}).get("attributes", {}))
    prefix = ".".join(segs[:i + 1])
    return [f"{prefix}.{n}" for n in vocab if n not in carried and not C.path_valid(f"{prefix}.{n}", cls)]


def candidates(t, stratum, vocab, class_paths=C.class_paths):
    cls, orig = t["cls"], t["ocsf"]
    fo = features(orig, cls)
    if stratum == "INV":
        return inv_candidates(orig, cls, vocab)
    if not fo["valid"]:
        return []
    pool = [p for p in class_paths(cls) if p != orig]
    if stratum == "R":
        sw = role_swap(orig)
        return [sw] if sw in pool and C.path_valid(sw, cls) else []
    out = []
    for p in pool:
        fp = features(p, cls)
        if not fp["valid"] or fo["fam"] is None or fp["fam"] is None:
            continue
        if stratum == "T" and fo["fam"] != fp["fam"]:
            out.append(p)
        elif stratum in ("K1", "K2") and fo["fam"] == fp["fam"] and k_class(fo, fp) == stratum:
            out.append(p)
    return out


def generate(triples, class_paths=C.class_paths, seed=C.SEED):
    vocab = all_attr_names()
    items, counts = [], {s: {"eligible": 0, "ineligible": 0} for s in STRATA}
    disagree = 0
    for t in triples:
        fo = features(t["ocsf"], t["cls"])
        if fo["valid"] and fo["fam"] is not None:
            for p in class_paths(t["cls"]):
                if p != t["ocsf"]:
                    fp = features(p, t["cls"])
                    if fp["valid"] and fp["fam"] == fo["fam"] and k_class(fo, fp) == "disagree":
                        disagree += 1
        for s in STRATA:
            cands = sorted(set(candidates(t, s, vocab, class_paths)))
            if not cands:
                counts[s]["ineligible"] += 1
                continue
            counts[s]["eligible"] += 1
            repl = rng(s, t["tid"], seed).choice(cands)
            items.append({"item_id": f"{t['tid']}-{s}", "tid": t["tid"], "stratum": s, "schema": t["schema"],
                          "source": t["source"], "cls": t["cls"], "cell": t.get("cell"), "orig_ocsf": t["ocsf"], "ocsf": repl,
                          "n_candidates": len(cands)})
    counts["k_disagree_pairs"] = disagree
    counts["seed"] = seed
    return items, counts


def main(argv):
    C.verify_pins()
    items, counts = generate(C.triples())
    C.write_jsonl(argv[1], items)
    json.dump(counts, open(argv[2], "w"), indent=1)
    print(json.dumps(counts, indent=1))
    print("items sha256", C.sha256(argv[1]))


if __name__ == "__main__":
    main(sys.argv)
