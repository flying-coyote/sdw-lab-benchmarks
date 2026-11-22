# Deterministic validator vs LLM grounding

Does a schema-constrained deterministic mapper beat the model at source→OCSF field mapping? BENCH-B ran
an LLM under five grounding conditions and saw silent-error rates (mapping to a non-existent OCSF path)
of 0.60–0.99. This builds the alternative the Fleak/ZephFlow "harness not the model" posture implies: a
deterministic mapper using generic field-name alias rules that **only ever emits a path that exists in
OCSF 1.8.0** (or marks the field unmapped), scored on the same gold key.

## Result (Tier B)

The deterministic mapper's silent-error rate is **0.00 — by construction** (it can't invent a path, so the zero is a property of the constraint and not a measured outcome; it could not have come out otherwise),
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
deterministic mapper out-covers a sub-frontier model. *(corrected 2026-11-17: this paragraph used to
call the frontier leg an open question. It has since run as a post-hoc re-score with no new model
calls, [results/RESULTS-FRONTIER-CONSTRAINED-2026-11-16.md](results/RESULTS-FRONTIER-CONSTRAINED-2026-11-16.md):
the cached June frontier-proxy predictions (claude-opus-4-8, three runs of 705 prompts) put behind a
reject wall built from the full OCSF 1.8.0 schema keep 57 to 66% path-correctness across the three
runs, with run 3's suspect schema batch excluded, at coverage 0.85 to 0.91 and silent error 0, against
the alias mapper's 0.16 at coverage 0.67. So behind the same constraint the frontier proxy maps about
3.5 to 4 times as many fields correctly as the alias rules, and the reading "the value is in the harness,
not the model" holds for the safety property only: the constraint removes invented paths for any
model, while correctness still depends on the model above the phi3 tier. That file is one model
family, not pre-registered, and the gold-exposure question on run 3 is open.)*

The alias table is generic (common field-naming, not tuned to the gold), so this is a fair
schema-constrained baseline, not an upper bound on a tuned deterministic mapper. *(corrected
2026-11-17: nothing in the files suggests tuning to the gold, since the table gets 23 of 141 fields
exactly right and sends 71 of its 94 attempts to a valid non-gold path, 60 of which a single-author
adjudication grades wrong (`results/alias-wrong-but-valid-adjudicated-2026-11-16.csv`, Tier D). But
"fair" overstates it. `run.py` l.30 matches substrings of the whole field name, so `ts` fires on
`packets` and CrowdStrike's `event.` envelope sends 18 fields to `metadata.event_code`, and a
whole-token re-run of the same rules (`alias_whole_token_check_2026_11_16.py`,
`results/alias-whole-token-check-2026-11-16.json`) maps 43 fields with 18 correct (0.13 of 141, against
0.16), so stricter matching lowers path-correct and coverage and raises precision among mapped fields from
0.24 to 0.42; 17 of the 60 adjudicated-wrong mappings persist. The 0.16 is one crude table's score, with
about five hits owed to substring accidents, and nothing here shows what a tuned alias table would reach.
(Tail reworded 2026-11-22: it used to read as though cleaner matching would score higher.))* Tier B. Complements
BENCH-B (ocsf-mapping-oracle) — same task, the harness side of the comparison.

## Hypothesis mapping

Advances **H-CONCEPT-GRAPH-01** — schema constraint as the lever: the 0.00-by-construction
silent-error rate shows the safety comes from constraining outputs to paths that exist in the
schema, not from the model. *(ID recorded 2026-06-10 per the benchmark-alignment audit.)*

## What would have made it fail

The silent-error zero cannot fail: the mapper only emits paths from the schema closure, so it is a
property of the constraint. The measured parts are path-correctness and coverage against the
141-field gold key, and those can fail. The comparison arm is phi3 from `../ocsf-mapping-oracle`,
unconstrained and behind the same reject and snap wall (`llm_behind_constraint.py`), plus the
post-hoc frontier re-score above. The alias table is a weak baseline (see the correction above), so
a gap in its favour against phi3 says more about phi3 than about rules.

## Pre-registration

None. `RESULTS-FRONTIER-CONSTRAINED-2026-11-16.md` states that no frozen pre-registration covers it,
and its correction 8 records that "headline fixed before looking" is not backed by a frozen file.

## Reproduce

```bash
python ocsf-deterministic-mapper/run.py                      # alias mapper vs the cached phi3 numbers
python ocsf-deterministic-mapper/llm_behind_constraint.py    # needs Ollama with phi3 pulled
python ocsf-deterministic-mapper/frontier_behind_constraint_2026_11_16.py   # post-hoc, no model calls
python ocsf-deterministic-mapper/alias_whole_token_check_2026_11_16.py
```

`run.py` reuses BENCH-B's gold key, the OCSF 1.8.0 closure and the committed phi3 numbers. The first
and the last two commands need only the checked-in gold key (`../ocsf-mapping-fidelity/mapping.py`),
the cached predictions under `../ocsf-mapping-oracle/` and the fetched schema under
`schema-ocsf-1.8.0-api-2026-11-16/`. `fetch_ocsf_1_8_0_full_2026_11_16.py` re-fetches that schema
and needs the network.

## Results

- `results/RESULTS.md` and `results/results.json`: the June alias-vs-phi3 table.
- `results/results-constrained.json`: phi3 behind the wall (reject and snap).
- `results/RESULTS-FRONTIER-CONSTRAINED-2026-11-16.md`, with its JSON and stdout: the current read,
  including the scorer findings that change the June silent-error figures (24 of 141 gold paths sat
  outside the June closure, and two gold paths do not exist in 1.8.0).
- `results/alias-wrong-but-valid-adjudicated-2026-11-16.csv` and
  `results/alias-whole-token-check-2026-11-16.json`: the alias-table checks.

## Versions and pins

Standard-library Python plus `requests` for the Ollama arm (root `requirements.txt`). The phi3 arm
used the Ollama tag `phi3:latest` (`results/results-constrained.json`, `model`), which is not a
pinned digest. The full schema was fetched from `schema.ocsf.io/1.8.0/api` on 2026-11-16 and is
checked in with `FETCH-META.json`.

## Evidence tier and limits

Tier B for the re-scores and Tier D for the wrong-but-valid adjudication (one author). One weak local
model and one frontier model family; the "schema" prompt condition was a partial path list
(`results/RESULTS-FRONTIER-CONSTRAINED-2026-11-16.md`, correction 1).

## Corrections

- 2026-11-22: `run.py` took the first model in `../ocsf-mapping-oracle/results/results.json`, which became the
  frontier proxy once that leg landed there, so between then and this fix a re-run would have written the frontier
  proxy's cells under the phi3 label. It now reads `phi3:latest` by key; a scratch re-run reproduces the committed
  `results/results.json` byte for byte. `run.py` still regenerates `results/RESULTS.md` from its template, so a
  re-run drops the frontmatter and the hand-added 2026-11-17 and 2026-11-22 notes in that file either way. The alias-baseline correction's tail was
  also turned the right way round (whole-token matching lowers path-correct and raises precision).
- 2026-11-17: the frontier sentence replaced with what the 2026-11-16 re-score found; the
  "fair baseline" claim qualified; the silent-error zero labelled as a property of the constraint.
