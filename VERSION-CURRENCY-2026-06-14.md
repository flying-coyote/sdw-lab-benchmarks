# Software version-currency pass — 2026-06-14

Per the "ensure software versions are as updated as possible" directive: audited the benchmark
stack against latest, updated where behind, and re-validated the literature-load-bearing
results on the current software. Net: **the cited numbers hold on the updated stack, with one
finding that moved — and it moved in the most instructive way.**

## Audit + updates

**Already latest (no action):** DuckDB 1.5.3, pyiceberg 0.11.1, polars 1.41.2, datafusion
53.0.0, opensearch-py 3.2.0, fastparquet 2026.5.0, trino 0.337.0; ClickHouse server 26.5.1
(`:latest`, 3 weeks old); Dremio OSS 26.0.5 (the OSS `:latest` — no newer tag published).

**Updated to latest:** clickhouse-connect 1.1.1 → 1.3.0 · chdb 4.1.8 → **4.1.9**
(chdb-core 26.3 → 26.5) · pyarrow 23.0.1 → 24.0.0 · pyiceberg-core 0.8.0 → 0.9.1.

**Engine image bumped:** OpenSearch (the flagship foil) **2.18.0 → 3.7.0** — it was the one
materially-stale component (2.18.0 was 17 months old). compose.yml now pins 3.7.0; the foil was
re-loaded (10M docs, fresh index) and re-validated.

(One known conflict from the bumps: `daft` 0.7.14 wants pyarrow<24 / fsspec<2026.3 — daft is
only used by the clickhouse-vs-duckdb Phase-E 13-engine harness, not the flagship or the
answer-eq mechanisms; pin pyarrow/fsspec back before re-running that specific harness.)

## Flagship foil (OpenSearch 2.18.0 → 3.7.0): no material change

OpenSearch 3.7.0 performs essentially identically to 2.18.0 on the 5-query suite. The clean
**same-draw** comparison (both 06-14, same machine state) is OS 2.18 **2.5816 s** vs OS 3.7
**2.5524 s** = **−1.1%**, answer-equality ALL IDENTICAL. (Against the 06-10 *published* 2.8537 s
the 3.7 number looks ~11% faster, but that is the common-mode ~10% machine/page-cache drift the
flagship revalidation already documented across every engine — not a version effect.)

So a current OpenSearch does **not** flatter or inflate the comparison: the two-regime multiples
(~10× Iceberg / ~45× native over the foil, 06-14 same-draw) hold on the current foil. The
published numbers are not an artifact of a stale 2.18 index. Evidence:
`zeek-flagship-rerun/results_version_currency_2026-06-14/`. Published 2.18 numbers stay canonical
in `results/`; compose tracks 3.7.0 for future runs.

## Answer-equivalence (the finding that moved): chDB 4.1.9 fixed one of the two bugs

The two silent-wrong Parquet readers behave differently on the latest libraries:

- **chDB bloom-pushdown undercount — FIXED in 4.1.9.** On chDB 4.1.8 the default v3 reader
  silently undercounted equality predicates (user1337 4966 vs 4972); on **4.1.9 it is ALL
  CORRECT** (the chdb-core ClickHouse engine moved 26.3 → 26.5). Caught here, version-bound,
  fixed by a point release.
- **fastparquet DuckDB-`PLAIN_DICTIONARY` mis-decode — STILL LIVE** on fastparquet 2026.5.0
  (already latest): user7 531 vs 532, 4,672/1M rows decoded wrong, no error.

So the "2 of 13 silently wrong" claim is now **1 of 13 on the very latest libraries**. This is
the clean demonstration of why the equality check belongs in CI: of the two bugs the lab caught,
one was fixed by the next point release and one persists — the failure set is real, version-bound,
and moving. Detail: `clickhouse-vs-duckdb/results/RECONFIRMATION-2026-06-14.md`.

## Net for the literature

- Flagship two-regime multiples: **hold on current software** (current foil, current engines).
- Answer-equivalence: update the copy from a static "2 silently wrong" to the version-pinned,
  CI-justifying form — **2 caught; chDB fixed in 4.1.9; fastparquet still wrong on latest**.
- All other heavily-cited benches were re-validated earlier today on the (already-current) stack.
