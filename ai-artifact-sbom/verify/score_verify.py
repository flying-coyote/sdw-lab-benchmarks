#!/usr/bin/env python3
"""R4 scorer: normalize each tool's raw output, then compute the pre-registered metrics.

Outputs results/scores.json and prints markdown tables. Reads only results/raw and results/runlog.jsonl.
"""
import hashlib, json, statistics as st, sys
from collections import defaultdict
from pathlib import Path

D = Path(__file__).resolve().parent.parent
RAW = D / "verify" / "raw"
RUNS = [1, 2, 3]

TARGETS = {  # id: (fixture dir name, name needles (strict), location needle (lenient))
    "T1": ("models-gguf", ["tinyllama"], "tinyllama-1.1b-chat"),
    "T2": ("ollama-store", ["tinyllama"], "ollama-store"),
    "T3": ("models-hf", ["all-minilm-l6-v2"], "all-MiniLM-L6-v2"),
    "T4": ("mcp-npm", ["@modelcontextprotocol/server-filesystem"], None),
    "T5": ("mcp-pip", ["mcp-server-git", "mcp_server_git"], None),
    "T6": ("vscode", ["prettier-vscode", "esbenp.prettier"], "prettier-vscode"),
}
EXPECTED_ADV = {
    "T4": [("GHSA-hc55-p739-j48w", "CVE-2025-53110"), ("GHSA-q66q-fx2p-7w4m", "CVE-2025-53109")],
    "T5": [("GHSA-5cgr-j3jf-jw3v", "CVE-2025-68143"), ("GHSA-9xwc-hfwc-8w59", "CVE-2025-68144"),
           ("GHSA-j22h-9j4x-23w5", "CVE-2025-68145"), ("GHSA-vjqx-cfc4-9h6v", "CVE-2026-27735")],
}
CONTROLS = {"controls-npm": "lodash", "controls-pip": "requests"}
VARIANTS = {  # variant: (original fixture, target id)
    "variants_V1": ("models-gguf", "T1"), "variants_V2": ("models-gguf", "T1"), "variants_V3": ("ollama-store", "T2"),
    "variants_V4": ("models-gguf", "T1"), "variants_V5": ("mcp-npm", "T4"), "variants_V6": ("mcp-npm", "T4"),
    "variants_V7": ("mcp-pip", "T5"), "variants_V8": ("vscode", "T6"),
}
SBOM_TOOLS = ["syft", "trivy-fs", "trivy-rootfs", "trivy-fs-cdx", "ai-bom", "cyclonedx-py"]
AI_TYPES = {"model", "machine-learning-model"}


def load(tool, fx, run):
    p = RAW / tool / fx / f"run{run}.json"
    if not p.exists() or p.stat().st_size == 0:
        return None
    return json.loads(p.read_text())


def comps(tool, fx, run):
    """Normalized components: dicts with name, version, type, purl, cpes, cpe_source, digests, locs."""
    d = load(tool, fx, run)
    if d is None:
        return None
    out = []
    if tool == "syft":
        fdig = {f["location"]["path"]: [x["value"] for x in f.get("digests", [])] for f in d.get("files", [])}
        for a in d["artifacts"]:
            locs = [l["path"] for l in a["locations"]]
            dig = sorted({v for l in locs for v in fdig.get(l, [])})
            md = a.get("metadata") or {}
            if isinstance(md, dict) and md.get("integrity"):
                dig.append("integrity:" + md["integrity"])
            out.append(dict(name=a["name"], version=a["version"], type=a["type"], purl=a.get("purl") or "",
                            cpes=[c["cpe"] for c in a.get("cpes", [])],
                            cpe_source=sorted({c.get("source", "") for c in a.get("cpes", [])}),
                            digests=dig, locs=locs, foundBy=a.get("foundBy"),
                            meta_publisher=md.get("publisher") if isinstance(md, dict) else None))
    elif tool in ("trivy-fs", "trivy-rootfs"):
        for r in d.get("Results", []) or []:
            for p in r.get("Packages", []) or []:
                out.append(dict(name=p["Name"], version=p.get("Version", ""), type=r.get("Type", ""),
                                purl=(p.get("Identifier") or {}).get("PURL", ""), cpes=[], cpe_source=[],
                                digests=[p["Digest"]] if p.get("Digest") else [],
                                locs=[r["Target"]] + [p.get("FilePath", "")]))
    else:  # CycloneDX outputs
        def walk(cs):
            for c in cs or []:
                yield c
                yield from walk(c.get("components"))
        for c in walk(d.get("components", [])):
            if c.get("type") == "file" and tool not in ("ai-bom",):
                continue
            out.append(dict(name=(c["group"] + "/" if c.get("group") else "") + c.get("name", ""), version=c.get("version", ""), type=c.get("type", ""),
                            purl=c.get("purl", ""), cpes=[c["cpe"]] if c.get("cpe") else [], cpe_source=[],
                            digests=[h["content"] for h in c.get("hashes", [])],
                            locs=[p.get("value", "") for p in c.get("properties", []) if "location" in p.get("name", "") or "path" in p.get("name", "")]))
    return out


def vulns(tool, fx, run):
    """List of (pkgname, {ids}) for matcher outputs."""
    if tool == "grype":
        d = load("grype", fx, run)
        if d is None:
            return None
        return [(m["artifact"]["name"], {m["vulnerability"]["id"]} | {r["id"] for r in m.get("relatedVulnerabilities", [])})
                for m in d.get("matches", [])]
    d = load(tool, fx, run)
    if d is None:
        return None
    res = []
    for r in d.get("Results", []) or []:
        for v in r.get("Vulnerabilities", []) or []:
            res.append((v["PkgName"], {v["VulnerabilityID"]} | set(v.get("VendorIDs") or [])))
    return res


def match_target(cs, tid, strict=True):
    needles = TARGETS[tid][1]
    hits = [c for c in cs if any(n in c["name"].lower() for n in needles)]
    if not hits and not strict and TARGETS[tid][2]:
        hits = [c for c in cs if c["type"] in AI_TYPES or any(TARGETS[tid][2] in l for l in c["locs"])]
        hits = [c for c in hits if c["type"] in AI_TYPES or "extension" in c["type"]]
    return hits


def comp_hash(cs):
    key = sorted((c["name"], c["version"], c["type"], c["purl"]) for c in cs)
    return hashlib.sha256(json.dumps(key).encode()).hexdigest()[:12]


def main():
    S = {"discovery": {}, "advisories": {}, "controls": {}, "variants": {}, "repeat": {}, "timing": {}}
    # Discovery + identifiers (run 1; repeatability checked separately)
    for tool in SBOM_TOOLS:
        for tid, (fx, _, _) in TARGETS.items():
            cs = comps(tool, fx, 1)
            if cs is None:
                continue
            strict = match_target(cs, tid, True)
            len_ = match_target(cs, tid, False)
            h = strict or len_
            S["discovery"][f"{tool}|{tid}"] = dict(
                n_components_in_fixture=len(cs), found_strict=bool(strict), found_lenient=bool(len_),
                as_ai_artifact=any(c["type"] in AI_TYPES for c in h),
                names=sorted({c["name"] for c in h})[:4], types=sorted({c["type"] for c in h}),
                purl=any(c["purl"] for c in h), purls=sorted({c["purl"] for c in h if c["purl"]})[:2],
                cpe=any(c["cpes"] for c in h), cpe_source=sorted({s for c in h for s in c["cpe_source"]}),
                digest=any(c["digests"] for c in h))
    # Advisories
    for m in ("grype", "trivy-fs", "trivy-rootfs"):
        for tid, (fx, _, _) in TARGETS.items():
            vs = vulns(m, fx, 1)
            if vs is None:
                continue
            ids = set().union(*[i for n, i in vs if any(k in n.lower() for k in TARGETS[tid][1])]) if vs else set()
            exp = EXPECTED_ADV.get(tid, [])
            S["advisories"][f"{m}|{tid}"] = dict(
                expected=len(exp), matched=sum(1 for g, c in exp if g in ids or c in ids),
                any_on_target=sorted(ids)[:8], total_matches_in_fixture=len(vs))
        for fx, pkg in CONTROLS.items():
            vs = vulns(m, fx, 1) or []
            S["controls"][f"{m}|{fx}"] = sum(1 for n, i in vs if n.lower() == pkg)
    # Variants: compare target tuple vs original
    for tool in SBOM_TOOLS:
        for v, (orig, tid) in VARIANTS.items():
            a, b = comps(tool, orig, 1), comps(tool, v, 1)
            if a is None or b is None:
                continue
            ha, hb = match_target(a, tid, False), match_target(b, tid, False)
            if not hb and tid in ("T1", "T2"):  # renamed model: any model component counts as found
                hb = [c for c in b if c["type"] in AI_TYPES]
            ka = sorted((c["name"], c["version"], c["purl"]) for c in ha)
            kb = sorted((c["name"], c["version"], c["purl"]) for c in hb)
            da = sorted({x for c in ha for x in c["digests"]}); db = sorted({x for c in hb for x in c["digests"]})
            pa = sorted({str(c.get("meta_publisher")) for c in ha}); pb = sorted({str(c.get("meta_publisher")) for c in hb})
            S["variants"][f"{tool}|{v}"] = dict(
                orig_found=bool(ha), still_found=bool(hb), identity_differs=ka != kb,
                digest_differs=bool(da or db) and da != db, digest_present=bool(db),
                publisher_differs=pa != pb, names=[x[0] for x in kb][:3])
    # Repeatability + timing
    log = [json.loads(l) for l in (D / "verify/runlog.jsonl").read_text().splitlines()]
    times = defaultdict(list); fails = defaultdict(int)
    for r in log:
        if r["rc"] == 0:
            times[(r["tool"], r["fixture"])].append(r["seconds"])
        else:
            fails[(r["tool"], r["fixture"])] += 1
    for (tool, fx), ts in sorted(times.items()):
        if tool in SBOM_TOOLS:
            hs = {comp_hash(c) for c in (comps(tool, fx, r) for r in RUNS) if c is not None}
            S["repeat"][f"{tool}|{fx}"] = dict(runs_ok=len(ts), distinct_component_hashes=len(hs))
        if len(ts) >= 2:
            S["timing"][f"{tool}|{fx}"] = dict(n=len(ts), median_s=round(st.median(ts), 3),
                                               cv_pct=round(100 * st.stdev(ts) / st.mean(ts), 1))
    S["failures"] = {f"{k[0]}|{k[1]}": n for k, n in fails.items()}
    (D / "verify/scores.verify.json").write_text(json.dumps(S, indent=1))
    print(json.dumps(S, indent=1))


if __name__ == "__main__":
    main()
