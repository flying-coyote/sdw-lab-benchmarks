# deterministic-routing-sim: the June routing-rule simulation (superseded)

**Status: superseded by [`../deterministic-routing-noncircular/`](../deterministic-routing-noncircular/), which is the test of these rules that could fail.** This folder is kept because essays and the non-circular bench link to it, and because the non-circular pre-registration hashes `route_sim.py` as the rule stack under test, so the file stays byte-identical.

## What it measures

`route_sim.py` implements three ordered routing rules for H-DETERMINISTIC-ROUTING-01 with `sqlglot` and no engine: R1 sends a query to the hot or cold tier from a static time predicate, R2 classifies the parsed query into one of about ten shapes, and R3 resolves known views to their true shape before R2 runs. Each pick is looked up in a per-shape, per-tier winners table copied from `engine-join-specialization/results/RESULTS.md`, and then scored as correct, a minor misroute or a catastrophic one. It runs eleven templated SOC and TPC-H shapes and five adversarial queries, one per misrouting mode.

## Result, and whether it is measured

Templated accuracy is 1.00 (11 of 11) and the full router gets 4 of 5 adversarial queries right against 3 of 5, with one catastrophic pick, without the view resolution (`results/route_sim.json`, `summary`). The 11 of 11 follows from construction and is not a routing accuracy. `route()` takes the first engine in `WINNERS[shape][tier]`, and `classify()` marks a pick correct when it sits in the same table's cell for the query's labelled shape and tier (`route_sim.py:207-243`). The templated queries and their labels were written alongside the rules, so the only way one of them could have failed is for `shape()` or `time_tier()` to disagree with its author's own label. The view-obfuscation contrast is one query against a one-entry, hand-written `VIEWS` stub (`route_sim.py:71-73`), so it shows the mechanism and nothing about a rate. `RESULTS-2026-06-15.md` already calls the headline "partly circular", and a dated correction at its top states the construction plainly.

## What would have made it fail

Nothing independent of the rule author: there is no held-out query set and no measured engine time in this folder. The non-circular bench supplied both, with 84 generated queries scored against measured winners on four engine arms, and on both of its runs it falsified H1 (placement accuracy 0.643 hot and 0.738 cold on 2026-11-15, 0.643 and 0.679 on 2026-11-16, against a 0.90 threshold) and H2 (catastrophic picks, two of them 4-table joins that R2 classifies as 3-table shapes and sends to native MergeTree, where on 2026-11-15 they took 110.9 s and 200.9 s against about 1 to 2 s on the best engine, inside the 300 s limit but 50 to 200 times slower), held H4 and H6, falsified H5, and split H3 between the two runs; its README gives each hypothesis in turn.

## Pre-registration

None. The non-circular follow-up is pre-registered and hashes `route_sim.py` (sha256 `1ce78608...603683`, `../deterministic-routing-noncircular/PREREGISTRATION.md:37`).

## Reproduce

```bash
python3 deterministic-routing-sim/route_sim.py   # needs sqlglot 30.11.0; no engines, runs in seconds
```

It writes `results/route_sim.json` beside the script.

## Results

- `RESULTS-2026-06-15.md`, the only results narrative, with the 2026-11-17 correction at the top.
- `results/route_sim.json`, the machine-readable summary and per-query rows.

## Versions and pins

`sqlglot` 30.11.0, recorded in `results/route_sim.json` (`host` field). It is not pinned in any requirements file.

## Evidence tier and limits

The folder labels itself "B- / simulation". One host's winners table, about ten shapes, and one query per adversarial mode; the RESULTS limitations list stands as written. The skew mode scores "correct" because engine-level routing cannot see intra-engine cost.

## Corrections

- 2026-11-17: dated note added to `RESULTS-2026-06-15.md` saying the 11 of 11 follows from construction and that the folder is superseded by `deterministic-routing-noncircular`.
