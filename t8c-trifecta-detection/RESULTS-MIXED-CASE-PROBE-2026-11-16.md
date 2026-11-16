---
type: benchmark-results
title: "T8c post-hoc probe: are the trifecta rules case-fragile across SQLite and DuckDB?"
created: 2026-11-16
status: post-hoc, not pre-registered, not independently verified
evidence_tier: B (deterministic, single machine)
---

# Mixed-case probe of the T8c rules (2026-11-16)

**Why.** R1 (`../atlas-ocsf-observables/RESULTS.md` l.125-132, 2026-11-09) found that pySigma-backend-sqlite
compiles Sigma `contains` to `LIKE '%…%'`, which SQLite evaluates case-insensitively (ASCII only) and DuckDB
case-sensitively, and the 2026-11-16 check on the `ocsf-attack-coverage` rules
(`../ocsf-attack-coverage/RESULTS-MIXED-CASE-2026-11-16.md`) reproduced it on that bench's one `contains` rule. T8c's
H5 reports identical matched sets on both engines for every rule both could run (`RESULTS.md`, Hypotheses), but its
corpus plants every value in the rule's own case, so the exposure could not show there. This probe is that test.
Post-hoc, not pre-registered; T8c's committed corpus, rules, `run.py` and results are untouched (`run.py` is imported
read-only for `compile_yaml`, `to_api`, `LEGS_CTE`, `QUAL_CTE`, `session_sql` and `SESSION_SQL`).

**Method.** Same as the `ocsf-attack-coverage` check, extended to rule level. `mixed_case_probe_2026_11_16.py`:

- compiles each tier (a) Sigma rule (a1 to a6) exactly as `run.py` l.164 does (`compile_yaml`, `to_api`,
  `SELECT metadata_uid`) and runs it on stdlib SQLite and DuckDB over a small `api` table holding the rule's matching
  value in its original case, lower, upper and one alternating mixed case, plus a non-matching row, with every other
  column the rule tests held at a matching value;
- runs the hand-SQL leg classifier (`LEGS_CTE`, `run.py` l.30-39) and the leg-3 content qualifier (`QUAL_CTE`,
  l.41-47) that the session rules share, over the same kind of table, covering all four of their `LIKE` predicates
  (the three leg-2 paths and the `api03-` qualifier);
- for the credential string, adds a `token-upper` variant that upper-cases only the constant `api03-` prefix the
  predicates match on and leaves the case-significant key body as planted;
- at rule level, builds one three-leg session per variant (`mail.fetch`, then a `file.read` of the sensitive path,
  then a `web.fetch` to an off-allowlist host carrying the credential string, 60 s apart, no delegation parent) and
  runs the four hand-SQL session rules from `run.SESSION_SQL` (b3, b4, c1, c2) on both engines, once varying the
  path with the credential as planted and once varying the credential with the path as planted;
- as a candidate fix, not part of T8c, rebuilds b4 and c2 through `run.session_sql` from copies of `LEGS_CTE` and
  `QUAL_CTE` with each of their four `LIKE`s wrapped in `lower()` (SQLite has no `ILIKE`; `lower()` runs on both
  engines), runs them over the same planted sessions, and restores the module constants afterwards.

The three pySigma correlation rules (a7, b1, b2) are out of scope, since they do not execute on DuckDB at all
(`RESULTS.md`, parser error on `end`).

**Versions, pinned to the original run.** A fresh venv built from T8c's `requirements.txt`, unchanged since the run's
commit; `pip freeze` in that venv matches `requirements.txt` exactly (all 17 pins, including pySigma 2.0.3,
pySigma-backend-sqlite 2.1.1 and DuckDB 1.5.3), with SQLite 3.45.1 and Python 3.12.3, the same versions
`coverage.json` and `VERIFICATION.md` l.154-156 record for the 2026-11-10 run. Output
`results/mixed-case-probe-2026-11-16.json` (versions block included), sha256
`e302999d4dd4b5b963269e7cd66e1c647b0cbc10257a616b1f6b1d2a8c03c920`, identical across two runs.

## Result

Single-step Sigma rules, which variants each engine matched:

| Rule | Predicate under test | SQLite | DuckDB |
| --- | --- | --- | --- |
| a1, a2, a3 (`api_operation` equality) | `api_operation='mail.fetch'` and similar | original (= lower) only | original (= lower) only |
| a4 `/proc/self/environ` read | `api_request_data LIKE '%/proc/self/environ%'` | original, lower, upper, mixed | original (= lower) only |
| a5 off-allowlist, allowlisted host `github.com` | `NOT dst_endpoint_hostname IN (…)` | fires on upper and mixed | fires on upper and mixed |
| a5 off-allowlist, off-list host | same | fires on every case | fires on every case |
| a6 credential shape | `api_request_data LIKE '%api03-%'` | every variant, including token-upper | original and lower only |

(The a5 "non-match" row holds the off-allowlist hostname `benign-value`, so a5 fires on it on both engines by design.)

Hand-SQL components shared by b3, b4, c1 and c2:

| Component | SQLite | DuckDB |
| --- | --- | --- |
| leg 2, `file.read` of `/proc/self/environ` | every case variant | original (= lower) only |
| leg 2, `file.read` of `/app/.env` | every case variant | original (= lower) only |
| leg 2, `file.read` of `/srv/app/credentials.json` | every case variant | original (= lower) only |
| leg 3, allowlisted host in another case | counted as off-allowlist on upper and mixed | same |
| leg-3 qualifier, de-prefixed credential string | every variant, including token-upper | original and lower only |

Session rules, one planted three-leg session per variant:

| Sweep | Rule | SQLite fires on | DuckDB fires on |
| --- | --- | --- | --- |
| vary the leg-2 path | b3, b4, c1, c2 | every variant | original (= lower) only |
| vary the credential | b3, c1 (unqualified) | every variant | every variant |
| vary the credential | b4, c2 (content-qualified) | every variant, including token-upper | original and lower only |

- Every `LIKE` that both engines run in T8c, two Sigma rules (a4, a6) and all four hand-SQL predicates, diverges by
  engine on case variants (SQLite matches every variant; DuckDB matches only those where the matched substring keeps
  its original case, so the original and, for values already lower-case in the matched part, the lower variant), which
  is R1's mechanism again, and the divergence carries through to the session rules. The seventh Sigma rule, a7, is a
  correlation rule that does not run on DuckDB. So T8c's "identical sets on
  both engines" holds for values in the rules' own case, as the corpus planted them, and does not hold for upper- or
  mixed-case values.
- The result that matters most for the essay: **c2, the only rule DETECTED on all four strata in T8c, misses on DuckDB
  when only the `api03-` prefix is upper-cased** and the key body is left intact (`token-upper`), while SQLite still
  fires. The prefix is a constant, so an attacker who removes `sk-ant-` to get past a secret scanner can upper-case
  `api03-` just as cheaply and restore it on receipt. That is a recoverable evasion of the credential qualifier on
  DuckDB, unless the leg-3 burst path qualifies the session instead (no burst was planted here).
  b4 behaves the same way. On SQLite this variant is caught.
- Upper-casing the whole value is a different matter. On Linux, where the CS0067 case ran, `/PROC/SELF/ENVIRON` is not
  the same file, and upper-casing the whole key destroys its case-significant body, so those variants are not working
  evasions there. On a case-insensitive filesystem (the macOS default, Windows) a `.ENV` or `CREDENTIALS.JSON` read
  reaches the same file, so the leg-2 path checks would differ by engine for an agent running there; that platform
  point is inference, not measured here.
- The equality predicates (`api_operation`, the allowlist) agree across engines and are case-sensitive on both, so
  they depart from Sigma's case-insensitive default everywhere, as the `ocsf-attack-coverage` check found. For the
  allowlist that fails toward noise, since `GitHub.com` counts as off-allowlist on both engines.

Candidate fix (not part of T8c), the same planted sessions:

| Sweep | Rule, every `LIKE` wrapped in `lower()` | SQLite fires on | DuckDB fires on |
| --- | --- | --- | --- |
| vary the leg-2 path | b4, c2 | every variant | every variant |
| vary the credential | b4, c2 | every variant, including token-upper | every variant, including token-upper |

- With `lower()` on the content side the two engines agree on every variant and the token-upper evasion is caught on
  both. This is a predicate-level check on hand-built sessions; the patched rules were not re-scored against T8c's
  corpus, so their precision there is untested, and a lower-cased match will also fire on case variants that are not
  the same file on Linux, which errs toward noise.

## Limits

Small hand-built tables, synthetic fixture values, single machine, ASCII only. This tests the compiled predicates and
the session rules on one planted session per variant, not T8c's corpus or its DETECTED / NOISY / MISSED states, which
stand as committed for the values the corpus plants. Other transformations an attacker would use against a content
rule (dropping the `api03-` prefix too, base64, reversal, splitting across calls) would defeat the qualifier on both
engines and are not tested here.
