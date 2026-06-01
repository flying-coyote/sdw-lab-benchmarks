# Results — OCSF flattening-fidelity benchmark (C2)

- DuckDB: `1.5.3`  
- Master seed: `20260601`  
- Determinism (re-run is byte-identical): **True**  
- Evidence tier: B (reproducible, first-party, controlled synthetic corpus; NOT a production claim)

All corpora are synthetic and generated deterministically. These are controlled measurements of a mechanism, not production telemetry.

## 1. Absence-vs-NULL collapse → silent detection miss

CloudTrail encodes "no MFA" as the *absence* of `mfaAuthenticated`. Flattening lowers that to a column where absent becomes NULL, so the naive translation `WHERE mfa = 'false'` matches nothing. Planted positives = privilege-escalation calls made without MFA.

| corpus events | planted positives | naive-flat recall | NULL-aware-flat recall | preserved-JSON recall | naive silent-miss rate |
|--:|--:|--:|--:|--:|--:|
| 1,000 | 141 | 0.00 | 1.00 | 1.00 | 100% |
| 10,000 | 1392 | 0.00 | 1.00 | 1.00 | 100% |
| 100,000 | 14140 | 0.00 | 1.00 | 1.00 | 100% |

The naive flattened query recovers none of the planted positives; the preserved schema and the NULL-aware flattened query recover all of them. The miss is structural, not probabilistic — absence and NULL are the same byte once flattened.

## 2. Grain loss → adversary timing query destroyed, routine query exact

Beacons (regular 60s) and benign decoys (bursty, same per-bucket count and same 43-byte payload) are separable only on inter-arrival jitter. Atomic grain keeps the timestamps; a (src, dst, 5-min) rollup does not.

| beacons | decoys | rows | atomic F1 | coarse F1 | adversary F1 loss | routine exact? | headline (adv − routine) |
|--:|--:|--:|--:|--:|--:|:--:|--:|
| 8 | 16 | 2,315 | 1.00 | 0.50 | 0.50 | yes | 0.50 |
| 16 | 32 | 4,671 | 1.00 | 0.50 | 0.50 | yes | 0.50 |

The rollup answers the volumetric routine queries exactly (bytes-per-host and pair-counts match to the row) while the beacon hunt loses precision because the discriminating feature — timing regularity — no longer exists in the schema.

## 3. Floating timestamps → cross-zone correlation silently lost

Cross-source chains truly within a 5-minute window in UTC, with sources in real timezones. The floating store drops the offset and compares local wall-clocks as if co-zoned.

| chains | cross-zone | UTC correlation recall | floating correlation recall |
|--:|--:|--:|--:|
| 200 | 108 | 1.00 | 0.46 |
| 1,000 | 501 | 1.00 | 0.50 |

UTC normalization correlates every planted chain; the floating store loses exactly the cross-zone chains, whose events scatter hours apart once the offset is gone. The same-zone chains survive either way, which is why the failure is quiet — half the results still look right.

