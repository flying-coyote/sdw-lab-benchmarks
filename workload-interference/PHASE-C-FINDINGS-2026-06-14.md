# Phase C — knee 3x reproduction + starrocks_mv (P5) — 2026-06-14

Tier B, single host (Beelink 5800H, WSL2 48 GB/14t, cpuset 12/2). A knee is claimable only when all 3 independent runs trip the mechanical stop rule at the SAME ladder step (README). run-1 = extend-ladder; run-2 = phase-C rep3 (salvaged; reps 1-2 lost to a `docker run` missing `-i` so its heredoc capture never ran); run-3 = clean finish pass (host-side capture).

## clickhouse_iceberg

- knee per run [run1, run2, run3]: [64.0, 64.0, 64.0] — **knee reproduced 3× at U=64.0**

| step (U) | p95 min | p95 median | p95 max | n runs |
|--:|--:|--:|--:|--:|
| 16.0 | 0.159 s | 0.164 s | 0.168 s | 2 |
| 32.0 | 0.16 s | 0.176 s | 0.193 s | 2 |
| 64.0 | 1.164 s | 2.698 s | 4.05 s | 3 |

## clickhouse_native

- knee per run [run1, run2, run3]: [64.0, 64.0, 64.0] — **knee reproduced 3× at U=64.0**

| step (U) | p95 min | p95 median | p95 max | n runs |
|--:|--:|--:|--:|--:|
| 16.0 | 0.066 s | 0.069 s | 0.072 s | 2 |
| 32.0 | 0.067 s | 0.083 s | 0.099 s | 2 |
| 64.0 | 3.11 s | 3.212 s | 3.473 s | 3 |

## starrocks

- knee per run [run1, run2, run3]: [64.0, 64.0, 64.0] — **knee reproduced 3× at U=64.0**

| step (U) | p95 min | p95 median | p95 max | n runs |
|--:|--:|--:|--:|--:|
| 16.0 | 0.1 s | 0.106 s | 0.111 s | 2 |
| 32.0 | 0.101 s | 0.106 s | 0.112 s | 2 |
| 64.0 | 3.249 s | 3.773 s | 4.93 s | 3 |

## dremio

- knee per run [run1, run2, run3]: [32.0, 32.0, 32.0] — **knee reproduced 3× at U=32.0**

| step (U) | p95 min | p95 median | p95 max | n runs |
|--:|--:|--:|--:|--:|
| 16.0 | 0.809 s | 0.901 s | 0.993 s | 2 |
| 32.0 | 4.353 s | 4.575 s | 4.798 s | 2 |
| 64.0 | 5.78 s | 5.83 s | 8.892 s | 3 |

## starrocks_mv (P5 — does the MV shift the knee right >=2 steps?)

- scored: True  · base starrocks knee U=64.0  · MV knee U=64.0  · shift: 0
- P5 (>=2 steps right): **False**
- p95 by step: {'16.0': 0.111, '32.0': 0.091, '64.0': 3.259, '128.0': 2.693}
