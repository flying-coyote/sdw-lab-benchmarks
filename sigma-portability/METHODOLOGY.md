# Methodology

Sigma is named a foundational standard across the site because a detection
written once should compile to whatever backend a buyer runs. This benchmark
tests how far that holds — not for simple filters, which port easily, but for
**correlation rules** (counting, distinct-counting, and sequencing over a time
window), which are where the abstraction is actually load-bearing and where it
quietly leaks.

## What this measures, and what it does not

It measures what the **pySigma compiler emits** for each backend: the query text.
It does **not** run those queries against a live SIEM, so a preserved element is
not proof the target executes it as intended, and a missing element might be
supplied out of band — a dashboard time range, a scheduled-search window, an
alerting interval. The honest claim is narrow and exact: *this element does, or
does not, appear in the query the compiler produced.* That is still the thing a
practitioner copies and runs, so a window that is absent from the query is a
window the practitioner has to remember to add back.

## Evidence tier

**Tier B** — reproducible and first-party. pySigma compilation has no clock and no
randomness, so `run.py` compiles every rule against every backend twice and
asserts the output is byte-identical before publishing. The result is the
generated queries and the fidelity scores, and they reproduce exactly on the
pinned versions (`requirements.txt`).

## The rule set

Eleven Sigma rules under `rules/`: six single-event detections (whoami, encoded
PowerShell, failed/successful logon, service install, `net user /add`) and five
correlation rules spanning the four pySigma correlation types — `event_count`
(brute force, password spray), `value_count` (account spray), `temporal` (recon
then encoded exec), and `temporal_ordered` (logon then user-add). Each correlation
file is self-contained: it carries its own base rule(s) plus the correlation, so
each compiles independently to one query.

## The backends and their pipelines

Four open targets, each with the field-mapping pipeline it is idiomatically used
with: **Splunk SPL** (`splunk_windows`), **Elasticsearch ES|QL** and
**Elasticsearch Lucene** (`ecs_windows`), and **OpenSearch PPL** (`ecs_windows`).
All four emit text and no commercial software runs, so the benchmark is fully
public. The pipeline renames the rule's Windows field names into each target's
schema, which is part of what translation does and is recorded per cell.

## The fidelity checks (disclosed)

For each correlation query the runner records the verbatim output and checks, by
case-insensitive substring, whether the structural machinery a correlation needs
survived. The token sets live in `fidelity.py` and are the check — editing them
edits the score:

- **aggregation** — `stats`, `count(`, `count()`, `dc(`, `count_distinct`, …
- **threshold** — the condition value present alongside a comparator (`>=`, `having`, …)
- **value-field distinct-count** (value_count only) — `dc(` / `count_distinct` over the named field
- **time window** — every dialect's form: SPL `bin _time span=5m`, ES|QL `date_trunc(5minutes, …)`, PPL `span(@timestamp, 5m)`

The fraction is preserved-elements / applicable-elements for the rule's type
(temporal rules are scored on aggregation + window, since a numeric threshold does
not apply). Every score was validated against the verbatim query before
publishing; the verbatim queries are in `results.json` so any score is auditable.

### Why the group-by field name is recorded but not scored

A backend legitimately renames the group-by field into its own schema —
Elasticsearch/OpenSearch map `IpAddress` to `source.ip` and `ComputerName` to
`winlog.computer_name` under ECS. Scoring an exact name match would penalise a
correct translation for renaming, so the group-by field set is recorded per cell
for inspection but kept out of the fraction. One renaming asymmetry is worth
noting from the verbatim output: OpenSearch PPL renames the *filter* fields to ECS
while leaving the *group-by* field under its original Windows name, which is a real
inconsistency a deployer should check, but it is reported here as an observation,
not scored.

## What the results say

- **Single-event rules port to all four backends** (6/6 each). The basic filter
  abstraction holds.
- **Lucene refuses every correlation rule** — a filter-only query language cannot
  express aggregation, and the backend raises rather than emit something wrong. A
  loud, safe failure.
- **Splunk SPL and ES|QL preserve** the count, distinct-count, and unordered-temporal
  correlations in full, including the time window, but **refuse `temporal_ordered`**:
  ordered sequence is not implemented in those backends at these versions.
- **OpenSearch PPL translates every correlation type, including the ordered sequence
  the others refuse, but silently drops the time window on the count-based rules**
  (`event_count`, `value_count`) — the generated query counts over the whole search
  range, not the rule's 5–10 minute window — while keeping the window on the temporal
  rules. The silent drop is the failure mode worse than a refusal, because nothing
  flags it.

## What would change the result

A different pipeline, a newer backend plugin, or a different correlation
construction could move any of these cells; "refused" means this backend at this
version does not implement that correlation type, not that the underlying SIEM
cannot do it by hand. The window-drop finding is about the emitted query text — if
a deployment always supplies the time range through its scheduler, the practical
impact is smaller, but the rule's declared window is gone from the artifact a user
copies. Pin versions and re-run to confirm; the harness makes that one command.
