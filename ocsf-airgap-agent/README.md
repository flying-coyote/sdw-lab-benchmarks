# Air-gapped agentic hunt (Adj.15)

Can a practitioner assemble an agentic threat hunt in which every part stays on the host, with model
weights served locally by Ollama, a short code-action loop that lets the model run read-only SQL, a local
DuckDB store of the APT29 evaluation telemetry and a mirrored SigmaHQ ruleset on disk, and nothing
reaching the internet? And when it runs, does a small local model finish one hunt task?

The folder name says OCSF, but the store is not OCSF. `run.py` reads the raw APT29 Parquet under
`../ocsf-context-collapse-apt29/_work/raw`, whose columns are Sigma field names (`Image`, `CommandLine`,
`ParentImage`, `User`, `Hostname`), and `results/RESULTS.md` carries a dated correction saying so. The
folder keeps its name because pages link to it.

## What it measures

- Whether the stack assembles from on-host parts. Offline operation holds by design rather than by
  measurement: the only network call in `run.py` is to `OLLAMA = "http://localhost:11434/api/chat"`
  (`run.py:36`, called at `run.py:76`), and the corpus and Sigma rules are local paths (`run.py:39-40`).
  The "what phoned home" ledger in the results is a fixed statement that `run.py:161-168` writes on every
  run, not an observation of traffic.
- Task success on one hunt (find the first suspicious executable and the account it ran under), the step
  count and the generation time, for two local models, `gemma4:e4b` and `phi4:latest`, at most six steps
  each (`MAX_STEPS = 6`).

## Result

`gemma4:e4b` found the dropper and the user in five steps (172 s of generation); `phi4:latest` used all
six steps on queries that DuckDB rejected with binder errors and returned no answer (`results.json`,
`final_answer` null). That is one task, one run per model, one host, so it shows the loop works end to
end and that one small model finished one task; it is not a capability rate, and the phi4 row is a
harness-and-prompt failure as much as a model one. The task is also easier than it reads. Its prompt
tells the model that suspicious executables "often live in unusual paths like C:\ProgramData", and the
dropper is the second process event in time order, so gemma4's successful step was
`SELECT CommandLine, User, Image FROM process_creation ORDER BY _event_ms ASC LIMIT 5`. The offline
property follows from how the code is written and was not observed, and the hunt result is a
demonstration.

## What would have made it fail

For the air-gap leg, nothing in the run could have shown egress, because the ledger is a literal written
by `run.py` whatever the traffic was, so this leg cannot fail as built. A real check would be a re-run
inside a network namespace with no route out, or a packet capture on the host during the run. For the
hunt leg, a model
could have returned the wrong executable or none, as phi4 did. There is no baseline (a plain
earliest-process query, which answers this task in one step, is the obvious one) and no repeat runs.

## Pre-registration

None.

## Reproduce

```bash
ollama pull gemma4:e4b && ollama pull phi4:latest
# build the APT29 raw store first: ../ocsf-context-collapse-apt29/ (its _work/raw and _work/sigma)
python ocsf-airgap-agent/run.py
```

## Results

`results/RESULTS.md` (with the 2026-11-16 correction) and `results/results.json`, which holds each step's
query and the observation fed back.

## Versions and pins

The models are Ollama tags, and `phi4:latest` is a floating tag, so a re-run may get different weights.
The folder has no requirements file; `run.py` imports `duckdb` and `requests`, which the root
`requirements.txt` pins. The Sigma rules are a local clone counted at 3,132 rules, with no commit
recorded in the results.

## Evidence tier and limits

The results file labels the build and air-gap mechanics Tier B and the hunt capability Tier D. Tier B fits
the buildability half, while the air-gap half rests on how `run.py` is written rather than on an
observation, and the Tier D for capability is right on this evidence: one task, one host, one run per
model, and a hinted task.

## Corrections

- 2026-11-16: in `results/RESULTS.md`, the phi4 row recorded as a loud failure and the store described
  as raw APT29 Parquet with Sigma field names.
- 2026-11-17: this README added, with the single-task scope and the task hint stated.
- 2026-11-17 (review): the air-gap leg restated as offline by design, because the "what phoned home"
  ledger is a fixed literal in `run.py:161-168` and no socket capture or no-route run produced it; the
  same correction is noted in `results/RESULTS.md`, which `run.py` regenerates.
