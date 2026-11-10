---
type: benchmark-verification
area: T5-model-artifact-scanning
date: 2026-11-09
verdict: NOT-VERIFIED
---

# Verification: T5 model-artifact scanning

**Verdict: NOT-VERIFIED.** The reason is that the deliverable is incomplete, not that the data is wrong. The
bench agent returned while the scan run was at 251 of 2,892 scans and exited before scoring, so there is no
`RESULTS.md` and the labelled post-hoc E1 never ran. There are no RESULTS claims to check against the data.
What does exist checks out: the pre-registration predates the run and its hash still matches, every fixture
and variant hash matches, the five anchor fixtures byte-match the upstream pinned commits, the run completed
2,892 of 2,892 scans with 0 verdict flips and 0 harness failures, and `score.py` runs cleanly on the full
runlog. I did not write `RESULTS.md`, because a verifier scoring results it authored is not independent. The
fix is a re-spawn of the bench step to write `RESULTS.md` from `results/scores.json` and the notes below,
followed by a fresh verification.

## What was checked and how

Same host and conditions as the run (Beelink, WSL2 kernel 6.6.87.2, the bench's own `.venv`), with other
benches running at the same time, so any timing I quote was taken under contention.

| Check | Command / artefact | Result |
|---|---|---|
| Pre-registration hash | `sha256sum PREREGISTRATION.md` vs `prereg.sha256` | match, `ebf91946…d4bc1b`, unchanged at end of verification |
| Pre-registration before run | mtimes (local -0500) and stamps | `PREREGISTRATION.md` 19:58:52, `prereg.frozen-at` 00:58:58Z, `labels.frozen.json` 19:58:58 → smoke run finished 20:01:30 → `results/rig.txt` 01:02:21Z → main run started ~20:03 → last scan 20:21:03. Order holds; mtimes are self-reported, not a third-party timestamp |
| Labels hash quoted in prereg | `sha256sum labels.json` | `5490275f…a34a3`, matches the prereg; `labels.json` and `labels.frozen.json` byte-identical |
| Fixture integrity | `sha256sum -c fixture-sha256.txt`, `sha256sum -c variants-sha256.txt` | 118 of 118 and 123 of 123 OK |
| Fixtures are the published test files | sha256 of `malicious1_v4.pkl`, `malicious2_v4.pkl`, `GHSA-4675-36f9-wf6r.pkl`, `dns_exfiltration.npy` from picklescan at `f15d54da…`, and `unsafe_zip_pytorch.pt` from modelscan at `61fcec9c…`, fetched from raw.githubusercontent.com | 5 of 5 byte-identical to the local copies (the five unsafe anchors) |
| Versions recorded | `requirements.txt`, `requirements.lock.txt`, `results/rig.txt` | modelscan 0.8.8, picklescan 1.0.5, fickling 0.1.12, numpy 2.5.4, h5py 3.16.0, Python 3.12.3, as the prereg states; post-hoc venv lock records numpy 2.2.6 |
| Run completeness | `results/runlog.jsonl`, `logs/run_scans.log` | 2,892 rows = 241 targets × 4 arms × 3 runs; log ends `done: 2892 scans` |
| Repeatability (H7) | `score.py` | 0 verdict flips, 0 harness failures, 0 retries |
| Scoring runs | `.venv/bin/python -I score.py` (verifier run; stdout saved in the verifier scratchpad) | exit 0. `results/scores.json` (mtime 20:27:15) was **produced by this verifier run**, not by the bench, which exited before scoring; the RESULTS writer should re-run `score.py` (deterministic) rather than treat it as bench output |
| Harness edited after freeze | `run_scans.py` mtime 20:03:15, 4 min 17 s after the freeze | the content cannot be diffed against a frozen copy. Mitigation: smoke and main run agree on all 52 shared (arm, target) cells, and the code implements the frozen verdict table as written (checked line by line) |
| Spot checks of raw output | modelscan JSON for a data2 "clean", the `.h5` skip, the `.npy` skip; picklescan A4-C3; fickling on the GGUF | all as summarised below |
| Spend | | $0 on the bench. The cross-provider call used agy quota (19,617 tokens, logged in the agy ledger), no money |
| Safety scope | fixture provenance above; `build_variants.sh` | unsafe files are the scanners' own published fixtures; variants are the same bytes renamed or wrapped with stdlib `zipfile`/`tarfile`/`gzip`; nothing in the harness unpickles; no Docker, no network during the run, no credentials. In scope |

## Fix made in place

1. **`posthoc.sh` tr range bug (clear error).** `tr -c 'A-Za-z0-9._-\n' '_'` fails with "range-endpoints of
   '_-\012' are in reverse collating sequence order", so the script died on its first target and E1 never
   produced output. Changed to `tr -c 'A-Za-z0-9._\n-' '_'` (dash moved to the end); the original is kept as
   `posthoc.sh.orig` in the verifier scratchpad, not in this tree. I then ran E1 once (3 runs per target, 18
   targets, 54 rows) as a **verifier-run post-hoc**; the output is in `results/posthoc/E1-numpy-2.2.6/`.

## Independent scoring of the hypotheses against their literal falsifiers

These are my readings from `results/scores.json`, offered to whoever writes `RESULTS.md`. Each is read against
the pre-registered "wrong if" sentence, not a charitable version of it.

| H | Outcome | Evidence |
|---|---|---|
| H1 format coverage | **Falsified** (by fickling); coverage half holds | modelscan and picklescan-dir skip the GGUF, safetensors and both ONNX files, as predicted. fickling "flags" all six real models, which trips the "any tool flags one" clause. The `.h5` prediction failed: modelscan skipped the Keras HDF5 with "Model Config not found" (a transformers weights-only h5 carries no Keras model config), so modelscan looked inside 1 of 6 real models (the PyTorch zip). picklescan-file reports all six "clean" because it parses the bytes as pickle whatever the extension |
| H2 bypass-set detection | **Holds** | on the 57 unsafe `data2` files: modelscan flagged 3 (48 scanned and cleared with 0 errors, 6 not looked at), picklescan-file 56 (circular, its own suite), picklescan-dir 55, fickling 55 (2 error) |
| H3 false positives | **Falsified** (by fickling) | modelscan 0 and picklescan 0 benign flagged, but modelscan's zero rests on skipping 11 of 18 benign files, including 5 of 6 real models. fickling flagged 11 of 18 benign, including all six real models, and 2 of 4 junk |
| H4 rename | **Holds only on the A1-A3 scoping in the hypothesis body; the literal falsifier fails** | the unscoped falsifier says wrong if modelscan flags any N1/N3/N4 variant, and modelscan flagged A4-N1, A4-N3 and A4-N4 (`unsafe_zip_pytorch` with no extension, `.txt`, `.safetensors`), so it opens a zip by content whatever the name. For A1-A3, N1/N3/N4 are skipped by modelscan and picklescan-dir and still flagged by picklescan-file and fickling, as predicted. But N2 (`.bin`) and N5 (`.pth`) were predicted flagged by all, and modelscan skipped all six of those A1-A3 cells. For A5 (`.npy` renamed), picklescan-file returned error on all five renames, not the predicted flag |
| H5 containers | **Falsified on two counts** | fickling "flags" every C3-C5 variant, though it flags every benign C3-C5 variant too (4 of 4 each), so the flag does not discriminate. picklescan-file flagged A4-C3 (a tar holding an uncompressed PyTorch zip; it reported `unsafe_zip_pytorch/data.pkl: posix system`). modelscan returned clean on A3-C7, so a C7 variant was missed. The substantive pattern holds otherwise: nested zip (C6) is skipped by all three tools for every anchor, and a zip whose member is renamed `.txt` (C2) defeats modelscan 3 of 3 and fickling 5 of 5 while picklescan-file still flags 4 of 5 |
| H6 identity | **Holds** | regex over every run-1 raw output for 32-64-char hex strings, `pkg:`, `cpe:` and the words sha256/digest: zero hits in any arm. Verdicts carry a file path and member name only |
| H7 repeatability | **Holds** | 0 flips across 3 runs for 964 (arm, target) cells |

## Claims a RESULTS writer must not make

- **"fickling detects 89 of 96 unsafe files" is not a detection rate.** At the pre-registered threshold
  (severity above LIKELY_SAFE) fickling flags 102 of 118 base files, including 11 of 18 benign and 2 of 4
  junk. Its non-pickle "flags" are mostly a parse rejection reported as a severity rather than an error (file list
  below). The discriminating cut is OVERTLY_MALICIOUS + LIKELY_OVERTLY_MALICIOUS:
  78 of 96 unsafe and 0 of 18 benign. Eight of the 9 unsafe files at LIKELY_UNSAFE name a genuinely risky
  import (`torch.utils.collect_env.run`, `_pyrepl.pager.pipe_pager` and similar), so a reader should see both
  numbers. By file, the 11 benign flags are: "invalid opcode(s)" at LIKELY_UNSAFE on the safetensors, the
  h5, the GGUF, `int_array.npy` and `object_array.npy` (5); EmptyPickleError at SUSPICIOUS on both ONNX files
  (2); `torch._utils._rebuild_tensor_v2` at LIKELY_UNSAFE on the MiniLM `pytorch_model.bin` and
  `new_pytorch_model.bin` (2); the TorchScript squeezenet's `__torch__` import (1); and picklescan's
  `pytorch_model.bin` at LIKELY_UNSAFE with no result text (1). This split is `score.py` §6b, which was written after the freeze and must be labelled as a derived
  post-freeze view.
- **"modelscan is extension-gated" overclaims.** It is for raw pickles (A1-A3 renamed to `.bin` or `.pth`
  are skipped too), but a PyTorch zip is opened by content under any name (A4-N1 to N5 all flagged).
- **modelscan's 0 false positives is mostly a coverage gap**, not specificity; say so next to the number.
- **The `.npy` story is a dependency break, then a miss.** Under the pinned numpy 2.5.4, modelscan's numpy
  scanner errors (`module 'numpy.lib.format' has no attribute '_check_version'`) and every `.npy` lands as
  skipped. With numpy 2.2.6 (verifier-run E1, 3 runs, 0 flips) modelscan scans all 7 numpy base files and
  returns **clean on `dns_exfiltration.npy`**, the unsafe object array carrying `ssl.get_server_certificate`;
  it also returns clean on `dns_exfiltration.npy.zip` and skips every other A5 variant. So fixing the pin
  does not turn the A5 cell into a detection. E1 flagged 0 of 54 scans.
- **Timing** is secondary and contended: per-run base totals fall run over run for every arm (modelscan
  90.2 / 68.7 / 49.9 s, CV 29%), which looks like cache warm-up on a loaded host. No cross-tool speed claim
  is supported.

## Cross-provider leg (Gemini, `agy-tracked.sh`, model gemini-3.8-flash)

I sent the five hypotheses with the most at stake (H1, H2, H3, H5, H6), each with its falsifier and the
matching data, and asked for agree/disagree. Gemini agreed with all five readings and raised five
refinements. Resolution against the data:

| Gemini point | Resolution |
|---|---|
| H2: pooling "skipped" with "missed" underclaims the mechanism | accepted; the table above splits 48 cleared from 6 not looked at |
| H3: modelscan's zero FP is an artefact of skipping 5 of 6 models | accepted; already flagged above |
| H1: fickling's "coverage" counts parse rejections as inspection; the `.h5` skip is a structural expectation, not an extension skip | accepted on both, confirmed in raw output ("invalid opcode(s)", "Model Config not found") |
| H5: understates picklescan's container handling (A4-C3, C2 4 of 5) | partly accepted. C2 resilience is real; A4-C3 is a tar holding an uncompressed zip, which picklescan read as a zip, so it is one cell, not general tar support (A1-A3 and A5 C3 are all clean) |
| H6: "SBOMs record sha256 but no PURL" overgeneralises | accepted; scope the tie-in to R4's measured tools (Syft on GGUF and safetensors), not SBOMs in general |

No disagreement survived the data. Prompt and answer are in the verifier scratchpad, not this tree.

## Deviations from the pre-registration (for the RESULTS writer to carry)

1. **D1 bench incomplete.** No `RESULTS.md`; E1 not run by the bench (verifier ran it after the fix above).
2. **D2 harness mtime after freeze.** `run_scans.py` modified 4 min after the freeze; mitigated as above.
3. **D3 post-freeze analysis.** `score.py` §6b (fickling severity split) and `posthoc.sh` were written after
   the freeze; both are labelled in their own code and must stay labelled.
4. **D4 instrument claim wrong.** The prereg says modelscan's `.h5` scanner is active through h5py; on this
   file it skipped for a missing Keras model config.
5. **D5 dependency break not anticipated.** `modelscan[h5py]==0.8.8` resolves numpy 2.5.4, which breaks its
   numpy scanner; every modelscan `.npy` result in the main run is a skip caused by that.
6. **D6 size estimate.** The prereg estimated "up to about 2.5 GB" of variants; on disk it is 5.0 GB.
7. **D7 isolation.** Methodology §5 asks for isolation; the brief ran several benches at once, so timings are
   contended and labelled as such.

## Limits of this verification

I re-scored the run's own runlog rather than re-running all 2,892 scans; the 0-flip repeatability across the
bench's three runs and the smoke/main agreement are the evidence that a re-run would match. File mtimes are
self-reported. I spot-checked 5 of 118 fixtures against upstream, chosen as the unsafe anchors.
