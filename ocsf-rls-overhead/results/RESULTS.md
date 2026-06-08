# OCSF RLS Overhead — engine-side predicate cost of row-level security

- DuckDB `1.5.3`  
- Host: 14 vCPU, `Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39`  
- Corpus: 1,000,000 rows, 100 tenants, fingerprint `92d8ed21b4e8253b…`  
- Answers identical (predicate ↔ view, every query/tier): **True**  
- Evidence tier: B (single machine; latencies are medians with CV; corpus and answers are deterministic; this is engine-side overhead only — catalog-layer enforcement (Polaris/Unity/Lake Formation) adds further cost not measured here)

> **Lower-bound caveat.** DuckDB evaluates RLS predicates as ordinary WHERE clauses after parsing. Real catalog systems (Polaris, Unity Catalog, AWS Lake Formation) enforce policy at the catalog protocol layer before the engine plans — adding token-validation, policy-evaluation, and protocol round-trip cost. Cross-reference q3-catalog-benchmark for the catalog-layer component.

Latencies are wall-clock **medians** (ms) with coefficient of variation (CV%) over 7 trials after 2 warmup calls. A delta below the CV is not a real difference. Overhead % = (enforced − baseline) / baseline × 100.

## tier_1pct  (visible_tenants=1, actual selectivity=1.0%)

| query | baseline ms (cv%) | predicate ms (cv%) | overhead % | view ms (cv%) | overhead % | pred↔view agree |
|---|--:|--:|--:|--:|--:|:--:|
| count_all | 0.7 (13%) | 1.3 (17%) | +81% | 1.3 (13%) | +94% | yes |
| top_talkers | 33.0 (5%) | 4.8 (28%) | -86% | 4.6 (27%) | -86% | yes |
| group_by_act | 1.9 (16%) | 2.5 (22%) | +30% | 2.0 (10%) | +2% | yes |
| needle | 0.8 (17%) | 0.8 (12%) | +11% | 0.8 (9%) | +8% | yes |

## tier_10pct  (visible_tenants=10, actual selectivity=10.0%)

| query | baseline ms (cv%) | predicate ms (cv%) | overhead % | view ms (cv%) | overhead % | pred↔view agree |
|---|--:|--:|--:|--:|--:|:--:|
| count_all | 0.7 (36%) | 1.2 (15%) | +67% | 1.2 (13%) | +65% | yes |
| top_talkers | 26.7 (7%) | 8.2 (9%) | -69% | 7.9 (16%) | -70% | yes |
| group_by_act | 2.1 (12%) | 2.0 (11%) | -3% | 2.0 (11%) | -3% | yes |
| needle | 1.0 (12%) | 0.9 (11%) | -1% | 0.8 (6%) | -16% | yes |

## tier_50pct  (visible_tenants=50, actual selectivity=50.0%)

| query | baseline ms (cv%) | predicate ms (cv%) | overhead % | view ms (cv%) | overhead % | pred↔view agree |
|---|--:|--:|--:|--:|--:|:--:|
| count_all | 0.7 (36%) | 1.1 (10%) | +54% | 1.3 (14%) | +96% | yes |
| top_talkers | 29.1 (6%) | 19.8 (8%) | -32% | 19.9 (33%) | -32% | yes |
| group_by_act | 2.3 (8%) | 2.6 (14%) | +12% | 2.6 (4%) | +15% | yes |
| needle | 1.0 (21%) | 1.0 (8%) | +5% | 1.0 (10%) | -3% | yes |

## Reading

The overhead% column is the cost, in extra latency, of enforcing row-level security at the engine layer across two mechanisms: a WHERE predicate appended to the query, and a secured VIEW the query hits directly. Both approaches incur the same logical work (filter the corpus by `tenant_id`), so they should produce identical answers — the correctness gate above confirms this. The overhead should scale with selectivity: a 1%-selectivity filter reads 99% fewer rows than the baseline (high overhead on a full-scan count but potentially near-zero on a needle lookup that hits an index-like path early), while a 50%-selectivity filter reads half the table and overhead should track selectivity roughly linearly for scan-shaped queries.

The gap between predicate and view overhead (if any) is the cost of the view-wrapper indirection — DuckDB should inline the view predicate into the plan, so the gap should be small or within CV. A systematic view-is-slower gap would indicate the view wrapper prevents a predicate-pushdown optimization that the raw predicate allows; that is the finding to watch for.

This is Tier B, single machine, DuckDB engine-side only. The "overhead" measured here is the lower bound: a real multi-tenant SIEM or data-lake platform with catalog-layer RLS (Polaris principal roles, Unity Catalog row filters, Lake Formation cell-level permissions) adds policy-evaluation and protocol round-trips on top of this engine cost. Cross-reference q3-catalog-benchmark for the catalog-enforcement component.

Advances H-SECURITY-02 (federated catalog RBAC). Run `python ocsf-rls-overhead/run.py` to reproduce.
