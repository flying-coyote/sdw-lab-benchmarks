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
  the others refuse** *(as an unordered co-occurrence query, which loses the order; see the
  2026-11-17 correction below)*, **but silently drops the time window on the three count-based
  rules.** A brute-force detection compiles to `stats count() ... by user | where
  count >= 10` with no time bucket, so it counts over the whole search range
  instead of the rule's five-minute window — a plausible, runnable query that lost
  its time-bounding with no error. PPL keeps the window on the temporal rules
  (`span(@timestamp, 5m)`), so the drop is specific to its count path.

*(corrected 2026-11-17: the third bullet used to read as though PPL compiles the ordered sequence
faithfully. The fidelity check scores a temporal rule on two elements only, aggregation and time window
(`fidelity.py:84-85`), so PPL's 2/2 on `temporal_ordered` does not test order, and this bench's own
recorded emit for `logon_exec_temporal_ordered` (`results/results.json`, `grid.os_ppl`) is
`stats dc(EventID) as unique_rules by span(@timestamp, 10m), ComputerName | where unique_rules >= 2`,
which has no ordering step. When the sibling bench
executed PPL's `temporal_ordered` emit
(`../ocsf-sigma-detection/RESULTS-temporal-execution-2026-06-16.md`), the query counted co-occurrence
with `dc(EventID) >= 2` instead of enforcing order and used a tumbling rather than sliding window, and it
missed every boundary-straddling sequence and fired on every reversed one. PPL emits a runnable query for
the ordered type, and that query does not keep the order.)*

The per-backend counts above re-derive from `results/results.json` (`summary.per_backend`).

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

## Measured or by construction, and what would have made it fail

The matrix is measured: each cell is what the pinned compiler emitted, and any cell could have come out
otherwise (a backend could emit a window, or refuse a rule). The rules were written for this bench, so
the set of correlation types is the bench's choice, and the window check is a disclosed substring test,
which is why a present window token is not proof the window works at execution.

## Pre-registration

None. No file in the folder records a design frozen before the run.

## Reconciliation with the newer-pySigma re-run

`../ocsf-sigma-detection/RESULTS-newer-pysigma-rerun-2026-07-07.md` moved pySigma from 1.3.3 to 1.4.0
and re-ran three *execution* harnesses in the sibling bench (`sqlite_execution.py`,
`duckdb_execution.py`, `temporal_execution.py`), whose JSON came out byte-identical. It did not re-run
this compile matrix, so the SPL, ES|QL and Lucene cells here are still the pySigma 1.3.3 result. The two
overlap only on the PPL and SQL count path, where both agree that `event_count` and `value_count`
compile without their window. That re-run also notes the Elasticsearch backend moved from 2.0.3 to
2.1.0 as a transitive dependency, which is a newer version than this folder pins and was not scored here.

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

## Hypothesis mapping

Advances **H-SIGMA-01** (registered in the tracker 2026-06-10): the per-backend
correlation-fidelity matrix is the first-party measurement of where write-once Sigma
portability holds and where it leaks. *(ID recorded 2026-06-10 per the
benchmark-alignment audit.)*

## Results

- [results/RESULTS.md](results/RESULTS.md) and [results/results.json](results/results.json): the only results file (regenerated by `run.py`).

## Versions and pins

`requirements.txt` pins sigma-cli 3.0.2, pySigma 1.3.3, pysigma-backend-splunk 2.1.0,
pySigma-backend-elasticsearch 2.0.3 and pySigma-backend-opensearch 2.0.3, and `results/results.json`
records pySigma 1.3.3.

## Evidence tier and limits

Tier B, compiler output only, eleven rules written for the bench.

## Corrections

- *(corrected 2026-11-17: PPL's full-fidelity score on `temporal_ordered` does not cover order, and
  execution showed the order is lost; the newer-pySigma re-run did not re-run this matrix.)*
