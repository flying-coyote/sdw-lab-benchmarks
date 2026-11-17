---
type: evidence
title: "Deterministic Validator vs LLM Grounding — Schema-Constrained OCSF Mapper Results"
created: 2026-06-05
tags: [ocsf-mapping, deterministic-mapper, llm-grounding, silent-errors, schema-constraint, tier-b]
---

# Deterministic validator vs LLM grounding (results)

**Tier B.** A schema-constrained deterministic source→OCSF mapper (generic field-name alias rules, only
ever emitting a path that exists in OCSF 1.8.0) vs BENCH-B's LLM under five grounding conditions, on the
same 141-mapping gold key and the same scoring.

| mapper | silent-error rate | path-correct |
|---|---|---|
| deterministic (schema-constrained) | 0.00 | 0.16 |
| phi3 / formal | 0.72 | 0.01 |
| phi3 / none | 0.99 | 0.00 |
| phi3 / schema | 0.69 | 0.01 |
| phi3 / skill | 0.60 | 0.04 |
| phi3 / wrong_grounding | 0.72 | 0.01 |

- Deterministic coverage (fields it maps rather than marking unmapped): **0.67**
- Path-correct *among the fields it maps*: **0.24**

## Reading

The deterministic mapper's silent-error rate is **0 by construction** — it picks targets only from the
OCSF 1.8.0 schema, so it can map a field correctly, map it wrong-but-valid, or mark it unmapped, but it
can never invent a path that doesn't exist. The LLM, by contrast, invents non-existent paths 60–99% of
the time depending on grounding. That is the "harness not the model" point made concrete: constraining
the output to the schema eliminates the security-relevant failure (a mapping that validates and ships and
is wrong) outright, where prompting alone never does. The honest trade is coverage and content: the
generic alias mapper only attempts the common fields (the rest go unmapped rather than guessed), and its
overall path-correctness is modest — but on the fields it does map it is at least as accurate as the weak
model, with none of the invented paths. The lesson isn't "rules beat models"; it's that the *schema-
constraint in the harness* is doing the safety work, and a model is only safe to use behind the same
constraint. Tier B; the alias table is generic (not tuned to the gold), so this is a fair schema-
constrained baseline, not an upper bound on what a tuned deterministic mapper could cover.

*(corrected 2026-11-17: two readings above are narrower than written. First, the 0.00 silent error is a
property of the constraint, so it could not have come out otherwise, and the comparison it supports is
safety, not accuracy. Second, "fair" overstates the alias baseline: `run.py` matches substrings, and a
whole-token re-run of the same rules maps 43 fields with 18 correct
(`alias-whole-token-check-2026-11-16.json`). The frontier leg has since run as a post-hoc re-score,
`RESULTS-FRONTIER-CONSTRAINED-2026-11-16.md`: behind a full-schema reject wall the June frontier-proxy
predictions keep 57 to 66% path-correctness at zero silent error, against 0.16 here, so "the harness, not
the model" holds for the safety property and not for correctness above the phi3 tier. `run.py`
regenerates this file and would drop this note; the same correction is in `../README.md`.)*
