# Sigma correlation — multi-event rules, multi-backend, executed (results)

**Tier B.** Multi-event correlation rules (a temporal-ordered exec→lateral sequence and an event-count
failed-logon burst), compiled across the four pySigma backends for portability and executed via the SQL
backend over a unified view of the fidelity store.

### `brute_force.yml`

- Portability: sql_sqlite: compiles · splunk: compiles · elasticsearch: unsupported (NotImplementedError) · opensearch: unsupported (NotImplementedError)
- SQL backend executed on the fidelity store, **49 correlation hit(s)**
  - sample: `('user0274@acme.example', 20)`

### `exec_then_lateral.yml`

- Portability: sql_sqlite: compiles · splunk: unsupported (NotImplementedError) · elasticsearch: unsupported (NotImplementedError) · opensearch: unsupported (NotImplementedError)
- SQL backend executed on the fidelity store, **1 correlation hit(s)**
  - sample: `('WS1', 'ps_exec,rdp_lat', 2, datetime.datetime(2026, 1, 8, 10, 5), datetime.datetime(2026, 1, 8, 11, 10, 5))`


## Reading

Correlation is where Sigma's portability gets uneven, and that shows here: the rules compile across some
backends and not others, extending C4's single-event-portability finding to correlation. On execution, the
**temporal-ordered exec→lateral sequence is detected** — but only because the unified view exposes a shared
`host` key across the process and network sources, which the fidelity store preserves; a flattened store
that lost the per-source host link couldn't join the sequence, the context-collapse tie-in. The event-count
rule exposes a correlation-fidelity gap: the SQL backend emits the count/group-by but **drops the timespan
window**, so "10 failures in 10 minutes" becomes "10 failures ever," which over-fires on background — a
portability caveat a detection engineer needs to know before trusting a compiled correlation rule. Tier B,
single machine; the portability map is the transferable finding, the execution is one chain.
