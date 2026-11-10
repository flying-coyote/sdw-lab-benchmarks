---
type: benchmark-results
title: "T8b results: instruction-shaped text in telemetry fields through an air-gapped local analyst agent"
created: 2026-11-09
area: T8b-telemetry-injection
---

# T8b results: planted instructions in OCSF-store fields, four renderings, two local models

**Pre-registration:** `PREREGISTRATION.md` sha256 `73a690b67e7939ed15a5b23863281bdfa809edd1a9df2d2fbae5040360be153b`,
frozen 2026-11-10T00:55:53Z (2026-11-09 19:55 local), frozen by agent before run; not owner-reviewed.

**Rig stamp (§7b):** Beelink, AMD Ryzen 7 5800H (14 threads visible to WSL2, 47 GiB), WSL2 kernel
6.6.87.2-microsoft-standard-WSL2, no GPU, Windows power plan not checked from inside the guest. Run date
2026-11-09/10 (local). Ollama 0.20.6 (system service, CPU); `gemma4:e4b` digest `c6eb396dbd5992bb` (8.0B,
Q4_K_M, thinking-capable, thinking disabled for this run); `phi4:latest` digest `ac896e5b8b34a1f4` (14.7B,
Q4_K_M). DuckDB 1.5.3, requests 2.34.2, pyarrow 23.0.1, Python 3.12.3. Clock: chrony; `chronyc tracking` read
0.58 s slow at the freeze and 0.00002 s fast ten minutes later (slewing finished). Every duration is
`time.perf_counter`. **Timings were taken under contention**: the process was capped to 4 threads
(`taskset -c 0-3`, `nice -n 10`, Ollama `num_thread 4`) while sibling lab benches ran on the same host
(1-minute load average 5 to 17 during the run), so absolute generation times are context, not a result.

**Tier:** B for the mechanism (first-party, one host, two small local models, a public corpus with a planted
benign fixture); the follow rates are small-N counts, not estimates of a population rate.

RESULTS BODY PENDING: the run is in progress; this file is replaced when `analyze.py` has run over the full grid.
