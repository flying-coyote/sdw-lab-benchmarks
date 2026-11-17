# agent-telemetry-retention (R6)

## What it measures

What a year of agent and LLM telemetry costs to keep, in bytes per million billed tokens, when OCSF 1.9.0
records carrying the `ai_operation` profile are stored with metadata only (T0), with a hash of the text (T1), with the
per-request delta text (T2), or with the full prompt as sent (T3). Parquet (pyarrow 24.0.0) and Iceberg (pyiceberg
0.12.0), zstd levels, Parquet dictionary encoding, row order, and a trained zstd dictionary for the per-record regime
are compared, and the bytes are priced with the inputs in `../cost-to-serve-retention/cost_model.py`.

## Result

For a coding-agent fleet, metadata only stored about 1.1 KB per million billed tokens, a hash about 2.6 KB, delta text
26 to 32 KB and the full prompt from about 0.2 MB to 0.9 MB, so full-context text runs roughly 180 to 800 times the
metadata footprint, and the spread comes from how the file is written rather than from the codec name; priced at
365-day steady state, 1,000 coding users would hold between 0.83 TB and 3.9 TB of full prompt text, about $19 to $89 a
month on S3 Standard (`RESULTS.md`, Headline). The byte sizes are measured, exactly and on one host, while the
fleet volumes and token rates come from vendor documentation (Tier B for what a product does, Tier C for usage
figures) and one Tier D assumption for the chat tier, so the dollar figures are a derived layer on top of the
measurement. The top of the full-prompt range comes from an exploratory single-seed probe; the pre-registered grid
alone gives 0.85 to 3.4 TB.

## What would have made it fail

H1 to H7 in `PREREGISTRATION.md` each carry a falsifier, and H4 was falsified for the text arms while H7 was falsified
on one metadata cell. A high-entropy text corpus runs beside the real-text corpus as the control for how much of each
effect comes from the text being compressible, and seed 99 is held out for dictionary training only.

## Pre-registration

`PREREGISTRATION.md`, frozen by agent before any measurement and not owner-reviewed, at 2026-11-09T22:56:38Z
(`.frozen`). There is no separate hash file; the sha256 recorded at the top of `RESULTS.md` (`4b7a0bd5…a407`) still
matches the file. The corpora the run measured were generated at 22:58Z (`results/data-sha256.txt` header), after the
freeze. Fixes made under the stop rule, including the Iceberg parity re-run, are listed in `RESULTS.md` under
Deviations and fixes.

## Reproduce

The Commands block in `RESULTS.md` is the exact sequence (local CPU only, no paid calls, about 3 minutes on the
Beelink): create the venv from `requirements.txt`, run `generate.py` for each tier, corpus and seed, then
`measure.py`, `measure.py iceberg`, the exploratory `probe_page_batching.py`, and `price.py`. The first line of that
block changes into the original scratch directory and has to be pointed at this folder.

Generated corpora (`data/`, about 2.1 GB) are gitignored. The high-entropy corpora regenerate byte-identically from
the seeds, but the real-text corpora do not, because `generate.py` reads the lab's own markdown as its prose pool and
that pool kept changing after the run. Exact numbers therefore need the original `data/` files, whose sha256 are in
`results/data-sha256.txt`; regenerated corpora land near, but not always inside, the three-seed range
(`VERIFICATION.md`).

## Results

- `RESULTS.md` is the entry point: headline, what drives the full-context number, the measured layer, the one-year
  bill, hypotheses, deviations and fixes, limits, commands.
- `results/summary.json` and `results/tables.md` hold the derived tables; `results/corpus.jsonl`,
  `results/parquet.jsonl`, `results/iceberg.jsonl` and `results/dict.jsonl` the per-cell measurements;
  `results/probe_page_batching.json` the exploratory probe.
- `results/iceberg-PREFIX-parity-missing-page-row-limit.jsonl` is the Iceberg measurement from before the parity
  fix, kept for the record and superseded by `results/iceberg.jsonl`.
- `results/source-pool-manifest-at-verification.txt` lists the prose pool as it stood at verification, not at run
  time.
- `VERIFICATION.md` is the independent check (VERIFIED-WITH-FIXES), which reproduced the exact numbers from the
  original corpora.

## Versions and pins

`requirements.txt` is the `pip freeze` of the venv that ran, with every line pinned (pyarrow 24.0.0, pyiceberg
0.12.0 among them).

## Evidence tier and limits

Measured layer, exact byte sizes on one host from synthetic OCSF 1.9.0 records whose text is real public code and
prose; volume layer Tier B and C from vendor documentation plus one Tier D chat-tier assumption; price layer AWS
us-east-1 list prices (`RESULTS.md`, layer labels). Privacy, erasure and legal exposure, which are the real reasons to
drop or hash prompt text, are not priced. See Limits in `RESULTS.md`.

## Corrections

- 2026-11-09: verifier fixes are marked in `RESULTS.md`.
- 2026-11-17: two first-person phrases in `RESULTS.md` were recast in neutral voice; this README was restructured to
  the lab layout and now names the superseded pre-fix Iceberg file.
