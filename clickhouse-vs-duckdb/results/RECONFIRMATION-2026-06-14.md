# Answer-equivalence re-confirmation (2026-06-14) — the two silent-wrong readers STILL reproduce

**Tier B · single host · ground-truth-verified.** The standing claim cited by the campaign,
Subsurface, and lab.astro — *"11 of 13 Parquet readers agree; 2 silently return wrong
answers"* — was re-checked on current versions as the B-COST/B-ANSWEREQ re-run. The question
was whether the two bugs had been fixed upstream (which would make the live claim
version-stale). **They have not.** Both minimal-reproduction mechanisms still fire.

## chDB / ClickHouse C++ v3 reader — bloom-pushdown undercount (STILL LIVE)

`mechanism_chdb_bloom.py` re-run, chDB `4.1.8`, 10M-row corpus, `ROW_GROUP_SIZE 12288`:

| reader config | verdict | example (user1337, truth 4972) |
|---|---|---|
| **default (v3 reader, bloom pushdown on)** | **DIVERGES** | **4966** (−6; every probe undercounts) |
| `input_format_parquet_bloom_filter_push_down=0` | correct | 4972 |
| `input_format_parquet_use_native_reader_v3=0` (older reader) | correct | 4972 |
| `filter_push_down=0` (min/max only) | DIVERGES | 4966 |
| `use_native_reader=0` | DIVERGES | 4966 |

Every probe undercounts under the default reader (user42 5092/5099, user1337 4966/4972,
user256 4988/5000, user1023 5012/5022) and is correct only with bloom pushdown or the v3
reader disabled — the same signature as the originally reported bug. The fast, confident,
wrong undercount on equality predicates is exactly the silent-detection-miss failure mode.

## fastparquet — DuckDB PLAIN_DICTIONARY mis-decode (STILL LIVE)

`mechanism_fastparquet_dict.py` re-run, fastparquet `2026.5.0`, pyarrow `23.0.1`, 1M-row
corpus:

| file | fastparquet user7 (truth 532) | rows where fastparquet ≠ pyarrow |
|---|---|---|
| **DuckDB-written (PLAIN_DICTIONARY)** | **531 (MISDECODE −1)** | **4,672** |
| pyarrow dict | 532 (OK) | 0 |
| pyarrow no-dict | 532 (OK) | 0 |

fastparquet still mis-decodes DuckDB's deprecated `PLAIN_DICTIONARY` string encoding —
4,672 rows in a 1M-row file read back as the wrong value, with no error.

## Reconciling with parquet-library-matrix / ocsf-pruning-correctness ("clean" benches)

Those two benches re-ran clean today (`parquet-library-matrix`: SILENT-WRONG none;
`ocsf-pruning-correctness`: every engine sound), which could read as "the bug class is fixed."
It is not — the difference is the **trigger conditions**, and that is itself the finding:

- The clean benches use small, low-cardinality, clean-ASCII test corpora and forced-encoding
  round-trips; under those structures neither bug fires.
- The mechanism scripts (and the Phase-E 13-engine test) use a realistic **high-cardinality**
  corpus (`corpus.gen_select`, many distinct `user_name` values) written with **small row
  groups** — the structure that builds per-row-group bloom filters and a large string
  dictionary, which is what both bugs key on. That is also the structure security telemetry
  actually has (high-cardinality IOC / user / host fields).

So the honest statement is **not** "no engine is silently wrong on current versions" — it is
"on current versions the two readers are silently wrong **under the high-cardinality,
small-row-group conditions security data hits**, and correct on a tiny clean test set." The
parquet-library-matrix / ocsf-pruning-correctness "clean" conclusions should carry that
coverage caveat; they do not contradict the live 11-of-13 claim, they just don't exercise the
trigger.

## Consequence for the published copy

The campaign (Post 9), Subsurface abstract, and lab.astro cite the present-tense "2 silently
return wrong answers." As of the chDB 4.1.8 test that language was correct; the version-currency
update below now sharpens it (one of the two was fixed by a point release). Pin the versions and
the trigger nuance (high-cardinality fields, small row groups) so the claim is precise.

## Version-currency update (2026-06-14) — chDB 4.1.9 FIXES the bloom undercount; fastparquet persists

Per the "as updated as possible" directive, the libraries were bumped to latest and the two
mechanisms re-run:

| reader | version tested | result |
|---|---|---|
| chDB / ClickHouse C++ v3 | 4.1.8 (yesterday) → **4.1.9** (latest) | bloom undercount **FIXED in 4.1.9** — default v3 reader now ALL CORRECT (user1337 4972 = truth); 4.1.8 diverged (4966). The chdb-core ClickHouse engine moved 26.3 → 26.5. |
| fastparquet | **2026.5.0** (already latest) | DuckDB-`PLAIN_DICTIONARY` mis-decode **STILL LIVE** — user7 531 vs 532, 4,672/1M rows ≠ pyarrow. |

So the honest current count is **1 of 13 silently wrong on the very latest libraries**
(fastparquet only), down from 2 on the versions first caught. This is the load-bearing point
of the whole answer-equivalence check, now demonstrated end-to-end: the chDB undercount was
*caught here, is version-bound, and was fixed by a point release* — while the fastparquet
mis-decode persists on the latest version. The claim to publish is therefore **not** a static
"2 silently wrong" and **not** "all fixed" — it is "**we caught 2 silently-wrong readers; one
(chDB) was fixed in the next point release, one (fastparquet) is still wrong on the latest
version — which is exactly why this equality check belongs in CI rather than being assumed.**"
The version-bound, moving nature of the failure IS the finding.
