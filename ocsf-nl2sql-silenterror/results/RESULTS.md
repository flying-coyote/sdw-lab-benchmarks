# OCSF NL2SQL silent-error benchmark — results

**Tier B, single machine, local models, one planted chain.** The headline is the **silent-error rate** (SQL runs, returns a non-empty wrong answer) and **where on the difficulty curve it concentrates**. Anchors (external): NL2KQL ~58% result-accuracy at ~42% confidently-wrong; BIRD 81.67% vs 92.96% human.

## phi3:latest

- result-accuracy: **0.36**
- silent-error rate: **0.09**
- counts: {'correct': 12, 'silent': 3, 'loud': 18}

| difficulty tier | n | correct | silent | loud | silent-rate |
|---|---|---|---|---|---|
| simple_filter | 5 | 3 | 2 | 0 | 0.40 |
| aggregation | 5 | 5 | 0 | 0 | 0.00 |
| group_by | 5 | 0 | 1 | 4 | 0.20 |
| time_window | 4 | 0 | 0 | 4 | 0.00 |
| multi_condition | 5 | 3 | 0 | 2 | 0.00 |
| join | 4 | 1 | 0 | 3 | 0.00 |
| adversary_tail | 5 | 0 | 0 | 5 | 0.00 |

<details><summary>per-question</summary>

| id | tier | kind | outcome | rows |
|---|---|---|---|---|
| F01 | simple_filter | scalar | correct | 1 |
| F02 | simple_filter | scalar | silent | 1 |
| F03 | simple_filter | set | correct | 22 |
| F04 | simple_filter | scalar | silent | 1 |
| F05 | simple_filter | scalar | correct | 1 |
| G01 | aggregation | scalar | correct | 1 |
| G02 | aggregation | scalar | correct | 1 |
| G03 | aggregation | scalar | correct | 1 |
| G04 | aggregation | scalar | correct | 1 |
| G05 | aggregation | scalar | correct | 1 |
| B01 | group_by | set | loud | 0 |
| B02 | group_by | scalar | silent | 1 |
| B03 | group_by | set | loud | 0 |
| B04 | group_by | scalar | loud | 0 |
| B05 | group_by | scalar | loud | 0 |
| T01 | time_window | scalar | loud | 0 |
| T02 | time_window | scalar | loud | 0 |
| T03 | time_window | scalar | loud | 0 |
| T04 | time_window | scalar | loud | 0 |
| M01 | multi_condition | scalar | loud | 0 |
| M02 | multi_condition | scalar | correct | 1 |
| M03 | multi_condition | scalar | correct | 1 |
| M04 | multi_condition | scalar | loud | 0 |
| M05 | multi_condition | scalar | correct | 1 |
| J01 | join | scalar | loud | 0 |
| J02 | join | scalar | loud | 0 |
| J03 | join | scalar | correct | 1 |
| J04 | join | set | loud | 0 |
| A01 | adversary_tail | uidset | loud | 0 |
| A02 | adversary_tail | substring | loud | 0 |
| A06 | adversary_tail | uid | loud | 0 |
| A08 | adversary_tail | substring | loud | 0 |
| A04 | adversary_tail | uidset | loud | 0 |

</details>

## gemma4:26b

- result-accuracy: **0.55**
- silent-error rate: **0.00**
- counts: {'correct': 18, 'silent': 0, 'loud': 15}

| difficulty tier | n | correct | silent | loud | silent-rate |
|---|---|---|---|---|---|
| simple_filter | 5 | 5 | 0 | 0 | 0.00 |
| aggregation | 5 | 5 | 0 | 0 | 0.00 |
| group_by | 5 | 0 | 0 | 5 | 0.00 |
| time_window | 4 | 2 | 0 | 2 | 0.00 |
| multi_condition | 5 | 4 | 0 | 1 | 0.00 |
| join | 4 | 2 | 0 | 2 | 0.00 |
| adversary_tail | 5 | 0 | 0 | 5 | 0.00 |

<details><summary>per-question</summary>

| id | tier | kind | outcome | rows |
|---|---|---|---|---|
| F01 | simple_filter | scalar | correct | 1 |
| F02 | simple_filter | scalar | correct | 1 |
| F03 | simple_filter | set | correct | 22 |
| F04 | simple_filter | scalar | correct | 1 |
| F05 | simple_filter | scalar | correct | 1 |
| G01 | aggregation | scalar | correct | 1 |
| G02 | aggregation | scalar | correct | 1 |
| G03 | aggregation | scalar | correct | 1 |
| G04 | aggregation | scalar | correct | 1 |
| G05 | aggregation | scalar | correct | 1 |
| B01 | group_by | set | loud | 0 |
| B02 | group_by | scalar | loud | 0 |
| B03 | group_by | set | loud | 0 |
| B04 | group_by | scalar | loud | 0 |
| B05 | group_by | scalar | loud | 0 |
| T01 | time_window | scalar | loud | 0 |
| T02 | time_window | scalar | correct | 1 |
| T03 | time_window | scalar | loud | 0 |
| T04 | time_window | scalar | correct | 1 |
| M01 | multi_condition | scalar | correct | 1 |
| M02 | multi_condition | scalar | correct | 1 |
| M03 | multi_condition | scalar | loud | 0 |
| M04 | multi_condition | scalar | correct | 1 |
| M05 | multi_condition | scalar | correct | 1 |
| J01 | join | scalar | correct | 1 |
| J02 | join | scalar | loud | 0 |
| J03 | join | scalar | correct | 1 |
| J04 | join | set | loud | 0 |
| A01 | adversary_tail | uidset | loud | 0 |
| A02 | adversary_tail | substring | loud | 0 |
| A06 | adversary_tail | uid | loud | 0 |
| A08 | adversary_tail | substring | loud | 0 |
| A04 | adversary_tail | uidset | loud | 0 |

</details>

## Reading

The question to read off the by-tier table: do silent errors cluster in the **mid-difficulty** band (aggregation / group-by / time-window / multi-condition), where the SQL plausibly runs and quietly returns the wrong number, rather than on the **adversary tail**, where a weak local model tends to fail *loudly* (hallucinated columns/functions → error or empty)? That mid-band silent concentration, if it holds, is the analyst-trust hazard this benchmark exists to surface.

Determinism: the corpus, the ground truth, and the correct/silent/loud scorer are deterministic and assertable (`--determinism`); the SQL the model composes is temperature-0 greedy decode — reproducible in practice, not asserted. See README for the relationship to BENCH-B (mapping-oracle) and BENCH-C (OBDA-vs-LLM).
