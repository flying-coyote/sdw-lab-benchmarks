---
type: benchmark-verification
title: "T6 fine-tune memorization: independent verification"
created: 2026-11-10
area: T6-finetune-memorization
verdict: VERIFIED-WITH-FIXES
---

# T6 verification (second pass, independent agent, 2026-11-10 ~04:30Z)

VERIFIED-WITH-FIXES: every headline number traces to a results file and reproduces bit-for-bit on a re-run slice,
deviations are disclosed, and no identifier or secret is present; four small wording and disclosure fixes were made
in RESULTS.md, each marked `[fixed in verify]`. The partial status (one seed of three, no full fine-tune arm) is
disclosed in RESULTS and is a scope limit on the conclusions, not a verification failure.

## Pre-registration

- `sha256sum PREREGISTRATION.md` = `3d02e906b235ec510b084ed628f13aa28c37c0d573b9e3f467f79d72436853c7`, identical to
  `PREREGISTRATION.sha256` and to the hash quoted at the top of RESULTS.md. File mtime 00:56:35Z, unchanged since the
  first verification pass.
- Freeze 00:56:41Z (`prereg.frozen-at`, `COMMANDS.log`) precedes corpus generation (00:58:48Z), the first launch
  (00:58:57Z) and the relaunch (03:02:43Z). The only pre-freeze model work is the disclosed random-token probe.
- `train.py` (00:57:38Z) and `measure.py` (00:58:41Z) were written after the freeze and before the first launch, and
  their mtimes show no edit since. The pre-registration fixes their settings but does not hash them; a static read
  confirms LoRA r 16 / alpha 32 / dropout 0.05 / seven targets, AdamW 2e-4, wd 0, warmup 5 linear, batch 8, seq 256,
  clip 1.0, and decoding A/B/C as pre-registered. Disclosure added to RESULTS Method.

## Headline numbers traced (script: re-derived from all four `results/*.json`)

- Every rank and bits value in the exposure table, all 40 cells, matches its JSON, and every cited line number
  (12, 104 ... 840 for `"rank"`) is correct. `exposure_bits` recomputes as log2(10^4) − log2(rank) in every cell; ties 0.
- Extraction: 151 attempts per canary (1 + 3 × 50), 1,510 per checkpoint, total hits 0 on all four checkpoints. c09
  epoch-3 hit lines 856 / 867 / 886 / 905 are correct.
- Blind: 0 hits everywhere; four-digit outputs 57 / 109 / 174 / 182 of 200 (line 934). Held-out ppl 43.925 / 9.877 /
  3.286 / 2.482 (line 1002).
- Per-n medians (epoch-3 summary table and every H5 figure) recompute to the stated values; largest median fall 0.437
  bits (n = 50, epoch 2 to 3). c09 rank 337 = top 3.37%.
- Training: 87 steps, 29 / epoch, 231 sequences, 59,257 tokens, last-step losses 2.4459 / 1.263 / 0.9764, total
  3,294.7 s; first-10-step mean 81.28 s, projection 117.85 min (Deviation 5 correct). Probe 12.2 s per step confirmed.
- Exploratory table matches `results/explore_incontext.json` and `logs/explore_incontext.txt`.
- Hypothesis scoring (H1 wrong, H2 wrong, H3 wrong on clause 2, H4 holds, H5 not falsified, H6/H7 not run) follows
  from the numbers and the pre-registered tests.

## Reproduction

- Fixtures: `sha256sum -c data/fixtures.sha256` OK for all three files (and the first pass regenerated them
  byte-for-byte in `verify-scratch/`).
- Re-run slice (about 4 min on an idle host, cores 4-7, same venv, offline): c00, c08 and c09 exposure and all four
  extraction settings, the 200-sample blind run and held-out perplexity, on both base (seed 0) and seed 7 epoch 3.
  Every rank, secret log-prob, top-5, hit count, top-3 output list, blind count and perplexity matched the saved
  JSON exactly. Script and output:
  `/tmp/claude-1000/-home-jerem-project1/af12c3ec-6e7f-4f5c-a239-70fb7dfd0d6e/scratchpad/t6v/rerun.py`, `rerun.json`.
- Instrument cross-check: the digit-tree log-prob for c09 on base (−10.39642) agrees with a direct single forward
  pass over the full sequence (−10.39641), so the rank computation scores the right tokens.
- Not re-run: training (55 min under contention, outside the 20-minute slice). CPU training determinism was
  therefore not tested, but the adapters on disk reproduce the measurements exactly.

## Deviations

All eight deviations in RESULTS match `COMMANDS.log` (stamps, elapsed seconds, rc=2 argparse failure, reorder
before any fine-tuned result, skips at 10,746 s past the 9,900 s line, full-FT not started, lane done at 11,411 s
inside 14,400 s). Two gaps were added as disclosures: the post-freeze authoring of the scripts (above), and that
A, B and C share one RNG seed per checkpoint, so their samples are paired; B and C have identical top-3 outputs in
27 of 40 cells.

## Secrets and identifiers

Grep of `results/` and `RESULTS.md` for API-key, token, AWS, GitHub, Slack, email, home-path, username, employer and
account patterns: no hits other than the word "tokens" in counts. The only secrets are the TEST FIXTURE 4-digit
canaries, by design.

## Fixes made in RESULTS.md (each marked `[fixed in verify]`)

1. c08 at epoch 3 is 0.70 bits below its epoch-1 value and below its base value, not "slightly below".
2. 19,599,208 bytes is the adapter directory total; the safetensors file is 19,593,064 bytes.
3. Method: scripts written post-freeze, pre-launch, unmodified; not hashed by the pre-registration.
4. Limits: A/B/C samples are paired through the shared seed.

## Earlier pass (2026-11-10 ~01:01Z, superseded)

The first pass returned NOT-VERIFIED because the original launch had died with empty logs and no results existed;
it confirmed the pre-registration hash and timing, byte-for-byte fixture regeneration in `verify-scratch/`, no
generator leak into the n = 0 controls, pinned versions, and a static read of `measure.py`. RESULTS.md cites that
regeneration, which still holds. `verify-scratch/` can be deleted.
