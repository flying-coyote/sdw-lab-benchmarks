# H-SIGMA-01 execution leg #4 — the dropped window generalizes to a SECOND backend (SQLite) (2026-06-17)

SIGMA-EXEC, the gated "execution on one OTHER backend" sub-condition. The PPL legs (2026-06-15/16) showed
OpenSearch PPL silently drops the correlation `timespan` and over-fires. This executes the pySigma **SQLite**
backend's emitted query on a file-based SQL engine — architecturally distinct from OpenSearch — against the
**same planted corpus and scorer** (`ppl_execution.gen_corpus`, apples-to-apples). Pre-registered
(`PRE-REG-sqlite-2ndbackend-2026-06-17.md`). Tier B, single host, pySigma 1.3.3 + pySigma-backend-sqlite 1.1.3.

## Result — identical over-fire shape on the second backend

The SQLite backend emits, for `event_count >= 10 per actor_user in 10m`:

```sql
SELECT actor_user, COUNT(*) AS event_count FROM (SELECT * FROM logs WHERE outcome='FAILURE') AS subquery
GROUP BY actor_user HAVING event_count >= 10
```

Windowless — the `timespan: 10m` is dropped, exactly like PPL.

| query | flagged | recall | precision | decoy FP |
|---|--:|--:|--:|--:|
| **emitted windowless SQLite** | 70 | 1.0 | **0.286** | **50 (all decoys)** |
| correct windowed SQL (10-min bucket) | 20 | 1.0 | 1.00 | 0 |

Identical to the PPL `event_count` leg (also 0.286 / 50 decoy FP). `value_count` also compiled **windowless**
on SQLite (matching PPL's value_count leg); `temporal_ordered` compiled. So a second, architecturally
different backend silently drops the same correlation window at compile and over-fires at execution.

## What it does to the hypothesis

The silent window-drop is now demonstrated **at execution on two architecturally distinct backends**
(OpenSearch PPL + SQLite), with identical over-fire shape — so it is a **cross-backend pattern, not a
PPL-plugin quirk** (H-SIGMA-01's Alternative — "a maturity artifact of one specific backend" — is weakened).
This is the gated "execution on one OTHER backend" sub-condition met. **Confidence 2.5/5 → 3/5.** The
sharper framing: the drop is a property of how **pySigma compiles correlation across its backend plugins** —
a green compile is not a portable detection, and the dangerous mode is the silent partial translation, now
on two targets. **Capped at 3/5:** both targets are pySigma backends (the cleanest next gate is execution on
a target-SIEM-native path outside pySigma, or a newer-pySigma maturity re-test); synthetic planted corpus;
the 0.286 over-fire *rate* tracks the planted 50:20 decoy:true ratio (the transferable claim is the
mechanism, not the rate). No contradiction — same direction as the PPL legs. Pre-registered prediction
matched (no surprise; falsifier — a loud refusal or a windowed compile — did not trigger). Route karen →
hypothesis-validator → contradiction-detector.
