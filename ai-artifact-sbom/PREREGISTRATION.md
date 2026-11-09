---
type: benchmark-preregistration
area: R4-ai-artifact-inventory
created: 2026-11-09
status: frozen by agent before run; not owner-reviewed
review_reference: ~/project1/02-projects/securitydataworks/SITE-REVIEW-2026-11-09.md section 5, row R4
hypothesis_served: H-AI-ARTIFACT-INVENTORY-01 (PROPOSED, gated-pending, no score); this bench is a first-party leg for the discovery half only
---

# Pre-registration: can SBOM and scanner tooling see models, MCP servers and agent extensions?

## Question

When a defender points the ordinary SBOM and vulnerability-scanning tools at a host directory holding
AI supply-chain artifacts (model weights in three on-disk layouts, an npm MCP server, a pip MCP server and
a VS Code extension), which of those artifacts show up as components, with what identifier (PURL, CPE,
content digest), whether a known advisory is attached, and whether a renamed or re-registered copy of an
artifact is told apart from the original.

This tests the discovery half of H-AI-ARTIFACT-INVENTORY-01. The takedown half (marketplace name reuse) is
simulated locally by the re-registration variants below; no marketplace is touched.

## Instruments (exact versions, pinned before run)

| Tool | Version | Source | Integrity |
|---|---|---|---|
| Syft (SBOM) | v1.55.0 (built 2026-10-19) | github.com/anchore/syft release binary, linux_amd64 | sha256 checked against the release `checksums.txt` (`tools/checksum-verify.txt`); cosign signature not checked |
| Grype (CVE match over the Syft SBOM) | v0.121.0 | github.com/anchore/grype release binary | same |
| Trivy (SBOM + CVE match) | v0.76.0 (2026-10-14) | github.com/aquasecurity/trivy release binary, Linux-64bit | same |
| ai-bom (Trusera, CycloneDX AI-BOM generator for Python) | 3.6.0 (PyPI, 2026-03-15) | pip, pinned in `requirements.txt` | pip hash of the wheel recorded |
| cyclonedx-bom (`cyclonedx-py`, the CycloneDX project's Python env SBOM generator) | 8.0.1 | pip, pinned | same |

Versions were chosen as the newest release at least two weeks old on 2026-11-09 (cooldown), so Syft
v1.56/1.57, Grype v0.121.1-3 and Trivy v0.76.1/0.76.2 exist and are deliberately not used. Vulnerability
databases (Trivy DB, Grype DB) are downloaded once at first run, their build timestamps recorded, and every
later run uses `--skip-db-update` / `GRYPE_DB_AUTO_UPDATE=false` so all three runs see the same DB.

ai-bom is a vendor tool (Trusera); what it detects is Tier B (the vendor describes its own feature), and
any claim about how well it works is measured here rather than taken from its README (Tier C).

No ML-BOM generator from the CycloneDX project itself exists on PyPI as of 2026-11-09 (checked names:
`aibom-generator`, `owasp-aibom-generator`, `aibom`, `mlbom`, `cdx-mlbom`); `cyclonedx-python-lib` 11.12.0 has
the ML-BOM data model but no generator that reads model files. The OWASP GenAI AIBOM generator is a web/HF-API
service, not a local Python CLI, and is out of scope (needs network calls per model).

## Fixture set (pre-registered; `fixtures/`)

Targets, six AI artifacts:

| ID | Artifact | Layout | Licence | Ground truth identity |
|---|---|---|---|---|
| T1 | TinyLlama 1.1B chat GGUF (Ollama `tinyllama:latest`, 637,699,456 bytes) | `models-gguf/tinyllama-1.1b-chat.Q4_0.gguf` (named file) | Apache-2.0 | sha256 `2af3b818…7c6816` |
| T2 | same weights in Ollama's own store | `ollama-store/models/manifests/registry.ollama.ai/library/tinyllama/latest` + `blobs/sha256-…` (extensionless blobs, as Ollama writes them) | Apache-2.0 | manifest digest + same blob sha256 |
| T3 | sentence-transformers/all-MiniLM-L6-v2 | `models-hf/all-MiniLM-L6-v2/{config.json,model.safetensors}` at HF revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` | Apache-2.0 | file sha256 recorded at download |
| T4 | npm MCP server `@modelcontextprotocol/server-filesystem@2025.3.28` | `mcp-npm/` with `package-lock.json` + `node_modules`, installed `--ignore-scripts` | MIT | OSV: GHSA-hc55-p739-j48w (CVE-2025-53110), GHSA-q66q-fx2p-7w4m (CVE-2025-53109), both fixed in 2025.7.1 |
| T5 | pip MCP server `mcp-server-git==2025.7.1` | `mcp-pip/venv/` (site-packages with dist-info) | MIT | OSV: GHSA-5cgr-j3jf-jw3v (CVE-2025-68143), GHSA-9xwc-hfwc-8w59 (CVE-2025-68144), GHSA-j22h-9j4x-23w5 (CVE-2025-68145), GHSA-vjqx-cfc4-9h6v (CVE-2026-27735) |
| T6 | VS Code extension `esbenp.prettier-vscode-12.4.0` from Open VSX | `vscode/extensions/esbenp.prettier-vscode-12.4.0/` (unpacked as VS Code installs it) plus the raw `.vsix` under `vscode/vsix/` | MIT | Open VSX sha256 checked at download |

Positive controls (prove the CVE matcher works in the same run): `lodash@4.17.15` (npm, `controls-npm/`)
and `requests==2.19.1` (pip, `controls-pip/venv`), both carrying well-known advisories.

Rename and re-registration variants (`variants/`):

| ID | What changes | Simulates |
|---|---|---|
| V1 | T1 bytes copied to `weights.bin` (extension dropped) | a model renamed to dodge a filename glob |
| V2 | T1 bytes copied to `totally-safe-assistant.gguf` | same weights, new name |
| V3 | Ollama manifest re-tagged `library/totally-safe-assistant/latest` pointing at the T2 blob | model re-registered under a new name |
| V4 | T1 copy with one byte flipped inside the tensor data, filename unchanged | weights swapped under the same name |
| V5 | T4 tree with `dist/index.js` modified, `package.json` and lockfile unchanged | re-registered npm name serving different code, same name+version |
| V6 | T4 lockfile with `resolved` URL and `integrity` changed to another tarball's value | re-published under the same name+version from a new source |
| V7 | T5 venv with `mcp_server_git/server.py` modified, dist-info `RECORD` unchanged | tampered pip package, same name+version |
| V8 | T6 directory with `package.json` `publisher` changed to `evil-publisher`, directory name unchanged | extension re-registered by a new publisher |

## Metrics

Each tool scans each fixture directory separately and also the whole `fixtures/` tree once per run.

1. **Discovery rate**: of the six targets, how many each tool reports as a component whose name identifies
   the artifact (case-insensitive match on the ground-truth name). Reported two ways: *found at all*, and
   *found as an AI artifact* (typed as a model, or marked MCP server / extension) rather than as a generic
   library or file.
2. **Identifier attach rate**: for each discovered target, whether the component carries a PURL, a CPE, and
   a content digest (sha256 of the artifact, in any field).
3. **Advisory attach**: for T4 and T5, how many of the OSV-listed advisories each matcher (Grype over Syft,
   Trivy) reports; for T1-T3 and T6, any advisory at all. Controls must match at least one advisory each or
   the run is void for this metric.
4. **Variant detection**: for V1-V8, (a) still discovered, (b) output differs from the original's output in a
   way a diff of two SBOMs would surface (name, version, PURL, or digest), (c) whether that difference is a
   content digest (the identity H-AI-ARTIFACT-INVENTORY-01 says is needed) or only a name.
5. **Repeatability**: three runs per (tool, fixture). The normalized component set (name, version, type,
   PURL, sorted) is hashed; report whether the three hashes agree. Wall time median and CV are recorded as a
   secondary number only (this is a correctness bench, not a latency bench).

## Hypotheses and what would prove each wrong

- **H1 (models, Syft)**: Syft v1.55.0's `gguf-cataloger` and `safetensors-cataloger` find T1 and T3, but not
  T2, because the Ollama store holds extensionless blobs. *Wrong if* Syft reports a tinyllama/llama model
  component for the T2 directory, or misses T1 or T3.
- **H2 (models, Trivy)**: Trivy v0.76.0 reports none of T1-T3. *Wrong if* it reports any model component.
- **H3 (MCP servers)**: Syft and Trivy both find T4 and T5 as ordinary npm/PyPI packages with a PURL, neither
  marks them as MCP servers, and the matchers attach all OSV-listed advisories (2 of 2 for T4, 4 of 4 for T5).
  *Wrong if* either server is missed, carries no PURL, or fewer than all listed advisories match.
- **H4 (extension)**: neither Syft nor Trivy reports T6 as a VS Code extension (no `pkg:vscode`-style identity);
  at most its bundled `package.json` surfaces as an npm package. *Wrong if* either reports an extension
  component with the publisher.name identity.
- **H5 (identifiers on models)**: no model component (T1-T3) gets a CPE or an advisory match. *Wrong if* any does.
- **H6 (variants)**: name-and-version SBOMs do not surface V5, V7 or V8 (same name and version, different
  bytes or publisher), and V1 (`.bin`) drops out of discovery. V4 is surfaced only if the tool records a
  file digest. *Wrong if* a default-config scan surfaces V5, V7 or V8 in an SBOM diff, or finds V1.
- **H7 (ai-bom, exploratory)**: no directional prediction. ai-bom scans source code and config for AI usage;
  report what it finds against T1-T6 and the variants.

The null for H-AI-ARTIFACT-INVENTORY-01's discovery half ("existing tooling reaches these artifacts closely
enough") is supported here if, across tools, all six targets are found with a stable identity and the
variants are surfaced; it is weakened, not falsified, by partial discovery, because one host and one
fixture set cannot speak for a fleet.

## Stop rule

Three runs per (tool, fixture). A failed run is retried once; a second failure is recorded as a failure, not
re-tried further. No tool flags are tuned after seeing results; any non-default flag run (for example Syft
`--select-catalogers` or file-digest options) is reported as a separate, labelled result after the default
result.

## Cost

$0. Local CPU on the Beelink (Ryzen 7 5800H, WSL2). Network is used only to download the pinned tools, the
fixtures (about 120 MB downloaded; the TinyLlama weights are copied from the local Ollama store and V1-V3 are hardlinks, so the tree holds about 1.3 GB of distinct bytes) and the free vulnerability databases. No paid API calls.
