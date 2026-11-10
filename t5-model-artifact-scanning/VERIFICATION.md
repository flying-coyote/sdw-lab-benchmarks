---
type: benchmark-verification
area: T5-model-artifact-scanning
date: 2026-11-09
verdict: VERIFIED-WITH-FIXES
supersedes: the round-1 verification of the same date (NOT-VERIFIED, written before RESULTS.md existed)
---

# Verification: T5 model-artifact scanning (round 2)

**Verdict: VERIFIED-WITH-FIXES.** Every headline number in `RESULTS.md` traces to `results/` and re-derives
independently from the saved raw outputs, the scoring reproduces byte for byte, a full one-run replay of the
bench on the same host reproduced 964 of 964 verdicts, the pre-registration predates the run and its hash still matches, the
deviations are disclosed, and no secret or account identifier appears in `results/` or `RESULTS.md`. Two
small corrections were made in `RESULTS.md`, both marked `[fixed in verify]`: the smoke-versus-main agreement
count was understated (52, actually 92 of 92), and the H6 row said "no version strings" when modelscan's JSON
does carry its own tool version (not an artifact version, so H6 still holds). Neither changes a hypothesis
outcome or a headline number.

## What was checked and how

Same host (Beelink, WSL2 6.6.87.2) and the bench's own `.venv`, with other benches running at the same
time. No git commands were run; nothing in the bench tree was written except this file and the three
marked edits in `RESULTS.md`. All my working copies are under
`/tmp/claude-1000/-home-jerem-project1/af12c3ec-6e7f-4f5c-a239-70fb7dfd0d6e/scratchpad/t5v/`.

| Check | How | Result |
|---|---|---|
| Pre-registration hash | `sha256sum PREREGISTRATION.md` vs `prereg.sha256`; also the `prereg_sha256` in RESULTS frontmatter | match, `ebf9194627b4…d4bc1b`, unchanged at end of verification |
| Labels hash | `sha256sum labels.frozen.json`; `cmp labels.json labels.frozen.json` | `5490275f…a34a3`, matches the prereg and RESULTS; the two files are byte-identical |
| Pre-registration before run | file mtimes (local -0500) | `PREREGISTRATION.md` 19:58:52, `prereg.frozen-at` 19:58:58 (00:58:58Z), first smoke raw 20:01:14, `rig.txt` 20:02:21, first main-run raw 20:03:17, last 20:21:03. `find results/raw ! -newer prereg.frozen-at` returns 0 files. mtimes are self-reported, not a third-party timestamp |
| Fixture integrity | `sha256sum -c fixture-sha256.txt`, `sha256sum -c variants-sha256.txt` | 118 of 118 and 123 of 123 OK (re-run in this pass) |
| Run completeness | `results/runlog.jsonl`, raw file count | 2,892 rows; 723 raw files per arm kind = 241 targets × 3 runs |
| Independent re-scoring from raw | my own script (`t5v/rescore.py`) re-derives every verdict from `results/raw/*.txt` and `*.modelscan.json` using the frozen verdict table, without reading `runlog.jsonl` or `score.py`, then scores against `labels.frozen.json` and `MANIFEST.tsv` | identical on every count RESULTS quotes: detection by arm and set (modelscan 29 / picklescan-file 92 / picklescan-dir 91 / fickling 89 of 96; data2 3 / 56 / 55 / 55; modelscan data2 48 clean, 6 skipped), the three GHSA files modelscan flagged, false positives (0 / 0 / 0 / 11 of 18; modelscan skipped 11, picklescan-dir 7), junk, the full 12 × 4 evasion table with benign counts, fickling's 78 of 96 unsafe and 0 of 18 benign at the overtly-malicious cut, 0 flips over 964 cells |
| Scoring reproduces | `score.py` re-run on a copy of `runlog.jsonl` in scratch (manifest paths relocated, see Limits) | `scores.json` and stdout both byte-identical to `results/scores.json` and `results/score-stdout.txt` |
| Cheap-slice re-run | full run 1 (241 targets × 4 arms = 964 scans) replayed with the bench's `run_scans.py`, `.venv` and fixtures, output in scratch only | exit 0, 964 scans in about 9 minutes under contention; joined to the original run-1 rows on (target, arm), 964 of 964 verdicts match, 0 harness failures |
| Cited line numbers | every `results/scores.json:N` and `results/score-stdout.txt:N` reference in RESULTS | all point at the claimed value (e.g. `:302` fickling data2 55, `:321` modelscan data2 3, `:339` picklescan-dir 55, `:357` picklescan-file 56, `:4719-4740` severity split, `:4743` empty identity block, `:4777` timing) |
| E1 post-hoc | `results/posthoc/E1-numpy-2.2.6/runlog.jsonl` | 54 rows over 18 targets, 24 clean, 30 skipped, 0 flagged; clean on all 7 numpy base files including `dns_exfiltration.npy`, and on `dns_exfiltration.npy.zip`, as RESULTS states |
| Quoted tool errors | grep over `results/raw` | "Model Config not found" is in the `.h5` modelscan output; `_check_version` is in the `dns_exfiltration.npy` modelscan output |
| fickling benign-flag reasons | read run-1 fickling JSON for the 11 benign flags | 5 "invalid opcode(s)" at LIKELY_UNSAFE, 2 EmptyPickleError at SUSPICIOUS (ONNX), 2 `_rebuild_tensor_v2`, 1 squeezenet `__torch__`, 1 picklescan `pytorch_model.bin` with no result text; matches RESULTS |
| Identity (H6) | regex for 32-64-char hex (either case), `pkg:`, `cpe:`, sha256, digest over all 3,615 raw files; separate search for `version` fields | 0 hits on the identity regex; the only version field is `"modelscan_version": "0.8.8"` in modelscan JSON, which is the tool version (see Fix 2) |
| Smoke vs main | re-derived the 92 smoke verdicts (`logs/smoke/raw`, 23 targets × 4 arms) and compared to main run 1 | 92 of 92 agree (RESULTS said 52; see Fix 1) |
| Harness vs frozen table | read `run_scans.py` and `fickling_scan.py` against the prereg verdict table | they implement it. One immaterial edge: the code calls fickling `error` only when every member errored and none flagged, where the table says "errors non-empty and nothing flagged"; the two agree on single-member inputs, which covers every fickling error cell in this run |
| Deviations disclosed | RESULTS "Deviations" vs prereg and what is on disk | all eight are real and match the evidence: incomplete bench finished by re-scoring, harness files postdate the freeze, §6b post-freeze view, the `.h5` skip, the numpy break, 5.0 GB vs 2.5 GB, contention, picklescan-dir skipping `.npy`. I found nothing undisclosed, and "no hypothesis, metric or threshold was changed" holds since the prereg hash is unchanged |
| Secrets and identifiers | grep of `results/` and `RESULTS.md` for cloud keys (AKIA/ASIA), `sk-`, `sk-ant-`, `ghp_`/`github_pat_`, Slack tokens, Google `AIza`, `hf_`, private-key headers, JWTs, email addresses, 12-digit account numbers, `arn:aws`, tenant/subscription/account ids, `/home/`, the owner's username, handle and employer names | zero hits. Raw modelscan JSON and `MANIFEST.tsv` carry absolute `/tmp/claude-1000/...` paths (a uid-derived directory, no username or email) and `rig.txt` names the host "Beelink"; I class neither as an account identifier |

## Fixes made in `RESULTS.md` (each marked `[fixed in verify]`)

1. Deviation 2, smoke agreement: "smoke and main runs agree on all 52 shared cells" became 92 of 92 (23
   targets × 4 arms), with the note that the smoke raw predates the last `run_scans.py` edit (20:01 vs
   20:03:15), which makes the agreement evidence that the edit did not change a verdict. The 52 was carried
   from round 1 and does not match what is on disk.
2. H6 row: "zero digest, PURL, CPE or version strings" became zero digest, PURL or CPE strings and no artifact
   version, with modelscan's own `modelscan_version` field named and excluded as a tool version. H6 still
   holds, because the falsifier is a hash of the scanned bytes or a package identifier.
3. Frontmatter status updated from "awaiting a fresh independent verification" to verified, with this verdict.

## Limits of this verification

- The one-run replay covers 964 of the 2,892 scans (run 1 only); runs 2 and 3 are covered by the 0-flip
  repeatability check over the saved raw.
- `score.py` reads `fixtures-variants/MANIFEST.tsv`, which stores absolute paths, so the README's reproduce
  line breaks if the folder moves; I had to rewrite the paths in a scratch copy to re-score. This is a
  portability limit, not a deviation, and does not affect any number.
- File mtimes are self-reported; there is no third-party timestamp on the freeze.
- Fixture provenance against upstream (5 of 5 unsafe anchors byte-identical to the pinned picklescan and
  modelscan commits) and the Gemini cross-provider leg were done in round 1 and not repeated here. The
  Gemini prompt and answer live in the round-1 verifier's scratchpad, not in this tree, so that leg cannot be
  reproduced from the bench folder alone.

## Round 1 (superseded, summarised for the record)

Round 1 returned NOT-VERIFIED because the bench agent had exited before scoring and no `RESULTS.md` existed.
It confirmed the pre-registration order and hash, fixture hashes and the five upstream anchors, ran
`score.py` (producing the `results/scores.json` that the RESULTS writer later re-ran byte-identically), fixed
a `tr` range bug in `posthoc.sh` (`'A-Za-z0-9._-\n'` to `'A-Za-z0-9._\n-'`) and ran the labelled post-hoc E1
as verifier-run, and ran a Gemini cross-provider check on H1, H2, H3, H5 and H6 that agreed with all five
readings. Its refinements (split 48 cleared from 6 not looked at; modelscan's zero FP as a coverage artefact;
fickling parse rejections reported as severities; A4-C3 as a single cell rather than tar support; scope the
H6 tie-in to R4's measured tools) are carried in the current `RESULTS.md`, and I checked its list of claims a
RESULTS writer must not make against the current text and found none of them made.
