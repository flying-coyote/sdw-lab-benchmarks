# H-SIGMA-01 execution leg #3 — value_count (userspray) over-fires too: the window-drop generalizes (2026-06-16)

SIGMA-EXEC, completing the correlation-type execution matrix. The compile finding (`sigma-portability`)
flagged THREE PPL count rules that silently drop the timespan window (bruteforce/passwordspray `event_count`
+ userspray `value_count`); the 2026-06-15 leg executed one `event_count` rule, the 2026-06-16 temporal leg
did `temporal_ordered`. This executes the `value_count` (distinct-count) path. `value_count_execution.py` +
`results/value_count_execution.json`. Tier B, single host, synthetic planted corpus, OpenSearch 3.7.0 +
pySigma `OpenSearchPPLBackend`.

## What the backend emits (compiled live, verbatim)

`userspray` (`value_count`: ≥10 DISTINCT `actor_user` per `src_ip` within 10m) →

```
| search source=auth-* | where outcome="FAILURE" | stats dc(actor_user) as value_count by src_ip
                       | where value_count >= 10
```

Windowless — the 10m timespan is dropped, exactly like `event_count`. ">=10 distinct users in 10 min" becomes
">=10 distinct users EVER".

## Result

Planted: 20 spray src_ips (≥12 distinct users in one 10m window), 50 decoy src_ips (≥12 distinct users spread
over 7 days — ≥10 ever, never ≥10 in any 10m window), 300 benign (<10 distinct).

| query | flagged | recall | precision | decoy FP |
|---|--:|--:|--:|--:|
| **emitted windowless PPL** | 70 | 1.0 | **0.286** | **50 (all decoys)** |
| correct windowed PPL (span 10m) | 20 | 1.0 | 1.00 | 0 |

Identical shape to the `event_count` leg (also 0.286 / 50 decoy FP): the windowless distinct-count flags every
src_ip that ever touched ≥10 distinct users, so **71% of its alerts are false positives**, while still
catching every real spray (recall 1.0). The correct windowed query flags exactly the 20.

## What it does to the hypothesis

The dropped-window over-fire is now confirmed at execution on **both** count-based correlation types
(`event_count` + `value_count`) — the count path the compile finding flagged as silently windowless is
runnable-but-wrong in the same way regardless of count vs distinct-count. Combined with the `temporal_ordered`
leg (dropped window+order → MISS), SIGMA-EXEC has now executed all the correlation shapes PPL silently
degrades: count rules over-fire, the ordered-sequence rule misses. **Confidence HELD 2.5/5** — same
single-backend (PPL), synthetic, corpus-design-dependent rate (the 71% tracks the 50:20 decoy:true ratio; the
transferable claim is the mechanism). No contradiction (consistent with the event_count leg). The two
remaining 3/5 sub-conditions (execution on one OTHER backend; a newer-pySigma maturity test) are unchanged.
