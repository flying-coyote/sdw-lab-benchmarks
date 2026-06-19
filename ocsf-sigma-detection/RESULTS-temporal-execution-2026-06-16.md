---
type: evidence
title: "H-SIGMA-01 Execution Leg #2 — PPL temporal_ordered Rule Drops Order and Window (2026-06-16)"
created: 2026-06-16
tags: [sigma, pysigma, opensearch-ppl, temporal-ordered, correlation, detection-fidelity]
---

# H-SIGMA-01 execution leg #2 — PPL's temporal_ordered rule misses real attacks AND over-fires (2026-06-16)

SIGMA-EXEC. The 2026-06-15 event_count leg (`RESULTS-ppl-execution-2026-06-15.md`) executed one correlation
type and found the dropped *window* causes an over-fire (recall stayed 1.0). This leg executes the type that
caveat left open — **`temporal_ordered`** (the exec→lateral sequence) — and it is worse: the rule is wrong in
**both** directions. Pre-registered in `PRE-REG-temporal-execution-2026-06-16.md`. Tier B, single host,
synthetic planted corpus, OpenSearch 3.7.0 + pySigma `OpenSearchPPLBackend`.

## What the backend emits (compiled live, verbatim)

`exec_then_lateral.yml` (`temporal_ordered`: `ps_exec` THEN `rdp_lat` per `host` within `2h`) →

```
| multisearch [search source=process_creation-* | where LIKE(cmd_line, "%-EncodedCommand%")]
              [search source=network_connection-* | where dst_port=3389]
| stats dc(EventID) as unique_rules by span(@timestamp, 2h), host | where unique_rules >= 2
```

It keeps a window (`span 2h`) — so it passed the compile-time window-fidelity check in `sigma-portability` —
but at execution two defects bite: the window is **tumbling, not sliding**, and the **ordering is gone**
(`dc(EventID) >= 2` is co-occurrence, not exec-*then*-lateral).

## Method

200 hosts, 5 planted populations (N=40 each), two synthetic indices (`process_creation-synth` +
`network_connection-synth`), fixed seed. EventID planted as a per-rule-type constant so `dc(EventID)` can run
at all (see the third defect below). Ran the **verbatim emitted PPL** against `zfr-opensearch`; scored flagged
hosts vs a correct **sliding + order-enforced** Python reference (`ps.ts < rdp.ts <= ps.ts + 2h`).

- **TRUE_INBUCKET** — ps then rdp, in order, same 2h bucket. A real attack.
- **TRUE_STRADDLE** — ps late in bucket k, rdp early in bucket k+1, in order, ~15 min apart (≪ 2h). A real attack.
- **WRONG_ORDER** — rdp then ps, same bucket. NOT the attack pattern.
- **BENIGN_SINGLE** — only one rule type. **BENIGN_FARAPART** — both, but > 2h apart.

## Result

| detector | flagged | recall | precision | inbucket | straddle | wrong-order | benign |
|---|--:|--:|--:|--:|--:|--:|--:|
| **emitted PPL** (tumbling span, unordered `dc>=2`) | 80 | **0.50** | **0.50** | 40 ✅ | **0 ✗ (all missed)** | **40 ✗ (all over-fired)** | 0 |
| correct sliding + ordered reference | 80 | 1.00 | 1.00 | 40 | 40 | 0 | 0 |

- **Dropped-window MISS RATE = 1.0** on the straddle set: every real exec→lateral sequence that crossed a 2h
  tumbling-bucket boundary was silently missed (neither bucket reached `dc>=2`). Recall halved, 1.0 → 0.50.
- **Dropped-order OVER-FIRE = 40/40**: every reversed (lateral-then-exec) sequence was flagged, because the
  query counts co-occurrence and never checks that exec preceded lateral. Precision halved, 1.0 → 0.50.

## What it says

The event_count leg showed the dropped *window* floods false positives but still catches every real burst
(recall 1.0) — annoying, not dangerous. **The temporal_ordered leg is the dangerous one: it misses real
attacks.** Run exactly as the PPL backend compiles it, the exec→lateral rule both (a) silently fails to fire
on a true sequence that straddles its tumbling-window boundary, and (b) fires on the reverse sequence that
isn't the attack. A detection engineer who compiles this rule and ships it gets a detector that is wrong in
both directions with no error at compile or run time. The **loud-refusing Lucene-family backend**
(`OpensearchLuceneBackend`) raises `NotImplementedError` on this rule (and on every correlation rule) — so on
a Lucene-family backend the same detection is a **100% miss** (nothing runs), which is at least visible rather
than silently wrong.

## Caveats (Tier B)

- **The 1.0 miss rate and 40/40 over-fire are corpus-design-dependent** — I planted every straddler on a
  boundary and every wrong-order reversed, to isolate the mechanisms. The transferable finding is the
  **mechanism**, not the rate. The realistic tumbling-miss rate ≈ gap/window for randomly-placed sequences
  (e.g. a 15-min exec→lateral gap in a 2h tumbling window straddles a boundary ~12.5% of the time — so ~1 in
  8 real sequences silently missed from this artifact alone, before the ordering defect). The over-fire rate
  depends on how often lateral-then-exec co-occurs benignly in an estate.
- **Third defect, noted not headlined:** the emitted query references `EventID`, a Windows-Event-Log field
  generic OCSF/Zeek data does not carry. On data without it, `dc(EventID)` collapses and the rule **silently
  never fires** — a 100% miss for a different reason. The corpus plants a per-rule-type EventID so the
  charitable execution can run at all; a real estate mapping OCSF would hit this wall first.
- n=1 backend executed for the sequence (OpenSearch PPL); n=1 chain shape; version-bound (OpenSearch 3.7.0,
  pySigma `OpenSearchPPLBackend`, 2026-06-16). `value_count` (userspray) is not separately executed — its
  window-drop generalizes the event_count over-fire mechanism (count path), already shown.

## What it does to the hypothesis

Extends H-SIGMA-01's execution-fidelity leg to a **second correlation type** and adds the **miss** direction
(false negatives) the event_count leg couldn't show. The dangerous mode — silent partial translation →
runnable-but-wrong — is now confirmed at execution on two rule shapes and in both directions (over-fire +
miss). **Stays Tier B / synthetic / single-chain** — strengthens the structural argument, does not clear the
hypothesis gate. Route through karen → hypothesis-validator → contradiction-detector before any confidence
move; the expected disposition is HOLD-with-attach, no magnitude change.
