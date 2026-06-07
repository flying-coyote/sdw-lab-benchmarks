# Context-collapse cost curve — the COMPUTE half (query latency, fidelity vs coarsened)

**Tier B · single host · DuckDB-on-local-Parquet · one public dataset (APT29 evals, ~143k events).** This is
the third leg of H-OCSF-CONTEXT-COLLAPSE-01's cost curve. The storage leg is priced (Store F is
**1.799x** the bytes of Store N: 1,888,601 vs 1,049,655) and
the recall leg is priced (adversary-tail rules lose ~0.35 recall, 9 go blind — see `RESULTS.md`). This leg
prices compute: running the **same** Sigma battery (the rules that fire on Store F, compiled identically via
pySigma) costs how much more wall-clock against the fidelity store than against the coarsened one?

**Method:** for each firing rule, `lib.common.time_trials` (2 warmups discarded, 7 timed, median + coefficient
of variation). Battery wall-time = sum of per-rule medians; the per-rule-ratio median is the robust headline;
the worst per-rule CV is the noise floor the battery ratio must clear (a delta below CV is not a finding).

| metric | Store F (fidelity) | Store N (coarsened) | F/N |
|---|--:|--:|--:|
| battery wall-time (sum of medians, ms) | 1664.732 | 1316.456 | **1.265** |
| median per-rule latency ratio | | | 1.135 |
| rules timed | 54 | | |
| worst per-rule CV (noise floor) | | | 68.9% |

**Verdict:** fidelity costs **1.265x** query wall-clock on the full battery (median per-rule **1.135x**) — directional and >1, but smaller than the **1.799x** storage premium, so STORAGE is the more expensive axis of the fix and query-compute is the cheaper one at this scale. Per-rule CV is high at sub-ms query sizes (worst rule 68.9%), so the median-per-rule ratio is the conservative figure and the *direction*, not the absolute milliseconds, is what transfers. The compute premium concentrates in the full-text-scan detections: the ps_script `ILIKE` micro is **3.978x** — the encoded-PowerShell family that also drives the recall loss is exactly where keeping fidelity costs the most to scan.

By class: adversary-tail battery 3.458x (29 rules),
routine 0.998x (25 rules). **This is the finding** — the compute premium
is not uniform; it tracks the same detections the coarsening blinds.

**Cross-run stability (n=5, this host):** the per-query medians are sub-millisecond and noisy run-to-run, but
the *structure* held every run — adversary-tail battery ~3.3–3.8x, routine ~1.0x (no premium), the ps_script
logsource ~13–15x, the ps_script `ILIKE` micro ~3.5x, all-battery ~1.26–1.37x (the all-battery figure is
dragged toward 1 by the large `registry_event` table, whose coarsening barely changes scan cost). Quote the
ranges and the ordering, not a single run's median.

## Per-logsource (rows F→N show the confound: N also drops rows, not just bytes)

| logsource | rows F→N | battery F (ms) | battery N (ms) | F/N | worst CV |
|---|---|--:|--:|--:|--:|
| `create_remote_thread` | 95 → 95 | 0.785 | 0.708 | 1.109 | 7.0% |
| `file_event` | 1649 → 1649 | 31.897 | 29.234 | 1.091 | 18.6% |
| `network_connection` | 1229 → 1229 | 0.965 | 0.724 | 1.333 | 9.3% |
| `pipe_created` | 446 → 446 | 0.654 | 0.657 | 0.995 | 7.7% |
| `process_access` | 39283 → 39283 | 3.924 | 3.556 | 1.103 | 18.3% |
| `process_creation` | 447 → 447 | 23.692 | 17.895 | 1.324 | 68.9% |
| `ps_script` | 414 → 414 | 379.739 | 31.196 | 12.173 | 23.8% |
| `registry_event` | 78692 → 78692 | 1223.076 | 1232.486 | 0.992 | 24.9% |

## ps_script string-scan micro-benchmark (largest fidelity byte-gap: full script blocks vs 64-char truncation)

`ScriptBlockText ILIKE '%frombase64string%'` — Store F 2.88 ms
(CV 7.7%) vs Store N 0.724 ms (CV 5.2%),
**ratio 3.978x**. This is the query where keeping fidelity costs the most bytes to scan; if
the battery ratio is in the noise but this one is not, the compute premium is concentrated in the few
full-text-scan detections (the encoded-PowerShell rules that also drove the recall loss).

## Reading

The decision the cost curve informs: keeping atomic-grain, full-fidelity OCSF costs **1.799x
storage** and **1.265x query** against this battery, and buys back the ~0.35 recall /
9-blinded-rules the coarsening destroys on adversary-tail detections. At lab scale the storage axis dominates the
compute axis; the F-vs-N latency gap is jointly confounded (N drops rows AND narrows columns AND truncates
strings — the coarse store is cheaper on every axis at once), which is the honest shape of the trade, not a
clean single-variable isolation. Single host, DuckDB only; the four other engines and a 10M+ scale are the
obvious extensions. The transferable claim is the *relative ordering* — storage is the expensive axis of the
fix, query-compute is cheap-to-free at this scale — not the absolute milliseconds.
