---
type: benchmark-verification
title: "T6 fine-tune memorization: independent verification"
created: 2026-11-09
area: T6-finetune-memorization
verdict: NOT-VERIFIED
---

# T6 verification (independent agent, 2026-11-10 ~01:01Z)

## Verdict: NOT-VERIFIED

There is nothing to verify yet, so this is a verdict on the state of the run rather than a finding against its
numbers. At inspection time (2026-11-10T01:00:54Z and again 01:01:13Z) the folder holds no `RESULTS.md`, and
`results/` holds only `probe_sizing_marker.json`. The two run logs, `logs/train-lora-seed7.txt` and
`logs/measure-base.txt`, are 0 bytes, `ckpt/lora-seed7/` is empty, and no `train.py` or `measure.py` process
exists on the host (`pgrep -af "train.py|measure.py"` returns nothing; no python process has a cwd in this
folder). `COMMANDS.log` shows `train.py --arm lora --seed 7` launched at 00:58:57Z and `measure.py --ckpt base`
at 00:59:03Z, so both processes appear to have exited (or been killed with the launching session) without
writing a line. The bench agent's run summary says it is waiting on a watch for the first step-time and canary
lines, but with no live writer those lines will not arrive; the run needs to be relaunched, preferably with
`nohup`/`setsid` so it outlives the launching shell and with stderr captured to the log.

Re-running the full bench myself was out of scope: it is a multi-hour training run (4 h cap in the
pre-registration) and would be executing the bench, not verifying it.

## What was checked and holds

- **Pre-registration predates the run.** `sha256sum PREREGISTRATION.md` = `3d02e906b235ec510b084ed628f13aa28c37c0d573b9e3f467f79d72436853c7`,
  identical to `PREREGISTRATION.sha256`. Freeze at 2026-11-10T00:56:41Z (`prereg.frozen-at`, `COMMANDS.log`);
  corpus generation at 00:58:48Z and T0 run start at 00:58:57Z, both after the freeze. The only pre-freeze
  model work is `probe_sizing.py` (00:51:35Z) on random token ids, disclosed in the pre-registration. File
  mtimes agree (PREREGISTRATION.md 19:56 local, gen_corpus.py 19:57, data/ 19:58). No `RESULTS.md` exists,
  so the "frozen by agent before run; not owner-reviewed" header could not be checked.
- **Fixtures reproduce byte-for-byte.** `gen_corpus.py` re-run in `verify-scratch/` gives the same three
  sha256 values as `data/fixtures.sha256` (corpus `8287821d…`, canaries `1df4fcca…`, heldout `c48fa9cd…`),
  152 planted sentences, insertion counts exactly 0/0/1/1/5/5/20/20/50/50 into distinct notes.
- **No generator leak into the controls.** The n = 0 facility names and sentences occur 0 times in the corpus;
  every planted canary's sentence occurs exactly n times; no canary facility appears in the held-out set.
- **Versions recorded.** `requirements.txt` pins torch 2.9.1+cpu, transformers 4.57.6, peft 0.17.1,
  accelerate 1.10.1, safetensors 0.6.2, numpy 2.3.4, and `pip freeze` in the venv matches; the model revision
  `93efa2f0…` is pinned in the pre-registration and printed in `logs/probe_sizing.txt`.
- **Instrument matches the pre-registration (static read of `measure.py`).** Exposure = log2(10^4) − log2(rank)
  with rank = 1 + count of strictly higher log-probs (ties reported separately); decoding settings A/B/C match
  (T 0.7 p 0.9; T 1.0 untruncated; T 1.0 k 40); `torch.manual_seed(1000 + seed)`; success = lstrip then
  startswith(secret); blind extraction at T 1.0 on the facility-less prefix.
- **Spend.** $0 cap; no API calls in any script; only network use is the one-time model download.
- **Safety scope.** Secrets are random 4-digit strings in an obviously synthetic sentence about fictional
  facilities, labelled TEST FIXTURE in the generator and `canaries.json`; no real credential shape; no exploit
  code; no containers.

## Not done, and why

- **Number reproduction:** no numbers exist.
- **Claims vs evidence:** no claims exist beyond the README, which states method, not results.
- **Cross-provider (Gemini) leg:** skipped, because there are no result claims or excerpts to send; sending
  the pre-registration's hypotheses would test the design, not the evidence.

## Fixes made in place

None. `verify-scratch/` (regenerated fixtures) can be deleted.

## To make this verifiable

Relaunch the LoRA arm and base measurement detached, confirm `logs/train-lora-seed7.txt` gains per-step lines,
then re-run this verification after `RESULTS.md` lands. The stop rule's 4 h cap counts from corpus generation
(00:58:48Z), so a relaunch should be recorded as a deviation with its new T0, or the corpus step re-run to
reset the clock as the pre-registration defines it.
