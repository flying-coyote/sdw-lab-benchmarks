# T5 model-artifact scanning (t5-model-artifact-scanning)

## What it measures

What modelscan 0.8.8, picklescan 1.0.5 and fickling 0.1.12 catch, miss and lose under rename or repack, on the
scanners' own published fixtures plus six benign real models (GGUF, safetensors, PyTorch zip, HDF5, ONNX), and
whether any verdict carries an identity an inventory could join on (the tie-in to `../ai-artifact-sbom/`, R4).

## Result

On the 57 unsafe files in picklescan's `tests/data2` bypass set, modelscan flagged 3, fickling 55 and picklescan 56 in
single-file mode, and modelscan returned clean on 48 of the 57 rather than failing to open them; fickling also flagged
11 of 18 benign files, including all six real models, and no scanner output carried a content digest, PURL, CPE or
artefact version (`RESULTS.md`, Headline, citing `results/scores.json` lines). These are measured outcomes on
public fixtures, though picklescan's own numbers are close to an install check, because 109 of the 118 base fixtures
and their labels come from its own suite, which `RESULTS.md` says as well. The fickling 78 of 96 figure is a
post-freeze derived view, labelled so.

## What would have made it fail

Each hypothesis in `PREREGISTRATION.md` has a falsifier, and four of the seven were falsified. Eighteen benign base
files, six of them real models, are the false-positive control, and ground truth comes from the suites' own test
text, not from this bench's judgment.

## Pre-registration

`PREREGISTRATION.md`, frozen by agent before the run and not owner-reviewed. Its sha256 in `prereg.sha256`
(`ebf91946…d4bc1b`) still matches, and `prereg.frozen-at` records 2026-11-10T00:58:58Z. The labels were frozen with
it: `PREREGISTRATION.md` line 49 carries the sha256 of `labels.frozen.json` (`5490275f…a34a3`), which still matches,
and `score.py` reads `labels.json`, which is byte-identical to `labels.frozen.json`. Every harness file was written
after the freeze (Deviation 2 in `RESULTS.md`), and the verifier checked the verdict mapping in `run_scans.py` against
the frozen table line by line. `fixture-sha256.txt` and `variants-sha256.txt` list absolute scratch paths for
fixtures that are not in this repo, so those hashes can be checked only against a rebuilt fixture tree.

## Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && bash build_variants.sh &&
.venv/bin/python -I run_scans.py && .venv/bin/python -I score.py
```

Fixtures were fetched by the commands recorded in `logs/fetch_fixtures.log`, and the TinyLlama GGUF and the MiniLM
safetensors are hardlinks into `../ai-artifact-sbom/fixtures/`. The fixtures (917 MB), variants (5.0 GB), the
`tools/` listings, the fetch, build and run logs, `results/raw/` and `results/runlog.jsonl` are not committed, so
`score.py` cannot be re-run from this tree; `results/scores.json` and `results/score-stdout.txt` are the committed
outputs. The unsafe fixtures are the scanners' own published test files; nothing here authors a payload or unpickles
anything. `posthoc.sh` is the labelled post-hoc E1 run (modelscan with numpy 2.2.6). `build_labels.py` writes
`labels.json` from the suites' test text (byte-identical copy `labels.frozen.json`); `run_scans.py` calls
`fickling_scan.py` for the fickling arm; `build_variants.sh` writes `fixtures-variants/` and its `MANIFEST.tsv`
(not committed).

## Results

- `RESULTS.md` is the entry point: headline, results by metric, hypotheses against their falsifiers, post-hoc E1,
  deviations, limits.
- `results/scores.json` and `results/score-stdout.txt` are the scorer outputs the RESULTS lines cite;
  `results/posthoc/E1-numpy-2.2.6/` holds the labelled post-hoc run; `results/rig.txt` the rig stamp.
- `logs/smoke/` is a harness check, not scored.
- `VERIFICATION.md` is the independent re-score (VERIFIED-WITH-FIXES), which re-derived every verdict from raw output
  against `labels.frozen.json`.

## Versions and pins

`requirements.txt` pins the direct dependencies, `requirements.lock.txt` is the full freeze, and
`requirements.posthoc-numpy.lock.txt` is the post-hoc venv; every line in all three carries `==`. The pinned
`modelscan[h5py]==0.8.8` resolves numpy 2.5.4, which breaks modelscan's numpy scanner, so every modelscan `.npy` and
`.npz` result in the main run is a skip (Deviation 5).

## Evidence tier and limits

`RESULTS.md` states no tier letter. 109 of 118 base fixtures come from picklescan's suite, the benign set is 18 files
so false positives are counts and not rates, TensorFlow and fickling's `torch` extra were not installed, and the run
covers one host and one version of each tool. See Limits in `RESULTS.md`.

## Corrections

- 2026-11-09: verifier fixes are marked `[fixed in verify]` in `RESULTS.md`.
- 2026-11-17: seven passages of `RESULTS.md` that narrated the finishing agent's steps in the first person were
  recast in neutral voice, and "the part I think matters most" now reads "probably the part that matters most"; this
  README was restructured to the lab layout and records which label file the scorer reads.
