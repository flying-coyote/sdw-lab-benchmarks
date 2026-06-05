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
