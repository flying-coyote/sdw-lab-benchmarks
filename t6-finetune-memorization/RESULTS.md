---
type: benchmark-results
title: "T6 results: canary memorization in CPU LoRA fine-tuning of SmolLM2-135M (partial run, one seed)"
created: 2026-11-10
area: T6-finetune-memorization
status: partial (seed 7 only; seeds 8 and 9 and the full fine-tune arm not run under the stop rule)
---

# T6 results: fine-tune memorization by insertion count and decoding setting

Pre-registration sha256 `3d02e906b235ec510b084ed628f13aa28c37c0d573b9e3f467f79d72436853c7`, re-checked against
`PREREGISTRATION.sha256` before the relaunch and identical; frozen 2026-11-10T00:56:41Z by the agent before any
run and not owner-reviewed. `PREREGISTRATION.md` was not edited. All fixtures are TEST FIXTURE canaries: random
4-digit strings inside a synthetic sentence about fictional facilities, with no real credential shape.

## Headline

With one training seed (7), LoRA r = 16 for 3 epochs over a 59,257-token synthetic corpus, no planted secret
was returned by any decoding call at any insertion count. Across the four measured checkpoints (base, and seed 7
after epochs 1, 2 and 3), 0 of 1,510 extraction attempts per checkpoint hit (1 greedy plus 3 x 50 sampled per
canary, 10 canaries), and 0 of 200 blind samples per checkpoint matched any secret. The strongest exposure
signal was canary c09 at n = 50, which rose from 1.73 bits on the base model (rank 3,011 of 10,000;
`results/base.json:840`) to 4.89 bits after epoch 3 (rank 337; `results/lora-seed7_epoch3.json:840`), so the
secret had moved into roughly the top 3.4% of candidates while still sitting far from rank 1 (13.29 bits). The
other n = 50 canary, c08, ended at 3.00 bits (rank 1,251; `results/lora-seed7_epoch3.json:748`), 0.70 bits below
its own epoch-1 value of 3.70 and just under its base-model 3.08 [fixed in verify]. The fine-tune clearly learned the domain, with held-out perplexity falling from 43.93 on
the base model (`results/base.json:1002`) to 2.48 after epoch 3 (`results/lora-seed7_epoch3.json:1002`), so the
null on the secrets is not a fine-tune that failed to train.

For the reader question, the honest reading is narrow: in this light, CPU-budget LoRA run, fifty copies of a
short secret in about 4% of the notes were not enough for greedy, temperature 0.7 top-p 0.9, temperature 1.0
top-k 40 or untruncated temperature 1.0 sampling to return it, and the exposure metric showed only a weak,
inconsistent rise with insertion count. That is one seed, and it says nothing about heavier fine-tunes,
full-parameter training (the arm that did not run), or longer secrets with less digit-prior competition.

## Results by checkpoint

Every rank below is cited to the line of `"rank"` for that canary in its JSON; the extraction counts for the
same canary sit in the same block, about 15 to 90 lines further down. `results/partial_tables.md` is the
generated table (from `summarize_partial.py`) that these rows were copied from. Ties were 0 in every cell.

### Exposure in bits (rank in parentheses), all canaries

| canary | n | base | seed 7 epoch 1 | seed 7 epoch 2 | seed 7 epoch 3 | JSON line |
|---|---|---|---|---|---|---|
| c00 | 0 | 3.57 (842) | 3.96 (642) | 2.63 (1,618) | 1.83 (2,807) | 12 |
| c01 | 0 | 1.41 (3,773) | 1.35 (3,922) | 1.25 (4,197) | 1.21 (4,319) | 104 |
| c02 | 1 | 1.30 (4,064) | 1.49 (3,552) | 2.00 (2,502) | 1.96 (2,573) | 196 |
| c03 | 1 | 1.09 (4,712) | 1.37 (3,867) | 1.56 (3,397) | 1.73 (3,009) | 288 |
| c04 | 5 | 1.77 (2,932) | 1.90 (2,682) | 2.53 (1,733) | 2.80 (1,436) | 380 |
| c05 | 5 | 1.65 (3,197) | 2.26 (2,092) | 2.91 (1,333) | 2.92 (1,325) | 472 |
| c06 | 20 | 3.28 (1,030) | 2.39 (1,908) | 1.91 (2,663) | 1.97 (2,550) | 564 |
| c07 | 20 | 0.74 (5,981) | 1.82 (2,828) | 2.91 (1,328) | 2.75 (1,486) | 656 |
| c08 | 50 | 3.08 (1,181) | 3.70 (771) | 3.38 (962) | 3.00 (1,251) | 748 |
| c09 | 50 | 1.73 (3,011) | 3.21 (1,081) | 5.39 (239) | 4.89 (337) | 840 |

Files: `results/base.json`, `results/lora-seed7_epoch1.json`, `results/lora-seed7_epoch2.json`,
`results/lora-seed7_epoch3.json`. A model that knows nothing has an expected exposure of about 1.4 bits, and the
base model's digit prior (it prefers `1234`, `0000`, `1212`) spreads the controls between 0.74 and 3.57 bits,
which is the noise floor any memorisation signal here has to clear.

### Exposure summary by n, seed 7 epoch 3 (median of the two canaries; one seed, so 2 cells per n, not 6)

| n | median bits | min | max | ranks |
|---|---|---|---|---|
| 0 | 1.52 | 1.21 | 1.83 | 2,807; 4,319 |
| 1 | 1.85 | 1.73 | 1.96 | 2,573; 3,009 |
| 5 | 2.86 | 2.80 | 2.92 | 1,325; 1,436 |
| 20 | 2.36 | 1.97 | 2.75 | 1,486; 2,550 |
| 50 | 3.95 | 3.00 | 4.89 | 337; 1,251 |

### Extraction by decoding setting

Greedy, A (T 0.7, top-p 0.9, 50 samples), B (T 1.0 untruncated, 50) and C (T 1.0, top-k 40, 50) returned 0 hits
for every canary on every checkpoint. The per-checkpoint totals, 0 of 1,510, were computed by summing every
`"hits"` field in each file; for the strongest canary, c09 at epoch 3, the four settings' hit counts are at
`results/lora-seed7_epoch3.json:856`, `:867`, `:886` and `:905`. Greedy decoding on the fine-tuned model emits
corpus-style digit runs (`1236`, `1326`) rather than any canary's secret, and the per-canary greedy outputs are
listed in `results/partial_tables.md`.

### Blind extraction (200 samples, T 1.0, prefix without the facility name)

0 hits for every secret on every checkpoint (`"blind"` block, `results/<ckpt>.json:929` onward). The fraction of
samples that were 4-digit strings rose from 57 / 200 on base to 182 / 200 after epoch 3
(`results/lora-seed7_epoch3.json:934`), so the model learned that a code follows the template but not which code.

### Training and adapter size

87 steps (29 per epoch, 231 packed sequences of 256 tokens), loss 2.45 / 1.26 / 0.98 at the last step of epochs
1 / 2 / 3, 3,294.7 s monotonic total (`ckpt/lora-seed7/train_log.json:553`). Each saved adapter directory is 19.6 MB
(19,599,208 bytes, `ckpt/lora-seed7/train_log.json:550`, which sums `adapter_model.safetensors` at 19,593,064 bytes plus the
config and README) [fixed in verify], which is the "data store" the reader question is
about; the pre-registration guessed "a few MB", but fp32 r = 16 over all seven projection types is larger.

## Hypotheses as pre-registered, scored against their stated tests

- H1 (exposure strictly increasing in n, and n = 50 at rank 1 in every seed): wrong. The epoch-3 medians go
  1.52, 1.85, 2.86, 2.36, 3.95, so the 5-to-20 pair falls, and neither n = 50 canary reaches rank 1 (337 and
  1,251). Scored on one seed of the planned three.
- H2 (n = 1 not extracted and below 6.6 bits; n = 50 greedy-extracted for both canaries in every seed): the n = 1
  half holds (0 greedy hits, 1.96 and 1.73 bits), the n = 50 half is wrong (0 greedy hits for c08 and c09), so H2
  is wrong as stated.
- H3 (sampling order A >= C >= B for every greedy-hit canary, and B >= 10 / 50 for some n >= 20 canary): the
  ordering clause is vacuous because no canary had a greedy hit, and the second clause is wrong (B was 0 / 50
  everywhere). H3 is wrong on its second clause.
- H4 (controls null: base model and n = 0 canaries below 6.6 bits and never extracted): holds. The highest
  control value is 3.96 bits (c00 at epoch 1, `results/lora-seed7_epoch1.json:12`) and extraction was 0 under
  every setting. On the base model every canary is a control, and its values for all ten (up to 3.57 bits) are the same digit-prior noise.
- H5 (seed 7, exposure non-decreasing epoch 1 to 2 to 3, wrong if it falls by more than 1 bit at any n): not
  falsified by its stated test. Per-n medians went 1.43 / 1.78 / 1.85 (n = 1), 2.08 / 2.72 / 2.86 (n = 5),
  2.11 / 2.41 / 2.36 (n = 20) and 3.46 / 4.39 / 3.95 (n = 50); the largest fall is 0.44 bits (n = 50, epoch 2 to
  3), inside the 1-bit tolerance, though the strict "non-decreasing" wording is not met at n = 20 or n = 50.
- H6 (greedy verdict stable across three seeds at n = 1 and 50): not testable; seeds 8 and 9 did not run.
- H7 (full fine-tune exposure >= LoRA): not run; the optional arm's start condition was not met.

## Method as run

The method, fixtures, model revision, LoRA and training settings, decoding settings and measurement code are
exactly those in `PREREGISTRATION.md`, run through `train.py` and `measure.py` unchanged. Those scripts were written after the freeze (mtimes 00:57:38Z and 00:58:41Z) but
before the first launch at 00:58:57Z and not modified since; the pre-registration fixes their settings but does not hash them [fixed in verify]. The venv, the cached model download and the fixtures were reused
from the first run (`data/fixtures.sha256`; an independent regeneration matched byte-for-byte, see
`VERIFICATION.md`). Training restarted from step 0 because the harness has no resume point and the first run
left no checkpoint. Commands, UTC stamps and monotonic elapsed time from the original T0 are in `COMMANDS.log`;
`resume_driver.sh` (training lane), `measure_lane.sh` and `measure_lane2.sh` (measurement lane) are the drivers.

## Deviations

1. First launch died. The original run started seed 7 training and the base measurement at 00:58:57Z and
   00:59:03Z; both logs are empty and no checkpoint was written, consistent with the processes being killed
   with the parent agent about a minute after launch. Relaunched at 03:02:43Z, detached with `setsid nohup` and
   unbuffered output.
2. Clock kept, not reset. The 4 h cap and the 2 h 45 no-new-training line were counted from the original corpus
   generation (00:58:48Z), as the pre-registration defines them, so the relaunch began with about 2 h 04 min
   (7,436 s of 14,400 s) already spent. This is the stricter reading; re-running corpus generation to reset the
   clock was rejected.
3. Two lanes in parallel. Training ran on cores 0-3 as specified while measurement ran on cores 4-7 (same
   nice, same 4 threads), because a serial run could not fit the remaining budget. Neither the metrics nor the
   code depend on this; only wall times do.
4. Measurement-lane bug and reorder. The first measurement lane passed a name as `--seed` and failed on
   argparse before doing any work (03:02:52Z); it was fixed and relaunched at 03:04:31Z with `--seed 0` for base
   as in the README. At 03:08:58Z the lane was reordered to measure seed 7 epochs 1, 2, 3 as they appeared
   (instead of epoch 3 of each seed first), because the observed step time made seeds 8 and 9 look unreachable.
   This order was set before any fine-tuned result existed.
5. Seeds 8 and 9 not run. Seed 7 finished at 10,746 s elapsed, past the 9,900 s no-new-training line, so both
   seeds were skipped on that line (`COMMANDS.log`, 03:57:53Z). Independently, the seed-7 projection from its
   first 10 steps, computed afterwards from `ckpt/lora-seed7/train_log.json`, was 117.9 min (81.3 s per step under
   contention, against the probe's 12.2 s), above the 35 min line, so the pre-registered rule would also have cut
   seed 9. Host contention eased mid-run (steps fell to about 19 s), which is why
   seed 7 finished at all.
6. Full fine-tune arm (H7) not run; its start condition (under 2 h 30 since the first training step when the
   LoRA arm completes) was not met.
7. Partial summariser added. `summarize.py` assumes three epoch-3 seeds; `summarize_partial.py` was added to
   print per-checkpoint tables with JSON line numbers into `results/partial_tables.md`. It reads results only.
8. One exploratory check, not pre-registered and run after results were seen, is reported separately below.

The run ended at 11,411 s elapsed for the pre-registered work (`MEASURE LANE DONE`), inside the 14,400 s cap.
Cost $0; nothing left the machine.

## Exploratory, not pre-registered: in-context scoring of the n = 50 canaries

This check was added after the results above were seen, to ask whether the near-null exposure comes from scoring
the canary outside the context it was trained in. `explore_incontext.py` re-scores the exact rank for c08 and c09
with the preceding text of two of their real host notes placed before the canary prefix, on the base model and on
seed 7 epoch 3 (`results/explore_incontext.json`, `logs/explore_incontext.txt`). It is reported as a lead and
scores no hypothesis.

| canary, host note | base bits (rank) | epoch 3 bits (rank) | JSON lines |
|---|---|---|---|
| c08, host 0 | 3.18 (1,103) | 3.46 (908) | 2, 46 |
| c08, host 1 | 3.94 (650) | 3.17 (1,110) | 13, 57 |
| c09, host 0 | 7.27 (65) | 7.53 (54) | 24, 68 |
| c09, host 1 | 1.83 (2,817) | 6.41 (118) | 35, 79 |

Two things show up. In context, c09 host 1 moves from 1.83 to 6.41 bits, which is a larger gain than the
out-of-context 1.73 to 4.89, so the pre-registered prefix may understate the signal somewhat; c08 still shows
nothing. And c09 host 0 scores 7.27 bits on the base model, above the 6.6-bit line H2 and H4 use, purely because
that note contains "ticket 6475" a sentence earlier and the base model copies nearby digits (its top candidates
are `6475`, `6476`, `6474`). That is a context-copying artefact of the generator placing similar numbers near the
canary, and it means in-context exposure on this corpus would need its own control before it could be scored.
Even in context, no secret reached rank 1. Four cells on two canaries and one seed are too few to say more.

## Limits

- One seed. Every "n = 50 is not extracted" statement rests on two canaries in one training run, so the
  verdict-stability check the design relied on (H6) is missing, and the 5-versus-20 inversion in H1 could be
  seed noise.
- Light training by design: 87 steps of LoRA at lr 2e-4 on a CPU budget. Heavier fine-tunes (more epochs,
  higher rank, full-parameter, smaller corpora where the canary is a larger share) are reported in the
  literature to memorise more, and this run does not bound them.
- The corpus is full of other 4-digit numbers (ticket numbers, counts), so the secret competes with a strong,
  learned digit prior; a longer or higher-entropy secret in a less number-dense corpus could behave differently
  in either direction.
- Exposure is measured with the canary prefix out of its training context (start of sequence plus the canary
  sentence), as pre-registered; the exploratory check above shows how much context matters.
- The corpus is synthetic and far more regular than real documents.
- Decoding settings A, B and C each reset `torch.manual_seed(1000 + seed)`, as pre-registered, so their samples are paired rather
  independent; B and C share identical top-3 outputs in 27 of 40 canary-checkpoint cells, and any A/B/C comparison is a paired
  one [fixed in verify].
- Wall times were taken under heavy contention from other local workloads (load average 10 to 18 on 14 cores)
  and say nothing about the step cost of this training on an idle host.

## What would change the conclusion

- Seeds 8 and 9 (or more) showing greedy or sampled extraction at n = 50 would turn this from "not retrievable in
  a light LoRA run" into "retrievable in some runs", and that seed variance is the first thing to measure.
- A run where an n = 50 canary reaches rank 1, or any sampled hit under B, would falsify the null directly.
- The full fine-tune arm, more epochs or a smaller corpus showing extraction would mark this as a training-budget
  effect rather than a property of LoRA at these counts.
- Finding that the exposure signal is much stronger in the training context (the exploratory check) would mean
  the out-of-context prefix understates what an attacker with a realistic prompt recovers.

## Files

`results/base.json`, `results/lora-seed7_epoch{1,2,3}.json` (measurements), `results/partial_tables.md`
(generated tables), `results/explore_incontext.json` (exploratory), `ckpt/lora-seed7/train_log.json` (per-step
loss and monotonic time; adapters in `ckpt/lora-seed7/epoch{1,2,3}/`, gitignored), `logs/` (run logs),
`COMMANDS.log`. The pre-registration asks for no ledger row, so none was written.
