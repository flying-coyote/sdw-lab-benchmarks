# H-SIGMA-01 execution leg — PPL's dropped correlation window over-fires at runtime (2026-06-15)

The compile-time finding (C4 / `correlation.py`): the pySigma **OpenSearch PPL** backend (2.0.3) compiles
the `brute_force` event-count correlation rule (≥10 failed logons per `actor_user` within **10 minutes**)
to a runnable query that **drops the timespan window**:

```
source=auth-* | where outcome="FAILURE" | stats count() as event_count by actor_user | where event_count >= 10
```

"≥10 failures in 10 minutes" silently becomes "≥10 failures **ever**." The Lucene backend instead refuses
loudly (`NotImplementedError: Backend does not support correlation rules`). This leg **executes** both the
emitted windowless PPL and a correct windowed PPL against OpenSearch 3.7.0 to measure the over-fire the
dropped window causes — moving the finding from compile-time omission to a runtime miss.

## Method (Tier B, single host, synthetic planted corpus)

4,093 synthetic auth events (`@timestamp`, `actor_user`, `outcome`), three planted populations:
- **20 TRUE** users — a real burst: 12 FAILUREs inside one (epoch-aligned) 10-min window (true bruteforce).
- **50 DECOY** users — 12 FAILUREs spread uniformly over 7 days: ≥10 *ever* but never ≥10 in any 10-min
  window (ordinary accumulated typos/lockouts). The windowed rule must IGNORE these.
- **500 BENIGN** users — <10 FAILUREs total.

Both queries run on zfr-opensearch `_plugins/_ppl`; users flagged are scored against the planted truth.
The windowed query is a tumbling `span(@timestamp, 10m)` count (the bursts are planted bucket-aligned so
the tumbling window is a fair baseline — see caveat).

## Result

| query | flagged | true caught | precision | false positives |
|---|--:|--:|--:|--:|
| **emitted windowless PPL** | 70 | 20/20 (recall 1.0) | **0.286** | **50 (all decoys)** |
| correct windowed PPL (span 10m) | 20 | 20/20 (recall 1.0) | 1.00 | 0 |

**The dropped window turns a precise correlation rule into one where 71% of its alerts are false positives
(50 of 70).** It still catches every real burst (recall 1.0) — but it *also* flags every user who ever
accumulated 10 failures, because it counts failures across all time instead of within the window. The
correct windowed query (and the loud-refusing Lucene backend) avoid this entirely. The compile-time
"the window is dropped" omission is now an **executed runtime over-fire**, quantified.

## What it does to the hypothesis

Moves H-SIGMA-01's execution-fidelity claim off compile-only: the silently-windowless PPL produces a real
runtime false-positive flood, not just a missing clause. The dangerous mode (silent partial translation →
runnable-but-wrong) is confirmed at execution on one backend.

## Caveats (Tier B)

- **The 71% false-positive rate is corpus-design-dependent** (it tracks the planted decoy:true ratio, 50:20).
  The transferable finding is the **mechanism** — a windowless count flags every ≥10-ever user — not the
  specific rate; a production estate's rate depends on how many users accumulate ≥10 failures over the
  retention window (in a long-retention SOC, that is *most* users, so the real over-fire is plausibly worse).
- **n=1 backend executed** (OpenSearch PPL); n=1 rule shape (event_count brute_force). The userspray
  value_count rule and the temporal-ordered exec→lateral rule are compiled but not executed here.
- The windowed baseline is **tumbling** `span` (not the rule's true *sliding* semantics); bursts are planted
  bucket-aligned so the baseline is fair, but a real sliding-window engine would also catch boundary-straddling
  bursts that tumbling misses — a separate, smaller fidelity gap not measured here.
- Single host, synthetic corpus, OpenSearch 3.7.0 + pySigma 1.3.3 / backend-opensearch 2.0.3 (version-bound).
