---
type: benchmark-results
title: "T8c post-hoc: credential-prefix case change on a mixed-case key body and on the bench's own corpus"
created: 2026-11-16
status: post-hoc, not pre-registered; one external reproduction (Fable review, seed 20261109), not otherwise verified
evidence_tier: B (deterministic, single machine)
---

# Corpus-level case check of the T8c session rules (2026-11-16)

**Why.** `RESULTS-MIXED-CASE-PROBE-2026-11-16.md` found that c2 and b4 miss an upper-cased `api03-` prefix on DuckDB.
An external review (Fable, 2026-11-16) found two gaps in that probe. First, the bench's fixture key body
(`gen_corpus.py` l.22, `"api03-" + "TESTFIXTURE0" * 3 + "0000"`) is all upper-case, so the probe's `upper` and
`token-upper` variants were the same string, and "prefix only, body intact" was never separated from "whole value".
Second, the result was predicate-level only. This file closes both gaps, using the recipe the reviewer gave. It is
post-hoc and not pre-registered. T8c's committed corpus, rules, `run.py`, results and the earlier probe are untouched;
`run.py` and `gen_corpus.py` are imported read-only.

**Method.** `corpus_case_check_2026_11_16.py`:

- **Part A, mixed-case key body.** Uses a synthetic fixture whose body mixes case (`aB3xY_z9Q-kLmN0pQrStUvWx7Zq`). It
  builds three-leg sessions (`mail.fetch`, a `file.read` of `/proc/self/environ`, a `web.fetch` carrying the
  credential to an off-allowlist host), each run directly and as a two-hop delegation (legs 2 and 3 in a child
  session), for five variants: as planted, `API03-` with the body intact, `Api03-`, the whole value upper-cased, and
  the prefix dropped. It adds one direct session with `API03-` plus a 24-call burst to one off-allowlist host. It runs
  b3, b4, c1 and c2 (`run.SESSION_SQL`) and b4 and c2 with each of the four hand-SQL `LIKE`s wrapped in `lower()` on
  both engines.
- **Part B, corpus.** For seeds 20261109, 20261110 and 20261111 at 2,000 sessions, it regenerates T8c's corpus in
  memory with `gen_corpus.gen` and scores the same six session rules with `run.score` against the 20 chain roots, per
  stratum, on both engines. It does this twice: as planted, and with `api03-` replaced by `API03-` in the planted
  leg-3 `web.fetch` rows, which are the CS0067-shaped chains (10 rows per seed). It also counts a6 single-step
  matches.
- **Schema check skipped.** `gen_corpus.validate_columns()` is skipped, because the OCSF 1.9.0 class JSON it reads
  (`../atlas-ocsf-observables/sources/ocsf-1.9.0/classes/api_activity.json`) is gitignored and not on disk. As a
  substitute, the as-planted scores were compared with `results/coverage.json`: for b3, b4, c1 and c2 on every seed,
  precision, recall and FP equal the committed values.

**Versions, pinned to the original run.** The venv was built from `requirements.txt`, and `pip freeze` matches all
17 pins: pySigma 2.0.3, pySigma-backend-sqlite 2.1.1, DuckDB 1.5.3, with SQLite 3.45.1 and Python 3.12.3. Output is
`results/corpus-case-check-2026-11-16.json` (versions block included), sha256
`928f69535e6f028d9b72d12404f4e82076c51704bdb0d99affda48750c02a663`, identical across two full runs.
Wall time was about 8 minutes per run, nearly all of it corpus generation.

## Part A: mixed-case key body (which sessions fire)

| Variant | c2 SQLite | c2 DuckDB | c2 with `lower()`, both engines |
| --- | --- | --- | --- |
| as planted, direct and delegated | fires | fires | fires |
| `API03-` + body intact, direct and delegated | fires | **does not fire** | fires |
| `Api03-` (title case), direct and delegated | fires | **does not fire** | fires |
| whole value upper-cased, direct and delegated | fires | does not fire | fires |
| prefix dropped, direct and delegated | does not fire | does not fire | does not fire |
| `API03-` + 24-call burst, direct | fires | fires (burst qualifier) | fires |

b4 behaves the same as c2 on the direct sessions. On the delegated sessions it does not fire for any variant on
either engine, because it does not walk delegation. b3 and c1 are unaffected by the credential string.

## Part B: the T8c corpus, three seeds

| Rule | Corpus | Engine | State (each seed) | Precision | Recall (each seed) | Recall by stratum (each seed) |
| --- | --- | --- | --- | --- | --- | --- |
| c2 | as planted | both | DETECTED | 1.0 | 1.0 | 1.0 on all four |
| c2 | prefix upper | SQLite | DETECTED | 1.0 | 1.0 | 1.0 on all four |
| c2 | prefix upper | DuckDB | **DETECTED** | 1.0 | **0.5** | CS0066 direct and delegated 1.0; **CS0067 direct and delegated 0.0** |
| b4 | prefix upper | DuckDB | DETECTED | 1.0 | 0.25 | CS0066-direct 1.0, CS0067-direct 0.0 |
| c2 with `lower()` | either corpus | both | DETECTED | 1.0, 0 FP | 1.0 | 1.0 on all four |
| b4 with `lower()` | either corpus | both | DETECTED | 1.0, 0 FP | 0.5 (unchanged) | direct strata 1.0 |
| b3, c1 | either corpus | both | NOISY | unchanged from `coverage.json` | unchanged | unchanged |

a6 single-step matches with the prefix upper-cased: 20 on SQLite and 10 on DuckDB on every seed (20 on both as
planted).

## Reading

- Upper-casing only the constant prefix, with the case-significant key body intact, takes a session out of c2's reach
  on DuckDB, directly and through delegation. SQLite still catches it. Title case does the same. An attacker can
  reverse either change on receipt, so this is a recoverable evasion of the credential qualifier on an engine whose
  `LIKE` is case-sensitive.
- The effect is scoped to the credential-qualified chains. On the corpus, c2 on DuckDB keeps every CS0066-shaped
  chain, which qualify through the burst, and loses every CS0067-shaped chain. Recall falls from 1.0 to 0.5 on all
  three seeds.
- The state label hides the loss. T8c's state is gated on precision (`run.py` l.92-97), so c2 stays DETECTED at
  precision 1.0 while half the planted chains go unseen.
- `lower()` on the four content matches restores recall 1.0 on both engines, with precision 1.0 and 0 false positives
  on the benign corpus on all three seeds. This closes the "not re-scored against benign sessions" gap the earlier
  probe left open.
- Dropping the prefix defeats c2 on both engines with or without `lower()`. That is the content-qualifier limit
  `RESULTS.md` already names, and it has nothing to do with case.

## Limits

- Post-hoc.
- One machine, synthetic corpus, ASCII only.
- The corpus mutation touches only the planted rows. It does not add case variants to benign sessions, so the
  `lower()` precision result says nothing about benign traffic that happens to carry an upper-case `API03-`.
- The schema-path validation was skipped, as stated above.
- The reviewer reproduced the seed-20261109 part B rows and the part A pattern independently (scratch scripts, not
  committed). Nothing else has been re-run by a second party.

Second run (2026-11-16, same venv): sha256 `928f69535e6f028d9b72d12404f4e82076c51704bdb0d99affda48750c02a663`, identical to the first.
