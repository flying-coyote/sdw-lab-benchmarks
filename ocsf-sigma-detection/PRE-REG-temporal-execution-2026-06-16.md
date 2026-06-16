# Pre-registration — temporal_ordered execution leg (SIGMA-EXEC, H-SIGMA-01) — 2026-06-16

Pre-registered BEFORE the scored run (M6 discipline). Extends the event_count PPL-execution leg
(`RESULTS-ppl-execution-2026-06-15.md`, which quantified the *count* rule's dropped-window over-fire) to the
**temporal_ordered** correlation rule — the one the 2026-06-15 caveats named as "compiled but not executed."

## What the PPL backend actually emits (verified 2026-06-16, pySigma OpenSearchPPLBackend)

The `exec_then_lateral` rule (`temporal_ordered`: `ps_exec` THEN `rdp_lat` per `host` within `2h`) compiles to:

```
| multisearch [search source=process_creation-* | where LIKE(cmd_line, "%-EncodedCommand%")]
              [search source=network_connection-* | where dst_port=3389]
| stats dc(EventID) as unique_rules by span(@timestamp, 2h), host
| where unique_rules >= 2
```

Two structural defects are visible in the emitted text and become measurable at execution:
1. **Ordering is DROPPED.** `temporal_ordered` means exec must precede lateral. The emitted query counts
   distinct rule-types co-occurring in a bucket — it fires on `rdp_lat` THEN `ps_exec` (reversed) too.
2. **The window is TUMBLING, not sliding.** `span(@timestamp, 2h)` is a fixed bucket. A real exec→lateral
   sequence whose two events fall on opposite sides of a 2h bucket boundary (but well within 2h of each
   other) lands in two different buckets, so neither bucket reaches `dc >= 2` — a silent miss.
3. **(Secondary) `EventID` is referenced** — a Windows-Event-Log field generic OCSF/Zeek data lacks; on
   data without it, `dc(EventID)` collapses and the rule silently never fires (a separate 100%-miss mode,
   noted but not the headline; the planted corpus carries a per-rule-type EventID so the charitable
   execution can run at all).

## Hypotheses / expected outcomes (pre-committed)

- **H1 (over-fire from dropped ordering):** the emitted PPL fires on WRONG-ORDER (lateral-then-exec)
  same-bucket sequences → precision < 1.0. Expected: it flags them (they are co-occurrence).
- **H2 (miss from tumbling window):** the emitted PPL MISSES in-order sequences that straddle a 2h bucket
  boundary → recall < 1.0. The **dropped-time-window miss rate** = (boundary-straddle true sequences missed)
  / (all true in-order-within-2h sequences). Expected: misses ~all boundary-straddlers.
- **Reference (the null/control):** a correct detector — sliding 2h window AND order enforced (exec.ts <
  lat.ts <= exec.ts + 2h) — computed in Python over the planted truth, scores recall 1.0 / precision 1.0.
  If the emitted PPL matched it, the null ("PPL executes the ordered sequence faithfully") would win.

## Planted synthetic corpus (boundary-safe: structured synthetic events only, no real telemetry)

Per-host populations, two indices `process_creation-synth` + `network_connection-synth`, fixed seed:
- **TRUE_INBUCKET** (N): `ps_exec` then `rdp_lat`, in order, both inside ONE aligned 2h bucket. True positive.
- **TRUE_STRADDLE** (N): `ps_exec` late in bucket k, `rdp_lat` early in bucket k+1, in order, gap < 2h.
  A real attack the SLIDING+ordered reference catches but the TUMBLING emitted query misses. (the miss rate)
- **WRONG_ORDER** (N): `rdp_lat` then `ps_exec`, same bucket. NOT the attack pattern; the ordered reference
  rejects it, the unordered emitted query flags it. (the over-fire)
- **BENIGN_SINGLE** (N): only `ps_exec` OR only `rdp_lat`. Neither fires (dc=1). Negative control.
- **BENIGN_FARAPART** (N): both events same host but > 2h apart. Neither fires. Window-present control.

Ground truth = TRUE_INBUCKET ∪ TRUE_STRADDLE are the real exec→lateral attacks; all others are negatives.

## Scoring

Run the **verbatim emitted PPL** against OpenSearch 3.7.0; flagged hosts vs the planted truth. Report:
recall (→ the miss rate = 1 − recall on the straddle set), precision (→ over-fire from WRONG_ORDER),
and the breakdown by population. Contrast against the sliding+ordered Python reference (recall/precision 1.0).
Tier B, single host, synthetic, one chain shape, OpenSearch 3.7.0 + pySigma OpenSearchPPLBackend
(version-bound). The transferable finding is the **mechanism** (dropped order → over-fire; tumbling window →
boundary miss), not the specific rate (rate tracks the planted straddle:inbucket ratio — disclosed).

## What it does to H-SIGMA-01 (pre-committed reading)

If H1+H2 hold: the second correlation type is now EXECUTED (not just compiled), and the dangerous mode
(silent partial translation → runnable-but-wrong) is confirmed on a SECOND rule shape with BOTH failure
directions — over-fire (count rules, event_count 2026-06-15) AND miss (ordered-sequence, this leg). Lucene
refuses all correlation at compile (verified), so on a Lucene-family backend the same rules are a 100% miss
(nothing runs). This strengthens the execution-fidelity leg; it does NOT clear H-SIGMA-01's gate on its own
(still synthetic, single chain). Gate via karen → hypothesis-validator → contradiction-detector before any
confidence move.
