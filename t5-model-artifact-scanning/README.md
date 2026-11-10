# T5 model-artifact scanning (t5-model-artifact-scanning)

What do modelscan 0.8.8, picklescan 1.0.5 and fickling 0.1.12 catch, miss and lose under rename or repack,
on the scanners' own published fixtures plus six benign real models (GGUF, safetensors, PyTorch zip, HDF5,
ONNX), and does any verdict carry an identity an inventory could join on (the R4 `ai-artifact-sbom/` tie-in)?

- `PREREGISTRATION.md`: question, instruments, fixtures, variants, verdict mapping, metrics, hypotheses, stop rule
  (frozen before run; hash in `prereg.sha256`, time in `prereg.frozen-at`)
- `RESULTS.md`: results, hypothesis outcomes, post-hoc, limits, deviations
- `build_labels.py` → `labels.json` (ground truth derived from the suites' own test text; frozen copy `labels.frozen.json`)
- `build_variants.sh` → `fixtures-variants/` (123 rename and container variants, `MANIFEST.tsv`), log in `logs/build_variants.log`
- `run_scans.py` (+ `fickling_scan.py`, the fickling arm): 3 runs × 4 arms × every target; raw output in `results/raw/`,
  one line per scan in `results/runlog.jsonl`, rig stamp in `results/rig.txt`
- `score.py` → `results/scores.json` and the tables quoted in RESULTS
- `posthoc.sh`: labelled post-hoc E1 (modelscan with numpy 2.2.6), output in `results/posthoc/`
- `requirements.txt` (pins), `requirements.lock.txt` (full freeze), `requirements.posthoc-numpy.lock.txt`
- `fixture-sha256.txt`, `variants-sha256.txt`; `tools/` holds the pinned upstream listings and the saved picklescan test file
- `logs/`: pip, fetch, build, smoke (`logs/smoke/`, harness check only, not scored) and run logs

Reproduce: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && bash build_variants.sh &&
.venv/bin/python -I run_scans.py && .venv/bin/python -I score.py` (fixtures are fetched by the commands in
`logs/fetch_fixtures.log`; TinyLlama GGUF and the MiniLM safetensors are hardlinks into `../ai-artifact-sbom/fixtures/`).
Fixtures (917 MB) and variants (5.0 GB) are local and should not be committed. The unsafe fixtures are the
scanners' own published test files; nothing here authors a payload or unpickles anything.
