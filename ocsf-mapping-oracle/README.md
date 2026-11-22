# BENCH-B — mapping oracle

Does grounding help a model map a source log field to the right OCSF attribute, and
which kind of grounding? Five conditions on one task (source field → OCSF 1.8.0
attribute path), scored against a hand-curated gold key:

- **none** — the field and the target class only; parametric knowledge.
- **schema** — plus a partial list of the class's valid attribute paths in context (the first 80 paths of depth at most one, alphabetically; see results/RESULTS.md correction 2026-11-16).
- **formal** — schema plus a conceptual grounding note for the class (what an actor, a
  user, an endpoint, traffic, metadata *mean* for this class), with no field-path hint.
- **skill** — schema plus an ontology-thinking reasoning discipline: decide actor vs
  object first, choose the most specific path, preserve absent/null/false, don't invent.
- **wrong_grounding** — schema plus a grounding note for the *wrong* class (the control).

The primary metric is the **silent-error rate** — a field mapped to an OCSF path that
does not exist in 1.8.0. That is the security-relevant failure: it validates and ships
as a real mapping and is wrong. Path-correctness (exact gold match) is reported too, but
it penalizes defensible alternatives, so silent-error carries the finding.

The `none` condition doubles as this bench's contamination floor: it is the no-data arm that
`BENCHMARKING-METHODOLOGY.md` §10 now asks every LLM bench over a public corpus to run. OCSF and the
vendor field docs behind the gold key are public, so a model's `none` score measures what it brings from
pretraining, and grounded conditions are read as lifts over that floor.

## Gold key and validation

The answer key is the hand-curated C1 source→OCSF mappings in
[`../ocsf-mapping-fidelity/mapping.py`](../ocsf-mapping-fidelity/mapping.py), built from
vendor documentation and the OCSF schema, never from an LLM. Every *predicted* path is
checked against the closure of the checked-in
[OCSF 1.8.0 subset](../ocsf-mapping-fidelity/schemas/ocsf/ocsf_1.8.0_subset.json), so an
invented attribute is caught as a silent error.

## State — local leg, 6 sources, with the wrong-grounding control

Runs the five conditions over all 141 real-path gold mappings across six vendor sources via
Ollama. Key finding on phi3 (3.8B): schema-in-context cuts the silent-error rate 0.99 → 0.69,
the ontology-thinking **skill** discipline cuts it most (→ 0.60) and lifts path-correctness
highest, while **conceptual grounding is inert — `formal` (0.72) equals `wrong_grounding` (0.72)
and is no better than schema-alone**, so the control shows the grounding-note *content* did no
work; the reasoning discipline is the lever, not the note. That corroborates the §9 grounding-value
verdict (the formal layer pays ~null over schema-conformance for field-mapping). The weak-vs-frontier
capability gap (H-PRACTITIONER-OWNED-AGENTIC-01) is approached by a local model ladder (phi3 → phi4)
rather than resolved; an independent frontier leg (needs an API key) closes it. Results in
[results/RESULTS.md](results/RESULTS.md).

*(corrected 2026-11-17: this section predates three later results in the folder. A larger local model,
gemma4:26b, is in `results/RESULTS.md` (silent error 0.18 under `schema`, 0.83 under `none`). A frontier
proxy leg ran in June through Claude Code subagents rather than an API key, three runs of all 705
prompts (`_frontier/REPLICATION-2026-06-14.md`: path-correct 57.6 / 67.2 / 68.5%), described as blind in the
June replication file, though gold-stripped inputs are archived for run 2 only and run 3's schema batch is
excluded from the headline band in the 2026-11-16 re-score (57 to 66% behind the full-schema wall,
`../ocsf-deterministic-mapper/results/RESULTS-FRONTIER-CONSTRAINED-2026-11-16.md`, correction 2; qualifier
added 2026-11-22), and that is one
model family, so the independent non-same-family leg is still open. And the silent-error metric itself
was found to be subset-sensitive: the validator dropped the subset's deep-accept rule, so 24 of the 141
gold paths sat outside the closure, and against the full OCSF 1.8.0 schema the frontier proxy's
invented-path rate is 5.0 / 9.1 / 9.1% of prompts rather than 17.0 / 26.7 / 26.1%, while phi3 under the
partial-list condition moves only from 0.69 to 0.68 (`results/RESULTS.md`, correction of 2026-11-16, and
`../ocsf-deterministic-mapper/results/RESULTS-FRONTIER-CONSTRAINED-2026-11-16.md`). The phi3 contrasts in
the paragraph above were measured against the June closure and should be read with that note.)*

## What would have made it fail

Every condition can fail, since the model's paths are scored against an independent hand-built gold key
and a schema validator, and the `wrong_grounding` arm is a real control for the grounding-note content.
The `none` arm is the contamination floor. The weak point is the validator, which was narrower than the
schema (see the 2026-11-17 note above), so the June silent-error figures overstate invented paths for
any model that emits real paths outside the transcribed subset.

## Pre-registration

None for the June local and frontier runs. The re-scores that correct them are post-hoc and say so.

## Reproduce

```bash
# the local model must be pulled in Ollama first (e.g. `ollama pull phi3`)
.venv/bin/python ocsf-mapping-oracle/run.py --models phi3:latest --fields-per-source 14
.venv/bin/python ocsf-mapping-oracle/run.py --render-only        # regenerate RESULTS.md
# frontier leg: a pinned API model as a second --models entry; the June frontier-proxy runs used
# dump_frontier_prompts.py + subagents + score_frontier.py instead (see _frontier/REPLICATION-2026-06-14.md)
```

## Results

- `results/RESULTS.md` and `results/results.json` (local ladder plus the frontier-proxy section and the
  appended 2026-11-16 correction); `results/gemma4_full_checkpoint.jsonl` holds the gemma4 predictions.
- `_frontier/REPLICATION-2026-06-14.md` and `_frontier/run2/`, `_frontier/run3/`: the three frontier
  runs. Gold-stripped inputs are archived for run 2 only.
- Current read on silent error: `../ocsf-deterministic-mapper/results/RESULTS-FRONTIER-CONSTRAINED-2026-11-16.md`.

## Versions and pins

Ollama tags `phi3:latest` and `gemma4:26b` (tags, not digests); the frontier proxy is claude-opus-4-8
through Claude Code at harness defaults, with no temperature or seed control. Python dependencies come
from the root `requirements.txt` (`requests==2.34.2`).

## Evidence tier

Tier B, and only the local leg (this paragraph describes the June local leg; the later frontier-proxy and
gemma4 results are in the note above, added 2026-11-22). Single weak model, single-shot, temperature 0, a curated
gold subset, exact-match path scoring that undercounts valid alternatives. The
silent-error contrast is the readable signal at this tier; the magnitudes are
model-and-subset-specific. For the full-corpus run, a seeded gold subset (about 100 hand-verified
mappings dispersed through the larger task, scored for precision and recall, with missed fields counted
as a first-class outcome) is a cheap scoring method that one practitioner team reports tracks whole-run
performance (methodology §10). Tier-A needs a published larger gold set, a named reviewer on
the ambiguous adjudications, and an independent (non-same-family) frontier model.

## Corrections

- 2026-11-16: validator deep-accept and partial-list findings appended to `results/RESULTS.md`.
- 2026-11-17: the "State" section annotated with the gemma4, frontier-proxy and full-schema results; the
  run comment reworded.
