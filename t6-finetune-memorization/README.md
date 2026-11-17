---
type: benchmark-readme
title: "T6: fine-tune memorization of planted canaries (secret-sharer), SmolLM2-135M LoRA on CPU"
created: 2026-11-09
area: T6-finetune-memorization
---

# T6: fine-tune memorization by insertion count and decoding setting

## What it measures

A fine-tuned model is a store of the text it was trained on, so it inherits that text's classification and
access control. This bench measures how many times a short secret has to appear in a small fine-tuning corpus
before an ordinary decoding call returns it, using the secret-sharer method (Carlini et al. 2019): planted
4-digit canaries at 0, 1, 5, 20 and 50 insertions, exact exposure over all 10^4 candidate secrets, and
extraction rate under four decoding settings, against the base model as a control.

## Result

With one training seed (7), LoRA r = 16 for 3 epochs over a 59,257-token synthetic corpus, no planted secret was
returned by any decoding call at any insertion count (0 of 1,510 extraction attempts per checkpoint), and the
strongest exposure signal, canary c09 at n = 50, rose from 1.73 bits on the base model to 4.89 bits after epoch 3
(`results/base.json:840`, `results/lora-seed7_epoch3.json:840`), while held-out perplexity fell from 43.93 to 2.48, so
the null is not a fine-tune that failed to train (`RESULTS.md`, Headline). This is a measured null: the planted
canaries could have been extracted, and the pre-registration predicted that the n = 50 canaries would be. It rests on
one seed of the three planned, because seeds 8 and 9 and the full fine-tune arm did not fit the time budget.

## What would have made it fail

Each hypothesis in `PREREGISTRATION.md` has a stated test, and H1, H2 and H3 were wrong. The base model and the n = 0
canaries are the control (H4, which held), and exposure is exact over all 10,000 candidates rather than sampled.

## Pre-registration

`PREREGISTRATION.md`, frozen by agent before any run and not owner-reviewed. Its sha256 in `PREREGISTRATION.sha256`
(`3d02e906…53c7`) still matches, and `prereg.frozen-at` records 2026-11-10T00:56:41Z, before the first training start
at 00:58:57Z in `logs/t0-run-start.txt`. Eight deviations are listed in `RESULTS.md`, among them the relaunch after the
first launch died, the two parallel lanes, and the seeds and arm that did not run.

## Reproduce

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python gen_corpus.py
nice -n 10 taskset -c 0-3 env OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 .venv/bin/python train.py --arm lora --seed 7
nice -n 10 taskset -c 0-3 env OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 .venv/bin/python measure.py --ckpt base --seed 0
nice -n 10 taskset -c 0-3 env OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 .venv/bin/python measure.py --ckpt ckpt/lora-seed7/epoch3 --arm lora --seed 7
.venv/bin/python summarize.py
```

The corpus and canaries are deterministic (one seeded RNG, fixed sub-seed), so the fixtures reproduce
byte-for-byte; training on CPU with fixed seeds is reproducible on the same library versions but not
guaranteed across BLAS builds. Timings in RESULTS were taken under contention from other benches and under a
4-core cap, so only the memorisation metrics and within-run ratios travel. The generated `data/` directory, the
adapter weights (only `adapter_config.json` and the per-epoch notes are committed under `ckpt/`) and `COMMANDS.log`
are not in the repo. `resume_driver.sh`, `measure_lane.sh` and `measure_lane2.sh` are the drivers the run used.

Files:

- `gen_corpus.py` writes `data/` (synthetic corpus, TEST FIXTURE canaries, held-out set; `data/fixtures.sha256`).
- `train.py` writes `ckpt/<arm>-seed<k>/epoch<e>/` (LoRA adapters per epoch, train log with per-step loss and
  monotonic time).
- `measure.py` writes `results/<ckpt>.json` (exposure, extraction, blind extraction, held-out perplexity).
- `summarize.py` builds markdown tables from `results/`; `summarize_partial.py` (Deviation 7) does the same for the
  one seed that ran.
- `probe_sizing.py` and `logs/probe_sizing.txt` are the pre-freeze sizing probe on random tokens.

## Results

- `RESULTS.md` is the entry point: tables, hypotheses scored, deviations, an exploratory in-context check, limits.
- `results/base.json` and `results/lora-seed7_epoch{1,2,3}.json` are the measurements; `results/partial_tables.md`
  the generated tables the RESULTS rows were copied from.
- `results/explore_incontext.json` is exploratory, not pre-registered, and run after results were seen.
- `VERIFICATION.md` is the independent check (VERIFIED-WITH-FIXES); `verify-scratch/` holds the verifier's copy of
  `gen_corpus.py` used to confirm the corpus regenerates byte for byte, and is not part of the result.

## Versions and pins

`requirements.txt` pins torch 2.9.1+cpu, transformers 4.57.6, peft 0.17.1, accelerate 1.10.1, safetensors 0.6.2 and
numpy 2.3.4, every line with `==`; `logs-pip-install.txt` is the install log.

## Evidence tier and limits

`RESULTS.md` states no tier letter. One seed, a 135M-parameter model, a light LoRA run, 4-digit secrets that compete
with a digit prior, and no full fine-tune arm; the result says nothing about heavier fine-tunes or longer secrets.
See Limits in `RESULTS.md`.

## Corrections

- 2026-11-09: verifier fixes are marked `[fixed in verify]` in `RESULTS.md`.
- 2026-11-17: this README was restructured to the lab layout, with no change to the existing method text.

## Safety and scope

Defensive measurement only. The secrets are random digits inside an obviously synthetic sentence about a
fictional facility; no real credential format (keys, tokens, card numbers) appears anywhere, nothing leaves
the machine except the one-time model download, and no exploit code is involved.
