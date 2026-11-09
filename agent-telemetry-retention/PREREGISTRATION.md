---
type: benchmark-preregistration
title: "R6 — The agent-telemetry retention bill: bytes per million tokens, with and without prompt/response text"
created: 2026-11-09
status: frozen-by-agent-before-run
tags: [ai-telemetry, ocsf, ai_operation, message_context, retention, parquet, iceberg, zstd]
---

# Pre-registration: R6, the agent-telemetry retention bill

Frozen by the agent before any measurement was run; not owner-reviewed. The sha256 of this file and the
freeze timestamp are recorded at the top of `RESULTS.md`. Anything run that is not listed here is labelled
*exploratory* in the results.

## Question

When agent and LLM activity is logged as OCSF records carrying the `ai_operation` profile, how many stored
bytes does a year of that telemetry cost per million billed tokens, and how much of the bill is the
`message_context.prompt_text` / `response_text` pair, compared with keeping only metadata or only a hash of
the text? Secondary: how much do the usual compression knobs (zstd level, Parquet dictionary encoding,
sort order, a trained zstd dictionary, Iceberg vs plain Parquet) move that number?

The motivating case is SITE-REVIEW-2026-11-09 article #8 ("What to keep when the agent did it"): the
most forensic fields in agent telemetry are the most expensive and the most privacy-exposed, so the
retention decision needs a measured price.

## Record shape

OCSF 1.9.0, verified 2026-11-09 against schema.ocsf.io:
- `ai_operation` profile = `ai_agent`, `ai_model`, `delegation`, `message_context`.
- `message_context` object = `ai_role`, `ai_role_id`, `application`/`service` (one required), `name`, `uid`,
  `uid_numeric`, `prompt_text`, `response_text`, `prompt_tokens`, `completion_tokens`, `total_tokens`.

Sub-fields of `ai_agent` and `ai_model` (uid, instance_uid, name, type_id; name, provider, version) come
from the hub's prior-art notes on OCSF PRs #1488 and #1641, not from the schema server, and are labelled as
approximate. Base class: API Activity (class_uid 6003) with the profile attached, plus the usual base
fields (time, activity_id, severity_id, status_id, duration, metadata.product, actor.user.uid,
src_endpoint.ip, api.operation, a session uid and sequence number). Tool calls carry a tool name and a JSON
arguments string. One record = one model API request.

The Parquet layout is flattened (dotted names as columns), which is how the lab's other OCSF benches store
it; nested-struct layout is out of scope.

## Volume model (the basis is cited, the conversion is shown)

Two user tiers. The headline metric (bytes per million billed tokens) is volume-independent; volume only
scales the bill.

**Coding-agent tier: about 23M billed tokens per active day, about 185 active days a year.**
Basis: the Claude Code costs page (code.claude.com/docs/en/costs, fetched 2026-11-09; vendor documentation,
Tier B for what the product does, C for usage claims) states "the average cost is around $13 per developer
per active day and $150-250 per developer per month, with costs remaining below $30 per active day for 90%
of users." The same page's `/usage` example shows "1.2k input, 5.3k output, 940.0k cache read, 50.0k cache
write ($0.55)", so about 996.5k billed tokens cost $0.55 at that mix. Scaling, $13 buys about 23.5M billed
tokens a day and the $30 p90 buys about 54M. Active days: $200/month midpoint divided by $13 per active day
is about 15.4 active days a month, about 185 a year. This conversion assumes the example's model and cache
mix holds for the average user, which it may not (an Opus-heavy mix buys fewer tokens per dollar); I flag it
as the largest single uncertainty in the volume, and the page's own example shows the key structural fact:
about 94% of billed tokens are the same context re-read on every request.

**Chat tier: 200k billed tokens per active day, 185 active days a year.** Tier D, an assumption labelled as
such: the same page says only that "one debugging session can consume more than a day of chat."

**Generator parameters (per tier).** Coding: system prompt about 15k tokens fixed per agent; sessions of
geometric length mean 40 requests; each request adds a delta (tool result, occasionally a user message)
with lognormal size, median 800 tokens, and an output with lognormal size, median 300 tokens; billed input
at request *t* = system prompt + all prior deltas and outputs + current delta. Sessions per user-day are set
so a user-day lands near 23M billed tokens. Chat: system prompt about 1k tokens, sessions of mean 6 turns,
user delta median 80 tokens, output median 400 tokens. These are my parameters, not measurements, and the
results report the realized tokens per user-day.

**Token counting.** tiktoken 0.14.0 `o200k_base`, which is an OpenAI tokenizer and serves here as a counting
proxy; Anthropic's tokenizer counts differ by some percent, which shifts bytes per token proportionally.

## Text source

Compressibility of the text columns depends on the text, so random token soup is not acceptable. Text is
sampled from:
- code: CPython 3.12 standard library `.py` files on this host (PSF licence, public);
- prose: the lab's own public markdown (`/tmp/claude-1000/lab-ai-research/**/*.md`, public benchmarks repo).

Coding-tier deltas are file excerpts (simulating file reads and grep output, drawn from a per-session working
set of files so re-reads happen), assistant outputs mix prose and code excerpts. A **high-entropy control**
replaces every delta and output with Zipf-sampled words from a 50k-word synthetic vocabulary, as a
lower-compressibility bound (precedent: `cost-to-serve-retention/high_entropy_corpus.py`). The raw-text zstd-3
ratio of each corpus is reported as a parameter.

## Arms

Text-capture arms:
- **T0 metadata-only**: no prompt_text / response_text.
- **T1 hash-only**: sha256 hex of the prompt and of the response instead of the text.
- **T2 delta text**: prompt_text = the new content in this request; response_text = full output.
- **T3 full-context text**: prompt_text = the entire prompt sent (system + history + delta).

Sort order: **session-sorted** (session, seq; best case) and **random order** (rows shuffled; worst-case
bound for a writer that interleaves many concurrent sessions).

Parquet variants (pyarrow 24.0.0, row group 1,048,576 rows max, Parquet format 2.6, data page size default
1 MiB unless stated):
- snappy (pyarrow default codec), recorded as the default-config baseline;
- zstd with no level given (pyarrow default) and zstd levels 1, 3, 9, 19;
- zstd default with dictionary encoding disabled on the two text columns;
- for T3 session-sorted only: zstd default with an 8 MiB data page.

Footers are read back (`pyarrow.parquet` metadata) to confirm codec, encodings and row-group counts.

**Iceberg** (pyiceberg 0.12.0, SqlCatalog on sqlite, local warehouse): one table per arm with pyiceberg
defaults (default-config result) and one with properties set to match the plain-Parquet zstd-default
variant (parity result). Reported: data-file bytes and metadata bytes separately.

**Trained zstd dictionary** (zstandard 0.25.0): pyarrow cannot apply a trained dictionary inside Parquet,
so this arm is per-record compression of prompt_text (T2 and T3) at zstd level 3, with and without a
112,640-byte dictionary trained on a **held-out** seed (different seed, same generator), compared with the
Parquet column size. This is the streaming/queue regime, following `ocsf-zstd-dictionary/run.py`.

## Metrics

- Bytes per million billed tokens (`total_tokens` summed), per tier × arm × order × variant; also bytes
  per record and per-column compressed bytes.
- Share of compressed bytes in the two text columns.
- Raw JSONL bytes (one record per line) as a reference point.
- Variance: byte sizes are deterministic for a given seed, so run-to-run variance is zero by
  construction; I report the spread (min / median / max, and CV) across **3 generator seeds**. No latency
  claims are made, so no rig stamp is required; the machine is recorded anyway.

## Hypotheses and what would prove each wrong

- **H1** In T2 and T3, the two text columns are at least 90% of compressed bytes. Wrong if under 75%.
- **H2** Under random order, T3 costs at least 10× the bytes per million tokens of T2 for the coding tier.
  Wrong if under 5×.
- **H3** Session-sorting T3 cuts its bytes by at least 2× versus random order (consecutive full prompts share
  nearly all their prefix). Wrong if under 1.3×.
- **H4** Raising zstd from default to level 19 saves at most 25% on any arm. Wrong if it saves more than 40%.
- **H5** Parquet dictionary encoding on the text columns changes bytes by under 5%. Wrong if over 10%.
- **H6** A trained dictionary makes per-record T2 prompt compression at least 1.5× smaller than per-record
  plain zstd, but Parquet's columnar zstd still beats it. Wrong if per-record + dictionary is smaller than
  the Parquet column.
- **H7** Iceberg at parity is within 2% of plain Parquet data bytes. Wrong if over 5%.

## Pricing (method and inputs reused, cited)

Method and price inputs from `/tmp/claude-1000/lab-ai-research/cost-to-serve-retention/cost_model.py`,
`PRICES_PER_GB_MONTH`: S3 Standard $0.023, gp3 $0.08, Glacier Instant Retrieval $0.004 per GB-month,
AWS us-east-1 list, verified 2026-06-10 and re-verified 2026-06-14 (five months old at run time; not
re-sourced here, flagged as a limit). Storage only; Glacier IR's $0.03/GB retrieval charge is excluded, as in
that model. Parquet/Iceberg maps to S3 Standard (warm) and Glacier IR (cold); gp3 is shown only as the
"kept hot on block storage" sensitivity.

"One year" is defined as the cost_model method defines retention cost: **steady-state monthly storage
cost at 365-day retention**, priced for 1,000 users per tier, plus that figure × 12 as the annual run rate
once steady. Year-1 accrual (the archive filling from empty) is about half the run rate and is reported
once, labelled. The p90 coding volume ($30/day, about 54M tokens) is a sensitivity row.

## Instrument, versions, stop rule, cost

- Host: Beelink (Ryzen 7 5800H), WSL2, 14 vCPU, 47 GB; chrony offset checked 2026-11-09 (9 µs).
- Python 3 venv in this directory; versions pinned in `requirements.txt`.
- Commands are recorded in `RESULTS.md`; scripts are `generate.py`, `measure.py`, `price.py`.
- Stop rule: one pass of the matrix above, 3 seeds per tier, no re-tuning of generator parameters after
  seeing results. A bug fix that changes numbers is logged with the before and after.
- Cost: $0. Local CPU only, no paid API calls.
