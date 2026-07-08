---
type: evidence
title: "NEEDLE-BM25 — Fuzzy Full-Text vs OpenSearch Foil (2026-07-07)"
created: 2026-07-07
tags: [bm25, full-text, opensearch, clickhouse, iceberg, zeek, two-regime, needle-bm25]
---

# NEEDLE-BM25 — the index's OTHER home turf, measured (2026-07-07)

`needle.py` (2026-06-14) closed the point-lookup half of the two-regime symmetry and flagged the
BM25 fuzzy-full-text half as future work, since the Zeek `conn` corpus has no text field. This arm
closes that gap: a **synthetic** text field (HTTP-URI / user-agent / DNS-query-style strings, no
real telemetry) extended onto the pinned 10M-row corpus by `uid`, seed `0xB255`
(`_work/bm25_text_fingerprint.json`), loaded into OpenSearch 3.7.0 (`zeek_conn_bm25text`, standard
analyzer, default BM25 similarity), ClickHouse 26.5.1.882-native (`benchmark.zeek_bm25text`,
experimental `text` index / `splitByNonAlpha` tokenizer, `allow_experimental_full_text_index=1`),
and ClickHouse-over-Iceberg (`icebergS3()` over `zeek/bm25text`, no index of any kind). 1 warmup +
7 trials/query, median + CV, CV-gated claims (`run_bm25_bench.py`, raw: `results/bm25_execution.json`).

## Result: the hypothesis holds on ranking, but a plain boolean token match is now a genuine tie

| query | OpenSearch (index) | ClickHouse-native (text-idx) | ClickHouse-Iceberg (no idx) | gate |
|---|--:|--:|--:|:--:|
| `token_exact` (planted token, 500 docs) | 71.2 ms | **21.4 ms** (OS is 3.3× *slower*) | 254.7 ms | claimable |
| `phrase_exact` (planted phrase, 300 docs) | 40.6 ms | 43.4 ms (~tie, 1.1×) | 238.6 ms | borderline — see caveat |
| `fuzzy_match` (edit-distance 1) | **5.8 ms** | 807.6 ms (139×) | 1016.3 ms (175×) | claimable, wide margin |
| `bm25_relevance` (5-term ranked top-10) | **29.7 ms** | 138.5 ms proxy (4.7×) | 526.0 ms proxy (17.7×) | claimable |

Answer-equality (deterministic queries): `token_exact` and `phrase_exact` return the **identical
uid set** across all three arms, matching the planted ground truth (500 / 300) exactly — verified,
not just count-matched.

## The honest finding: boolean full-text converged, ranked/fuzzy retrieval did not

ClickHouse 26.5 ships an experimental `text` index (the renamed "inverted index") that accelerates
`hasToken`/`hasAnyToken`/LIKE — and on a plain single-token exact match, it actually **beats**
OpenSearch (21 ms vs 71 ms), reversing the pre-registered direction. Phrase search is a near-tie
(1.1×, and the 6.9% gap barely clears the 6.4% CV gate — I'd call this a tie within noise, not a
real ClickHouse win or loss, given how thin the margin is over the isolation caveat below). So the
part of the hypothesis that predicted a wide OpenSearch margin on **simple boolean full-text** was
wrong: a modern lakehouse engine with its own text index closes that gap, sometimes past parity.

But the two capabilities that make BM25 full-text a distinct regime — **fuzzy/edit-distance
matching** and **true relevance ranking** — do not converge. ClickHouse can express fuzzy matching
(`editDistance()` over an `ARRAY JOIN` of tokens — a real capability, and the two ClickHouse arms
agree exactly at 2,001,030 matches; the OpenSearch fuzzy cell recorded a capped hit total of
10,000, the default `track_total_hits` with top-20 retrieval, so per the harness's own
`answer_note` this cell is capability + latency, not answer-equality — the multiple compares an
index-terminated query against ClickHouse's exhaustive full-corpus `count()`) but has **no index
support for it**: brute-force scan, and OpenSearch's indexed Lucene automaton wins by 139–175×. And ClickHouse has **no BM25 or
any ranked-relevance function at all** (checked `system.functions`: `hasToken`/`hasAnyToken`/
`hasAllTokens` only, no `bm25`/rank hit) — the 4.7–17.7× I report there is OpenSearch's real BM25
against a ClickHouse *proxy* (a naive matched-term count, no IDF, no term-frequency saturation, no
document-length normalization), which is not the same computation, so the multiple is directional
evidence for a capability gap, not an apples-to-apples speed comparison.

**Falsification condition (from the pre-reg) revisited:** the pre-registered falsifier was "the
lakehouse arm matches OpenSearch within CV on BM25-style relevance retrieval... no capability gap,
multiple ≤ ~2×." On boolean token search, that falsifier **did trigger** (no gap, and ClickHouse
edges the win) — I'm reporting that plainly rather than reframing it after the fact. On fuzzy and
ranked relevance, it did not: the capability gap is real (ClickHouse cannot rank by relevance at
all) and the latency gap is wide (139–175× on fuzzy). So the two-regime claim survives, narrowed:
it's not "full-text is a distinct regime," it's "**ranked/fuzzy retrieval** is a distinct regime" —
boolean token/phrase matching is not, once the lakehouse engine ships its own text index.

## Scope / caveats (Tier B)

- **Isolation caveat (constraint-driven, per pre-reg):** timed co-resident with the idle `moar-*`
  stack (not stopped, per the standing constraint), not a bare window. CVs ran 0.9%–11.7% across
  the 12 arm×query cells — none blew past a level that would force a downgrade to direction-only,
  except the `phrase_exact` vs ch_native cell, which is thin enough (gap 6.9% vs gate 6.4%) that I
  read it as a tie, not a claim, despite technically clearing the gate.
- Iceberg is used only via ClickHouse's `icebergS3()` reader (no separate Iceberg-native full-text
  engine tested) — Iceberg/Parquet fundamentally has no index concept here, so this arm is really
  "does the *reading engine* have an index," not an Iceberg-specific finding.
- **ClickHouse `text` index is EXPERIMENTAL** (`allow_experimental_full_text_index`, ClickHouse
  26.5.1.882) — not a production-default feature; a fair comparison would note OpenSearch's
  inverted index is a stable default and ClickHouse's is opt-in and young. Version-bound finding.
- Synthetic corpus (structured HTTP-URI/UA/DNS-style strings, planted tokens/phrases/relevance
  terms) — no real telemetry, per the injection-surface boundary. The planted-ratio design means
  absolute counts (500/300) are not a transferable rate; the mechanism (index vs boolean-match tie,
  fuzzy/ranking gap) is the transferable claim.
- n=1 host, n=1 corpus shape, single run of each query class (7 trials each, not independent
  corpus draws) — Tier B.
- **Provenance note:** the pairwise comparison blocks in `results/bm25_execution.json` (gap %,
  gate, `faster_is`, multiple) were recomputed direction-aware after the run — the in-run
  `gap_claim` in `run_bm25_bench.py` assumes OpenSearch is the faster arm and mis-adjudicates the
  reversed `token_exact` cell (`bm25_execution_partial.json` preserves the original `_x` blocks:
  claimable=false, multiple=0.3 there). Every recomputed value re-derives from the recorded
  per-trial durations, but the script needs the direction-aware fix before any re-run.

## What it does to H3-PERFORMANCE-01 / the two-regime symmetry claim

Sharpens, doesn't overturn: the fair-broker "test where the SIEM wins too" posture holds, but the
honest boundary of where it wins moved. It's not full-text broadly — it's fuzzy matching and
relevance ranking specifically, where ClickHouse has no accelerated or no-native-function path at
all. Route through karen → hypothesis-validator → contradiction-detector before any confidence
move; this is a narrowing of scope, not a reversal, and the pre-registered falsifier partially
triggered (on the boolean-match cell only) — that should be recorded as such, not smoothed over.
