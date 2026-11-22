# Text search and regex: columnar engine vs inverted index

## What it measures

On Sigma-style text filtering over a message field, does a columnar engine match an inverted-index
search engine, and does ClickHouse's native full-text index or Hyperscan close the gap? Four arms run on
one synthetic corpus of 2,000,000 log messages with planted targets at known rates: OpenSearch 3.7.0 with
the message as an analyzed `text` field, ClickHouse 26.5.1 by brute scan (`position`, `match`),
ClickHouse with its native text index (`hasToken`), and ClickHouse with Hyperscan (`multiMatchAny`).
Each arm's count is checked against the planted count.

## Result (Tier B)

From [RESULTS-2026-06-15.md](RESULTS-2026-06-15.md) and `results/synth_text.json`: on whole-token
filtering ClickHouse's text index ties OpenSearch (about 5 ms each, against 54 ms for brute scan), on a
sub-token substring the inverted index wins (5 ms against 52 ms), and on a regex for base64 blobs
(`[A-Za-z0-9+/]{40,}`) OpenSearch returns 3,159 of 7,946 planted blobs in 5 ms while ClickHouse's
`match()` and Hyperscan both return all 7,946 in about 106 ms. Storage was 181 MB for ClickHouse and
209 MB for OpenSearch.

The undercount is a measured mechanism with a constructed magnitude. OpenSearch's standard analyzer
splits on `+` and `/`, so a blob is found only if some fragment between delimiters is at least 40
characters long. The generator draws each blob as 52 characters from a 64-character alphabet that
includes both delimiters (`synth_text_bench.py:49-54`), and the probability that such a blob keeps a
delimiter-free run of 40 works out to 0.386, close to the observed 3,159 / 7,946 = 0.398. So the roughly
60% miss rate follows from the blob length and alphabet the bench chose; the fact that an analyzed index
silently undercounts token-spanning regex is what transfers.

## What would have made it fail

Each arm's count could have disagreed with the planted truth, and two did: OpenSearch's regex count
(3,159 of 7,946), and the substring arm, where both OpenSearch and ClickHouse brute scan returned 10,066
against 10,064 planted (`results/synth_text.json`). Regenerating the seeded corpus from
`synth_text_bench.py` (`random.seed(13)`, 2M rows) reproduces the planted counts exactly and gives
exactly two random base64 blobs that contain "B64", neither on a row that also carries the planted token,
so 10,064 + 2 = 10,066 and the planted truth for that arm undercounts rather than either engine
overcounting (confirmed 2026-11-22; the expected count from 7,946 blobs of 52 characters is about 1.5).
The two arms ask slightly different questions, since the OpenSearch `*b64*` wildcard runs on lowercased
tokens while ClickHouse `position()` is case-sensitive, but that did not change the count on this corpus,
where the case-insensitive blob count is also two. The baselines are fair in
the sense that each engine runs its own default way of answering the pattern; the RESULTS file
notes that a `keyword` field or a custom analyzer would change OpenSearch's substring and regex
behaviour, and that Hyperscan was tested with a single regex, which does not exercise its multi-pattern
advantage.

## Pre-registration

[DESIGN-2026-06-15.md](DESIGN-2026-06-15.md) is titled a design and pre-registration, but it carries a
dated update appended after the halt on real attack telemetry and the switch to a synthetic corpus, and
no hash file, so it is an amended design rather than a frozen one.

## Reproduce

```bash
python text-search-regex/synth_text_bench.py
```

The script expects OpenSearch 3.7.0 on `localhost:9200` and ClickHouse 26.5.1 reachable with the
lab's local credentials, generates the corpus with `random.seed(13)`, loads it into both engines, and
writes `results/synth_text.json`. The compose setup for the two engines is not in this folder.

## Results

- [RESULTS-2026-06-15.md](RESULTS-2026-06-15.md) with `results/synth_text.json`: the only results file.

## Versions and pins

No `requirements.txt`. The script imports `clickhouse_connect` and `requests`, which the root
`requirements.txt` pins (`clickhouse-connect==1.1.1`, `requests==2.34.2`). Engine versions are stated
in the RESULTS file.

## Evidence tier and limits

Tier B: one host, synthetic text that is lower-variety than real telemetry (which flatters both indexes),
median of five runs with no CV recorded in `results/synth_text.json`, one regex. The RESULTS file links to a private session note by wiki-link name; that
note is not part of this repo.

## Corrections

- *(corrected 2026-11-17: the RESULTS table marked the substring arm as matching truth, but both engines
  returned 10,066 against the 10,064 recorded as planted; see "What would have made it fail" above.)*
