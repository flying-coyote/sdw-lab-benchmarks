# BENCH-B — mapping oracle

Does grounding help a model map a source log field to the right OCSF attribute, and
which kind of grounding? Four conditions on one task (source field → OCSF 1.8.0
attribute path), scored against a hand-curated gold key:

- **none** — the field and the target class only; parametric knowledge.
- **schema** — plus the OCSF class's valid attribute paths in context.
- **formal** — schema plus a conceptual grounding note for the class (what an actor, a
  user, an endpoint, traffic, metadata *mean* for this class), with no field-path hint.
- **skill** — schema plus an ontology-thinking reasoning discipline: decide actor vs
  object first, choose the most specific path, preserve absent/null/false, don't invent.

The primary metric is the **silent-error rate** — a field mapped to an OCSF path that
does not exist in 1.8.0. That is the security-relevant failure: it validates and ships
as a real mapping and is wrong. Path-correctness (exact gold match) is reported too, but
it penalizes defensible alternatives, so silent-error carries the finding.

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

## Run it

```bash
# the local model must be pulled in Ollama first (e.g. `ollama pull phi3`)
.venv/bin/python ocsf-mapping-oracle/run.py --models phi3:latest --fields-per-source 14
.venv/bin/python ocsf-mapping-oracle/run.py --render-only        # regenerate RESULTS.md
# frontier leg (Jeremy's key) is the expansion — a pinned API model as a second --models entry
```

## Evidence tier

Tier B, and only the local leg. Single weak model, single-shot, temperature 0, a curated
gold subset, exact-match path scoring that undercounts valid alternatives. The
silent-error contrast is the readable signal at this tier; the magnitudes are
model-and-subset-specific. Tier-A needs a published larger gold set, a named reviewer on
the ambiguous adjudications, and an independent (non-same-family) frontier model.
