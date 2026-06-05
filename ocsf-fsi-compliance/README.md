# BENCH-F — FSI compliance-report (scaffold)

Does producing a SEC Reg SCI §1003(b) annual-review evidence package cost fewer human-hours
on an Iceberg + catalog + time-travel lakehouse than on a schema-on-read SIEM + document
store + manual export? The headline metric is **human-hours per review cycle**, which a
machine can't measure — so this is a *scaffold*, not a completed benchmark. It builds
everything around the human-hours measurement and leaves that to the operator.

## What's here

- **`gen_corpus.py`** — a seeded, OCSF-shaped synthetic FSI corpus over a compressed six-year
  retention window (72 monthly partitions, ~36k events), with a planted five-step intrusion
  whose timeline is the ground truth. Entirely synthetic; reproducible from one seed.
- **`REPORT-SPEC.md`** — the frozen §1003(b) report spec: four sections (retention attestation,
  incident timeline, lineage/chain-of-custody, point-in-time reproduction) each with an
  acceptance definition, the stopwatch timing protocol with its confound controls, and the
  pre-committed ≥40% / <20% decision rule.
- **`defensibility.py`** — produces the results template and *demonstrates* the lakehouse-side
  defensibility: it mechanically produces sections (a), (b), and (d) against the corpus
  (DuckDB standing in as the lakehouse engine) and checks them against ground truth, so
  "machine-checkable provenance" is shown rather than asserted. Human-hours stay as operator
  placeholders.

## What's pending (the operator's part)

The human-hours headline needs both substrates built to comparable finish and the report
produced on each under the stopwatch protocol — that's a person at a keyboard, not a script,
and it carries the self-timed confound the spec is built around. `defensibility.score()`
applies the decision rule once the per-section hours are filled into the template.

## Run it

```bash
.venv/bin/python ocsf-fsi-compliance/gen_corpus.py       # seeded corpus + ground truth
.venv/bin/python ocsf-fsi-compliance/defensibility.py    # template + lakehouse machine-checks
```

## Evidence tier

Tier B at best, and self-timed synthetic — the weakest evidence in the lab, stated plainly.
The regulatory text (§1003(b), §1005, 17a-4) is Tier A as a *requirement*; the human-hours
*result* would be Tier B/C. Tier-A needs a named-FSI run with the entity's own operators and
corpus, which is gated and is a paid engagement, kept distinct from this public synthetic
scaffold. This measures evidence-production effort, not regulatory sufficiency, and is not a
migration recommendation (the §1002 evidence-integrity obligation cuts the other way on
cutover risk).
