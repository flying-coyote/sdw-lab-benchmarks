---
type: benchmark-readme
title: "T6: fine-tune memorization of planted canaries (secret-sharer), SmolLM2-135M LoRA on CPU"
created: 2026-11-09
area: T6-finetune-memorization
---

# T6: fine-tune memorization by insertion count and decoding setting

A fine-tuned model is a store of the text it was trained on, so it inherits that text's classification and
access control. This bench measures how many times a short secret has to appear in a small fine-tuning corpus
before an ordinary decoding call returns it, using the secret-sharer method (Carlini et al. 2019): planted
4-digit canaries at 0, 1, 5, 20 and 50 insertions, exact exposure over all 10^4 candidate secrets, and
extraction rate under four decoding settings, against the base model as a control.

- `PREREGISTRATION.md` (frozen before any run; sha in `PREREGISTRATION.sha256`, time in `prereg.frozen-at`)
- `RESULTS.md` (tables, hypotheses scored, deviations, limits)
- `gen_corpus.py` -> `data/` (synthetic corpus, TEST FIXTURE canaries, held-out set; `data/fixtures.sha256`)
- `train.py` -> `ckpt/<arm>-seed<k>/epoch<e>/` (LoRA adapters per epoch, train log with per-step loss and monotonic time)
- `measure.py` -> `results/<ckpt>.json` (exposure, extraction, blind extraction, held-out perplexity)
- `summarize.py` (markdown tables from `results/`)
- `probe_sizing.py`, `logs/probe_sizing.txt` (pre-freeze sizing probe on random tokens)
- `COMMANDS.log` (every command, UTC-stamped), `logs/` (run logs, clock state)

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
4-core cap, so only the memorisation metrics and within-run ratios travel.

## Safety and scope

Defensive measurement only. The secrets are random digits inside an obviously synthetic sentence about a
fictional facility; no real credential format (keys, tokens, card numbers) appears anywhere, nothing leaves
the machine except the one-time model download, and no exploit code is involved.
