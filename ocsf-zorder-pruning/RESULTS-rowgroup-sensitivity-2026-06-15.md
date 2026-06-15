# Z-order pruning — row-group-size sensitivity leg (2026-06-15)

Owed follow-on for **H-LAKEHOUSE-ZORDER-01** (the hypothesis-evidence gate flagged the
row-group-size sensitivity as the untested leg that decides whether the dominant-query-shape
Null survives). Question: does z-order's pruning-coverage advantage on the dimensions a single
sort can't serve (Q3/Q4) survive at DuckDB's default **122,880-row** groups, or is it an
artifact of the bench's **50,000-row** groups?

## Method (contention-safe)

The pruning measure is read from Parquet **footer min/max statistics** (`count_prunable_rgs`),
so it is **deterministic and machine-state-independent** — unlike latency, it is not confounded by
concurrent load, which is why this leg can run outside a dedicated quiet window. The driver
(`rowgroup_sensitivity.py`) imports the canonical bench's own functions (`_gen_corpus`,
`build_queries`, `write_unordered/single_sort/zorder`, `row_group_stats`, `count_prunable_rgs`)
and runs the pruning analysis at both row-group sizes on the same 2,000,000-row seeded OCSF
Network Activity corpus. DuckDB 1.5.3 / pyarrow 24.0.0, single host, Tier B. Latency was **not**
re-run (contention-sensitive and secondary — the hypothesis is a pruning-*coverage* claim).

**Validation:** the 50,000-row-group pass reproduces the canonical `RESULTS.md` numbers exactly
(Q1 single_sort 95.0% / zorder 72.5%; Q2 97.5% / 65.0%; Q3 zorder 15.0%; Q4 zorder 65.0%), so the
driver is faithful and the corpus generation is deterministic.

## Result — pruning coverage (% of row groups prunable on footer min/max)

| query | predicates | 50,000-row groups (40 rgs) | 122,880-row groups (17 rgs) |
|---|---|---|---|
| Q1 `src_ip ∈ /24 AND time` | single-sort's key | single_sort **95.0%** / zorder 72.5% | single_sort **94.1%** / zorder 58.8% |
| Q2 `dst_port AND src_ip` | single-sort's key | single_sort **97.5%** / zorder 65.0% | single_sort **94.1%** / zorder 47.1% |
| Q3 `dst_endpoint AND port` | single-sort can't see | zorder **15.0%** (others 0%) | zorder **11.8%** (others 0%) |
| Q4 `time-window only` | single-sort can't see | zorder **65.0%** (others 0%) | zorder **47.1%** (others 0%) |

(unordered prunes 0% on every query at both sizes.)

## Finding — the Null is not supported; the effect weakens but survives

At DuckDB's default 122,880-row groups (17 row groups vs 40), z-order **still** buys real pruning
coverage on exactly the dimensions a single sort abandons — Q3 11.8% and Q4 47.1% where both
single-sort and unordered prune 0% — so the coverage advantage is **not** an artifact of the
bench's smaller row groups. It **weakens** with the coarser granularity (Q4 65.0% → 47.1%, a ~28%
relative drop; Q3 15.0% → 11.8%, ~21%), because fewer, wider row groups carry wider min/max ranges
and prune less precisely. The **shape is unchanged**: z-order is the only layout that prunes Q3/Q4,
single-sort still wins Q1/Q2 outright, and every layout prunes 0% on the dimensions it can't see.

So the hypothesis's narrow claim — z-order is a pruning-coverage lever on the dimensions a single
sort can't serve, paid at write time — is **robust to row-group size, weakened not eliminated**,
and the dominant-query-shape Null ("the coverage gain doesn't survive at realistic row-group
sizes") is **not** supported on this single-file corpus. Still owed before any promotion past the
narrow within-file claim: the multi-file catalog leg (cross-file pruning additive to within-file)
and the Bloom-filter / page-index comparison (the Alternative). Tier B, single host; the relative
ordering and the weakens-but-survives shape transfer, the exact percentages are corpus-specific.
