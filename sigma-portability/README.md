# Sigma correlation-backend portability

A reproducible benchmark for a claim the site leans on: that a Sigma detection
written once compiles to whatever backend a buyer runs. It holds for simple
filters. This measures where it leaks — in **correlation rules**, the counting,
distinct-counting, and sequencing over a time window that real detections depend
on — by compiling one rule set to four open backends and checking what survives
translation.

## What it measures

Eleven Sigma rules — six single-event detections and five correlation rules across
all four pySigma correlation types — compiled to **Splunk SPL**, **Elasticsearch
ES|QL**, **Elasticsearch Lucene**, and **OpenSearch PPL**. For each correlation
query the harness records the verbatim output and checks whether the structural
machinery survived: the aggregation, the threshold, the distinct-count of the
value field, and the time window. Every backend emits text, so no commercial
software runs and the benchmark is fully public.

## Results (pySigma 1.3.3, pinned backends)

Single-event rules translated on all four backends (6/6 each). Correlation is
where they diverge:

| backend | correlation full-fidelity | partial | refused | silent window-drop |
|---|--:|--:|--:|--:|
| Splunk SPL | 4 | 0 | 1 | 0 |
| Elasticsearch ES&#124;QL | 4 | 0 | 1 | 0 |
| Elasticsearch Lucene | 0 | 0 | 5 | 0 |
| OpenSearch PPL | 2 | 3 | 0 | 3 |

- **Lucene refuses all five correlation rules** — a filter-only query language
  cannot aggregate, and the backend raises rather than emit something wrong.
- **Splunk SPL and ES|QL** preserve the count, distinct-count, and unordered-temporal
  correlations in full — aggregation, threshold, and the time window — but both
  **refuse `temporal_ordered`** (ordered sequence is not implemented there).
- **OpenSearch PPL translates every correlation type, including the ordered sequence
  the others refuse, but silently drops the time window on the three count-based
  rules.** A brute-force detection compiles to `stats count() ... by user | where
  count >= 10` with no time bucket, so it counts over the whole search range
  instead of the rule's five-minute window — a plausible, runnable query that lost
  its time-bounding with no error. PPL keeps the window on the temporal rules
  (`span(@timestamp, 5m)`), so the drop is specific to its count path.

Full matrix and the verbatim generated queries are in
[`results/RESULTS.md`](results/RESULTS.md) and
[`results/results.json`](results/results.json).

## Honesty boundary

This is **Tier B**. It measures what the pySigma *compiler emits*, not what a
target SIEM executes — a preserved element is not proof of correct execution, and a
missing one could be supplied out of band (a dashboard time range, a scheduler).
But the query text is what a practitioner copies and runs, so a dropped window is a
window someone has to remember to add back. The fidelity checks are disclosed
substring tests (see [`METHODOLOGY.md`](METHODOLOGY.md)), validated against the
verbatim output, and the group-by *field name* is recorded but not scored because
backends legitimately rename it into their own schema (ECS `source.ip`). "Refused"
means the backend at this version does not implement that correlation type, not
that the SIEM cannot do it by hand. Pin versions and re-run to confirm.

## Reproduce

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python run.py
```

`run.py` compiles every rule to every backend twice and asserts the output is
byte-identical before scoring — the determinism behind the Tier-B label.

## Layout

```
rules/single/         six single-event detection rules
rules/correlation/    five correlation rules (event_count, value_count, temporal, temporal_ordered)
backends.py           the four backends + their field-mapping pipelines
fidelity.py           the disclosed structural checks
run.py                compile all, verify determinism, score, write results/
results/              RESULTS.md + results.json (generated)
requirements.txt      pinned pySigma + backend plugins
```
