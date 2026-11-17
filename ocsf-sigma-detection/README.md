# Sigma detection execution vs the testbed

## What it measures

C4 (`sigma-portability`) measured whether a Sigma rule *compiles* to four backends. This bench runs
compiled rules end to end: real Sigma rules go through pySigma to SQL and are executed over the fidelity
store (Store F) built from the shared testbed, and the harness records whether each rule matches its
planted attack-chain stage and how much background it also matches. Later dated arms in this folder
execute the correlation rules on OpenSearch PPL, SQLite, DuckDB and four lakehouse engines, decompose the
over-fire under a scheduler, re-run on a newer pySigma, and swap in an independently generated corpus.

## Result (Tier B)

*(corrected 2026-11-17: the headline below used to read "4/4 planted-chain stages detected" as though it
were a recall. It is now stated as what the harness can show.)* **4 of 4 planted stages matched by rules
written for them; this shows the compile-and-execute round trip and is not a recall.** Each rule compiled
through pySigma, ran over the OCSF store and returned its planted event. The three precisions of 1.0 and
the RDP rule's 0.0003 (2,960 matches, 2,959 of them benign port-3389 connections) follow from how the
testbed generator built the corpus rather than from anything the rules had to discover, as the next
section shows. The numbers are in [results/RESULTS.md](results/RESULTS.md).

The one arm in this folder whose detection result could have come out otherwise is the EvidenceForge arm
([RESULTS-evidenceforge-arm-2026-07-04.md](RESULTS-evidenceforge-arm-2026-07-04.md)), which ran the same
four rules unmodified over a corpus from an unrelated generator and scored 1 of 2 planted targets: the
structural RDP rule matched its target at precision 0.0072, and the literal C2-domain rule missed because
the other generator's C2 domain is a different string.

## What would have made it fail

For the Store F headline, nothing the harness could produce, because each rule keys on a value the testbed
generator planted:

| rule | what it matches | why it cannot miss, and why its precision is fixed |
|---|---|---|
| `c2_domain.yml` | `query_hostname = 'cdn-telemetry-sync.net'` | the literal is the planted C2 domain (`ocsf-semantic-testbed/generate.py:110`); background domains are two-word names that cannot equal it; and `run.py:74-77` counts every match of this rule as a true positive with zero false positives, so its precision is 1.0 by definition |
| `encoded_powershell.yml` | `cmd_line` contains `-EncodedCommand` and `device_hostname = 'WS1'` | background command lines are the bare image name (`generate.py:284`), so only the planted command line (`generate.py:342`) carries the flag, and `WS1` is reserved for the chain (background hosts start at `WS3`, `generate.py:164-166`) |
| `nomfa_privesc.yml` | `AttachUserPolicy` and not `mfa_present` | every background CloudTrail row carries the `mfaAuthenticated` key (`generate.py:304`) and only the planted row omits it (`generate.py:400-408`), and Store F's `mfa_present` flag is true whenever the key exists (`bench-a-context-collapse/stores.py:112`); the roughly 30% of background `AttachUserPolicy` calls with MFA recorded as false are scored as non-events by this definition |
| `rdp_lateral.yml` | `dst_port = 3389` | 3389 is the planted lateral port (`generate.py:113`); the 2,959 false positives are the generator's background port weight for 3389 (`generate.py:84-86`, weight 0.05 of 60,000 connections) |

The correlation arms (PPL, SQLite, DuckDB, the four lakehouse engines, the scheduled arm and the newer
pySigma re-run) test something else: whether the compiler keeps a correlation rule's time window and
order. That can fail, and a windowed compile would have failed it. Their over-fire rates (precision 0.286
from 50 decoys against 20 true bursts, the 40 of 40 wrong-order over-fires) are fixed by the planted
decoy-to-true ratio, as each of those files already says. Arm by arm:

| arm | corpus | could the result have come out otherwise? |
|---|---|---|
| Store F headline (2026-06-05) | testbed Store F | no for detection and for the three 1.0 precisions; the RDP precision is the generator's port weight |
| Store N precision (2026-06-05) | testbed Store N | yes for each coarsening knob, though which rule a knob blinds is fixed by the generator (the C2 domain is resolved once, so a "seen fewer than 3 times" DNS filter must drop it) |
| PPL event_count (2026-06-15), value_count and temporal (2026-06-16) | `ppl_execution.gen_corpus`, planted bursts and decoys | yes for the window and order finding (the compiled query is live); the rates are fixed by the 50:20 and 40:40 plantings |
| SQLite (2026-06-17), DuckDB and engines 4 to 7 (2026-06-23) | same planted corpus | yes for windowed versus windowless emit; the identical 70 / 0.286 / 50 rows are corpus-determined |
| scheduled arm (2026-06-24) | two planted decoy corpora | yes; it found the 0.286 is the unbounded-scan extreme |
| EvidenceForge (2026-07-04) | independent generator, rules unseen | yes, and the C2 rule missed |
| newer pySigma (2026-07-07) | same harnesses | yes; a changed emit would have shown as a diff, and none appeared |

## Pre-registration

Five dated pre-registrations sit in this folder, none with a hash file:
[PRE-REG-temporal-execution-2026-06-16.md](PRE-REG-temporal-execution-2026-06-16.md),
[PRE-REG-sqlite-2ndbackend-2026-06-17.md](PRE-REG-sqlite-2ndbackend-2026-06-17.md),
[PRE-REG-lakehouse-engines-2026-06-22.md](PRE-REG-lakehouse-engines-2026-06-22.md),
[PRE-REG-scheduled-arm-2026-06-24.md](PRE-REG-scheduled-arm-2026-06-24.md) and
[PRE-REG-evidenceforge-arm-2026-07-04.md](PRE-REG-evidenceforge-arm-2026-07-04.md). Each says it was
frozen before its run, and four of the five carry the same date as the RESULTS file they govern, so the
freeze-before-run order rests on the files' own statements. The original Store F run (2026-06-05) and the
2026-06-15 PPL and 2026-06-16 value_count legs have no pre-registration. The newer-pySigma re-run cites a
pre-registration held outside this repo.

## Reproduce

```bash
pip install -r ocsf-sigma-detection/requirements.txt
python ocsf-semantic-testbed/generate.py          # the shared corpus
python bench-a-context-collapse/run.py            # builds Store F
python ocsf-sigma-detection/run.py                # the Store F headline
```

`requirements.txt` leaves pySigma and the SQLite backend unpinned. A fresh install today pulls
pySigma-backend-sqlite 2.x, which emits `FROM logs` where the June backend emitted a `<TABLE_NAME>`
placeholder, and `run.py:62` replaces only the placeholder, so the runner would query a table that does
not exist and score every rule as not detected (the same mechanism is recorded for the sibling bench in
`../ocsf-attack-coverage/RESULTS-MIXED-CASE-2026-11-16.md`). Install pySigma 1.3.3 and
pySigma-backend-sqlite 1.1.3, the versions the 2026-06-17 SQLite arm records, to reproduce the published
numbers; the 2026-06-05 Store F run did not record its own (`results/results.json` has no environment block). The
correlation arms need a running OpenSearch 3.7.0 (`temporal_execution.py`, `ppl_execution.py`,
`value_count_execution.py`) or the lakehouse engines named in their RESULTS files.

## Results

The entry point for the Store F run is [results/RESULTS.md](results/RESULTS.md) with
[results/results.json](results/results.json). The supplements, in date order:

- [results/CORRELATION.md](results/CORRELATION.md) and [results/STORE-N-PRECISION.md](results/STORE-N-PRECISION.md) (2026-06-05): correlation portability and the same four rules over the coarse Store N.
- [RESULTS-ppl-execution-2026-06-15.md](RESULTS-ppl-execution-2026-06-15.md): PPL `event_count`, dropped window.
- [RESULTS-temporal-execution-2026-06-16.md](RESULTS-temporal-execution-2026-06-16.md) and [RESULTS-value-count-2026-06-16.md](RESULTS-value-count-2026-06-16.md).
- [RESULTS-sqlite-execution-2026-06-17.md](RESULTS-sqlite-execution-2026-06-17.md): second backend.
- [RESULTS-lakehouse-duckdb-2026-06-23.md](RESULTS-lakehouse-duckdb-2026-06-23.md) and [RESULTS-lakehouse-engines-4-7-2026-06-23.md](RESULTS-lakehouse-engines-4-7-2026-06-23.md).
- [RESULTS-scheduled-arm-2026-06-24.md](RESULTS-scheduled-arm-2026-06-24.md): the 0.286 over-fire is the unbounded-scan extreme.
- [RESULTS-evidenceforge-arm-2026-07-04.md](RESULTS-evidenceforge-arm-2026-07-04.md): the independent-corpus arm, the current detection result.
- [RESULTS-newer-pysigma-rerun-2026-07-07.md](RESULTS-newer-pysigma-rerun-2026-07-07.md): pySigma 1.4.0 reproduces the SQLite and DuckDB arms and the PPL temporal arm (`temporal_execution.py`) byte for byte; the 2026-06-15 PPL event_count and 2026-06-16 value_count arms were not re-run.

## Versions and pins

`requirements.txt` pins `duckdb==1.5.3` and leaves `pysigma` and `pysigma-backend-sqlite` unpinned. The
arms record pySigma 1.3.3 with pySigma-backend-sqlite 1.1.3 (June) and pySigma 1.4.0 (the 2026-07-07
re-run and the EvidenceForge arm), DuckDB 1.5.3 or 1.5.4, OpenSearch 3.7.0, ClickHouse 26.5.1, Trino 481,
StarRocks 4.1.1 and Dremio OSS 26.0. The EvidenceForge write-up says its compiled SQL matched "the 1.3.3
backend the original arm's `requirements.txt` pins", but the file does not pin it.

## Evidence tier and limits

Tier B: one synthetic chain on one machine for the headline, one independently generated scenario for
the EvidenceForge arm. What transfers is the split the EvidenceForge arm shows (structural rules survive a
corpus swap and pay for it in precision, literal-IOC rules do not survive it) and the correlation
window-drop mechanism, not the Store F counts.

## Corrections

- *(corrected 2026-11-17: the Store F headline is restated as 4 of 4 planted stages matched by rules
  written for them, a round-trip demonstration and not a recall; the earlier README called the
  precision split "the real SOC noise problem" measured, where the precisions follow from the
  generator's planted values and background port weights.)*
