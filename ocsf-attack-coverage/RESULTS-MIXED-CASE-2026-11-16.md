---
type: benchmark-results
title: "ocsf-attack-coverage: mixed-case check of the four Sigma rules on SQLite and DuckDB"
created: 2026-11-16
status: post-hoc, not pre-registered, not independently verified
evidence_tier: B (deterministic, single machine)
---

# Mixed-case check of the four `ocsf-attack-coverage` rules (2026-11-16)

**Why.** R1 (`../atlas-ocsf-observables/RESULTS.md` l.125-132, 2026-11-09) found that pySigma-backend-sqlite
compiles Sigma `contains` to `LIKE '%…%'`, which SQLite evaluates case-insensitively and DuckDB case-sensitively,
and noted that this bench compiles with the same backend and executes in DuckDB (`run.py` l.40, l.88-89) but plants
values whose case matches its rules, so the exposure had never been tested here. This is that test. Post-hoc, not
pre-registered; the bench's committed corpus, rules, `run.py` and results are untouched.

**Method.** `mixed_case_check_2026_11_16.py` compiles each rule exactly as `run.py` does (SigmaCollection, then
`sqliteBackend().convert`, then `SELECT *` to `SELECT event_uid`) and runs it on SQLite and on DuckDB over a
five-row table: the rule's matching value in its original case, lower case, upper case and one alternating mixed
case, plus a non-matching row, with every other field the rule tests held at a matching value. Versions: pySigma
2.0.3, pySigma-backend-sqlite 2.1.1, DuckDB 1.5.3 (the R1 pins), SQLite 3.45.1, Python 3.12.3, in a scratch venv.
Output `results/mixed-case-check-2026-11-16.json`, sha256 `da94bd996f6eba3f8a017bb0f3a6b078bc63c4094a0f2c8cb5b0b2c94a7cce69`,
identical across two runs.

## Result

| Rule | Compiled predicate under test | SQLite matches | DuckDB matches |
| --- | --- | --- | --- |
| `encoded_powershell.yml` (T1059.001) | `cmd_line LIKE '%-EncodedCommand%'` | original, lower, upper, mixed | original only |
| `c2_domain.yml` (T1071) | `query_hostname='cdn-telemetry-sync.net'` | original (= lower) only | original (= lower) only |
| `nomfa_privesc.yml` (T1098) | `api_operation='AttachUserPolicy'` | original only | original only |
| `rdp_lateral.yml` (T1021) | `dst_port=3389` | original | original (integer, no case) |

- One of the four rules, the only one using `contains`, loses every case variant on DuckDB while SQLite keeps them,
  which is R1's mechanism reproduced on this bench's own rule. A mixed-case `-encodedcommand` on `WS1` would be
  MISSED in the bench's DuckDB pipeline and caught under SQLite.
- The two string-equality rules are case-sensitive on both engines, because the backend emits plain `=`. Sigma's
  default string matching is case-insensitive, so those rules diverge from Sigma semantics everywhere, not just on
  DuckDB; the engines agree with each other, which is why a cross-engine comparison would not surface it.
- The port rule is unaffected.

## Side finding

pySigma-backend-sqlite 2.1.1 emits `FROM logs`, while `run.py` l.89 replaces the placeholder `<TABLE_NAME>` that an
older backend emitted. `requirements.txt` leaves pySigma unpinned, so a fresh install of this bench today would
query a table named `logs` that the bench never creates and score every rule MISSED (`exec_error`). The check
script replaces both forms; `run.py` was not changed.

## Limits

Five planted rows per rule on a single machine; this tests the compiled predicate, not the bench's corpus or its
DETECTED/NOISY/MISSED states, which stand as committed for the values the corpus actually plants.
