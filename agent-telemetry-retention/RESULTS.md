---
type: evidence
title: "R6 — Agent-telemetry retention bill: bytes per million tokens with and without prompt/response text"
created: 2026-11-09
tags: [ai-telemetry, ocsf, ai_operation, message_context, retention, parquet, iceberg, zstd, cost-to-serve]
---

# RESULTS: keeping the prompt text costs storage pennies, but its size depends mostly on how it is written

**Pre-registration:** `PREREGISTRATION.md`, sha256 `4b7a0bd551eb3db8304f759e05f5f09a179aec414d0e68c146e2dc137bc9a407`,
frozen 2026-11-09T22:56:38Z. Frozen by the agent before the run; not owner-reviewed.

**Layer labels.** Measured layer: exact byte sizes, single host, synthetic OCSF 1.9.0 records whose text is
real public code and prose. Volume layer: derived from vendor documentation (Tier B for what the product
does, C for the usage figures) plus one Tier D assumption for the chat tier. Price layer: AWS us-east-1 list
prices dated 2026-06-10 and re-verified 2026-06-14, taken from `../cost-to-serve-retention/cost_model.py`.
Cite each layer separately.

**Rig.** Beelink (Ryzen 7 5800H), WSL2, 14 vCPU, 47 GB, chrony offset 9 µs at the start. This file reports
sizes and ratios only, and no durations, so the §7b latency rig stamp does not apply. pyarrow 24.0.0,
pyiceberg 0.12.0 (SqlCatalog on SQLite), zstandard 0.25.0, tiktoken 0.14.0 (`o200k_base`, used only to
count tokens), numpy 2.5.4, Python 3.12.3 (whose `/usr/lib/python3.12` stdlib is also the code-text source); full
pins in `requirements.txt`. Independently re-run and checked 2026-11-09: see `VERIFICATION.md`.

## Headline

For a coding-agent fleet, retaining only metadata (the token triple, model, agent, tool name; arm T0)
stores about **1.1 KB per million billed tokens**. A sha256 of the prompt and the response (T1) costs
about **2.6 KB**. Keeping the new content of each request (T2, delta text) costs **26 to 32 KB**, and
keeping the full prompt as sent on every request (T3) costs from about **0.2 MB to 0.9 MB per million
tokens**. That puts full-context text at roughly 180 to 800 times the metadata-only footprint, and the
range comes from how the file is written, not from the codec name.

Priced at the cost_model method (steady-state storage at 365-day retention), 1,000 coding-agent users at
the documented average volume hold about 5 GB a year of metadata and between 0.83 TB and 3.9 TB of full
prompt text, which is **$19 to $89 a month on S3 Standard**, or about $228 to $1,068 a year once steady.
The top of that range (890 KB per million tokens) comes from the exploratory, single-seed page-batching
probe; the pre-registered three-seed grid alone (zstd default, session-sorted to random, 195,906 to
785,203 bytes per million tokens) gives 0.85 to 3.4 TB, $20 to $79 a month, $235 to $942 a year.
Against an inference bill of roughly $2.4M a year for the same fleet ($13 per active day × 185 days ×
1,000 users, from the same vendor page), storing the full text costs about 0.01% to 0.04% of what the
tokens cost. So, on these numbers, object-storage dollars are not a reason to drop `prompt_text`; the
reasons to drop or hash it are privacy, erasure and legal exposure, which this bench does not price.
Where the bytes do bite is ingest-metered tooling: the raw JSON for full-context logging comes to about
**100 GB per active day per 1,000 coding users** (T3), against about 3.3 GB for delta text and 0.6 GB
for metadata.

## What drives the full-context number

The full prompt on request *t* repeats the whole prompt of request *t−1* plus one delta, so almost all
of T3 is redundant, and the stored size depends on whether the compressor can see the previous prompt
when it compresses the current one. Three knobs decide that, and in this run they moved T3 by an order
of magnitude while moving T2 by tens of percent.

- **Row order.** Session-sorted T3 is 4.0× smaller than randomly ordered T3 (coding, zstd default:
  195,906 vs 785,203 bytes per million tokens), and 3.7× for chat.
- **zstd level.** pyarrow's default zstd level is 1 (`zstd_default` and `zstd_1` produced identical bytes
  in every cell); level 1 has a small match window, and level 19's window is large enough to reach back
  across several ~200 KB prompts. Level 19 saved 86 to 88% on coding T3.
- **Page and batch framing.** pyarrow only checks `data_page_size` after each write batch (default
  1,024 rows; pyiceberg passes 20,000), so with ~200 KB values the nominal 1 MiB page can hold a whole
  session and the compressor sees all of it at once. Forcing the check per row (`write_batch_size=1`,
  exploratory probe, seed 0) put coding session-sorted T3 at 303,234 bytes per million tokens at level 1
  and 192,184 at level 19, against 162,990 and 34,712 with the default batch. So most of the level-19
  saving on T3 comes from the oversized pages, and I would not quote the 28 KB best case as something a
  streaming writer will see. A collector that flushes small files every few seconds splits sessions across
  files and lands nearer the random-order row.

The defensible range for full-context text on real code and prose is therefore about 190 KB per million
tokens (session-sorted, large frames) to 890 KB (random order, per-row pages), and that is the range the
bill above uses.

## Layer 1: measured bytes per million billed tokens

Median over three generator seeds, with min–max and coefficient of variation across seeds. Byte sizes are
deterministic for a given seed, so the variance here is seed-to-seed, not run-to-run. The coding corpus is
two user-days per seed (25 to 35 sessions), which is why its seed spread is wider than the chat tier's.

### Coding tier, real text, Parquet zstd default (level 1)

| Arm | Order | bytes / M tokens (median, min–max, CV) | text-column share | raw JSONL bytes / M tokens |
|---|---|---|---|---|
| T0 metadata-only | session-sorted | 1,067 (1,061–1,236, 7.2%) | 0% | 23,901 |
| T0 metadata-only | random | 1,151 (1,132–1,334, 7.6%) | 0% | 23,901 |
| T1 hash-only | session-sorted | 2,563 (2,499–2,968, 7.8%) | 61.3% | 27,640 |
| T1 hash-only | random | 2,655 (2,555–3,090, 8.4%) | 59.4% | 27,640 |
| T2 delta text | session-sorted | 25,922 (24,404–33,044, 13.6%) | 96.4% | 138,376 |
| T2 delta text | random | 32,476 (30,024–41,312, 14.0%) | 96.8% | 138,376 |
| T3 full-context text | session-sorted | 195,906 (162,990–217,288, 11.6%) | 99.5% | 4,253,613 |
| T3 full-context text | random | 785,203 (764,650–857,459, 5.0%) | 99.9% | 4,253,613 |

### Chat tier, real text, Parquet zstd default (level 1)

| Arm | Order | bytes / M tokens (median, min–max, CV) | text-column share | raw JSONL bytes / M tokens |
|---|---|---|---|---|
| T0 metadata-only | session-sorted | 9,376 (9,372–10,267, 4.4%) | 0% | 251,202 |
| T0 metadata-only | random | 10,504 (10,467–11,477, 4.3%) | 0% | 251,202 |
| T1 hash-only | session-sorted | 25,447 (25,373–27,689, 4.1%) | 63.8% | 292,105 |
| T1 hash-only | random | 26,486 (26,383–29,115, 4.6%) | 61.1% | 292,105 |
| T2 delta text | session-sorted | 204,199 (201,952–218,811, 3.6%) | 95.5% | 826,265 |
| T2 delta text | random | 205,975 (203,622–220,091, 3.5%) | 95.0% | 826,265 |
| T3 full-context text | session-sorted | 363,349 (360,259–386,690, 3.2%) | 97.5% | 4,379,971 |
| T3 full-context text | random | 1,327,012 (1,320,070–1,329,835, 0.3%) | 99.2% | 4,379,971 |

Chat costs about nine times more per token than coding in the metadata arms because a chat request
carries far fewer tokens (a short context) for the same per-record overhead; per record, the two tiers are
close. The high-entropy control tables (Zipf words, raw zstd-3 ratio 3.2 against 4.8 to 6.3 for the real
text) are in `results/tables.md`; their bytes per token are not comparable one-for-one with the real text,
because random-letter words tokenize at about three tokens each, but they show the same ordering of arms
and the same direction of order effect on T3 (3.6× for chat, but only 1.7× for coding, which falls in
H3's inconclusive gap).

### Codec and dictionary variants (real text, median bytes per M tokens)

| Tier | Arm | Order | snappy | zstd default (=1) | zstd 3 | zstd 9 | zstd 19 | zstd default, no dict on text |
|---|---|---|---|---|---|---|---|---|
| coding | T0 | sorted | 1,637 | 1,067 | 1,090 | 1,094 | 1,053 | 1,067 |
| coding | T1 | sorted | 4,476 | 2,563 | 2,623 | 2,728 | 2,518 | 2,563 |
| coding | T2 | sorted | 44,766 | 25,922 | 20,614 | 18,475 | 16,991 | 26,629 |
| coding | T2 | random | 49,447 | 32,476 | 22,749 | 20,022 | 18,372 | 34,779 |
| coding | T3 | sorted | 1,695,381 | 195,906 | 42,350 | 33,690 | 27,793 | 193,739 |
| coding | T3 | random | 1,739,571 | 785,203 | 409,469 | 227,212 | 97,964 | 785,870 |
| chat | T2 | sorted | 297,587 | 204,199 | 149,139 | 133,990 | 122,925 | 204,746 |
| chat | T3 | sorted | 1,198,600 | 363,349 | 285,273 | 244,167 | 210,633 | 363,879 |
| chat | T3 | random | 2,088,061 | 1,327,012 | 714,583 | 471,506 | 329,145 | 1,327,421 |

The full grid (every arm, both orders, both corpora) is in `results/tables.md`. The pre-registered 8 MiB
page variant for T3 produced the same bytes as the default (195,906 coding, 361,638 vs 363,349 chat)
because, as above, the page boundary is set by the write batch rather than the page-size knob with values
this large, so that variant turned out uninformative.

### Iceberg (pyiceberg 0.12.0) against plain Parquet, session-sorted, data bytes per M tokens

| Tier | Arm | plain Parquet zstd default | Iceberg default | Iceberg at parity | Iceberg parity + metadata files | parity vs plain |
|---|---|---|---|---|---|---|
| coding | T0 | 1,067 | 1,110 | 1,110 | 1,419 | +4.0% |
| coding | T1 | 2,563 | 2,609 | 2,609 | 2,899 | +1.8% |
| coding | T2 | 25,922 | 25,185 | 25,968 | 26,258 | +0.2% |
| coding | T3 | 195,906 | 189,118 | 195,951 | 196,241 | +0.0% |
| chat | T2 | 204,199 | 192,449 | 204,301 | 204,953 | +0.1% |
| chat | T3 | 363,349 | 350,406 | 363,451 | 364,101 | +0.0% |

Footers confirm ZSTD and the same encodings (`PLAIN`, `RLE`, `RLE_DICTIONARY`) on both writers, both
`parquet-cpp-arrow version 24.0.0`. Iceberg's default write came out 3 to 6% smaller than plain pyarrow on
the text arms, and the whole difference is pyiceberg's `write_batch_size` of 20,000: plain pyarrow with
that one knob changed (exploratory row in `results/iceberg.jsonl`) matches Iceberg default to within 0.2% on the text arms (0.02% to 0.18%).
That is the configuration-parity trap the methodology opens with, in a smaller form. The metadata-only arms
show Iceberg 1 to 8% larger, which is fixed footer and schema overhead on files of 10 to 60 KB; the
metadata tree adds about 16 KB per commit, which is large in proportion here only because the test files are
tiny.

### Trained zstd dictionary, per-record prompt_text (the streaming and queue regime)

Dictionary of 112,640 bytes trained on held-out seed 99 (capped at 32 MB of training text), each record
compressed alone at zstd level 3.

| Tier | Column | per-record zstd 3 | + trained dict | dict gain (min–max) | Parquet prompt column, zstd default | Parquet prompt column, zstd 3 |
|---|---|---|---|---|---|---|
| coding | delta | 28,315 | 23,028 | 1.23× (1.19–1.26) | 13,815 sorted / 19,301 random | 10,993 / 12,729 |
| coding | full | 840,249 | 767,782 | 1.10× (1.09–1.11) | 183,881 / 773,419 | 32,810 / 399,530 |
| chat | delta | 59,250 | 38,234 | 1.55× (1.54–1.56) | 40,659 / 40,885 | 29,845 / 29,656 |
| chat | full | 1,433,926 | 1,080,636 | 1.32× (1.32–1.34) | 199,830 / 1,156,129 | 166,000 / 586,027 |

A trained dictionary helps a per-record pipeline by 1.2 to 1.6× on delta text, and it does little for
full-context prompts because a single record already contains its own long repeats. In the real-text cells,
columnar Parquet at the same zstd level (3, an exploratory comparison not in the pre-registration) beats
per-record plus dictionary, but at pyarrow's level-1 default, which is the comparison the pre-registration
named, the chat delta column (40,659 sorted, 40,885 random) is larger than per-record level 3 with a
dictionary (38,234), and so is the high-entropy coding delta column (14,404 against 13,810), so a level-1
lake can lose to a well-tuned queue on short prompts.

## Layer 2: the one-year bill

Prices from `../cost-to-serve-retention/cost_model.py` `PRICES_PER_GB_MONTH`: S3 Standard $0.023, gp3
$0.08, Glacier Instant Retrieval $0.004 per GB-month, AWS us-east-1 list, verified 2026-06-10 and
re-verified 2026-06-14. Storage only (Glacier IR's $0.03/GB retrieval charge excluded, as in that model).
"One year" = steady-state monthly cost at 365-day retention (the cost_model method), with the annual run
rate at 12× that; year-1 accrual from an empty archive is 6.5× the monthly figure. Volume: 23.5M billed
tokens per active day (average) or 54M (p90), 185 active days, 1,000 users.

| Coding fleet, 1,000 users | bytes / M tok used | GB held (avg / p90) | S3 Std $/mo (avg / p90) | S3 Std $/yr run rate (avg) | Glacier IR $/mo (avg) | gp3 $/mo (avg) |
|---|---|---|---|---|---|---|
| T0 metadata-only, zstd default | 1,067–1,151 | 5 / 11 | $0.11 / $0.25 | $1.4 | $0.02 | $0.40 |
| T1 hash-only | 2,563–2,655 | 11 / 27 | $0.26 / $0.61 | $3.2 | $0.05 | $0.92 |
| T2 delta text, zstd default | 25,922–32,476 | 113–141 / 259–324 | $2.59–$3.25 / $5.96–$7.45 | $31–$39 | $0.45–$0.56 | $9.02–$11.30 |
| T3 full text, defensible range | 190,000–890,000 | 826–3,870 / 1,898–8,892 | $19–$89 / $44–$205 | $228–$1,068 | $3.30–$15.48 | $66–$310 |
| T3 full text, pre-registered grid (zstd default, sorted to random) | 195,906–785,203 | 852–3,414 / 1,957–7,844 | $19.59–$78.51 / $45–$180 | $235–$942 | $3.41–$13.65 | $68–$273 |
| Chat fleet, T3 full text, zstd default | 363,349–1,327,012 | 13.4–49.1 | $0.31–$1.13 | $3.7–$13.6 | $0.05–$0.20 | $1.08–$3.93 |

The T3 row uses the defensible range from the page-framing probe rather than the zstd-19 best case;
`results/tables.md` has the per-variant rows, including the zstd-19 figures I do not lead with.

## Hypotheses

| | Prediction | Result | Verdict |
|---|---|---|---|
| H1 | Text columns ≥90% of compressed bytes in T2/T3 | 95.0% to 99.9% in every T2/T3 cell at zstd default, both corpora; 91.9% minimum across all codec variants (chat T2 random, zstd 19) | Supported |
| H2 | T3 ≥10× T2 under random order, coding | 24.2× at zstd default (785,203 / 32,476); 5.3× at zstd 19 | Supported at default; above the 5× falsifier at every level |
| H3 | Session-sorting cuts T3 ≥2× | 4.0× coding, 3.7× chat at default (real text); 2.9× coding with per-row pages (seed 0); high-entropy control 3.6× chat, 1.7× coding | Supported on real text; the coding high-entropy control sits in the 1.3–2× inconclusive gap |
| H4 | zstd 19 saves ≤25% vs default; wrong if >40% | Real text: 1–5% on T0/T1, 34–43% on T2, 42–88% on T3 (high-entropy control: 22% on T2, 21–94% on T3) | **Falsified** for text arms (coding T2 random 43.4%, all T3). Cause: pyarrow's default zstd level is 1, and on T3 the oversized pages give higher levels a long window to exploit |
| H5 | No-dict on text columns changes bytes <5%; wrong if >10% | −1.1% to +2.7% in 7 of 8 real-text cells; +7.1% on coding T2 random | Supported in 7 of 8; one cell in the 5–10% gap, neither confirmed nor falsified |
| H6 | Trained dict ≥1.5× on per-record T2; Parquet still smaller | 1.55× chat, 1.23× coding (high-entropy 1.46×, 1.21×); at the pre-registered Parquet zstd default, per-record + dict is smaller than the Parquet column for chat delta (38,234 vs 40,659 / 40,885) and high-entropy coding delta (13,810 vs 14,404); Parquet is smaller at zstd-3 parity in the real-text cells (exploratory) | **Falsified** by its own pre-registered condition (per-record + dict smaller than the Parquet column), and the ≥1.5× gain held only for chat real text. Corrected at verification from "Split" |
| H7 | Iceberg at parity within 2% of plain Parquet; wrong if >5% | +0.0% to +0.2% on text arms; +0.4% to +7.9% on metadata/hash arms | Supported for text-bearing arms; falsified only on coding high-entropy T0 (+7.9%); coding real T0 (+4.0%), coding high-entropy T1 (+4.0%) and chat high-entropy T0 (+2.1%) sit in the 2–5% inconclusive gap. Cause: fixed footer and schema overhead on files under 60 KB. Corrected at verification from "falsified on T0 for coding (4.0% real)" |

## Deviations and fixes (logged under the stop rule)

1. Generator details fixed before the first run but not written in the pre-registration: lognormal sigma
   (1.0 coding, 0.8 chat), request inter-arrival, a session cap of 120 requests (coding) and 60 (chat) to
   keep contexts under about 150k tokens, 85% of coding deltas being tool results drawn from a 10-file
   per-session working set.
2. The chat tier has no tool calls, so `tool.name` and `tool_call.arguments` were all-null; Iceberg v2
   rejects the null type, so those columns are cast to string in every arm (Parquet too, for parity).
   Dots in column names are replaced by `__` and `time` cast from ms to µs, in every arm.
3. **Iceberg parity bug, found and fixed.** The smoke test showed Iceberg at "parity" 6% smaller than plain
   Parquet; reading pyiceberg's `_get_parquet_writer_kwargs` showed it passes `write_batch_size=20000`
   (from `write.parquet.page-row-limit`) where pyarrow defaults to 1,024. The full run had already loaded
   the old code, so the Iceberg arm was re-run with `write.parquet.page-row-limit=1024` added to the parity
   properties. The pre-fix rows are kept in `results/iceberg-PREFIX-parity-missing-page-row-limit.jsonl`;
   the fix moved parity data bytes by −0.8% to +6.9%.
4. Exploratory additions, labelled as such: `probe_page_batching.py` (write_batch_size 1 / 1,024 / 20,000
   × zstd 1 / 3 / 19, seed 0, T3) and the plain-Parquet `write_batch_size=20000` row in the Iceberg table.
5. Dictionary training capped at 32 MB of held-out text per column (not in the pre-registration).
6. The high-entropy generator asks for 0.75 words per requested token, but its random-letter words tokenize
   at roughly three tokens each, so its sessions carry more tokens per record than intended (realized
   25–48M tokens per coding user-day against 24–31M for the real text). Its tables are a compressibility
   bound, not a volume model.
7. Realized chat volume came out at about 230–260k billed tokens per user-day against the 200k target,
   because the last session of each day overshoots. The bill uses the pre-registered volumes; the
   transferable metric is bytes per million tokens.
8. Logged at verification: the headline and bill use a "defensible range" for T3 (190,000 to 890,000 bytes
   per million tokens) whose upper bound is the exploratory page-batching probe (seed 0 only,
   `write_batch_size=1`, zstd 1, random order) and whose lower bound is rounded from the pre-registered
   session-sorted median (195,906) and the probe's per-row zstd-19 figure (192,184). The pre-registered
   three-seed grid at zstd default spans 195,906 to 785,203, which prices at $20 to $79 a month; both are
   now stated in the headline.

## Limits

- Synthetic records. The text is real code and prose, and full-context prompts are built append-only as a
  real agent's are, but real prompts carry fixed tool schemas and system text that would compress further,
  and real tool output (stack traces, JSON, logs) may compress differently from source excerpts.
- The coding volume rests on one vendor page and assumes its `/usage` example's model and cache mix holds
  for the average developer. An Opus-heavy fleet buys fewer tokens per dollar, so it would store less per
  dollar of inference; the bytes-per-token metric is unaffected.
- tiktoken `o200k_base` is an OpenAI tokenizer standing in for Anthropic's; token counts may differ by some
  percent, which shifts bytes per token by the same proportion.
- One record per API request is one choice; OpenTelemetry GenAI spans or gateway logs may emit more records
  (one per tool call) or fewer, and some emit the full message array as JSON, which adds per-message
  framing that this bench does not model.
- Iceberg metadata overhead is measured on one commit per table with tiny files; it says nothing about
  manifest growth over a year of commits. Compaction would also change sort order, and therefore T3 size.
- Prices are five months old and storage-only. Nothing here prices SIEM ingest licensing, query or
  retrieval, PUT requests for small-file streaming writers, or the legal and privacy cost of holding the
  text, which on these numbers is likely to dominate the decision.
- No latency or throughput was measured; zstd 19 is far slower to write than level 1, and that cost is
  outside this bench.

## Commands

```bash
cd /tmp/claude-1000/lab-ai-research/agent-telemetry-retention
python3 -m venv .venv && .venv/bin/pip install pyarrow==24.0.0 zstandard 'pyiceberg[sql-sqlite]' tiktoken numpy
.venv/bin/pip freeze > requirements.txt
sha256sum PREREGISTRATION.md                      # 4b7a0bd5..., frozen 2026-11-09T22:56:38Z
for t in coding chat; do for c in real high_entropy; do for s in 0 1 2 99; do
  .venv/bin/python generate.py --tier $t --corpus $c --seed $s; done; done; done   # run 8-way parallel via xargs
.venv/bin/python measure.py                       # corpus, parquet, iceberg (pre-fix), dict
.venv/bin/python measure.py iceberg               # re-run after the parity fix
.venv/bin/python probe_page_batching.py > results/probe_page_batching.json   # exploratory
.venv/bin/python price.py > results/tables.md
```

Seed 99 is held out for dictionary training only. Generated corpora (`data/`, about 2.1 GB) are
git-ignored. The high-entropy corpora regenerate byte-identically from the seeds, but the real-text corpora
do not: `generate.py` reads the lab's live markdown as its prose pool, sibling areas kept writing to it after
the run, and at verification the regenerated real-text corpora had different `text_sha256` values from
`results/corpus.jsonl`. So reproducing the exact numbers needs the original `data/` files, whose sha256 are
in `results/data-sha256.txt`; regenerated corpora land near, but not always inside, the three-seed
min–max (see `VERIFICATION.md`). `results/source-pool-manifest-at-verification.txt` lists the pool as it
stood at verification, not at run time.

## Files

- `PREREGISTRATION.md`: frozen design.
- `generate.py`, `measure.py`, `price.py`, `probe_page_batching.py`: the instrument.
- `results/parquet.jsonl` (684 rows), `results/iceberg.jsonl`, `results/iceberg-PREFIX-...jsonl`,
  `results/dict.jsonl`, `results/corpus.jsonl`, `results/probe_page_batching.json`, `results/summary.json`,
  `results/tables.md`.
- `logs-*.txt`: run logs.
