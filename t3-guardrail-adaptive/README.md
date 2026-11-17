# t3-guardrail-adaptive (T3)

## What it measures

What a vendor claim like "blocks prompt injection" can mean in measured terms: three small open
prompt-injection and jailbreak classifiers (Protect AI DeBERTa v2, deepset DeBERTa, jackhhao BERT jailbreak
classifier) run on CPU against public, citable attack and benign sets (deepset prompt-injections, Lakera
Gandalf, in-the-wild jailbreaks, NotInject, Dolly, JBB benign), untransformed and under nine documented input
transformations from the literature (character spacing, Base64, ROT13, leetspeak, upper-casing, vowel removal,
zero-width characters, Cyrillic homoglyphs). Detection rate, false-positive rate, the drop under each
transform, Wilson and paired-bootstrap 95% intervals, truncation share, determinism.

Meta Prompt Guard 2 was named in the brief and is not here, because its repos are gated and this host has no Hugging
Face token (declared in `PREREGISTRATION.md` before the run).

## Result

Under character spacing, Base64, ROT13 and leetspeak none of the three classifiers kept useful separation between
attack and benign text, and each failed differently: `protectai-v2` went blind on short direct injections under
the encodings, `deepset` flagged almost any transformed text, and `jackhhao-jb` went blind under spacing
(`RESULTS.md`, Headline, with `results/tables.md` line numbers). The detection and false-positive rates are measured
on public sets the classifiers were not built around, so they could have come out otherwise, and four of the eight
pre-registered hypotheses held while four did not (`RESULTS.md`, verdict table). The discrimination score J that the headline leads with is a post-hoc view and is
labelled so in `RESULTS.md`.

## What would have made it fail

Each hypothesis in `PREREGISTRATION.md` carries a falsifier on a Wilson or bootstrap bound, and the untransformed T0
pass on the same items is the baseline every transform is compared against. Benign sets (NotInject, Dolly, JBB
benign, in-the-wild regular prompts) measure false positives on the same models.

## Pre-registration

`PREREGISTRATION.md`, frozen by agent before the run and not owner-reviewed, with freeze time 2026-11-10T00:52:49Z in
`FROZEN.sha256` and a chrony reading in `clock-pre-run.txt`. A dated amendment (2026-11-10) was appended after the
run, so the whole file no longer matches the frozen hash; its first 201 lines, everything above the amendment
heading, hash to `63d5aaff…3e10`, which is the value in `FROZEN.sha256`, so the frozen body is intact. The amendment
records that the stop rule dropped T6 and T8 and capped A3 and B4 at 150 items, and that a further cut to 50 items for
T2 to T5 and T7 went beyond the stop rule; no hypothesis, metric or threshold changed.

## Reproduce

Local CPU only, no paid calls:

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # torch from https://download.pytorch.org/whl/cpu
.venv/bin/python fetch_data.py
for m in protectai-v2 deepset jackhhao-jb; do .venv/bin/python run.py $m; .venv/bin/python run_stability.py $m; done
.venv/bin/python analyze.py && .venv/bin/python verdicts.py
```

`run_all.sh` is the driver the run used. Fixtures regenerate from pinned dataset revisions, and the per-item score
files (`results/scores-*.jsonl`, `results/stability-*.jsonl`) and fixture JSONL are gitignored. `COMMANDS.log` and
`fixtures/MANIFEST.json`, which the docs cite for exact commands and fixture hashes, are not committed, so a
regeneration cannot be checked against the original fixture hashes from this tree.

## Results

- `RESULTS.md` is the entry point: headline, verdicts per hypothesis (computed by `verdicts.py`), mechanism notes,
  method as run, deviations, limits.
- `results/tables.md`, `results/summary.json` and `results/verdicts.json` hold the tables and metrics the RESULTS
  lines cite; `results/log-*.txt` are the per-model run logs.
- `VERIFICATION.md` is the independent check (VERIFIED-WITH-FIXES); its fixes are marked `[fixed in verify]` in
  `RESULTS.md`.

## Versions and pins

`requirements.txt` pins every package with `==` (torch 2.15.0+cpu, transformers 5.22.2 and the rest), taken from the
venv that ran the bench. Model checkpoints and dataset revisions are pinned in `PREREGISTRATION.md`.

## Evidence tier and limits

`RESULTS.md` states no tier letter. Three base-size open classifiers on CPU rather than the commercial products that
wrap similar models, declared contamination on `deepset`'s A1 and B1 and on A3 for the other two, single user-turn
strings only, and capped A3 and B4 cells that lean toward the lowest source indices. See Limits in `RESULTS.md`.

## Corrections

- 2026-11-17: three passages of `RESULTS.md` that narrated the finishing agent's steps in the first person were
  recast in neutral voice with no change of substance; this README was restructured to the lab layout and now records
  the prefix-hash check on the amended pre-registration and the uncommitted `COMMANDS.log` and fixture manifest.
