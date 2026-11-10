#!/usr/bin/env python3
"""T1-shadow-ai-discovery: run the offline discovery methods against each run's artifacts and score them.

For each results/run<N>/: Zeek over eth0.pcap (primary) and any.pcap (secondary), Syft over the fixture home,
the egress-allowlist check, then the pre-registered rules (PREREGISTRATION.md, "Discovery methods") applied to
Zeek logs, the dnsmasq log, the osquery JSON and the Syft JSON. Writes results/run<N>/{zeek-eth0,zeek-any,syft.json,
egress.json,fired.json,method-timing.json} and results/{scores.json,matrix.md}. stdlib only; time.monotonic().
"""
import json, pathlib, re, statistics, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent
RES = HERE / "results"
HOME = HERE / "fixtures" / "endpoint-home"
SYFT = HERE.parent / "ai-artifact-sbom" / "tools" / "bin" / "syft"
SCORE_ONLY = "--score-only" in sys.argv   # re-apply rules to existing Zeek/Syft outputs without re-running them
RUNS = [int(a) for a in sys.argv[1:] if a.isdigit()] or [1, 2, 3]
NICE = ["nice", "-n", "10", "taskset", "-c", "0-3"]

# ---- pre-registered lists (copied verbatim from PREREGISTRATION.md) ----
AI_DOMAINS = ["openai.com", "chatgpt.com", "oaistatic.com", "anthropic.com", "claude.ai", "generativelanguage.googleapis.com",
              "gemini.google.com", "aistudio.google.com", "mistral.ai", "openrouter.ai", "groq.com", "cohere.com", "cohere.ai",
              "huggingface.co", "hf.co", "perplexity.ai", "copilot.microsoft.com", "registry.ollama.ai", "ollama.com", "together.ai",
              "together.xyz", "replicate.com", "fireworks.ai", "deepseek.com", "x.ai", "character.ai", "poe.com", "stability.ai",
              "cursor.sh", "cursor.com", "codeium.com", "windsurf.com", "tabnine.com", "api.githubcopilot.com",
              "copilot-proxy.githubusercontent.com"]
RUNTIME_PORTS = {11434, 8000, 1234, 8080, 5000, 7860, 3000, 8081}
RUNTIME_PROCESS_RE = re.compile(r"ollama|llama[-_.]?(cpp|server)|vllm|lmstudio|\blms\b|koboldcpp|gpt4all|localai|open[-_]?webui|litellm|text-generation|tabby", re.I)
AI_PKGS = {p.lower().replace("_", "-") for p in ["openai", "anthropic", "huggingface-hub", "huggingface_hub", "safetensors", "tokenizers", "transformers",
           "torch", "langchain", "langchain-core", "langchain_core", "langgraph", "llama-index", "llama_index", "mcp", "gguf", "llama-cpp-python",
           "llama_cpp_python", "litellm", "vllm", "ollama", "google-generativeai", "google-genai", "cohere", "mistralai", "sentence-transformers",
           "onnxruntime", "tiktoken"]}
AI_EXT_IDS = {"saoudrizwan.claude-dev", "continue.continue", "github.copilot", "github.copilot-chat", "codeium.codeium", "tabnine.tabnine-vscode",
              "amazonwebservices.amazon-q-vscode", "google.geminicodeassist", "rooveterinaryinc.roo-cline", "kilocode.kilo-code",
              "anthropic.claude-code", "sourcegraph.cody-ai"}
MODEL_EXT = (".gguf", ".safetensors", ".ggml", ".pt", ".pth", ".onnx", ".tflite", ".h5", ".ckpt")
MODEL_DIRS = ("/.ollama/models/blobs/", "/.cache/huggingface/", "/.lmstudio/models/")
CHROME_AI_RE = re.compile(r"(?i)\b(ai|gpt|chat|llm|copilot|assistant)\b")
ALLOWLIST = ["example.com", "wikipedia.org", "github.com", "debian.org", "pypi.org", "docker.io", "githubusercontent.com"]
ESTABLISHED = {"SF", "S1", "S2", "S3", "RSTO", "RSTR"}
HTTP_URI_RE = re.compile(r"^/v1/|^/api/(generate|chat|tags|embeddings|pull)")
HTTP_UA_RE = re.compile(r"ollama|OpenAI|Anthropic")

# ---- ground truth: which identifier belongs to which surface / control ----
S8_HOSTS = {"api.openai.com", "api.anthropic.com", "generativelanguage.googleapis.com", "api.mistral.ai", "openrouter.ai", "api.groq.com",
            "api.cohere.com", "huggingface.co"}
S9_HOSTS = {"chatgpt.com", "claude.ai", "gemini.google.com", "www.perplexity.ai", "copilot.microsoft.com", "copilot.com"}  # copilot.com is the redirect target seen in the discarded run
C2_HOSTS = {"example.com", "www.wikipedia.org", "github.com", "deb.debian.org", "pypi.org"}
S1_HOSTS = {"registry.ollama.ai"}
S6_NAMES = {"openai", "anthropic", "huggingface-hub", "safetensors", "tokenizers", "langchain-core", "mcp", "gguf"}
C5_NAMES = {"requests", "numpy"}
IP_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$|^[0-9a-f:]+$")


def suffix_in(name, lst):
    name = (name or "").lower().rstrip(".")
    return any(name == d or name.endswith("." + d) for d in lst)


def host_surface(h):
    h = (h or "").lower().rstrip(".")
    if h in S8_HOSTS: return "S8"
    if h in S9_HOSTS: return "S9"
    if h in S1_HOSTS: return "S1"
    if h in C2_HOSTS: return "C2"
    return "?"


def port_surface(p):
    return {11434: "S1", 8000: "S2", 8080: "C1"}.get(int(p), "?")


def sh(cmd, timeout=900):
    t0 = time.monotonic()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r, round(time.monotonic() - t0, 3)


def zeek_logs(d):
    out = {}
    for name in ["conn", "dns", "ssl", "http"]:
        p = d / f"{name}.log"
        out[name] = [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
    return out


def run_zeek(pcap, outdir):
    outdir.mkdir(exist_ok=True)
    r, t = sh(NICE + ["docker", "run", "--rm", "--cpuset-cpus", "0-3", "-v", f"{pcap.parent}:/pcap:ro", "-v", f"{outdir}:/out", "-w", "/out",
                      "zeek/zeek:8.0.11", "zeek", "-C", "-r", f"/pcap/{pcap.name}", "local", "LogAscii::use_json=T"])
    (outdir / "zeek-stderr.txt").write_text(r.stderr + r.stdout)
    return t


def fire(fired, method, rule, ident, target, detail=""):
    fired.setdefault(method, []).append({"rule": rule, "id": ident, "target": target, "detail": detail})


def analyze_run(n):
    rd = RES / f"run{n}"
    if SCORE_ONLY and (rd / "method-timing.json").exists():
        timing = json.loads((rd / "method-timing.json").read_text())   # keep the first pass's Zeek/Syft outputs and timings
    else:
        timing = {}
        # M1 Zeek
        timing["zeek_eth0"] = run_zeek(rd / "eth0.pcap", rd / "zeek-eth0")
        timing["zeek_any"] = run_zeek(rd / "any.pcap", rd / "zeek-any")
        # M4 Syft
        r, timing["syft"] = sh(NICE + [str(SYFT), f"dir:{HOME}", "-o", f"syft-json={rd / 'syft.json'}", "-q"])
        (rd / "syft-stderr.txt").write_text(r.stderr)
    fired = {}
    # ---- M1 rules ----
    for view in ["eth0", "any"]:
        z = zeek_logs(rd / f"zeek-{view}")
        m = "M1_zeek" if view == "eth0" else "M1b_zeek_any"
        for row in z["ssl"]:
            sni = row.get("server_name")
            if sni and suffix_in(sni, AI_DOMAINS):
                fire(fired, m, "Z1_ssl_sni", sni, host_surface(sni))
        for row in z["dns"]:
            q = row.get("query")
            if q and suffix_in(q, AI_DOMAINS):
                fire(fired, m, "Z2_dns_query", q, host_surface(q))
        for row in z["http"]:
            p = row.get("id.resp_p"); uri = row.get("uri") or ""; ua = row.get("user_agent") or ""
            if p in RUNTIME_PORTS or HTTP_URI_RE.search(uri) or HTTP_UA_RE.search(ua):
                fire(fired, m, "Z3_http", f"{row.get('id.orig_h')}->{row.get('id.resp_h')}:{p} {row.get('method')} {uri}", port_surface(p), f"ua={ua}")
        seen = set()
        for row in z["conn"]:
            p = row.get("id.resp_p")
            if p in RUNTIME_PORTS and row.get("conn_state") in ESTABLISHED and row.get("proto") == "tcp":
                key = (row.get("id.orig_h"), row.get("id.resp_h"), p)
                if key not in seen:
                    seen.add(key)
                    fire(fired, m, "Z4_conn_port", f"{key[0]}->{key[1]}:{p}", port_surface(p), row.get("conn_state"))
        # the raw destination inventories, for RESULTS and for M5
        (rd / f"zeek-{view}" / "summary.json").write_text(json.dumps({
            "ssl_sni": sorted({r.get("server_name") for r in z["ssl"] if r.get("server_name")}),
            "dns_queries": sorted({r.get("query") for r in z["dns"] if r.get("query")}),
            "http_rows": [{k: r.get(k) for k in ["id.orig_h", "id.resp_h", "id.resp_p", "method", "host", "uri", "user_agent", "status_code"]} for r in z["http"]],
            "conn_resp_ports": sorted({r.get("id.resp_p") for r in z["conn"] if r.get("proto") == "tcp"}),
            "rows": {k: len(v) for k, v in z.items()}}, indent=1))
    # ---- M2 dnsmasq ----
    dns_names = []
    for line in (rd / "dnsmasq.log").read_text().splitlines():
        mm = re.search(r"query\[(\w+)\] (\S+) from (\S+)", line)
        if mm:
            dns_names.append(mm.group(2))
    for q in sorted(set(dns_names)):
        if suffix_in(q, AI_DOMAINS):
            fire(fired, "M2_dnslog", "D1_query", q, host_surface(q))
    (rd / "dnsmasq-names.json").write_text(json.dumps(sorted(set(dns_names)), indent=1))
    # ---- M3 osquery ----
    oq = {}
    for p in (rd / "osquery").glob("*.json"):
        try:
            oq[p.stem] = json.loads(p.read_text())
        except Exception as e:
            oq[p.stem] = {"error": str(e)}
    for row in oq.get("O1_processes", []) if isinstance(oq.get("O1_processes"), list) else []:
        txt = f"{row.get('name','')} {row.get('cmdline','')}"
        if RUNTIME_PROCESS_RE.search(txt):
            tgt = "S1" if "ollama" in txt.lower() else "?"
            fire(fired, "M3_osquery", "O1_process", f"{row.get('name')} {(row.get('cmdline') or '').split(' ')[0:2]}", tgt, f"pid={row.get('pid')} {(row.get('cmdline') or '')[:120]}")
    for row in oq.get("O2_listening_ports", []) if isinstance(oq.get("O2_listening_ports"), list) else []:
        if int(row.get("port") or 0) in RUNTIME_PORTS:
            fire(fired, "M3_osquery", "O2_listen_port", f"{row.get('port')}/{row.get('protocol')} {row.get('name')}", port_surface(row.get("port")), (row.get("cmdline") or "")[:120])
    for row in oq.get("O3_files_home", []) if isinstance(oq.get("O3_files_home"), list) else []:
        path = row.get("path", "")
        if path.lower().endswith(MODEL_EXT):
            tgt = "S7" if path.startswith("/home/dev/models/") else "?"
            fire(fired, "M3_osquery", "O3_model_file_ext", path, tgt, row.get("size"))
        elif any(d in path for d in MODEL_DIRS):
            fire(fired, "M3_osquery", "O3_model_dir", path, "S7b", row.get("size"))
    for key, rule in [("O4a_python_packages_default", "O4a_pkg_default"), ("O4b_python_packages_directed", "O4b_pkg_directed")]:
        for row in oq.get(key, []) if isinstance(oq.get(key), list) else []:
            nm = (row.get("name") or "").lower().replace("_", "-")
            if nm in AI_PKGS:
                fire(fired, "M3_osquery", rule, f"{nm}=={row.get('version')}", "S6" if nm in S6_NAMES else "?", row.get("directory"))
    for row in oq.get("O5_vscode_extensions", []) if isinstance(oq.get("O5_vscode_extensions"), list) else []:
        # osquery 5.24.0 fills `name` with the full publisher.name id from extensions.json and leaves `publisher` empty
        # (results/posthoc/P3_vscode_extensions_full.json), so the pre-registered publisher.name identity is taken
        # from `name` when it already carries the dot. Normalization only; the rule (id in AI_EXT_IDS) is unchanged.
        ident = (row.get("name") or "").lower() if "." in (row.get("name") or "") and not row.get("publisher") else f"{row.get('publisher','')}.{row.get('name','')}".lower()
        if ident in AI_EXT_IDS:
            fire(fired, "M3_osquery", "O5_vscode_ext", f"{ident}@{row.get('version')}", "S3", row.get("path"))
    for row in oq.get("O6_chrome_extensions", []) if isinstance(oq.get("O6_chrome_extensions"), list) else []:
        txt = f"{row.get('name','')} {row.get('description','')}"
        if CHROME_AI_RE.search(txt) or suffix_in(row.get("permissions", ""), AI_DOMAINS):
            fire(fired, "M3_osquery", "O6_chrome_ext", f"{row.get('name')} id={row.get('identifier')}", "S5", row.get("permissions"))
    for row in oq.get("O7a_mcp_config_files", []) if isinstance(oq.get("O7a_mcp_config_files"), list) else []:
        fire(fired, "M3_osquery", "O7a_mcp_config_path", row.get("path"), "S4", f"size={row.get('size')}")
    o7b = oq.get("O7b_mcp_config_yara")
    if isinstance(o7b, list):
        for row in o7b:
            if int(row.get("count") or 0) > 0:
                fire(fired, "M3_osquery", "O7b_mcp_config_yara", row.get("path"), "S4", row.get("matches"))
    else:
        fire(fired, "M3_osquery", "O7b_mcp_config_yara", "QUERY_ERROR", "S4", json.dumps(o7b)[:200])
    # ---- M4 Syft rules ----
    syft = json.loads((rd / "syft.json").read_text())
    arts = syft.get("artifacts", [])
    for a in arts:
        nm = (a.get("name") or "").lower().replace("_", "-")
        locs = [l.get("path", "") for l in a.get("locations", [])]
        typ = a.get("type", "")
        if nm in AI_PKGS:
            fire(fired, "M4_syft", "S1_ai_package", f"{nm}=={a.get('version')}", "S6" if nm in S6_NAMES else "?", f"{typ} {a.get('purl','')}")
        if "model" in typ.lower() or any(l.lower().endswith((".gguf", ".safetensors")) for l in locs):
            tgt = "S7" if any("/models/" in l for l in locs) else ("S7b" if any(".ollama" in l for l in locs) else "?")
            fire(fired, "M4_syft", "S2_model_component", f"{a.get('name')}@{a.get('version')}", tgt, f"{typ} purl={a.get('purl','')} locs={locs[:2]}")
        for l in locs:
            if "/.vscode/extensions/saoudrizwan." in l:
                fire(fired, "M4_syft", "S3_location_cline", f"{a.get('name')}@{a.get('version')}", "S3", f"{typ} {l}")
            elif "/.config/google-chrome/" in l:
                fire(fired, "M4_syft", "S3_location_chrome", f"{a.get('name')}@{a.get('version')}", "S5", f"{typ} {l}")
            elif "/.cursor/" in l or "/.config/Claude/" in l:
                fire(fired, "M4_syft", "S3_location_mcp", f"{a.get('name')}@{a.get('version')}", "S4", f"{typ} {l}")
            elif "/.ollama/" in l:
                fire(fired, "M4_syft", "S3_location_ollama", f"{a.get('name')}@{a.get('version')}", "S7b", f"{typ} {l}")
    (rd / "syft-summary.json").write_text(json.dumps({"artifact_count": len(arts), "types": sorted({a.get("type") for a in arts}),
        "names": sorted({f"{a.get('name')}@{a.get('version')}:{a.get('type')}" for a in arts}),
        "prettier_or_cline_locations": sorted({l.get("path") for a in arts for l in a.get("locations", []) if ".vscode" in l.get("path", "")}),
        "benign_controls_seen": sorted({a.get("name") for a in arts if (a.get("name") or "").lower() in C5_NAMES})}, indent=1))
    # ---- M5 egress allowlist ----
    z = zeek_logs(rd / "zeek-eth0")
    dests = set(r.get("server_name") for r in z["ssl"] if r.get("server_name")) | set(r.get("query") for r in z["dns"] if r.get("query")) \
        | set(r.get("host") for r in z["http"] if r.get("host")) | set(dns_names)
    flagged = sorted(d for d in dests if d and not IP_RE.match(d.split(":")[0]) and not suffix_in(d, ALLOWLIST))
    for d in flagged:
        fire(fired, "M5_egress", "E1_not_allowlisted", d, host_surface(d))
    (rd / "egress.json").write_text(json.dumps({"destinations": sorted(d for d in dests if d), "flagged": flagged,
                                                "allowed": sorted(d for d in dests if d and d not in flagged)}, indent=1))
    (rd / "fired.json").write_text(json.dumps(fired, indent=1))
    (rd / "method-timing.json").write_text(json.dumps(timing, indent=1))
    return fired, timing


SURFACES = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S7b", "S8", "S9"]
METHODS = ["M1_zeek", "M2_dnslog", "M3_osquery", "M4_syft", "M5_egress"]
# structural inability: the method's input cannot contain the surface (pre-registered reasoning)
STRUCTURAL = {
    "M1_zeek": {"S3", "S4", "S5", "S6", "S7", "S7b"}, "M2_dnslog": {"S2", "S3", "S4", "S5", "S6", "S7", "S7b"},
    "M5_egress": {"S2", "S3", "S4", "S5", "S6", "S7", "S7b"}, "M4_syft": {"S1", "S2", "S8", "S9"},
    # M3_osquery: no structural cells. VERIFICATION.md (2026-11-09): the live endpoint's process_open_sockets held TIME_WAIT
    # rows to the remote :443 addresses (IP only, pid -1), so S8/S9 are a missing rule, not an input that cannot contain them.
    "M3_osquery": set(),
}


def grade(method, surface, hits):
    """found / partial / missed from the fired rules on that surface, per the pre-registered scoring section."""
    rules = {h["rule"] for h in hits}
    ids = {h["id"] for h in hits}
    if not hits:
        return "missed"
    if method == "M1_zeek":
        if surface in ("S8", "S9"): return "found" if rules & {"Z1_ssl_sni", "Z2_dns_query"} else "partial"
        if surface == "S1": return "partial"  # port/URI from a peer plus a registry name; the runtime itself is inferred, never named
        if surface == "S2": return "partial"
    if method == "M2_dnslog":
        if surface in ("S8", "S9"): return "found"
        if surface == "S1": return "partial"  # registry name only
    if method == "M5_egress":
        if surface in ("S8", "S9"): return "found"  # names the destination, which is the surface
        if surface == "S1": return "partial"
    if method == "M3_osquery":
        if surface == "S1": return "found" if "O1_process" in rules else "partial"
        if surface == "S2": return "partial" if "O2_listen_port" in rules and not ("O1_process" in rules) else ("found" if "O1_process" in rules else "missed")
        if surface == "S3": return "found" if "O5_vscode_ext" in rules else "partial"
        if surface == "S4": return "found" if "O7b_mcp_config_yara" in rules and not any(h["id"] == "QUERY_ERROR" for h in hits) else "partial"
        if surface == "S5": return "found" if "O6_chrome_ext" in rules else "partial"
        if surface == "S6":
            n = {h["id"].split("==")[0] for h in hits if h["rule"] == "O4b_pkg_directed"}
            return "found" if n >= S6_NAMES else ("partial" if n else "missed")
        if surface == "S7": return "found" if len({h["id"] for h in hits if h["rule"] == "O3_model_file_ext"}) >= 2 else "partial"
        if surface == "S7b": return "found"  # path rule names the Ollama store
    if method == "M4_syft":
        if surface == "S6":
            n = {h["id"].split("==")[0] for h in hits if h["rule"] == "S1_ai_package"}
            return "found" if n >= S6_NAMES else ("partial" if n else "missed")
        if surface == "S7": return "found" if len({h["id"] for h in hits if h["rule"] == "S2_model_component"}) >= 2 else "partial"
        if surface == "S3": return "partial"  # an npm package in place of an extension identity
        return "partial"
    return "partial"


def main():
    all_fired, all_timing = {}, {}
    for n in RUNS:
        all_fired[n], all_timing[n] = analyze_run(n)
        print(f"run{n} analyzed: " + json.dumps(all_timing[n]))
    # matrix from run 1 (checked identical to runs 2-3 below; differences are reported)
    matrix, fps, per_run_sets = {}, {}, {}
    for n in RUNS:
        per_run_sets[n] = {m: sorted({(h["rule"], h["id"]) for h in all_fired[n].get(m, [])}) for m in METHODS + ["M1b_zeek_any"]}
    base = RUNS[0]
    variance = {m: [n for n in RUNS if per_run_sets[n][m] != per_run_sets[base][m]] for m in METHODS + ["M1b_zeek_any"]}
    for m in METHODS:
        hits = all_fired[base].get(m, [])
        matrix[m] = {}
        for s in SURFACES:
            g = grade(m, s, [h for h in hits if h["target"] == s])
            if g == "missed" and s in STRUCTURAL.get(m, set()):
                g = "missed (structural)"
            elif g == "missed":
                g = "missed (rule gap)"
            matrix[m][s] = g
        fps[m] = [h for h in hits if h["target"].startswith("C") or h["target"] == "?"]
    found_counts = {m: sum(1 for s in SURFACES if matrix[m][s] == "found") for m in METHODS}
    union = {s: "found" if any(matrix[m][s] == "found" for m in METHODS) else ("partial" if any(matrix[m][s] == "partial" for m in METHODS) else "missed") for s in SURFACES}
    timing_stats = {}
    for k in ["zeek_eth0", "zeek_any", "syft"]:
        xs = [all_timing[n][k] for n in RUNS]
        timing_stats[k] = {"median_s": round(statistics.median(xs), 3), "cv_pct": round(100 * statistics.pstdev(xs) / statistics.mean(xs), 1) if len(xs) > 1 else None, "samples": xs}
    lab_t = {}
    for n in RUNS:
        t = json.loads((RES / f"run{n}" / "timing.json").read_text())
        for k in ["activity_endpoint", "activity_peer", "osquery_total"]:
            lab_t.setdefault(k, []).append(t[k])
    for k, xs in lab_t.items():
        timing_stats[k] = {"median_s": round(statistics.median(xs), 3), "cv_pct": round(100 * statistics.pstdev(xs) / statistics.mean(xs), 1), "samples": xs}
    scores = {"runs": RUNS, "matrix": matrix, "found_counts": found_counts, "union": union, "false_positives": fps,
              "variance_runs_differing_from_run1": variance, "timing_under_contention": timing_stats,
              "fired_run1": all_fired[base], "per_run_fired_sets": {n: {m: len(v) for m, v in s.items()} for n, s in per_run_sets.items()}}
    (RES / "scores.json").write_text(json.dumps(scores, indent=1, default=str))
    # markdown matrix
    lines = ["| Surface | " + " | ".join(METHODS) + " | union |", "|---|" + "---|" * (len(METHODS) + 1)]
    for s in SURFACES:
        lines.append(f"| {s} | " + " | ".join(matrix[m][s] for m in METHODS) + f" | {union[s]} |")
    lines.append("| **found count** | " + " | ".join(str(found_counts[m]) for m in METHODS) + f" | {sum(1 for s in SURFACES if union[s]=='found')} |")
    (RES / "matrix.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("FPs:", {m: [(h["rule"], h["id"], h["target"]) for h in v] for m, v in fps.items()})
    print("variance:", variance)


if __name__ == "__main__":
    main()
