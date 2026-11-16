---
type: benchmark-results
title: "R1 post-hoc probe: are the two DETECTED rules case-fragile on DuckDB?"
created: 2026-11-16
status: post-hoc, not pre-registered, not independently verified
evidence_tier: B (deterministic, single machine)
---

# Probe: case variants against R1's two DETECTED rules (2026-11-16)

**Why.** R1 found that pySigma-backend-sqlite compiles Sigma `contains` to `LIKE '%…%'`, case-insensitive in SQLite
(ASCII only) and case-sensitive in DuckDB (`RESULTS.md` l.125-132), and applied that to the prompt-injection rule
only. A reviewer (Fable pass, 2026-11-16) reported that the T0049 rule is exposed too; this probe checks it.

**Method.** `probe_detected_rules_case_2026_11_16.py` compiles `rules/T0049_sqli_union.yml` and
`rules/T0050_python_exec_b64.yml` the way `run_planted.py` does (`compile_rule`, `single_sql`) and runs each on SQLite
and DuckDB over a small table of case variants of a matching value plus one benign value. Versions: pySigma 2.0.3,
pySigma-backend-sqlite 2.1.1, DuckDB 1.5.3 (R1's pins), SQLite 3.45.1, Python 3.12.3. Raw output
`results/probe-detected-rules-case-2026-11-16.json`, sha256
`e2e6ca5adae397892eec7aa845887491d8ea699188d6270d5ba4e681e815901a`, identical across two runs. R1's corpus, rules and
results are untouched.

## Result

| Rule | Compiled predicate | SQLite | DuckDB |
| --- | --- | --- | --- |
| T0049 (`contains\|all: UNION, SELECT, --`) | three `LIKE '%…%'` terms | upper (as planted), lower, mixed | upper only |
| T0050 (`contains\|all: ' -c ', exec(, b64decode`) | three `LIKE '%…%'` terms | as planted, `B64DECODE` | as planted only |

- T0049 reproduces the reviewer's report: on DuckDB, R1's pre-registered engine, a lower-case or mixed-case
  `union select` injection goes unmatched, while SQLite matches it. SQL keywords are case-insensitive, so the
  lower-case form is an ordinary attacker choice. R1's DETECTED state stands for the corpus as planted (upper case).
- T0050's DuckDB miss is on an upper-case `B64DECODE`, which Python would reject at runtime (identifiers are
  case-sensitive), so it is not a working evasion and is recorded only for completeness.

## Limits

One table per rule, synthetic values, single machine; this tests the compiled predicate, not R1's planted states.
