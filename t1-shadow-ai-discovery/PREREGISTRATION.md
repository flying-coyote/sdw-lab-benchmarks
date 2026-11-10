---
type: benchmark-preregistration
area: T1-shadow-ai-discovery
created: 2026-11-09
status: frozen by agent before run; not owner-reviewed
hypothesis_served: H-AI-ARTIFACT-INVENTORY-01 (PROPOSED, gated-pending, no score); discovery half, extended from on-disk artifacts (R4) to running services, client configs, browser extensions and network egress
related: ai-artifact-sbom/ (R4, same host, same day)
---

# Pre-registration: which discovery method sees which shadow-AI surface?

## Question

A developer workstation carries nine kinds of AI deployment surface at once (a local model runtime, a
local OpenAI-compatible server, an IDE AI extension, MCP client configs, a browser AI extension, Python ML
packages, model files on disk, outbound calls to public model APIs, and visits to AI SaaS sites). When a
defender runs the five discovery methods that security teams actually have, which surfaces does each one
find, find only partially, or miss, how many benign controls does each one flag, and which misses are
structural (the method's input does not contain the surface) rather than a rule gap?

## Lab environment (pre-registered)

One Docker bridge network (`t1lab`), three containers, everything bound to localhost or to that network.
Nothing is published to the host beyond `127.0.0.1`.

| Container | Image | Role |
|---|---|---|
| `t1-endpoint` | `python:3.12-slim` (local image) plus `curl`, `ca-certificates`, `procps`, osquery 5.24.0 deb; runs as user `dev` (uid 1000, home `/home/dev`) for the workloads, root for osquery | the simulated endpoint; `/home/dev` is a bind mount of `fixtures/endpoint-home/` so Syft on the host and osquery in the container read the same bytes |
| `t1-dns` | `t1-sidecar:local` (`alpine:3.22` + `tcpdump` 4.99.5 + `dnsmasq` 2.91) | the endpoint's only resolver (`--dns <t1-dns ip>`), `--log-queries`, forwarding to Docker Desktop's resolver `192.168.65.7` |
| `t1-cap` | same sidecar image, `--network container:t1-endpoint`, `NET_ADMIN`+`NET_RAW` | `tcpdump -i eth0 -s 0 -w eth0.pcap` (primary, the network-tap view) and `tcpdump -i any -w any.pcap` (secondary, includes loopback) |
| `t1-peer` | `python:3.12-slim` | a second workstation on the lab network that calls the endpoint's runtime ports once, so the network view has a chance at S1/S2 |

Host tools: Ollama 0.20.6 (the host binary `/usr/local/bin/ollama` and `/usr/local/lib/ollama`, bind-mounted
read-only into `t1-endpoint`, serving from a copied store), Syft 1.55.0 (`../ai-artifact-sbom/tools/bin/syft`,
checksum verified there), Zeek 8.0.11 (`zeek/zeek:8.0.11`, pulled 2026-11-09), Docker 29.5.3.

CPU cap: every container runs with `--cpuset-cpus 0-3`; host-side commands run under `nice -n 10 taskset -c 0-3`.
Other benches run concurrently on this host, so timings are secondary and labelled as taken under contention.

## Surfaces planted (`fixtures/endpoint-home/` unless noted)

| ID | Surface | How it is planted | Activity in each run |
|---|---|---|---|
| S1 | Local model runtime | Ollama 0.20.6 as `dev`, `OLLAMA_HOST=0.0.0.0:11434`, `OLLAMA_MODELS=/home/dev/.ollama/models` holding `tinyllama:latest` copied from the host store (blob sha256 `2af3b818…7c6816`, same bytes as R4 T1/T2) | one `POST /api/generate` from loopback (`curl`, 8 tokens, `num_thread: 4`); one `GET /api/tags` and one `POST /api/generate` from `t1-peer`; one `ollama pull t1-lab-does-not-exist:latest` (fails; its purpose is the `registry.ollama.ai` DNS/TLS) |
| S2 | Local OpenAI-compatible server | `openai_compat_stub.py` (stdlib `http.server`, answers `/v1/models` and `/v1/chat/completions` with a fixed JSON body) on `0.0.0.0:8000`. A labelled stand-in for the API shape of vLLM, LM Studio, llama.cpp `server`; no model behind it | one loopback `POST /v1/chat/completions` with `Authorization: Bearer sk-lab-dummy-0000`; one from `t1-peer` |
| S3 | IDE AI extension | Cline `saoudrizwan.claude-dev` 4.1.26 from Open VSX (published 2026-10-26), unpacked to `.vscode/extensions/saoudrizwan.claude-dev-4.1.26/` and listed in `.vscode/extensions/extensions.json` as VS Code writes it | none (static) |
| S4 | MCP client configs | `.cursor/mcp.json` and `.config/Claude/claude_desktop_config.json`, each declaring `filesystem` (`npx -y @modelcontextprotocol/server-filesystem`) and `git` (`uvx mcp-server-git`); env holds `LAB_DUMMY_TOKEN=lab-dummy`, no real secret | none |
| S5 | Browser AI extension | `.config/google-chrome/Default/Extensions/<id>/1.0.0_0/manifest.json`, an authored MV3 manifest named "AI Chat Sidebar (lab fixture)" with `host_permissions` for `https://chatgpt.com/*` and `https://api.openai.com/*`; no code; labelled fixture | none |
| S6 | Python ML packages | venv `ml-venv/` (Python 3.12 from the image) with openai 3.37.0, anthropic 2.3.0, huggingface-hub 2.3.0, safetensors 0.8.0, tokenizers 0.23.3, langchain-core 1.7.0, mcp 2.3.0, gguf 0.19.0 (each the newest release at least two weeks old on 2026-11-09, resolved from PyPI JSON) | none |
| S7 | Model files on disk | `models/tinyllama-1.1b-chat.Q4_0.gguf` (hardlink of the R4 T1 bytes) and `models/all-MiniLM-L6-v2/{config.json,model.safetensors}` (R4 T3, HF revision `1110a243…`); the Ollama store under S1 is scored as S7b "weights in the Ollama store" | none |
| S8 | Outbound calls to public model APIs | `curl` from `dev` with dummy key `sk-lab-dummy-0000` to `api.openai.com/v1/chat/completions`, `api.anthropic.com/v1/messages`, `generativelanguage.googleapis.com/v1beta/models`, `api.mistral.ai/v1/models`, `openrouter.ai/api/v1/models`, `api.groq.com/openai/v1/models`, `api.cohere.com/v2/models`, `huggingface.co/api/models?limit=1`; HTTP errors are expected and irrelevant, the DNS name and TLS SNI are the observable | eight requests per run |
| S9 | AI SaaS visits | `curl -L` with a browser user agent to `https://chatgpt.com/`, `https://claude.ai/`, `https://gemini.google.com/`, `https://www.perplexity.ai/`, `https://copilot.microsoft.com/` | five requests per run |

Benign controls (false-positive bait), planted in the same home and run in the same script:
- C1 local benign server: `python3 -m http.server 8080` serving `/home/dev/public`, one loopback GET and one from `t1-peer`
- C2 benign destinations: `curl` GET to `https://example.com/`, `https://www.wikipedia.org/`, `https://github.com/`, `https://deb.debian.org/`, `https://pypi.org/`
- C3 benign IDE extension: `esbenp.prettier-vscode-12.4.0` (copied from `../ai-artifact-sbom/fixtures/vscode/extensions/`), also in `extensions.json`
- C4 benign browser extension: authored MV3 manifest "Lab Tab Manager (fixture)", `host_permissions` for `https://www.wikipedia.org/*`
- C5 benign packages in the same venv: requests 2.34.2, numpy 2.5.4
- C6 benign files: `documents/notes.txt`, `documents/archive.bin` (4 MB of zeros), `public/index.html`

No real credentials anywhere. No exploit code. The only "attack content" is a dummy API key string and a
fixture manifest; both are labelled.

## Discovery methods and pre-registered analyst rules

The rules are the queries a reasonable analyst would write before seeing this lab; they are fixed here and
not tuned after the run. Any query added after the run is labelled post-hoc.

Shared lists:
- `AI_DOMAINS` (suffix match): openai.com, chatgpt.com, oaistatic.com, anthropic.com, claude.ai,
  generativelanguage.googleapis.com, gemini.google.com, aistudio.google.com, mistral.ai, openrouter.ai,
  groq.com, cohere.com, cohere.ai, huggingface.co, hf.co, perplexity.ai, copilot.microsoft.com,
  registry.ollama.ai, ollama.com, together.ai, together.xyz, replicate.com, fireworks.ai, deepseek.com,
  x.ai, character.ai, poe.com, stability.ai, cursor.sh, cursor.com, codeium.com, windsurf.com, tabnine.com,
  api.githubcopilot.com, copilot-proxy.githubusercontent.com
- `RUNTIME_PORTS`: 11434 (Ollama), 8000 (vLLM default), 1234 (LM Studio), 8080 (llama.cpp server default), 5000,
  7860 (Gradio), 3000 (Open WebUI), 8081
- `RUNTIME_PROCESS_RE` (case-insensitive, on name or cmdline): `ollama|llama[-_.]?(cpp|server)|vllm|lmstudio|\blms\b|koboldcpp|gpt4all|localai|open[-_]?webui|litellm|text-generation|tabby`
- `AI_PKGS`: openai, anthropic, huggingface-hub, huggingface_hub, safetensors, tokenizers, transformers, torch,
  langchain, langchain-core, langchain_core, langgraph, llama-index, llama_index, mcp, gguf, llama-cpp-python,
  llama_cpp_python, litellm, vllm, ollama, google-generativeai, google-genai, cohere, mistralai,
  sentence-transformers, onnxruntime, tiktoken
- `AI_EXT_IDS` (publisher.name): saoudrizwan.claude-dev, continue.continue, github.copilot, github.copilot-chat,
  codeium.codeium, tabnine.tabnine-vscode, amazonwebservices.amazon-q-vscode, google.geminicodeassist,
  rooveterinaryinc.roo-cline, kilocode.kilo-code, anthropic.claude-code, sourcegraph.cody-ai
- `MCP_CONFIG_PATHS`: `/home/%/.cursor/mcp.json`, `/home/%/.config/Claude/claude_desktop_config.json`,
  `/home/%/.claude.json`, `/home/%/.vscode/mcp.json`, `/home/%/.codeium/windsurf/mcp_config.json`,
  `/home/%/.continue/config.yaml`, `/home/%/.gemini/settings.json`
- `MODEL_EXT`: .gguf, .safetensors, .ggml, .pt, .pth, .onnx, .tflite, .h5, .ckpt; `MODEL_DIRS`: `/.ollama/models/blobs/`,
  `/.cache/huggingface/`, `/.lmstudio/models/`

| Method | Instrument | Rules |
|---|---|---|
| M1 Zeek | `zeek -C -r eth0.pcap local LogAscii::use_json=T` in `zeek/zeek:8.0.11`; logs conn, dns, ssl, http | Z1 `ssl.log server_name` suffix in `AI_DOMAINS`; Z2 `dns.log query` suffix in `AI_DOMAINS`; Z3 `http.log` with `id.resp_p` in `RUNTIME_PORTS`, or `uri` starting `/v1/` or `/api/(generate\|chat\|tags\|embeddings\|pull)`, or `user_agent` matching `ollama\|OpenAI\|Anthropic`; Z4 `conn.log` with `id.resp_p` in `RUNTIME_PORTS` and `conn_state` in an established set |
| M2 DNS logs | dnsmasq `--log-queries` output of `t1-dns` | D1 `query[...]` name suffix in `AI_DOMAINS` |
| M3 osquery | `osqueryi --json` inside `t1-endpoint`, osquery 5.24.0 (2026-10-09; 5.24.1 of 2026-10-29 is inside the two-week cooldown) | O1 `processes` where name or cmdline matches `RUNTIME_PROCESS_RE`; O2 `listening_ports JOIN processes` where port in `RUNTIME_PORTS` (reported with the owning process name); O3 `file WHERE path LIKE '/home/%/%%'` filtered to `MODEL_EXT` or `MODEL_DIRS`; O4a `python_packages` with no directory constraint, O4b `python_packages WHERE directory = '/home/dev/ml-venv/lib/python3.12/site-packages'` (the directed form, where the analyst already knows the venv path), both filtered to `AI_PKGS`; O5 `users CROSS JOIN vscode_extensions USING (uid)` filtered to `AI_EXT_IDS`; O6 `users CROSS JOIN chrome_extensions USING (uid)` where name or description matches `(?i)\b(ai\|gpt\|chat\|llm\|copilot\|assistant)\b` or permissions/host match `AI_DOMAINS`; O7a `file` rows for `MCP_CONFIG_PATHS`, O7b `yara` over those paths with a sigrule matching the literal `mcpServers` |
| M4 Syft | `syft dir:fixtures/endpoint-home -o syft-json`, default catalogers, Syft 1.55.0 | S1 packages whose name is in `AI_PKGS`; S2 components typed as a model (`machine-learning-model` or GGUF/safetensors cataloger output); S3 any component whose location is under `.vscode/extensions/saoudrizwan.*`, `.config/google-chrome/`, `.cursor/`, `.config/Claude/`, or `.ollama/` |
| M5 Egress allowlist | a deterministic check (`egress_check.py`) over the destination names seen by the network (Zeek `ssl.log` SNI, `dns.log` query, `http.log` host, and the dnsmasq log) against `ALLOWLIST` = {example.com, wikipedia.org, github.com, debian.org, pypi.org, docker.io, githubusercontent.com, the lab resolver, RFC1918} | E1 any destination not matched by the allowlist is flagged; a surface is "found" when its activity produces a flagged destination |

## Scoring

Per (surface, method) cell, after the three runs:
- **found**: a pre-registered rule fires on the surface's artifact or traffic and the output names the surface
  specifically enough to act on (the runtime by process name or product, the package by name, the model file
  by path or type, the domain by name, the extension by id or name, the config by path and content).
- **partial**: a rule fires but the output is ambiguous or incomplete (a port with a generic process name,
  a file's existence without its content, a generic npm package in place of an extension identity, only the
  network half of a surface that also has a filesystem half, or only one of the surface's components).
- **missed**: no pre-registered rule fires.
- **structural**: marked alongside missed when the method's input cannot contain the surface at all (a pcap has
  no files; a filesystem scan has no traffic; an eth0 tap has no loopback). A miss that is a rule or parser
  gap is marked **rule gap** instead.
- **false positives**: the count of benign controls (C1-C6) on which each method's rules fire, per rule.
- **variance**: the three runs' per-method result sets (set of fired (rule, identifier) pairs) are compared;
  any difference is reported. Wall time per method is recorded as median and CV over the three runs, secondary,
  under contention.

## Hypotheses and what would prove each wrong

- **H1 (network methods and remote surfaces).** Zeek (Z1, Z2), the DNS log (D1) and the egress check (E1) find
  S8 and S9 in all three runs, through the DNS name and the TLS SNI, and structurally miss S3-S7. *Wrong if*
  any S8 or S9 hostname is absent from `ssl.log` SNI or `dns.log` in any run (ECH or a resolver cache would be
  the likely reasons), or if any of the three reports a filesystem surface.
- **H2 (network methods and local runtimes).** On the eth0 capture, Zeek sees S1 and S2 only through the
  `t1-peer` calls, logging them in `http.log` with the `/api/...` and `/v1/...` URIs (Z3), and sees nothing of
  the loopback use; the `-i any` capture shows the loopback calls, which is the secondary result. The
  `ollama pull` attempt gives S1 a DNS/SNI footprint (`registry.ollama.ai`). *Wrong if* Zeek fails to produce
  `http.log` rows for the peer calls on ports 11434 and 8000 (dynamic protocol detection failing on
  non-standard ports), or if the pull produces no `registry.ollama.ai` DNS query.
- **H3 (osquery).** osquery finds S1 (O1 process `ollama`, O2 port 11434 owned by `ollama`), S7 and S7b (O3 by
  extension and by the `.ollama/models/blobs/` path), S3 (O5) and S5 (O6) as typed extension rows, and S4 as
  file presence (O7a, partial) and as content (O7b, found). It finds S6 only with the directed query (O4b); the
  undirected O4a misses the venv. S2 is partial: O2 shows port 8000 owned by `python3`, and O1 does not match
  the stub. *Wrong if* O5 or O6 return no row for the fixture layout, if O4a finds the venv packages, if O1
  matches the stub, or if the `yara` table is unavailable in the 5.24.0 Linux build.
- **H4 (Syft).** Syft finds S6 (all eight AI packages by name, with PURLs) and S7 (both model files as model
  components, the safetensors one under its base-model name as in R4), and misses S7b (Ollama store), S4, S5
  and S2. For S3 it reports at most an npm package named from Cline's `package.json` (partial), never an
  extension identity. *Wrong if* Syft reports the Ollama blobs, types any component as an MCP server or
  extension, or misses any of the eight AI packages.
- **H5 (coverage shape).** The union of the five methods reaches every one of the nine surfaces as found or
  partial, but no single method reaches more than five of nine at "found", and S4 and S5 are reached at
  "found" by osquery alone. *Wrong if* any single method scores six or more "found", or if a second method
  reaches S4 or S5 at "found".
- **H6 (false positives).** Port rules fire on C1 (Z3/Z4 and O2 on port 8080): one false positive each.
  Domain rules (Z1, Z2, D1, E1), package rules (O4, Syft S1), process rule (O1), extension rules (O5, O6) and
  the model-file rule (O3) fire on no benign control. *Wrong if* any of those fires on a control, or if the
  port rules do not fire on C1.
- **H7 (relation to R4).** On the two surfaces shared with R4 (S7 named model files, S7b Ollama store), Syft's
  result reproduces R4 exactly (found T1 by GGUF header name, T3 under the base-model name, nothing in the store),
  and osquery reaches the store that Syft cannot, because a path rule does not need a cataloger. *Wrong if*
  Syft's model components differ from R4's, or if O3 misses the store blobs.

## Repeats, stop rule, deviations

Three full runs. Each run tears the containers down, starts fresh ones, runs the activity script once, stops the
capture, then executes every method against that run's artifacts. Filesystem methods (osquery, Syft) are
expected to be deterministic across runs and are run three times anyway. A method that errors is retried once;
a second failure is recorded as a failure for that run, not retried further. No rule, list or flag changes after
the first run; anything added later is a labelled post-hoc result. Deviations from this document are listed in
RESULTS.md under "Deviations".

## Cost

$0. Local CPU only. Network use: pull `zeek/zeek:8.0.11` and `alpine:3.22` (done before freeze), download
osquery 5.24.0 deb (11.2 MB), Cline 4.1.26 vsix, and about 60 MB of wheels; the live-traffic steps make
about 20 HTTPS requests per run to public hosts, each expected to return an error or a landing page. No paid
API calls; the dummy key cannot authenticate. Nothing about any employer is involved.
