---
type: benchmark-verification
area: R4-ai-artifact-inventory
date: 2026-11-09
verdict: VERIFIED-WITH-FIXES
---

# Verification: R4 AI artifact inventory

**Verdict: VERIFIED-WITH-FIXES.** Every measured number reproduces exactly in an independent re-run. Four
claims in `RESULTS.md` were corrected in place (one factual count, one wrong mechanism, two places where the
hypothesis outcomes or headline counts leaned on scoring rules or a Trivy mode the pre-registration did not
name), and five deviations from the pre-registration are recorded below. No hypothesis outcome flips from
supported to unsupported on the evidence, but H1 and H3 are now stated against the pre-registered rules, which
makes each partly wrong as written.

## What was checked and how

Machine and conditions match the original: Beelink, WSL2, kernel 6.6.87.2, same pinned binaries and `.venv`,
same local vulnerability DBs with updates disabled (Grype DB v6.1.10 built 2026-11-08T06:19:57Z; Trivy DB v2
updated 2026-11-09 19:03:15 UTC, downloaded 22:57:16Z). Start stamp in `verify/rig-verify.txt`.

| Check | Command / artefact | Result |
|---|---|---|
| Pre-registration hash | `sha256sum PREREGISTRATION.md` vs `prereg.sha256` | match, `040142bd…6da8`, still unchanged after verification edits |
| Pre-registration written before the run | file mtimes (local -0500) | `PREREGISTRATION.md` 17:55:08 (= 22:55:08Z, matches `prereg.frozen-at`) → `build_fixtures.sh` 17:55:30 → fixtures 17:56 → `run_scans.py` 17:59:05 → first raw output 17:59:40 → `score.py` 18:06:57. Order holds; mtimes are self-reported, not a third-party timestamp |
| Tool versions | `syft version`, `grype version`, `trivy --version`, `pip list` | Syft 1.55.0, Grype 0.121.0, Trivy 0.76.0, ai-bom 3.6.0, cyclonedx-bom 8.0.1, as stated |
| Release integrity | release `checksums.txt` vs tarballs; tarball `syft` vs `tools/bin/syft` | all three OK; binary matches its tarball |
| Wheel integrity | `pip download --no-deps` + sha256 vs PyPI JSON; wheel RECORD vs installed RECORD | both match (added to `tools/checksum-verify.txt`, see deviation D4) |
| Fixture integrity | `sha256sum -c fixture-sha256.txt` | 16 of 16 OK |
| Scoring reproduces from raw | re-ran `score.py` on original raw | `results/scores.json` byte-identical |
| Full re-run | `verify/run_scans_verify.py` (copy of `run_scans.py`, output dir changed only) | 315 invocations, 0 non-zero exits, 0 retries; `verify/scores.verify.json` identical to the original in discovery, advisories, controls, variants, repeatability, failures |
| Cross-session reproduction | component-set hash per (tool, fixture), original runs 1-3 vs verify runs 1-3 | 88 of 88 pairs identical across all six runs; Grype match sets 17 of 17 and Trivy vuln sets 34 of 34 identical across six runs |
| Post-hoc E1/E2 | `verify/posthoc_verify.sh` (one run) | all 11 outputs identical to the originals |
| Spot checks of raw claims | CPE strings, Grype `matchDetails`, ai-bom PURLs and provider, Trivy rootfs on T6, Syft T5 digest locations, npm registry `prettier-vscode` | all as described, except the two items fixed below |
| No CycloneDX-project ML-BOM generator on PyPI | PyPI JSON API for the five names the prereg lists | all five return 404, as stated (absence under other names not checked) |
| Timing (secondary) | whole-tree medians/CV, verify vs original | CVs 19-61% in verify vs 21-46% originally; medians differ by up to 34% (Trivy `rootfs` 0.33 s vs 0.50 s; ai-bom 3.55 s vs 5.05 s). Consistent with the original's refusal to claim any timing comparison |

## Fixes made in place (`RESULTS.md`)

1. **E2 file counts (factual).** "out of 2,516, 3,348 and 104 hashed files" was wrong: 2,516 and 3,348 are
   Syft file-inventory entries including directories, and 104 matches nothing in the output. Hashed regular
   files are 2,310, 2,896 and 89 (inventory entries 2,516, 3,348, 105). Corrected.
2. **E2 V8 caveat (claim exceeds evidence).** The V8 "single-file difference" holds only after aligning trees:
   the `vscode` fixture holds `vsix/` and nests the extension under `extensions/`, while V8 has it at the root,
   so a raw path diff shows 211 differences. After stripping the prefix and excluding `vsix/`, exactly one file
   (`package.json`) differs in all three runs. Caveat added.
3. **T3 provider mechanism (factual).** RESULTS said ai-bom labelled T3 "HuggingFace" because the folder is
   `models-hf`. `ai_bom/scanners/model_file_scanner.py` line 39 maps every `.safetensors` file to HuggingFace by
   extension; the path-substring guess (lines 188-217) is used only for `.bin` files. The "Anthropic" on
   `weights.bin` is the path guess, as stated. Corrected.
4. **Headline and hypothesis outcomes against the pre-registered rules (claim exceeds evidence).**
   - The headline credited the two AI-typed finds to Syft only; the table credits ai-bom too. Reworded, and
     "neither carries a PURL" changed to "no usable PURL", since ai-bom emits `pkg:pypi/<filename>`.
   - Metric 1 was pre-registered as a case-insensitive *name* match. `score.py` adds a lenient "model component
     at the target's path" rule that is not in the pre-registration, and T3 is found by Syft and ai-bom only
     under it. Under the pre-registered rule the union is 4 of 6 found and 1 of 6 found as an AI artifact.
   - Trivy `rootfs` was not in the pre-registration, and T6 is found only by it. Without it the union is 4 of 6
     (lenient) or 3 of 6 (strict).
   - H1's stated falsifier is "misses T1 or T3"; by the pre-registered name match Syft misses T3 (it names it
     `MiniLM-L6-H384-uncased`, the base model). Restated as supported for T1/T2 and for T3 only under the
     post-hoc rule.
   - H3 was "Syft and Trivy find T5…"; Trivy at its default `fs` mode misses T5 and its four advisories, so H3 is
     wrong as pre-registered for Trivy. Restated; it holds for Syft+Grype and for Trivy `rootfs`.
   A "Verification corrections" section at the end of RESULTS.md lists these. `README.md` points to this file.

## Deviations from the pre-registration (recorded, not fixable)

- **D1** Trivy `rootfs` mode and the Trivy CycloneDX output (`trivy-fs-cdx`) ran from the first run but are not
  in the instrument table. Not tuning after seeing results, but the stop rule asks for non-default runs to be
  reported as a separate, labelled result, and RESULTS mixed `rootfs` into the headline and H3.
- **D2** The lenient match rule and the scoring code (`score.py`, mtime 18:06:57) were written after the runs.
  The metrics are pre-registered; their implementation is not.
- **D3** The pre-registration says versions are "the newest release at least two weeks old"; cyclonedx-bom
  8.0.1 was uploaded to PyPI 2026-11-04T13:40Z, five days before the run. Its only contribution is one cell
  (T5 found via the pip environment), so the impact is small.
- **D4** The pre-registration says the pip wheel hash was recorded; `requirements.txt` has no hashes and
  `logs/pip.log` is empty. Recorded at verification instead: ai-bom 3.6.0 wheel `f4414401…5b37`, cyclonedx-bom
  8.0.1 wheel `b91ac00e…aab3`, both matching PyPI's published digests and the installed RECORD files.
- **D5** The cost section estimates about 1.3 GB of distinct bytes; the tree holds about 2.2 GB because the T2
  Ollama blob and V4 are full copies rather than hardlinks. No effect on results.

## What holds without qualification

Repeatability (88 of 88), zero failures in 630 total invocations across both sessions, the advisory table
(2 of 2 and 4 of 4 via Grype and Trivy `rootfs`, 0 on models and the extension; controls Grype npm 5 / pip 5, Trivy `fs` npm 6 / pip 0 (mode limitation), Trivy `rootfs` npm 6 / pip 5), every variant
outcome, the `syft-generated` CPEs and the GHSA `exact-direct-match` path, the ai-bom PURL and provider
behaviour, the npm `prettier-vscode` name collision (registry shows only 1.0.0, unrelated maintainer), and E1/E2.
The limits section in RESULTS already covers single host, simulated re-registration, advisory-selected MCP
servers and the vendor-tool tiering; I found no claim in it that overreaches.

## Files added at verification

`VERIFICATION.md`; `verify/` (`run_scans_verify.py`, `score_verify.py`, `posthoc_verify.sh`, `raw/`,
`posthoc/`, `runlog.jsonl`, `scores.verify.json`, `scores.orig.json`, `rig-verify.txt`, logs, `dl/` wheels);
two appended lines in `tools/checksum-verify.txt`.
