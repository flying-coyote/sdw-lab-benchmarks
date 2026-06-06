# MV maintenance: the base:batch crossover (T2.4)

**Tier B · single machine.** R5 gave incremental-vs-recompute at one base size; this sweeps the base at a
fixed batch (200,000 rows) to find the ratio where incremental maintenance overtakes full
recompute, for a bounded- and an unbounded-cardinality high-card MV. `recompute/incremental > 1` ⇒
incremental wins (a full recompute costs ∝ base; an incremental merge costs ∝ MV rows + batch).

### bounded_high_card (user_name × dst_port)

| base:batch | base | MV rows | recompute ms | incremental ms | recompute/incremental | winner |
|--:|--:|--:|--:|--:|--:|---|
| 5:1 | 1M | 16,000 | 29.6 | 31.2 | 0.95× | ❌ recompute |
| 25:1 | 5M | 16,000 | 65.8 | 34.6 | 1.9× | ✅ incremental |
| 100:1 | 20M | 16,000 | 183.9 | 33.0 | 5.57× | ✅ incremental |
| 200:1 | 40M | 16,000 | 356.8 | 42.0 | 8.49× | ✅ incremental |

### unbounded_high_card (src_ip)

| base:batch | base | MV rows | recompute ms | incremental ms | recompute/incremental | winner |
|--:|--:|--:|--:|--:|--:|---|
| 5:1 | 1M | 968,023 | 1158.2 | 1812.9 | 0.64× | ❌ recompute |
| 25:1 | 5M | 4,312,607 | 5046.0 | 7082.6 | 0.71× | ❌ recompute |
| 100:1 | 20M | 11,666,665 | 14153.0 | 19030.7 | 0.74× | ❌ recompute |
| 200:1 | 40M | 15,221,360 | 18791.8 | 24001.1 | 0.78× | ❌ recompute |

## Crossover

- **bounded_high_card (user_name × dst_port)**: incremental first wins at **base:batch ≈ 25:1**
- **unbounded_high_card (src_ip)**: incremental **never wins** in the swept range (MV grows with base)

## Reading

The maintenance economics are a ratio, not a verdict. For a **bounded**-cardinality MV (here user_name ×
dst_port, which saturates at 16,000 groups), the incremental merge re-aggregates a roughly fixed MV plus
the arriving batch, so its cost is ~flat in the base size, while a full recompute rescans the whole base —
so once the base is large enough relative to the batch, incremental wins, and the crossover above is where.
That is the regime a streaming SOC lives in (a huge, growing base table and small frequent batches), which
is exactly where incremental maintenance pays. For an **unbounded**-cardinality MV (src_ip, whose group
count grows with the base), the MV is nearly as large as the base, the merge re-aggregates almost
everything every batch, and incremental never pulls ahead — so the honest design rule is: incremental
maintenance is the right call for **bounded-cardinality** panels at high base:batch, and an
unbounded-cardinality "MV" is really just a recompute wearing a hat. Tier B, single machine; the crossover
ratio is this corpus's, the shape (bounded saturates → wins; unbounded doesn't) is the transferable finding.
