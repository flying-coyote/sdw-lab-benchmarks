# R4 AI artifact inventory (ai-artifact-sbom)

## What it measures

Can Syft, Grype, Trivy and a CycloneDX AI-BOM generator (ai-bom 3.6.0) see model weights, MCP servers and a
VS Code extension, attach identifiers and advisories, and tell a renamed or re-registered copy from the original?

## Result

Five of the six AI artefacts surfaced in some form, but only the named GGUF file and the safetensors directory
surfaced as AI artefacts, neither with a usable PURL, CPE or advisory; the two MCP servers were seen well as ordinary
npm and PyPI packages with every OSV-listed advisory matched, yet no tool marked either as an MCP server, the Ollama
store was seen by no tool, and no default scan surfaced a same-name, same-version swap (`RESULTS.md`, Headline). These
are measured outcomes of real tools on public fixtures. Two qualifiers in the headline matter: five of six needs
Trivy in `rootfs` mode, which was not pre-registered, and the safetensors directory counts only under a lenient
path rule added at scoring, so under the pre-registered name match the counts are four of six found (three without
`rootfs`) and one of six found as an AI artefact.

## What would have made it fail

Each hypothesis in `PREREGISTRATION.md` names a prediction that the tools could have contradicted, and H3 was wrong as
pre-registered for Trivy while H1 and H6 held only in part. Two benign controls sit beside the six artefacts, and the
eight rename and re-registration variants each have a stated expected outcome.

## Pre-registration

`PREREGISTRATION.md`, frozen by agent before the run and not owner-reviewed. Its sha256 in `prereg.sha256`
(`040142bd…6da8`) still matches, and `prereg.frozen-at` records 2026-11-09T22:55:08Z, before the scans at 22:59Z to
about 23:10Z that `RESULTS.md` reports. `fixture-sha256.txt` lists the fixture tree by relative path, and the fixtures
are not committed, so those hashes can be checked only against a rebuilt tree. Recorded deviations, including the
lenient match rule and `score.py` written after the run, Trivy `rootfs` mode, and a cyclonedx-bom release inside the
pre-registered two-week cooldown, are listed at the end of `RESULTS.md`.

## Reproduce

`bash build_fixtures.sh && .venv/bin/python -I run_scans.py && .venv/bin/python -I score.py`.

`build_fixtures.sh` builds `fixtures/`: the TinyLlama GGUF from the local Ollama store, all-MiniLM-L6-v2 at a pinned
Hugging Face revision, two MCP servers with known advisories, prettier-vscode 12.4.0 from Open VSX, two controls and
eight variants. `run_scans.py` runs every tool against every fixture three times, and `score.py` computes
`results/scores.json`. The fixtures (about 2.2 GB), the vulnerability database caches, the pinned release binaries
and `checksum-verify.txt` under `tools/`, the raw scanner output under `results/raw/` and the post-hoc output under
`results/posthoc/` are gitignored, so `score.py` cannot be re-run from this tree; `results/scores.json`,
`results/runlog.jsonl` and `results/rig.txt` are committed. `posthoc.sh` runs the labelled post-hoc E1 (MCP client
config) and E2 (Syft hashing every file); `fixtures-posthoc/E1-mcp-config/` is the E1 input.

## Results

- `RESULTS.md` is the entry point: discovery and identifiers, advisory attach, rename and re-registration variants,
  post-hoc runs, hypotheses, limits, and the verification corrections.
- `results/scores.json` and `results/runlog.jsonl` hold the scored output.
- `posthoc-ollama-api-digest-2026-11-16.md` and `posthoc-ollama-api-show-2026-11-16.md` are post-hoc, read-only
  observations made a week after the run, not pre-registered and agent-run, on what Ollama's own API exposes as a
  content digest; the digest file finds that `/api/tags` reports the manifest's hash, not the weights blob's. Neither
  file changes a result in `RESULTS.md`.
- `VERIFICATION.md` is the independent re-run of all 315 scans (VERIFIED-WITH-FIXES). Under `verify/`,
  `scores.orig.json` is a superseded copy of the scores from before the verifier's fixes, and the rest is the
  verifier's own run (`scores.verify.json`, `runlog.jsonl`, the verify scripts and downloaded wheels); none of them is
  the current result.

## Versions and pins

`requirements.txt` pins every Python dependency with `==`. Syft 1.55.0, Grype 0.121.0 and Trivy 0.76.0 ran as pinned
release binaries, with versions and database builds in the `RESULTS.md` instrument line; the binaries themselves are
not committed.

## Evidence tier and limits

`RESULTS.md` states no tier letter for the run; it notes that ai-bom is a vendor tool whose feature list is Tier B
and whose efficacy as measured here is first-party. One host, one fixture set, default configurations except the
labelled post-hoc runs, and re-registration simulated locally rather than observed on a real registry. See Limits in
`RESULTS.md`.

## Corrections

- 2026-11-09: verification corrections are listed in their own section at the end of `RESULTS.md`.
- 2026-11-17: this README was restructured to the lab layout, now names the two 2026-11-16 post-hoc files, which no
  other file in the folder cited, and labels the superseded copies under `verify/`.
