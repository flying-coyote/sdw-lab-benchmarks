# Results — Sigma correlation-backend portability (C4)

- pySigma: `1.3.3`  ·  backends: Splunk SPL, Elasticsearch ES|QL, Elasticsearch Lucene, OpenSearch PPL  
- Determinism (re-compile is byte-identical): **True**  
- Evidence tier: B (reproducible, first-party; compiler-output fidelity, not target-SIEM execution)

Every backend emits text, so this measures what the *compiler* produces, not what a target SIEM executes. Each correlation cell scores the elements that appear in the generated query (see `METHODOLOGY.md` for the exact checks), and the verbatim queries are in `results.json` so any score is auditable.

## Single-event rules — do they translate?

| rule | Splunk SPL | Elasticsearch ES|QL | Elasticsearch Lucene | OpenSearch PPL |
|---|---|---|---|---|
| failed_logon | ✓ | ✓ | ✓ | ✓ |
| net_user_add | ✓ | ✓ | ✓ | ✓ |
| powershell_encoded | ✓ | ✓ | ✓ | ✓ |
| service_install | ✓ | ✓ | ✓ | ✓ |
| successful_logon | ✓ | ✓ | ✓ | ✓ |
| whoami_exec | ✓ | ✓ | ✓ | ✓ |

## Correlation rules — how much of the semantics survives?

Cells show preserved-elements / applicable-elements; `refused` means the backend raised rather than emit a query; `⚠ no window` flags a query that translated but dropped the time-span construct.

| correlation rule | type | Splunk SPL | Elasticsearch ES|QL | Elasticsearch Lucene | OpenSearch PPL |
|---|---|---|---|---|---|
| bruteforce_event_count | event_count | 3/3 | 3/3 | refused | 2/3 ⚠ no window |
| logon_exec_temporal_ordered | temporal_ordered | refused | refused | refused | 2/2 |
| passwordspray_event_count | event_count | 3/3 | 3/3 | refused | 2/3 ⚠ no window |
| recon_exec_temporal | temporal | 2/2 | 2/2 | refused | 2/2 |
| userspray_value_count | value_count | 4/4 | 4/4 | refused | 3/4 ⚠ no window |

## Per-backend summary

Across 6 single-event and 5 correlation rules:

| backend | single-event translated | correlation full-fidelity | partial | refused | silent window-drop |
|---|--:|--:|--:|--:|--:|
| Splunk SPL | 6/6 | 4 | 0 | 1 | 0 |
| Elasticsearch ES|QL | 6/6 | 4 | 0 | 1 | 0 |
| Elasticsearch Lucene | 6/6 | 0 | 0 | 5 | 0 |
| OpenSearch PPL | 6/6 | 2 | 3 | 0 | 3 |

