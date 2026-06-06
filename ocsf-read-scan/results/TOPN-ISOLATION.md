# Isolating R8's topn_src divergence — read path vs spill (T2.5)

**Tier B, single machine.** 100,000,000 rows of byte-identical Parquet (verified identical)
registered into an Iceberg table, a DuckLake table, and read directly via `read_parquet(glob)`, with the
topn_src 16.7M-group aggregate (16,733,960 distinct src_ip) run under a high memory cap
(fits in RAM, no spill) and a forced-spill low cap.

## topn_src median ms (CV) by arm × memory config

| memory config | Iceberg ext | DuckLake | read_parquet(glob) |
|---|---|---|---|
| high_cap_no_spill | 3435 (6%) | 3690 (4%) | 4050 (4%) |
| low_cap_forced_spill | 8152 (2%) | 7092 (2%) | 7999 (2%) |

- Iceberg/DuckLake at high cap (no spill): **0.93×** · at forced spill: **1.15×**
- Iceberg/read_parquet at high cap: 0.85× · DuckLake/read_parquet at high cap: 0.91×

## Reading

**No divergence reproduced at 100M.** Both caps sit at parity (high 0.93×, spill 1.15×) — R8's 1.30× did not reappear at this scale, consistent with it being a 1B-specific spill effect; the same-files read-neutrality claim holds at 100M. The `read_parquet(glob)` arm is the native-reader scan-path baseline; whichever extension matches
it is paying no read-path overhead. Tier B, single machine, hot/warm; the transferable finding is which of
the two candidate mechanisms (extension read path vs memory-cap spill) the gap isolates to.
