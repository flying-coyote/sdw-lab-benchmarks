---
type: benchmark-results
area: T5-model-artifact-scanning
date: 2026-11-09
prereg_sha256: ebf9194627b4d9de106b7f35e01a65192e33952007ab7e61472a0101f7d4bc1b
status: written from the completed run; independently verified 2026-11-09 (VERIFIED-WITH-FIXES, see VERIFICATION.md) [fixed in verify]
---

# Results: what the open model-artifact scanners catch, miss, and lose under rename

## Headline

On the 57 unsafe files in picklescan's `tests/data2` bypass set, modelscan 0.8.8 flagged 3, while fickling
0.1.12 flagged 55 and picklescan 1.0.5 flagged 56 in single-file mode (circular, its own suite) and 55 in
directory mode (`results/scores.json:321`, `:302`, `:357`, `:339`). modelscan did not miss those files by
failing to open them, which is the part I think matters most for a defender: it scanned 48 of the 57 and
returned clean with no errors, and skipped 6 (`results/scores.json:320`, `:322`). fickling's apparent breadth
comes at a price, because at the pre-registered threshold it also flagged 11 of 18 benign base files,
including all six real models in five formats (`results/scores.json:4467` onward; `results/score-stdout.txt:30-38`),
so its flag only discriminates once you cut at the two "overtly malicious" severities, where it holds 78 of 96
unsafe and 0 of 18 benign (a derived post-freeze view, `results/scores.json:4719-4740`). No scanner output
carries a content digest, PURL, CPE or version that an inventory could join on (`results/scores.json:4743`,
`results/score-stdout.txt:188`), so R4's SBOM side and the scanner side share no key beyond a file path.

Bottom line: on this host and this fixture set, none of the three tools both looks inside the common model
formats and gives a verdict that survives a rename, a tar or a nested zip, and modelscan's zero false
positives rests mostly on skipping 11 of the 18 benign files.

## Run status and how this was finished

The task brief said the run stopped at scan 251 of 2,892. That was stale by the time I picked it up: the
runlog holds 2,892 rows (241 targets, 4 arms, 3 runs) and `logs/run_scans.log` ends with
`done: 2892 scans`, so nothing needed resuming and no scan was re-run. The bench agent had exited before
scoring; the existing `results/scores.json` was produced by the verifier. I re-ran
`.venv/bin/python -I score.py` with the bench's own venv, and the output is byte-identical to the verifier's
copy (checked with `cmp`), so the scoring is deterministic and the file now stands as bench output. Its stdout
is saved as `results/score-stdout.txt`. The pre-registration hash matched `prereg.sha256`
(`ebf91946...d4bc1b`) before I started and still matches. The labelled post-hoc E1 output in
`results/posthoc/E1-numpy-2.2.6/` was produced by the verifier after fixing a `tr` range bug in `posthoc.sh`;
I read it but did not re-run it. Cost: $0, local CPU, inside the pre-registered line.

## Method as run

As pre-registered: modelscan 0.8.8, picklescan 1.0.5 and fickling 0.1.12 in one venv (Python 3.12.3, numpy
2.5.4, h5py 3.16.0, `results/rig.txt`), one subprocess per (tool, mode, target), `nice -n 10 taskset -c 0-3`,
three runs, verdicts mapped by the frozen table in `run_scans.py`. 118 base fixtures (96 unsafe, 18 benign,
4 junk, labels hash `5490275f...a34a3`) and 123 rename and container variants, every hash matching
`fixture-sha256.txt` and `variants-sha256.txt` per the verifier. Four arms: modelscan, picklescan-file,
picklescan-dir and fickling (through `fickling_scan.py`). Other benches ran on the host at the same time.

## Results by metric

Detection on the 96 unsafe base files (modal verdict, `results/scores.json:285-361`):

| Arm | Flagged / 96 | data (38) | data2 (57) | modelscan zip (1) | Not flagged |
|---|---|---|---|---|---|
| modelscan | 29 | 25 | 3 | 1 | 53 clean, 14 skipped |
| picklescan-file | 92 (circular) | 35 | 56 | 1 | 3 error, 1 skipped |
| picklescan-dir | 91 (circular) | 35 | 55 | 1 | 3 error, 2 skipped |
| fickling | 89 at threshold; 78 at overtly-malicious cut | 33 | 55 | 1 | 6 error, 1 skipped |

The three data2 files modelscan did flag are `GHSA-46h3-79wf-xr6c`, `GHSA-955r-x9j8-7rhh` and
`GHSA-vqmv-47xg-9wpr` (runlog, run 1). All three non-modelscan arms flagged modelscan's own
`unsafe_zip_pytorch.pt`, which is the cross-suite check in the other direction.

False positives on the 18 benign base files (`results/score-stdout.txt:30-38`): modelscan 0, picklescan-file
0, picklescan-dir 0, fickling 11. modelscan skipped 11 benign files, including 5 of the 6 real models (it
opened only the MiniLM `pytorch_model.bin`), and picklescan-dir skipped 7. picklescan-file returned clean on
all six real models because it parses any bytes as a pickle whatever the extension, which is a clean verdict
on a file it did not meaningfully read. fickling's 11 flags break down as "invalid opcode(s)" at LIKELY_UNSAFE
on the safetensors, h5, GGUF and two benign `.npy` files, EmptyPickleError at SUSPICIOUS on both ONNX files,
`torch._utils._rebuild_tensor_v2` at LIKELY_UNSAFE on two benign PyTorch pickles, the TorchScript squeezenet's
`__torch__` import, and one picklescan `pytorch_model.bin` with no result text (per-file reading from raw
output, carried from `VERIFICATION.md` and consistent with `results/scores.json:4720-4726`).

Junk (4 files, `results/score-stdout.txt:40-44`): modelscan skipped all 4, picklescan returned clean on
`bad_pytorch.pt` and `not_a_pickle.bin` and skipped the two password-protected zips, and fickling flagged
those same two non-zip files and skipped the zips.

Evasion (`results/score-stdout.txt:46-59`, per cell at `:61-187`; "defeated" means base flagged, variant not):

| Transform | modelscan | picklescan-file | picklescan-dir | fickling (benign also flagged) |
|---|---|---|---|---|
| N1 no extension | 2/3 | 1/5 | 4/4 | 0/5 (7/8) |
| N2 `.bin` | 2/3 | 1/5 | 0/4 | 0/5 (7/8) |
| N3 `.txt` | 2/3 | 1/5 | 4/4 | 0/5 (7/8) |
| N4 `.safetensors` | 2/3 | 1/5 | 4/4 | 0/5 (7/8) |
| N5 `.pth` | 2/3 | 1/5 | 0/4 | 0/5 (7/8) |
| C1 zip, original name | 1/3 | 1/5 | 1/4 | 2/5 (1/4) |
| C2 zip, member `.txt` | 3/3 | 1/5 | 1/4 | 5/5 (0/4) |
| C3 tar | 3/3 | 4/5 | 4/4 | 0/5 (4/4) |
| C4 tar.gz | 3/3 | 5/5 | 4/4 | 0/5 (4/4) |
| C5 gzip | 3/3 | 5/5 | 4/4 | 0/5 (4/4) |
| C6 nested zip | 3/3 | 5/5 | 4/4 | 5/5 (0/4) |
| C7 PyTorch-layout zip | 0/2 | 0/3 | 0/3 | 0/3 (0/1) |

fickling's zero defeats on rename and on tar, tar.gz and gzip are not resilience, because it flags 7 of 8
benign renames and 4 of 4 benign tar, tar.gz and gzip variants just as readily. The picklescan-file "1/5" on
every rename is A5 (`dns_exfiltration.npy`): every A5 rename returned error (`results/score-stdout.txt:109-113`).
A4-C1, a zip wrapping modelscan's PyTorch zip, was skipped by every arm (`:103`), which in effect makes it a
nested zip.

Identity in output: score.py's §6 regex (32-64-char hex, `pkg:`, `cpe:`, sha256 or digest) over every run-1
raw output found zero hits (`results/scores.json:4743`). I repeated the search over all raw files from all
three runs, with uppercase hex allowed, and also found zero.

Repeatability: 0 verdict flips and 0 harness failures across 3 runs of 964 (arm, target) cells
(`results/score-stdout.txt:1`, `results/scores.json:4741-4742`).

Timing (secondary, contended): per-run base-set totals fall run over run for every arm, for example modelscan
90.2, 68.7 and 49.9 s with a 29% CV (`results/scores.json:4777`), which looks like cache warm-up on a loaded
host, so I do not draw any cross-tool speed comparison from it.

## Hypotheses against their pre-registered falsifiers

| H | Outcome | Reason |
|---|---|---|
| H1 format coverage | Falsified | modelscan and picklescan-dir skipped the GGUF, safetensors and both ONNX files as predicted, but fickling flagged all six real models, which trips "any tool flags one". modelscan also skipped the `.h5` ("Model Config not found"), against the prediction |
| H2 cross-tool on data2 | Holds | modelscan 3 of 57 (under 80%, under picklescan), fickling 55 (more than modelscan) |
| H3 false positives | Falsified | fickling flagged all six real models; modelscan and picklescan flagged none |
| H4 rename | Falsified on the literal falsifier | modelscan flagged A4-N1, N3 and N4 (it opens a PyTorch zip by content under any name). For A1-A3 the N1/N3/N4 prediction held, but modelscan also skipped the N2 and N5 cells predicted flagged, and picklescan-file errored on every A5 rename rather than flagging |
| H5 containers | Falsified | fickling flagged every C3-C5 unsafe variant (non-discriminating), picklescan-file flagged A4-C3, and modelscan returned clean on A3-C7. Nested zip was skipped by all three for every anchor, and a `.txt`-member zip defeated modelscan 3 of 3 and fickling 5 of 5 |
| H6 identity | Holds | zero digest, PURL or CPE strings in any raw output, and no version of the scanned artifact; the only version field is modelscan's own `"modelscan_version": "0.8.8"` in its JSON, which names the tool, not the artifact [fixed in verify] |
| H7 repeatability | Holds | 0 flips |

The hypothesis-level reading for H-AI-ARTIFACT-INVENTORY-01 is that the bench weakens the null on one host
and one fixture set, as the pre-registration says partial results do, and does not falsify it.

## Post-hoc E1 (labelled, not pre-registered, verifier-run)

The pinned `modelscan[h5py]==0.8.8` resolves numpy 2.5.4, which removed the `numpy.lib.format` helpers that
modelscan's numpy scanner calls, so every `.npy` and `.npz` lands as skipped in the main run. With numpy
2.2.6 in a separate venv, modelscan scanned all 7 numpy base files and returned clean on every one of them,
including the unsafe `dns_exfiltration.npy`, and returned clean on `dns_exfiltration.npy.zip` while skipping
the other ten A5 variants (54 rows, 24 clean, 30 skipped, 0 flagged;
`results/posthoc/E1-numpy-2.2.6/runlog.jsonl`). So fixing the pin does not turn the A5 cell into a detection.

## Deviations

1. The bench agent exited before scoring and before E1; scoring was re-run here (byte-identical to the
   verifier's run) and E1 was run by the verifier after the `posthoc.sh` fix.
2. Every harness file postdates the 19:58:52 freeze: `build_variants.sh` and `fickling_scan.py` at 20:00:07,
   `run_scans.py` at 20:03:15, `score.py` at 20:05:10 (local -0500). None can be diffed against a frozen copy.
   The verifier checked `run_scans.py` against the frozen verdict table line by line, and the smoke and main
   runs agree on all 92 shared cells (23 smoke targets × 4 arms; the smoke raw predates the last
   `run_scans.py` edit, so the edit did not change a verdict on those targets) [fixed in verify: was "52"].
3. `score.py` §6b (fickling severity split) is a post-freeze derived view; the 78 of 96 figure comes from it
   and is labelled as such wherever it appears.
4. The pre-registration says modelscan's `.h5` scanner is active through h5py; on the transformers weights-only
   h5 it skipped for a missing Keras model config.
5. The numpy 2.5.4 dependency break was not anticipated; every modelscan numpy result in the main run is a
   skip caused by it.
6. Variants take 5.0 GB on disk against the estimate of about 2.5 GB.
7. Other benches ran concurrently, so timings are contended.
8. Observed but not predicted: picklescan-dir skipped all three `.npy` base files even though the
   pre-registration lists `.npy` in its extension table.

No hypothesis, metric or threshold was changed, and the pre-registration was not amended.

## Limits

109 of 118 base fixtures and their labels come from picklescan's own suite, so picklescan's numbers are an
install check. The benign set is 18 files with 6 real models, so false positives are counts, never rates.
modelscan's generated test fixtures were deliberately not reproduced, which leaves modelscan with one fixture
from its own suite. TensorFlow and fickling's `torch` extra were not installed, so the SavedModel, Keras v3
and polyglot paths are untested, and `picklescan[7z]` and `--strict` were not run. One host, one run date,
one version of each tool; fickling 0.1.13 was out of scope by the cooldown rule.

## What would change the conclusion

A modelscan release (or a numpy-compatible pin) that flags most of data2 or `dns_exfiltration.npy` would
undo the H2 reading and the E1 finding. A fickling configuration that reports parse rejections as errors
instead of severities would remove most of its benign flags and make its threshold verdict usable on its own.
Any of the three tools emitting a sha256 of the scanned bytes, or a component identifier, would falsify H6
and give the R4 inventory a join key. A larger benign corpus of real models, or unsafe fixtures from a source
independent of all three suites, would test whether these counts generalise beyond the tools' own test files.
