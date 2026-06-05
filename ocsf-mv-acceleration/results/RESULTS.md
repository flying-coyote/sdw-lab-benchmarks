# Materialized-view acceleration for SOC dashboards — with its cost (R5)

**Tier B · single machine.** 20,000,000 OCSF events ingested in 20 streaming
batches; three SOC-dashboard panels served two ways — a base-table scan on every refresh vs a tiny
additive materialized view maintained incrementally per batch. Read latencies are medians with CV;
storage is exact on-disk Parquet bytes. H-MV-SECURITY-01.

| panel | base scan ms (cv) | MV serve ms (cv) | read speedup | MV maint ms/batch | full-recompute ms | incremental vs recompute | MV storage overhead |
|---|--:|--:|--:|--:|--:|--:|--:|
| class_rollup | 70 (40%) | 0.9 (7%) | 76.8× | 29.61 | 85 | 2.9× | +0.0% |
| time_series_5m | 65 (7%) | 1.2 (4%) | 53.6× | 32.78 | 62 | 1.9× | +0.001% |
| failed_auth_by_user | 32 (11%) | 0.7 (4%) | 45.3× | 31.65 | 31 | 1.0× | +0.002% |

Base table: 709 MB.

## Reading

The read speedup is the headline a dashboard owner sees: serving a panel from the pre-aggregated MV
collapses a full-corpus scan to a read of a few hundred rows. But the cost is in the other columns. The
MV has to be maintained, and the maintenance strategy is where the real engineering choice sits:
recomputing the aggregate from the base table on every refresh delivers the same read speedup while
throwing the compute saving away (it re-scans the whole corpus each time), whereas merging each ingest
batch's partial aggregate keeps the MV current for a small per-batch cost — the `incremental vs recompute`
column is how much cheaper the streaming-correct path is. The storage overhead is small here because these
panels collapse to few groups, but it scales with the aggregate's cardinality, not the base table's.

The constraint the speedup hides is that an MV only answers the questions you pre-decided: all three
panels here are additive count/sum group-bys, which is exactly what lets them be maintained incrementally,
and an ad-hoc query — a new pivot, a different filter, a hunt — still pays the base scan. So a
materialized view is a bet that a fixed set of questions is worth paying storage and per-batch maintenance
to answer fast, and it's the right bet precisely for the always-on SOC dashboard whose question set is
stable, not for exploratory analysis. Tier B, single machine; the speedup/maintenance/storage trade is the
transferable finding, the magnitudes are this corpus's.
