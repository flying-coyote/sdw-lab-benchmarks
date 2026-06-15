# UEBA + rare-value on PLANTED ground truth — detection correctness + answer-equality (2026-06-15)

The 2026-06-15 SOC-shape bench (`RESULTS-ueba-rare-2026-06-15.md`) measured the UEBA two-level-agg and
rare-value shapes' latency/ranking on `soc.conn`, but both detections returned **0 rows** (the corpus has
no volume-spike hosts and no single-source dests), so detection-correctness and cross-engine
answer-equality were UNVALIDATED — the H-ARCH-02 evidence file flags this explicitly ("the empty-set
answer-equal must not be cited as cross-engine correctness"). This leg plants ground truth and closes that
gap. `gen_ueba_corpus.py` builds `soc.conn_ueba_planted` (868,790 rows): 3,000 NORMAL low-steady hosts,
**15 SPIKE hosts** (baseline + one 7× spike hour → Z≈4.8, ground truth), **60 high-steady decoys**
(~100/h, low variance → Z≈1.6, must NOT flag), and **15 rare destinations** each contacted by exactly one
source (ground truth). `ueba_planted_bench.py` scores precision/recall vs the plant and cross-engine
set-equality. Tier B, single host, synthetic.

## Result (all four Iceberg engines, 5 trials)

| engine | UEBA P | UEBA R | UEBA (tp/fp) | rare P | rare R | rare (tp/fp) | ueba s | rare s |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| ClickHouse-Iceberg | 0.75 | **1.0** | 15/5 | **1.0** | **1.0** | 15/0 | 0.068 | 0.061 |
| StarRocks | 0.75 | **1.0** | 15/5 | **1.0** | **1.0** | 15/0 | 0.087 | 0.084 |
| Trino | 0.75 | **1.0** | 15/5 | **1.0** | **1.0** | 15/0 | 0.294 | 0.280 |
| Dremio | 0.75 | **1.0** | 15/5 | **1.0** | **1.0** | 15/0 | 0.505 | 0.374 |

**Detection is correct and engine-portable.** Every engine catches all 15 planted spike hosts (UEBA
recall 1.0) and all 15 single-source rare dests (recall 1.0, precision 1.0). The UEBA precision 0.75 is
**5 false positives that are all NORMAL hosts** whose random per-hour jitter happened to clear Z>3 (genuine
statistical outliers in the synthetic baseline + the Z>3 threshold, not a detection error) — **zero of the
60 high-steady decoys leaked**, so the Z-score correctly flags *anomaly-relative-to-own-baseline*, not
heavy talkers (the decoy test the shape is built to pass). The five FPs are the *same five hosts* on every
engine.

**Cross-engine answer-equality CONFIRMED on planted truth.** All four engines return the **identical
flagged set** for UEBA (the same 20 hosts: 15 spikes + the same 5 chance-FPs) and for rare_dest (the same
15 dests) — `ueba_answer_equal_set = true`, `rare_answer_equal_set = true`. This is the cross-engine
correctness datapoint the empty-set run could not provide. (Scored on the entity SET, not the float-laden
rows: avg/stddev format differently per engine, so set-equality is the meaningful agreement check.)

## What it does to the hypothesis — and the honest qualification of the inversion

This closes the H-ARCH-02 UEBA/rare evidence gap: the two-level-agg and high-card count-DISTINCT shapes
now have **measured detection correctness (recall 1.0) and confirmed four-engine answer-equality on planted
ground truth**, replacing "0-row, correctness UNVALIDATED."

But the **StarRocks-overtakes-ClickHouse UEBA inversion does NOT reproduce here**: on this 868k corpus
ClickHouse wins UEBA (0.068 s) over StarRocks (0.087 s) — the ranking is ClickHouse < StarRocks < Trino <
Dremio for *both* shapes, the same as the flat baseline, no inversion. The inversion was measured at
**10.3M** rows on `soc.conn`; this corpus is both **smaller (868k) and a different distribution** (3,000
hosts + planted anomalies vs the flagship's flow mix), so the two differ on scale AND shape and the
non-reproduction can't be cleanly attributed to either alone. The honest read: the inversion is
**scale/corpus-specific to the 10.3M soc.conn run, not a general "StarRocks wins UEBA" property** — it
stands as measured at its scope, and this leg says it does not generalize down to 868k on a different
corpus. (Detection correctness, by contrast, is identical across both — the engines agree on the answer.)

## Caveats (Tier B)

- Single host, one synthetic corpus, one coarsening of "anomaly." The 5 UEBA chance-FPs are a property of
  the synthetic noise + threshold, not a detection defect; a real estate's FP rate depends on baseline
  variance and the Z cutoff.
- The latency numbers are this-corpus-only (868k) and are NOT comparable to the 10.3M soc.conn draw; the
  inversion is neither re-confirmed nor refuted at 10.3M here — it is shown not to generalize to 868k.
- Spike Z (~4.8) and decoy Z (~1.6) are planted well clear of the 3.0 threshold so the flagged set is
  robust to cross-engine float differences — which is *why* answer-equality holds; a borderline planting
  would test float-portability harder (a separate question).
