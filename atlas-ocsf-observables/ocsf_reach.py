"""Mechanical OCSF 1.9.0 reachability. For every object: which event classes carry it as an
attribute, and the shortest attribute path per class, in two arms:
  core    -- class/object definitions fetched with ?profiles= (no profiles applied), and paths
             that pass through generic wrappers (enrichments, observables, metadata, unmapped,
             osint, evidences, malware, related findings) are excluded. This is "a native field
             of the event class".
  profile -- definitions with every profile applied (the server default), wrappers allowed.
Reads only sources/ocsf-1.9.0{,-noprofile}/{classes,objects}/*.json from schema.ocsf.io/api/1.9.0."""
import json, os, glob, collections
HERE = os.path.dirname(os.path.abspath(__file__))
MAX_DEPTH = 4
WRAPPERS = {"enrichments", "observables", "metadata", "unmapped", "osint", "evidences", "malware",
            "malware_scan_info", "attacks", "finding_info", "related_events", "vulnerabilities",
            "query_evidence", "remediation", "kb_article_list", "affected_packages", "raw_data_hash"}

def load(d, kind):
    return {os.path.basename(f)[:-5]: json.load(open(f))
            for f in sorted(glob.glob(os.path.join(HERE, "sources", d, kind, "*.json")))}

def reach(d, exclude_wrappers):
    objs, classes = load(d, "objects"), load(d, "classes")
    res = collections.defaultdict(dict)
    for c in classes.values():
        uid = c.get("uid")
        if not uid:
            continue
        frontier = [(v, a) for a, v in c["attributes"].items()]
        for depth in range(1, MAX_DEPTH + 1):
            nxt = []
            for v, path in frontier:
                ot = (v.get("object_type") or "").replace("win/", "")
                if not ot:
                    continue
                if exclude_wrappers and path.split(".")[-1] in WRAPPERS:
                    continue
                cur = res[ot].get(uid)
                if cur is None or path.count(".") < cur.count("."):
                    res[ot][uid] = path
                if ot in objs:
                    nxt += [(v2, path + "." + a2) for a2, v2 in objs[ot]["attributes"].items()]
            frontier = nxt
    names = {c["uid"]: n for n, c in classes.items() if c.get("uid")}
    return res, names, objs

def main():
    core, names, objs = reach("ocsf-1.9.0-noprofile", True)
    prof, _, objs_p = reach("ocsf-1.9.0", False)
    fields = {n: sorted(o["attributes"]) for n, o in objs_p.items()}
    out = {"ocsf_version": "1.9.0", "max_depth": MAX_DEPTH, "wrappers_excluded_in_core": sorted(WRAPPERS),
           "class_names": {str(k): v for k, v in sorted(names.items())},
           "core": {o: {str(k): v for k, v in sorted(d.items())} for o, d in sorted(core.items())},
           "profile": {o: {str(k): v for k, v in sorted(d.items())} for o, d in sorted(prof.items())},
           "object_fields": fields}
    json.dump(out, open(os.path.join(HERE, "results", "ocsf_reach.json"), "w"), indent=1, sort_keys=True)
    print(len(names), "classes;", len(objs), "objects; core-reachable", len(core), "profile-reachable", len(prof))

if __name__ == "__main__":
    main()
