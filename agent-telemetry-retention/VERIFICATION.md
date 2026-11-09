---
type: evidence
title: "R6 agent-telemetry retention: independent verification"
created: 2026-11-09
tags: [verification, ai-telemetry, ocsf, retention, parquet, iceberg]
---

# Verification of R6 (agent-telemetry retention bill)

**Verdict: VERIFIED-WITH-FIXES.**

Every measured number in `RESULTS.md` reproduces byte-for-byte from the corpora in `data/`, the bill
arithmetic is correct, and the pre-registration was frozen before any corpus was generated. The fixes are
to claims, not measurements: two hypothesis verdicts were stated more favourably than the pre-registered
conditions allow (H6, H7), the headline bill range leaned on an exploratory single-seed probe without
saying so, and the README's "regenerable from the seeds" claim is false for the real-text corpora.

Verifier: a separate agent, 2026-11-09, same host (Beelink Ryzen 7 5800H, WSL2, 14 vCPU, 47 GB), the area's
own `.venv` (Python 3.12.3, pyarrow 24.0.0, pyiceberg 0.12.0, zstandard 0.25.0, tiktoken 0.14.0, numpy
2.5.4, matching `requirements.txt`). No paid calls and no git commands. Re-runs wrote to a scratch
directory, so the original `results/*.jsonl` files were not overwritten.

## 1. Pre-registration timing and integrity

- `sha256sum PREREGISTRATION.md` = `4b7a0bd551eb3db8304f759e05f5f09a179aec414d0e68c146e2dc137bc9a407`, the
  same value recorded in `RESULTS.md`.
- File times (UTC; WSL's clock runs about 4% slow, but only the ordering matters here):
  `PREREGISTRATION.md` 22:56:33, `.frozen` 22:56:38 (contents `2026-11-09T22:56:38Z`), `generate.py`
  22:57:41, first corpus in `data/` 22:58:01, `measure.py` last edit 23:00:40 (the Iceberg parity fix,
  as logged), `results/parquet.jsonl` 23:01:44. So the freeze predates every generated corpus and every
  result. The `.venv` (22:53) predates the freeze, which is just the install step.
- I can't rule out a smoke test before the freeze from file times alone, but it would have needed
  corpora, and none predate 22:58.

## 2. Reproduction

| Re-run | Result |
|---|---|
| `measure.py` (corpus, parquet, iceberg, dict) on the existing `data/` | `parquet.jsonl` 684/684 rows, `iceberg.jsonl` 144/144 data_bytes, `dict.jsonl` 24/24, `corpus.jsonl` 12/12 text_sha256: **byte-identical** |
| Iceberg `metadata_bytes` | 96 of 144 rows differ by about 170–200 bytes (absolute paths and UUIDs in manifests); the data+metadata column moves by under 0.3%. Expected, not an error |
| `probe_page_batching.py` | output **byte-identical** to `results/probe_page_batching.json` |
| `price.py` | `summary.json` identical; `tables.md` identical except the Iceberg data+metadata column, for the reason above |
| Wall clock | 2 min 43 s for `measure.py`, against 1 min 56 s logged (a different load on the shared host; durations are not claimed anywhere) |

Run-to-run variance is zero by construction (deterministic byte sizes), and the reported spread is
seed-to-seed across 3 seeds, as pre-registered. Every Layer-1 table cell in `RESULTS.md` (16 rows of
medians, min–max, CV, text share and JSONL bytes; 9 rows of codec variants; the Iceberg and dictionary
tables; the probe figures 303,234 / 192,184 / 162,990 / 34,712 / 890,119) matches `summary.json` or the
raw jsonl. Spot checks also pass: raw-text zstd-3 ratio 4.78–6.31 real and 3.20–3.22 high-entropy; realized
coding tokens 24.2–31.4M per user-day real and 24.0–48.0M high-entropy; chat 232–249k.

**Generator regenerability (fails for real text).** Regenerating four corpora with `generate.py`:
`chat-high_entropy-s0` is byte-identical, but `coding-real-s0`, `coding-real-s99` and `chat-real-s0` differ
(different row counts, and `text_sha256` `89450bee…` vs `df0c4125…` recorded for coding-real-s0). The
cause is `load_sources()`, which globs `/tmp/claude-1000/lab-ai-research/**/*.md` live: 29 sibling `.md`
files changed after 17:57 local time. The run-time prose pool was never snapshotted. Measuring the
regenerated seed-0 corpora shows the conclusions are robust but not exact: coding T3 203,687 (sorted) and
796,441 (random), coding T2 27,816 / 34,621, chat T3 360,154 / 1,337,402. The coding cells sit inside the
original three-seed min–max (4–7% off the medians), but several chat cells land just outside it, because
the chat seed spread is narrow (chat T3 random 1,337,402 against a max of 1,329,835; chat T0 random 10,208
against a min of 10,467). No conclusion or hypothesis verdict changes on the regenerated corpora.

## 3. Arithmetic of the bill

All rows recomputed: GB = bytes/Mtok × tokens/day × 185 × 1,000 / 1e9; S3 $0.023, Glacier IR $0.004, gp3
$0.08 per GB-month, from `../cost-to-serve-retention/cost_model.py`. T3 826 / 3,870 GB → $19 / $89 a
month → $228 / $1,068 a year; p90 1,898 / 8,891 GB → $44 / $205; year-1 accrual 6.5× monthly is the
correct linear fill; $13 × 185 × 1,000 = $2.405M inference; 0.0095%–0.044% share; raw ingest 100.0 / 3.25 /
0.56 GB per active day per 1,000 users. All correct.

## 4. Pre-registration against analysis

| Item | Finding |
|---|---|
| Arms, orders, codec variants, 8 MiB page, Iceberg default and parity, trained dictionary, 3 seeds + held-out 99 | Run as pre-registered |
| Generator details, null-column casts, 32 MB dictionary cap, Iceberg `page-row-limit` parity fix | Logged as deviations 1–6 by the original agent; confirmed in code |
| Headline bill range 190K–890K bytes/Mtok | **Not logged.** The upper bound is the exploratory, seed-0-only probe (`write_batch_size=1`). Pre-registered grid gives 195,906–785,203 → $20–$79 a month. Added as deviation 8, with both figures in the headline and a new bill row |
| Dictionary vs Parquet at zstd 3 | Exploratory comparison not in the pre-registration, used to soften H6. Now labelled exploratory |
| Stop rule (no generator re-tuning) | `generate.py` last modified before the first corpus; consistent |
| Versions | Recorded; Python 3.12.3 was missing and is now added (it is also the code-text source) |

## 5. Fixes made in place

1. **RESULTS headline, bill figures.** Before: "between 0.85 TB and 3.9 TB … $20 to $89 a month … $235 to
   $1,070 a year" (lower bound from 195,906, while the table used 190,000). After: "0.83 TB and 3.9 TB …
   $19 to $89 … $228 to $1,068", plus a sentence that the top of the range is from the single-seed
   exploratory probe and the pre-registered grid gives 0.85–3.4 TB, $20–$79 a month, $235–$942 a year.
2. **RESULTS bill table.** Added a "T3 full text, pre-registered grid" row (195,906–785,203; 852–3,414 GB;
   $19.59–$78.51 a month; $235–$942 a year).
3. **Deviation 8 added** for the exploratory-derived headline range.
4. **H6 verdict.** Before: "Split: … second half holds at parity and fails at default config for chat".
   After: **Falsified**. The pre-registered falsifier was "per-record + dictionary is smaller than the
   Parquet column", the pre-registered Parquet comparison is zstd default, and at that setting per-record
   + dict wins for chat real delta (38,234 vs 40,659 / 40,885) and high-entropy coding delta (13,810 vs
   14,404). The zstd-3 parity comparison is exploratory. The ≥1.5× gain held only for chat real text
   (1.55×; coding 1.23×, high-entropy 1.46× and 1.21×). The dictionary prose paragraph was corrected to match.
5. **H7 verdict.** Before: "falsified on T0 for coding (4.0% real, 7.9% high-entropy)" and "+1.1% to
   +7.9% on metadata/hash arms". After: falsified only on coding high-entropy T0 (+7.9%); coding real T0
   (+4.0%), coding high-entropy T1 (+4.0%) and chat high-entropy T0 (+2.1%) are in the 2–5% inconclusive
   gap; range +0.4% to +7.9%.
6. **H1 scope.** "95.0% to 99.9% in every T2/T3 cell" holds at zstd default; across all codec variants the
   minimum is 91.9% (chat T2 random, zstd 19). Still supported; wording scoped.
7. **H3 and the high-entropy sentence.** The coding high-entropy control shows 1.70×, inside H3's 1.3–2×
   gap, so "the same order effect on T3" overstated it. Now: same direction, 3.6× chat, 1.7× coding.
8. **H4 scope.** The 34–43% / 42–88% figures are real text; the high-entropy control figures (22% on T2,
   21–94% on T3) are added. The Falsified verdict stands.
9. **Iceberg write_batch_size match.** Before: "matches Iceberg default to within 0.05%". After: "within
   0.2% on the text arms (0.02% to 0.18%)"; coding T2 is 25,139 vs 25,185.
10. **Regenerability.** RESULTS "Commands" and README said the corpora are regenerable from the seeds and
    `corpus.jsonl` lets a regeneration be checked. Rewritten to say the high-entropy corpora regenerate
    identically and the real-text ones don't. Added `results/data-sha256.txt` (sha256 of the 32 files in
    `data/` that the run measured) and `results/source-pool-manifest-at-verification.txt` (the prose and code
    pool as it stands now, labelled post-hoc, not the run-time pool).
11. **Versions.** Python 3.12.3 added to the Rig paragraph.

Nothing in `generate.py`, `measure.py`, `price.py` or `probe_page_batching.py` needed a code fix, and no
result file was altered. A future re-run should snapshot the prose pool (a file list plus hashes, or a
copied directory) before generating, so the real-text corpora can be regenerated.

## 6. Claims against evidence

The run summary's main claims hold once scoped: storage dollars for full prompt text are small against
token spend ($19–$89 a month per 1,000 coding users, or $20–$79 on the pre-registered grid alone), raw
ingest volume is the cost that bites (about 100 GB per active day per 1,000 users for T3 JSON), and T3
size depends mostly on row order, zstd level and pyarrow's page/batch framing. The run summary's "H6 split"
and "H7 fails on the tiny metadata-only files" should read "H6 falsified" and "H7 falsified only on the
coding high-entropy T0 cell, inconclusive on three other metadata/hash cells". The remaining limits stated
in RESULTS (synthetic records, one vendor page for volume, an OpenAI tokenizer as proxy, five-month-old
storage-only prices, no latency, one Iceberg commit) are accurate and still apply. One more applies:
the 890 KB upper bound and the per-row framing figures rest on seed 0 alone.
