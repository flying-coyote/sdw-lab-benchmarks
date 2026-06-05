# Deterministic validator vs LLM grounding

Does a schema-constrained deterministic mapper beat the model at source→OCSF field mapping? BENCH-B ran
an LLM under five grounding conditions and saw silent-error rates (mapping to a non-existent OCSF path)
of 0.60–0.99. This builds the alternative the Fleak/ZephFlow "harness not the model" posture implies: a
deterministic mapper using generic field-name alias rules that **only ever emits a path that exists in
OCSF 1.8.0** (or marks the field unmapped), scored on the same gold key.

## Result (Tier B)

The deterministic mapper's silent-error rate is **0.00 — by construction** (it can't invent a path),
versus the LLM's 0.60 (best) to 0.99. And its overall path-correctness is **0.16**, higher than even the
LLM's best condition (0.04), with coverage 0.67 (it maps the common fields and marks the rest unmapped
rather than guessing). The lesson isn't "rules beat models" — it's that the **schema constraint in the
harness** does the safety work, and a model is only safe behind the same constraint. Full numbers in
[results/RESULTS.md](results/RESULTS.md).

### The model behind the constraint (`llm_behind_constraint.py`)

The maturity step the first pass promised: put phi3 *behind* the same schema constraint and see whether
the model then adds value. It does not, on this task. Constrained two ways — reject an invalid path to
unmapped, or snap it to the nearest valid path — phi3's silent-error rate goes to **0.00** (the
constraint makes it safe), but its path-correctness is **0.01–0.02** at coverage 0.31–0.65, versus the
deterministic alias mapper's **0.16** at coverage 0.67. So behind the same harness the weak model is
~8× *worse* than simple alias rules: the constraint provides the safety, and for field-mapping a
deterministic mapper out-covers a sub-frontier model. Whether a frontier model behind the constraint adds
coverage the alias rules miss is the open question (the frontier leg). This sharpens the conclusion — the
value is in the harness, not the model, at least at this capability tier.

## Run it

```bash
# reuses BENCH-B's gold key + OCSF-1.8.0 closure + committed phi3 numbers
python ocsf-deterministic-mapper/run.py
```

The alias table is generic (common field-naming, not tuned to the gold), so this is a fair
schema-constrained baseline, not an upper bound on a tuned deterministic mapper. Tier B. Complements
BENCH-B (ocsf-mapping-oracle) — same task, the harness side of the comparison.
