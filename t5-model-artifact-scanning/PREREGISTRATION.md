---
type: benchmark-preregistration
area: T5-model-artifact-scanning
created: 2026-11-09
status: frozen by agent before run; not owner-reviewed
review_reference: ~/project1/02-projects/securitydataworks/SITE-REVIEW-2026-11-09.md section 5, row T5
related: ai-artifact-sbom/ (R4; SBOM tools give models no PURL/CPE)
hypothesis_served: H-AI-ARTIFACT-INVENTORY-01 (PROPOSED, gated-pending, no score); this bench is a first-party leg on the "can a defender tell a safe model file from an unsafe one, and does the verdict attach to any identity" question
---

# Pre-registration: what do the open model-artifact scanners catch, miss, and defeat-by-rename?

## Question

When a defender runs the three open model-artifact scanners (modelscan, picklescan, fickling) over a
directory of model files, which unsafe files are flagged, which benign model files are falsely flagged or
cannot be read at all, which formats each tool actually looks inside, and whether renaming or re-packaging
the same bytes (a different extension, a zip, a tar, a gzip, a nested zip, a PyTorch-layout zip) changes
the verdict. A second question ties this to R4 (`ai-artifact-sbom/`): R4 found that SBOM tools give model
weights a content hash but no PURL or CPE; here the question is whether any scanner verdict carries an
identity (digest, name, version) that an inventory could join on, or whether the two tool families produce
outputs with nothing in common.

**Circularity, stated up front.** 109 of the 118 base fixtures are picklescan's own unit-test files, with
labels taken from picklescan's own test expectations. picklescan's detection rate on them is therefore a
check that the install works, not a result. The pre-registered signal is cross-tool: modelscan and
fickling measured against the picklescan corpus (especially the 57 unsafe files in `data2/`, which are
mostly bypass fixtures named after GHSA advisories filed against picklescan itself), and picklescan and
fickling measured against modelscan's unsafe PyTorch zip. No headline may be read as "picklescan wins".

## Instruments (exact versions, pinned before run; `requirements.txt`, `requirements.lock.txt`)

| Tool | Version (release date) | Install | Notes fixed before run |
|---|---|---|---|
| modelscan (Protect AI) | 0.8.8 (PyPI 2026-02-18) | `modelscan[h5py]==0.8.8` → h5py 3.16.0, numpy 2.5.4, rich 14.3.4, click 8.5.1 | TensorFlow not installed, so the SavedModel (`.pb`) and Keras v3 (`.keras`) scanners cannot load; `.h5` scanner active through h5py. Extension table read from `modelscan/settings.py`: `.pkl .pickle .joblib .dill .dat .data` (pickle), `.bin .pt .pth .ckpt` (PyTorch), `.npy`, `.h5`, `.keras`, `.pb`; zip containers `.zip .npz`. Nested zips are rejected by the source ("ModelScan does not support nested zip files"). |
| picklescan (Matthieu Maitre) | 1.0.5 (PyPI 2026-07-01) | `picklescan==1.0.5`, no extras | No `py7zr`, so the `.7z` fixture will fail with the tool's own "install picklescan[7z]" error; this is the default install and is reported as such. Extension tables from `picklescan/scanner.py`: pickle `.pkl .pickle .joblib .dat .data`, PyTorch `.bin .pt .pth .ckpt`, numpy `.npy`, zip `.zip .npz .7z`. Single-file mode scans the bytes whatever the extension; directory mode skips files outside the tables. |
| fickling (Trail of Bits) | 0.1.12 (PyPI 2026-06-26) | `fickling==0.1.12`, no extras | 0.1.13 (2026-11-03) is inside the two-week cooldown and is not used. The `torch` extra is not installed, so `fickling.polyglot` (format identification) is unavailable; the scan API `fickling.scan_file` / `fickling.scan_zip_archive` does not need it. fickling has no directory mode. |
| Python | 3.12.3 (Ubuntu system interpreter, venv in `.venv/`) | | all harness code runs with `python -I` |

Versions are the newest release at least two weeks old on 2026-11-09. Each tool is used as a CLI where it
has one that fits (modelscan, picklescan) and through its documented scan API where the CLI does not take a
model file (fickling: the CLI's `--check-safety` reads one raw pickle stream; its own Hugging Face path in
`fickling/cli.py` dispatches zip files to `scan_zip_archive` and other files to `scan_file`, and the harness
does the same).

## Fixture set (118 base files, `fixtures/`; sha256 of every file in `fixture-sha256.txt`)

Labels are derived mechanically by `build_labels.py` from the suites' own test text and recorded in
`labels.json` (sha256 `5490275fa2c9de29ba88b4d647bcee424d3231b38e4bed5f5429d5fb806a34a3`): **96 unsafe,
18 benign, 4 junk**. Junk = not a readable artifact at all (a PNG named `.pt`, invalid bytes, two
password-protected zips); junk files are excluded from detection and false-positive denominators and each
tool's behaviour on them (error, clean, skipped) is reported separately.

| Set | Files | Source (pinned) | Licence | Labels |
|---|---|---|---|---|
| `picklescan-data/` | 46 | github.com/mmaitre314/picklescan `tests/data` at tag v1.0.5 (commit `f15d54da3dec9aa28a87ede82f87882bb80f1023`) | MIT | 38 unsafe (incl. `malicious-invalid-bytes.pkl` and `broken_model.pkl`, both partial-parse files the suite counts as infected), 5 benign (`benign0_v{0,3,4}.pkl`, `pytorch_model.bin`, `new_pytorch_model.bin`), 3 junk (`bad_pytorch.pt`, `not_a_pickle.bin`, `benign_password_protected.zip`). Already includes the suite's own repack variants of `malicious1`: `.zip`, `.7z`, zip with flag bits 0x1/0x20/0x40, central-directory-only zip, zip with a wrong extension |
| `picklescan-data2/` | 63 | same repo, `tests/data2` at v1.0.5 | MIT | 57 unsafe (41 `GHSA-*` bypass fixtures, numpy `dns_exfiltration.npy`, cloudpickle code injection, stdlib gadgets such as `io_FileIO`, `urllib_request_urlopen`, `logging_FileHandler`, `types_CodeType`, type-confusion and keyerror exploits, `malicious21-23`, `malicious1_crc.zip`), 6 benign (`int_array.npy`, `int_arrays.npz`, `int_arrays_compressed.npz`, `object_array.npy`, `object_arrays.npz`, `object_arrays_compressed.npz`; the suite marks the object-array globals Innocuous, so a flag on them counts as a false positive with the policy disagreement noted) |
| `modelscan-data/` | 2 | github.com/protectai/modelscan `tests/data` at tag v0.8.8 (commit `61fcec9c2a37c24c1fb12d84ede30fe248a364bd`) | Apache-2.0 | `unsafe_zip_pytorch.pt` unsafe; `password_protected.zip` junk. modelscan's other test fixtures are generated at test time by pickling `__reduce__` classes and are not reproduced here (no new payloads are authored) |
| `fickling-fixtures/` | 1 | github.com/trailofbits/fickling `test/fixtures` at tag v0.1.12 (commit `c3c695cdcce451c04dfe892802675161614287a2`) | LGPL-3.0 (repo); the fixture is a TorchScript export of torchvision squeezenet1_0 | benign |
| `benign-models/` | 6 | TinyLlama 1.1B chat Q4_0 GGUF (637,699,456 B, Apache-2.0, bytes from the local Ollama `tinyllama:latest` blob, the same file as R4's T1, hardlinked); sentence-transformers/all-MiniLM-L6-v2 at HF revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` (Apache-2.0): `model.safetensors` (same file as R4's T3, hardlinked), `pytorch_model.bin` (zip-format torch pickle), `tf_model.h5` (Keras HDF5), `onnx/model_O4.onnx`; `mnist-8.onnx` from onnx/models `validated/vision/classification/mnist/model/` at main commit `c5cae0f1942c8d7727372c7b1f6b485aa39e4421` (Apache-2.0) | as listed | 6 benign; formats GGUF, safetensors, PyTorch zip, HDF5, ONNX ×2 |

The benign denominator is small (18 files, of which 6 are real models in 5 formats and 7 are benign
pickles, numpy arrays or a TorchScript archive). False positives are reported as counts, never as a rate.

## Rename and repack variants (`fixtures-variants/`, built by `build_variants.sh` before the run)

Every variant is the unchanged bytes of a base fixture in a different file name or container. No new
payload is authored; the directory is labelled test fixtures. Anchors are chosen for distinct mechanisms:

| Anchor | Base file | Label | Why this one |
|---|---|---|---|
| A1 | `picklescan-data/malicious1_v4.pkl` | unsafe | `builtins.eval`, protocol 4, the canonical case |
| A2 | `picklescan-data/malicious2_v4.pkl` | unsafe | `posix.system` |
| A3 | `picklescan-data2/GHSA-4675-36f9-wf6r.pkl` | unsafe | `ctypes.CDLL`, a blocklist-bypass fixture |
| A4 | `modelscan-data/unsafe_zip_pytorch.pt` | unsafe | already a PyTorch-layout zip, from a different suite |
| A5 | `picklescan-data2/dns_exfiltration.npy` | unsafe | numpy object array carrying `ssl.get_server_certificate` |
| B1-B6 | the six `benign-models/` files | benign | format coverage under rename |
| B7 | `picklescan-data/benign0_v4.pkl` | benign | plain benign pickle |
| B8 | `picklescan-data/pytorch_model.bin` | benign | legacy PyTorch pickle |

Transforms (N = name only, C = container; the file's bytes are identical to the anchor's in every N case
and are the sole member in every C case):

| Code | Transform | Applied to |
|---|---|---|
| N1 | extension removed | A1-A5, B1-B8 |
| N2 | renamed `.bin` | A1-A5, B1-B8 |
| N3 | renamed `.txt` | A1-A5, B1-B8 |
| N4 | renamed `.safetensors` | A1-A5, B1-B8 |
| N5 | renamed `.pth` | A1-A5, B1-B8 |
| C1 | zip, member keeps its original name | A1-A5, B5 (mnist-8.onnx), B2 (safetensors), B7, B8 |
| C2 | zip, member renamed to `payload.txt` | same |
| C3 | tar | same |
| C4 | tar.gz | same |
| C5 | gzip of the raw file (`.gz`) | same |
| C6 | nested zip (C1 placed inside another zip) | same |
| C7 | PyTorch-layout zip: member stored as `archive/data.pkl`, file named `.pt` | A1-A3, B7 only (raw pickles; mimics `torch.save` layout without using torch) |

That is 13 anchors × 5 renames = 65, plus 9 anchors × 6 containers = 54, plus 4 × C7 = 4: **123 variant
files**. Containers are built with Python's `zipfile` (deflate), `tarfile` and `gzip` from the standard
library; nothing opens a fixture as a pickle. The picklescan suite's own `malicious1` repack set (zip,
7z, flag-bit zips, central-directory zip, wrong-extension zip) is counted as published repack variants and
scored in the base set.

## Harness and verdict mapping (frozen; `run_scans.py` implements exactly this)

Every scan is one process per (tool, mode, target file), run as `nice -n 10 taskset -c 0-3` with
`OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4`, wall time by `time.monotonic()` around the
subprocess, output captured to `results/raw/`. Other benches run on the host at the same time, so timings
are taken under contention and are a secondary number.

| Tool / mode | Invocation | flagged | clean | skipped (tool did not look) | error |
|---|---|---|---|---|---|
| modelscan | `modelscan scan -p FILE -r json -o OUT --show-skipped` | JSON `issues` non-empty (any severity) | exit 0, no issues, file in `scanned` | exit 3, or file only in `skipped` | exit 2, or JSON `errors` non-empty with no issues |
| picklescan-file | `picklescan -p FILE -g` | exit 1 (≥1 Dangerous global) | exit 0 with `Scanned files: ≥1` | `Scanned files: 0` with exit 0 | exit 2 |
| picklescan-dir | `picklescan -p DIR -g` where `DIR` is a per-target directory holding only that file (hardlink) | same | same | `Scanned files: 0` (extension filtered) | exit 2 |
| fickling | harness `fickling_scan.py FILE`: `zipfile.is_zipfile` → `scan_zip_archive(graceful=True)` else `scan_file(graceful=True)`; prints JSON | any result severity > `LIKELY_SAFE` (the CLI's `--check-safety` threshold) | all severities `LIKELY_SAFE`, no errors, ≥1 scanned | zip with zero members ending `.pkl/.pickle/.bin` | `errors` non-empty and nothing flagged |

picklescan "Suspicious" globals alone do not flag under default settings; their count is recorded. `--strict`
is not run. Every flagged result also records the tool's own named globals or issue strings so mechanism
coverage can be tallied.

## Metrics

1. **Coverage** per tool and format: share of base files the tool looked inside (flagged or clean) versus
   skipped or error, reported per fixture set and per extension.
2. **Detection** on the 96 unsafe base files: flagged / unsafe, per set (`data`, `data2`, modelscan), and
   per tool; for picklescan this is the sanity check named above.
3. **False positives** on the 18 benign base files: count flagged, listed by file; errors on benign files
   listed separately (an error is not a false positive, but a real model that a scanner cannot read is a
   coverage gap and is reported as one).
4. **Junk behaviour**: verdict on the 4 junk files per tool.
5. **Evasion matrix**: for each (anchor, transform, tool, mode), the verdict, next to the anchor's base
   verdict. "Defeated" = base flagged, variant not flagged. For benign anchors the question is whether a
   rename or container changes a clean or skipped verdict into a flag or error.
6. **Identity in output**: for each tool, whether any output field carries a content digest (sha256 or other
   hash of the file or member), a component name, or a version, beyond the file path. Prediction below.
7. **Repeatability and timing**: 3 runs of every scan. Verdict flips across runs are counted (expected 0).
   Wall time median and CV per (tool, mode) over the whole base set and over the six real models,
   reported as secondary, under contention, monotonic clock.

## Hypotheses and what would prove each wrong

- **H1 (format coverage).** modelscan and picklescan-dir do not look inside the GGUF, safetensors or ONNX
  files (extensions outside their tables), and fickling attempts every file and returns an error or a
  clean verdict on those formats without flagging. The `.h5` is looked at by modelscan only; the PyTorch
  zip (`pytorch_model.bin`) is looked at by all three. *Wrong if* modelscan or picklescan-dir reports a
  GGUF/safetensors/ONNX file as scanned, or any tool flags one.
- **H2 (cross-tool detection on the bypass set).** On the 57 unsafe `data2` files, modelscan flags fewer
  than picklescan, and fewer than 80% of them, because its blocklist is the smaller one; fickling flags
  more than modelscan on the same set. *Wrong if* modelscan flags ≥ 80% of `data2` unsafe files, or
  fickling flags fewer than modelscan.
- **H3 (false positives).** No tool flags any of the six real models or the three benign pickles. fickling
  errors rather than flags on the non-pickle formats. The numpy object arrays (3 files) may be flagged by
  modelscan or fickling as a policy difference with picklescan; that is recorded as a false positive
  against the suite's label, with the disagreement noted. *Wrong if* any tool flags a real model file.
- **H4 (rename defeats extension-gated tools, not content-based ones).** For A1-A3, N1/N3/N4 (no
  extension, `.txt`, `.safetensors`) are skipped by modelscan and picklescan-dir and so defeat them, while
  picklescan-file and fickling still flag them. N2 (`.bin`) and N5 (`.pth`) are still flagged by all
  (both tools try pickle parsing after a failed PyTorch magic check). For A5 (`.npy` → anything else) the
  numpy path is lost in modelscan and picklescan-dir; picklescan-file falls back to pickle parsing, which
  is predicted to still flag because an `.npy` with an object dtype carries a pickle stream after the
  header, though this is the least certain cell. *Wrong if* modelscan or picklescan-dir flags an N1/N3/N4
  variant, or fickling misses one.
- **H5 (containers).** tar, tar.gz and gzip (C3-C5) defeat all three tools (none opens them). zip with the
  original member name (C1) is seen by all three. zip with a `.txt` member (C2) is seen by picklescan
  (content-based on members) but not by fickling (`scan_zip_archive` filters members to
  `.pkl/.pickle/.bin`) and not by modelscan (extension-gated members). Nested zip (C6) is seen by
  picklescan, rejected by modelscan ("does not support nested zip files"), and not opened by fickling
  (no recursion). PyTorch-layout zip (C7) is flagged by all three. *Wrong if* any tool flags a C3/C4/C5
  variant, or misses a C7 variant.
- **H6 (identity, the R4 tie-in).** No scanner output carries a content digest, component name, version,
  PURL or CPE; each identifies a finding by file path and member name only. So the SBOM side (R4: Syft
  records a sha256 for GGUF and safetensors but no PURL) and the scanner side have no common key. *Wrong
  if* any tool's output includes a hash of the scanned bytes or a package identifier.
- **H7 (repeatability).** Verdicts are identical across the three runs for every (tool, mode, target).
  *Wrong if* any verdict flips.

The bench supports the null for H-AI-ARTIFACT-INVENTORY-01's "existing tooling reaches these artifacts"
reading only if all three tools look inside every format, flag the unsafe set at high rates across suites,
and keep the verdict under rename and repack; partial results weaken the null on one host and one fixture
set and do not falsify it.

## Stop rule

Three runs per (tool, mode, target). A non-zero exit is a verdict (the tools use exit codes as verdicts),
not a failure; a harness failure (timeout at 600 s, or the subprocess cannot start) is retried once and then
recorded as a failure. No tool flag is tuned after seeing results; any non-default run (for example
`picklescan --strict` or `pip install picklescan[7z]`) would be a separate labelled post-hoc result.

## Cost and resources

$0; local CPU only, 4 cores under `taskset -c 0-3 nice -n 10`, no Docker, no network during the run.
Network was used before the run for the pinned PyPI installs (`logs/pip.log`) and the fixture downloads
(`logs/fetch_fixtures.log`; about 230 MB downloaded, the rest hardlinked from R4's tree, 917 MB in
`fixtures/`, up to about 2.5 GB more in `fixtures-variants/`). Fixtures and variants are local and are not
committed.
