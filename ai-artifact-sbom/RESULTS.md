---
type: benchmark-results
area: R4-ai-artifact-inventory
date: 2026-11-09
hypothesis_served: H-AI-ARTIFACT-INVENTORY-01 (discovery half; PROPOSED, gated-pending, no score; nothing here moves its confidence, that goes through the evidence gate and the owner)
---

# Results: can SBOM and scanner tooling see models, MCP servers and agent extensions?

**Pre-registration:** `PREREGISTRATION.md`, sha256 `040142bded8642001bcabb00cf46a937e9221da2d3714cd2ea58cabe10996da8`,
frozen 2026-11-09T22:55:08Z, frozen by agent before run; not owner-reviewed. The file's hash at write-up time
matches the frozen hash, so it was not edited after the run.

**Rig stamp (§7b; durations here are secondary, the bench is a correctness bench):** Beelink, AMD Ryzen 7 5800H,
14 vCPU / 47 GB to WSL2, kernel 6.6.87.2-microsoft-standard-WSL2, Windows power plan High performance, run
2026-11-09 22:59Z to about 23:10Z. Clock: chrony, `chronyc tracking` checked before the run and reported
`System time` 0.297 s slow of NTP (larger than the methodology's milliseconds guideline, so treat absolute
wall-clock stamps as off by about 0.3 s; every duration was timed with `time.monotonic()`, which the offset does
not affect). Full stamp in `results/rig.txt`.

**Tools as run:** Syft 1.55.0, Grype 0.121.0 (DB schema v6.1.10, built 2026-11-08T06:19:57Z), Trivy 0.76.0
(DB v2 updated 2026-11-09 19:03:15 UTC), ai-bom 3.6.0 (Trusera), cyclonedx-bom 8.0.1. Release binaries
sha256-verified against each release's checksums file (`tools/checksum-verify.txt`); cosign signatures not
checked. Node 22.23.4, npm 10.9.9, Python 3.12.3, Ollama 0.20.6 (source of the TinyLlama blob).

**Runs:** 3 runs × 17 scan targets (8 fixtures, 8 variants, the whole tree) × 6 to 7 tool modes = 315 tool
invocations, 0 failures, 0 retries (`results/runlog.jsonl`). Every (tool, fixture) pair produced an identical
normalized component set (name, version, type, PURL) in all three runs: 88 of 88 pairs, so every number below
holds across runs and is reported once.

## Headline

Across every tool, five of the six AI artifacts surface in some form, but only two (the named GGUF file and
the safetensors directory) surface *as* AI artifacts, through Syft's model catalogers and through ai-bom, and
neither carries a usable PURL (Syft gives none, ai-bom gives a made-up `pkg:pypi/<filename>`), a CPE or an
advisory. Two scoring qualifiers apply to those counts (see "Verification corrections" at the end): the
five-of-six count needs Trivy in `rootfs` mode, which was not in the pre-registration (Trivy's default `fs` mode
plus the other tools give four of six), and the safetensors directory counts only under a lenient
"model component at the target's path" rule added at scoring, because Syft names it after its base model; under
the pre-registered name match the counts are four of six found (three without `rootfs`) and one of six found as
an AI artifact. The two MCP servers are seen well, because they are ordinary
npm and PyPI packages: both carry a PURL and every OSV-listed advisory matched (2 of 2 and 4 of 4) through
Grype and through Trivy in `rootfs` mode, yet no tool marks either as an MCP server. The Ollama store, which is
how models actually sit on a host that runs Ollama, was seen by no tool, and the VS Code extension surfaced
only as a mislabelled npm package. On re-registration, none of the default scans surfaced a same-name,
same-version swap of the npm server's code, the pip server's code or the extension's publisher (V5, V7, V8),
which is the takedown-half failure the hypothesis predicts, though only as a local simulation.

## Discovery and identifiers (run 1; identical in runs 2-3)

Found = a component whose name identifies the target (strict) or a model component located at the target's
path (lenient, used only where the strict name match failed). "As AI" = typed as a model / machine-learning-model.

| Target | Syft | Trivy `fs` | Trivy `rootfs` | ai-bom | cyclonedx-py |
|---|---|---|---|---|---|
| T1 TinyLlama GGUF, named file | **found as AI**: `TinyLlama`, version UNKNOWN, no PURL/CPE, file sha256 recorded | not found | not found | found as AI: `tinyllama-1.1b-chat.Q4_0.gguf`, PURL `pkg:pypi/tinyllama-1.1b-chat.q4-0.gguf`, no digest | n/a |
| T2 same weights in Ollama store | not found | not found | not found | not found | n/a |
| T3 all-MiniLM-L6-v2 safetensors | found as AI (lenient): named `MiniLM-L6-H384-uncased` (the base model, from `config.json`), no PURL/CPE, sha256 of both files recorded | not found | not found | found as AI (lenient): `model.safetensors`, PURL `pkg:pypi/model.safetensors`, no digest | n/a |
| T4 npm MCP server | found as npm library, `pkg:npm/%40modelcontextprotocol/server-filesystem@2025.3.28`, CPE (`syft-generated`), lockfile `integrity` | found, same PURL, no CPE, no digest | found, same | not found | n/a |
| T5 pip MCP server | found as python library, `pkg:pypi/mcp-server-git@2025.7.1`, CPE (`syft-generated`), sha256 of `METADATA` and `RECORD` only | **not found** (fs mode does not read installed site-packages; it also found 0 packages in the pip control) | found, same PURL, no digest | not found | found, same PURL |
| T6 VS Code extension | not found (0 components in the fixture) | not found | found as **npm** `pkg:npm/prettier-vscode@12.4.0` plus `@12.2.0` from a nested `legacy/package.json` | not found | n/a |
| **Found (strict / lenient)** | 3 / 4 of 6 | 1 / 1 of 6 | 3 / 3 of 6 | 1 / 2 of 6 | 1 of 1 applicable |
| **Found as AI artifact** | 2 of 6 | 0 | 0 | 2 of 6 | 0 |

Trivy's CycloneDX output in `fs` mode matched its JSON output (T4 only). Union over all tools and modes: 5 of 6
found in some form, 2 of 6 found as AI artifacts, T2 found by none. Without the non-pre-registered Trivy `rootfs`
mode the union is 4 of 6 (T6 drops out); under the pre-registered strict name match it is 4 of 6 with `rootfs`
and 3 of 6 without, and 1 of 6 (T1) as an AI artifact. The lenient column is a scoring rule added after the run.

Three identity details that matter more than the counts:
- **The CPEs are guesses.** Both MCP-server CPEs are marked `syft-generated` (for example
  `cpe:2.3:a:anthropic\,_pbc__project:python-mcp-server-git:2025.7.1`), not taken from the NVD dictionary. Grype's
  matches on T4 and T5 came through the GHSA/PURL path (`exact-direct-match`), so the CVE attach worked without
  a real CPE, which is the ecosystem-package path and not the CPE path the hypothesis describes.
- **ai-bom's PURLs are not identities.** Every model it found got `pkg:pypi/<filename>`, which puts a weights file
  into the PyPI namespace under its filename; the MCP servers it found from config (post-hoc E1 below) got PURLs
  with spaces, such as `pkg:pypi/git (mcp server)`. Its `provider` field comes from substrings of the file path:
  `weights.bin` was attributed to "Anthropic" because the scratch path contains `claude-1000`, and T3 to
  "HuggingFace" because the folder is `models-hf` (`ai_bom/scanners/model_file_scanner.py`, path-substring
  heuristic; corrected at verification: the T3 "HuggingFace" label comes from the scanner's extension table,
  which maps every `.safetensors` file to HuggingFace, not from the `models-hf` folder name; only the `.bin`
  attribution goes through the path-substring guess). The "Anthropic" label is a fixture-path artefact, which is the point: the attribution is not evidence-based.
- **The extension's npm label collides with a real npm name.** Trivy reports the Open VSX extension
  `esbenp.prettier-vscode` as `pkg:npm/prettier-vscode`, dropping the publisher, and the npm registry holds an
  unrelated package called `prettier-vscode` (version 1.0.0, checked 2026-11-09). An advisory filed against that npm
  package would attach to the extension, and an advisory filed against the extension has no ecosystem to land in.

## Advisory attach

| Target | Expected (OSV) | Grype over Syft | Trivy `fs` | Trivy `rootfs` |
|---|---|---|---|---|
| T4 npm MCP server | 2 | **2 of 2** | 2 of 2 | 2 of 2 |
| T5 pip MCP server | 4 | **4 of 4** | 0 of 4 (package not seen) | 4 of 4 |
| T1, T2, T3 models | none listed | 0 | 0 | 0 |
| T6 extension | none listed | 0 | 0 | 0 |
| Control `lodash@4.17.15` | ≥1 | 5 | 6 | 6 |
| Control `requests==2.19.1` | ≥1 | 5 | 0 (fs mode) | 5 |

Controls pass for Grype and Trivy `rootfs`; Trivy `fs` is void for the pip rows because its mode does not read
installed packages, which is documented Trivy behaviour, so the T5 miss is a mode choice an operator has to know
to make, not a matcher failure. The model rows are a structural zero rather than a measured one: the model
components have no PURL or CPE, so there is nothing for a matcher to key on.

## Rename and re-registration variants (default configs)

"Surfaced" = an SBOM diff of the variant against the original would show a difference in the target component
(name, version, PURL or digest).

| Variant | Syft | Trivy (`fs`/`rootfs`) | ai-bom |
|---|---|---|---|
| V1 GGUF renamed `weights.bin` | **lost** (cataloger only reads `*.gguf`) | not seen either way | found as `weights.bin` (".bin over 1 MB" heuristic), no digest, provider "Anthropic" |
| V2 GGUF renamed `totally-safe-assistant.gguf` | same component (`TinyLlama`, name from the GGUF header) and same sha256, so it links back to T1 | not seen | new component named after the file, no digest, nothing links it to T1 |
| V3 Ollama re-tag `totally-safe-assistant` | not seen (nor was T2) | not seen | not seen |
| V4 one byte flipped in tensor data | **surfaced** by the file sha256 only; name, version unchanged | not seen | not surfaced (no digest) |
| V5 npm server code changed, same name+version+lock | not surfaced (lock `integrity` unchanged) | not surfaced | not seen |
| V6 lock `resolved`+`integrity` changed | **surfaced** via the lock `integrity` value in Syft JSON | not surfaced | not seen |
| V7 pip server code changed, `RECORD` unchanged | not surfaced (digests cover `METADATA`/`RECORD`, not code) | not surfaced (`rootfs`) | not seen |
| V8 extension `publisher` changed | not seen (nor was T6) | not surfaced (`rootfs`: same `pkg:npm/prettier-vscode@12.4.0`) | not seen |

Against H6's prediction, every default scan missed V5, V7 and V8. Syft surfaced the two variants where a
recorded digest changed (V4 file hash, V6 lockfile hash) and kept a renamed `.gguf` tied to its original by
header name and hash (V2), which is the digest-bound identity the hypothesis says the program needs, available
today for named GGUF and safetensors files only.

## Post-hoc exploratory runs (not pre-registered; labelled; 3 runs each, identical across runs)

- **E1, MCP client config.** ai-bom found nothing for installed MCP packages, and its scanner list suggested it
  reads client configs, so a `.vscode/mcp.json` and a `claude_desktop_config.json` declaring both servers
  (`fixtures-posthoc/E1-mcp-config/`) were scanned. ai-bom reported 4 `service` components for the 2 servers
  (one per config file, under two naming styles), with no version and no link to the package or its
  advisories, even though the pinned versions sit in the `args`. Syft and Trivy reported nothing. So the one tool
  that labels MCP servers as MCP servers does it from config text, and the tools that see the package and its
  CVEs do not know it is an MCP server; nothing in this set joins the two.
- **E2, Syft hashing every file** (`SYFT_FILE_METADATA_SELECTION=all`, non-default). The file inventory then
  surfaced V5 (`dist/index.js`), V7 (`mcp_server_git/server.py`) and V8 (`package.json`) as single-file digest
  differences against the originals, out of 2,310, 2,896 and 89 hashed regular files (2,516, 3,348 and 105
  file-inventory entries including directories; corrected at verification from "2,516, 3,348 and 104 hashed
  files"). For V8 the single-file result holds only after aligning the two trees: the original fixture also
  holds `vsix/` and nests the extension under `extensions/`, so a raw path diff shows 211 differences until the
  `extensions/` prefix is stripped and `vsix/` excluded. The package components themselves
  stayed identical, and the extension still produced 0 package components, so the swap is visible only to someone
  who diffs whole file inventories against a known-good baseline. V3 (Ollama re-tag) showed as a changed manifest
  path with identical blob hashes, which is detectable as "same weights, new name" only by a consumer that reads
  Ollama manifests, and none of these tools does.

## Hypotheses

| | Prediction | Outcome |
|---|---|---|
| H1 | Syft finds T1, T3, not T2 | **Supported for T1 and T2; T3 only under the lenient path rule added at scoring.** Syft names T3 `MiniLM-L6-H384-uncased` (the base model in `config.json`), so by the pre-registered name match it misses T3, which is H1's stated falsifier |
| H2 | Trivy finds none of T1-T3 | **Supported** |
| H3 | Syft and Trivy find T4, T5 with PURL, not as MCP; all advisories match | **Wrong as pre-registered for Trivy**: its default `fs` mode misses T5 and its 4 advisories. Holds for Syft+Grype, and for Trivy in `rootfs` mode, which was not in the pre-registration |
| H4 | No tool reports T6 as a VS Code extension | **Supported**; Trivy `rootfs` reports it as an npm package under a colliding name |
| H5 | No model gets a CPE or advisory | **Supported** (and no Syft model component has a PURL) |
| H6 | V5, V7, V8 not surfaced; V1 lost; V4 only with a digest | **Supported for V5, V7, V8 and V4; partly wrong on V1**, which Syft lost but ai-bom found by a size heuristic |
| H7 | ai-bom, exploratory | Finds model files by extension or size, names them by filename, attaches invalid PURLs, guesses provider from path, misses Ollama storage and installed MCP packages; sees MCP servers only in client configs (E1) |

For H-AI-ARTIFACT-INVENTORY-01's discovery half, this is first-party evidence against the null on one host and
one fixture set: the tools reach MCP servers *as packages* closely enough (PURL plus every listed advisory), which
is a point for the null on that artifact class and worth stating plainly, but they do not reach model weights in
Ollama's store, do not attach any identifier a matcher can use to model weights anywhere, do not see the extension
as an extension, and do not surface same-name re-registration without a non-default whole-file baseline.

## Timing (secondary)

Whole-tree scan (about 2.2 GB on disk, 3 runs, monotonic): Syft median 3.26 s (CV 45.6%), Grype 2.59 s (21.5%),
Trivy `fs` 0.45 s (30.2%), Trivy `rootfs` 0.50 s (30.8%), ai-bom 5.05 s (21.3%). The CVs are high because run 1
was cold-ish and the durations are short; no timing comparison is claimed. Per-pair figures are in
`results/scores.json`.

## Limits

- One host, one fixture set of six targets, one version of each tool, default configs except the labelled E2.
  Newer releases exist (Syft 1.57.1, Grype 0.121.3, Trivy 0.76.2) and were skipped under the two-week cooldown;
  their model or extension support may differ.
- Re-registration is simulated by editing local files; no marketplace, registry or hub was touched, so the
  takedown half (identity retirement on removal) is not tested.
- The CVE-attach result for MCP servers rests on two packages chosen *because* they have published advisories;
  most MCP servers have none, so "every listed advisory matched" does not mean MCP servers are well covered by
  advisories.
- ai-bom is a vendor tool (Trusera); its feature list is Tier B and its efficacy as measured here is first-party.
  Its provider attribution was influenced by this lab's scratch path, which a real deployment would not share,
  though a path-substring heuristic will misfire on other paths in the same way.
- No CycloneDX-project ML-BOM generator that reads model files exists on PyPI as of 2026-11-09, so the "CycloneDX
  ML-BOM generator" arm is ai-bom's CycloneDX output plus Syft's `machine-learning-model` components.
- Trivy was run in `fs` (its default for a directory) and `rootfs`; Docker image scanning, which is how many
  teams run these tools, was not tested.

## Verification corrections (2026-11-09, independent re-run; detail in `VERIFICATION.md`)

An independent re-run of all 315 scans (`verify/`) reproduced every component set, advisory match and
variant outcome above exactly (88 of 88 tool and fixture pairs, 17 of 17 Grype match sets and 34 of 34 Trivy
vulnerability sets identical across all six runs). These corrections were made in place:
- E2 file counts corrected to hashed regular files (2,310, 2,896, 89), with the V8 tree-alignment caveat.
- T3's "HuggingFace" provider label comes from ai-bom's extension table, not from the folder name.
- The headline now credits ai-bom as well as Syft for the two AI-typed finds, and states the counts under the
  pre-registered strict name match and without the non-pre-registered Trivy `rootfs` mode.
- H1 and H3 outcomes restated against the pre-registered rules: H1 holds for T3 only under the lenient rule
  added at scoring, and H3 is wrong as pre-registered for Trivy (default `fs` mode misses T5).

Recorded deviations from the pre-registration (not fixable after the fact): Trivy `rootfs` and the Trivy
CycloneDX output were not in the instrument table; the lenient match rule and `score.py` itself were written
after the run; cyclonedx-bom 8.0.1 was published 2026-11-04, inside the two-week cooldown the pre-registration
sets; the pre-registered wheel hashes were not recorded at install (recorded at verification in
`tools/checksum-verify.txt`, matching PyPI and the installed RECORD files); the fixture tree holds about 2.2 GB
of distinct bytes, not the pre-registered 1.3 GB, because the T2 blob and V4 are copies. Timing in the re-run
again showed CVs of 19-61% on the whole-tree scans with different medians (for example ai-bom 3.55 s vs
5.05 s), which supports making no timing claim.
