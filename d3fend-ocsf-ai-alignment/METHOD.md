---
type: benchmark-spec
title: "R8 method note: D3FEND AI artifact nouns vs OCSF ai_* objects"
created: 2026-11-09
status: frozen by agent before table was built; not owner-reviewed
---

# R8 method note (analysis, no bench)

This replaces a full pre-registration because R8 is a document comparison, not a measurement run
(SITE-REVIEW-2026-11-09.md section 5, row R8). Nothing is timed, so the methodology's
variance and repeat-run rules do not apply; the analogue here is pinning every source to a commit
or tag so a second reader gets the same rows.

## Question

For each AI-specific artifact or event noun proposed on the D3FEND side, does OCSF have a
counterpart, at what grade, and in which OCSF version; and for each OCSF `ai_*` object or draft
class, does D3FEND (develop, or an open proposal) have a counterpart? The output is a shared
vocabulary table for D3FEND #606 and OCSF #1754 discussion.

## Row set (fixed before grading)

D3FEND side to OCSF:
- The residual nouns in `02-projects/d3fend-atlas-crosswalk/RESIDUAL.md`: `MachineLearningModel`
  (AML.T0005.002, T0016.002, T0043.002), `RAGDataSource` (AML.T0064), `AIAgentToolDefinition`
  (AML.T0084.001). Five techniques, three distinct nouns. Source inconsistency flagged, not fixed:
  RESIDUAL.md's summary line says "4×MachineLearningModel" while its own table and the #606 thread
  list three techniques.
- The four artifacts asked for in D3FEND issue #586 (Agent Tool Invocation, Tool Response Content,
  Inter-Agent Message, Agent Memory Record).
- The four classes in D3FEND PR #601 (`AIAgentToolConfiguration`, `AIAgentToolManifest`,
  `AIAgentToolCall`, `AIAgentMessage`).
- The four MVP classes in the image posted by a D3FEND maintainer on #606 (`ext:AIModel`,
  `ext:AIInteractionMessage`, `ext:AIToolInvocation`, `ext:ProvenanceAttestation`).
- The `d3f:MachineLearningEvent` family proposed on #606 (parent plus Training, FineTuning,
  Inference).

Where two proposals name the same thing (#586 Agent Tool Invocation = #601 `AIAgentToolCall` =
MVP `ext:AIToolInvocation`), they share one row and the row lists every source.

OCSF side to D3FEND: `ai_model`, `ai_agent` (and `ai_agent.charter`), `ai_capability` (and its
`Prompt Template` type), `delegation`, `message_context`, `ai_status`, the `ai_operation` profile,
the #1754 draft `ai_agent_activity` class with its info objects, and the name collision between
D3FEND `Agent`, OCSF `agent` (a sensor) and OCSF `ai_agent`.

## Grading rubric

Each row runs the category checklist first (continuant or occurrent; carrier, content or
occurrence; kind or role), then gets one grade:
- **exact**: same kind and same scope; a `rdfs:seeAlso` could be asserted today without a note.
- **partial**: same kind, but the counterpart is narrower, broader, at a different granularity
  (one capability vs a set of declarations), or missing an attribute the other side relies on.
- **wrong-kind**: the nearest counterpart is a different category (an identity descriptor for a
  learned-parameter artifact, an event-integrity record for an artifact-provenance record).
- **none**: nothing on that side, including draft PRs.

OCSF availability is recorded in three columns because "exists" changes by version: released
1.9.0, main (1.10.0-dev), and the #1754 draft. D3FEND availability is recorded as develop vs
open proposal.

## Pinned sources

| Source | Pin | Fetched |
|---|---|---|
| OCSF schema, released | tag `v1.9.0` (release 2026-08-03) | gh api, 2026-11-09 |
| OCSF schema, main | `d1cbd619d76b7e1b8463785cd79beaaf4e3c2bdf` (committed 2026-11-09T17:07:42Z), `version.json` = 1.10.0-dev | gh api, 2026-11-09 |
| OCSF PR #1754 (draft, open) | head `08d6f530bfcda1675f54dc6351624051efb368b4`, fork `davemcatcisco/ocsf-schema`, updatedAt 2026-11-09T14:40:38Z | gh api, 2026-11-09 |
| D3FEND ontology develop | `048c693601220dbd8752b4bd67eb81e84c548d41` (2026-11-05), `d3fend-protege.ttl` sha256 `d3b44c77617a85816334a5955d155d5901db465c26e7d650480a89301c742d15` | gh api, 2026-11-09 |
| D3FEND PR #601 (open) | head `87f09c71cd2066a1955a62cc7def846aa85d21a9`, updatedAt 2026-11-06 | gh pr diff, 2026-11-09 |
| D3FEND #586, #606 | issue bodies and comments as of 2026-11-09; MVP image saved as `sources/img/mvp.png` | gh, curl |

Copies of every fetched file sit under `sources/`.

## Machine and tooling

Beelink, WSL2 (kernel 6.6.87.2-microsoft-standard-WSL2). Python 3 stdlib only plus the `gh` CLI
read-only, so nothing was pip-installed and `requirements.txt` says so. No reasoner was run and no
OWL bridge file was written; every grade is a reading of definitions, so it is Tier D-to-B
analysis (the OCSF and D3FEND definitions themselves are Tier B as vendor-of-their-own-schema
docs), not a measured result.

## Stop rule and cost

Stop when every row above has a grade and an availability stamp. Cost: zero, no paid calls.
