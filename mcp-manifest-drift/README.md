# mcp-manifest-drift (R5)

## What it measures

Whether MCP tool poisoning can be caught as manifest drift: a snapshotter takes `tools/list` from three MCP servers
(the lab's own `security-context-graph` server and the reference `server-everything` and `server-filesystem`
packages), a stateful differ turns each change into an OCSF Application Lifecycle (6002) Update event with the
`ai_operation` profile, and five Sigma rules (S1 any drift, S2 contract drift, S3 hidden-instruction markers, S4
description similarity, S5 schema widening) run over those events through two pySigma backends. Three poisoned
mutations (rug-pull, hidden instruction, schema widening) and five benign ones are applied to one target tool per
server, and a later arm replays eleven real release-to-release transitions of the two reference packages.

## Result

The two change rules caught every poisoned change only because they catch every change: S1, which uses OCSF-native
fields alone, fired on 9 of 9 poisoned and 12 of 15 benign mutations, because `ai_capability` carries fingerprints and
no description text, so a hidden instruction and a typo fix produce the same native signal (`RESULTS.md`, Headline).
The composite of the body-aware rules (S3, S4, S5) separated the authored sets completely, 9 of 9 detected and 0 of 15
benign fired, but that separation follows from construction, since the same agent wrote the poisonings and the rules
in the same pre-registration and S3's marker list contains the literals the hidden-instruction mutation plants
(`<IMPORTANT>`, `~/.ssh`), so the 0 of 15 is an upper bound and not a false-positive rate. The non-authored check ran
post hoc on 2026-11-16: on eleven real release transitions the composite fired once, an S4 similarity of 0.494 on a
genuine capability change in `read_media_file`, so the pre-registered "fires on zero transitions" was wrong
(`RESULTS-RELEASE-ARM-2026-11-16.md`).

## What would have made it fail

H0 to H6 in `PREREGISTRATION.md` carry stated outcomes, and H5 and part of H6 were wrong. The null-drift arm (17
consecutive unchanged snapshot pairs per server, 51 in all) is the control for drift noise, and it emitted no events.
For H4 the benign mutations are the only false-positive control, and they were written by the same agent as the rules,
which is why the release arm is the arm that could show real false positives.

## Pre-registration

`PREREGISTRATION.md`, frozen by agent before the run and not owner-reviewed, together with the five rule files: all
six lines of `FROZEN.sha256` still match (the pre-registration and `rules/s1` to `rules/s5`), with freeze time
2026-11-09T22:59:06Z, and the rules and the mutation definitions were therefore fixed before any snapshot existed.
`RESULTS.md` gives the first server contact as 22:59:45Z from `COMMANDS.log`, which is not committed;
`clock-pre-run.txt` holds the chrony reading. The release arm used the frozen rules and detector unchanged but ran a
week after the H4 results were known, with a driver written after them, and says so. `sigma_run.py` received a
behaviour-preserving edit to its default arguments after the recorded runs (`RESULTS.md`, Files).

## Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt                       # path a, DuckDB backend
python3 -m venv .venv-sqlite && .venv-sqlite/bin/pip install -r requirements-sqlite.txt  # paths b and c
.venv/bin/python -I snapshot.py live
.venv/bin/python -I detect.py
.venv/bin/python -I sigma_run.py a && .venv-sqlite/bin/python -I sigma_run.py b && .venv-sqlite/bin/python -I sigma_run.py c
.venv/bin/python -I score.py
# release arm, post hoc
.venv/bin/python -I snapshot.py release && .venv/bin/python -I release_arm_2026_11_16.py
```

Two venvs are needed because the DuckDB backend pins `pysigma<2.0.0` while the SQLite backend needs `pysigma>=2.0.1`.
Node and `npx` are required for the reference servers. `snapshot.py` reaches the lab server through an
absolute path into the original scratch directory (`SCG`, line 15), which has to be pointed at
`../security-context-graph/scg_mcp.py` first. `probe_backend_semantics.py` is an exploratory, post-hoc probe of two latent
differences between the backends.

## Results

- `RESULTS.md` is the entry point for the pre-registered run: servers, detection and false-positive counts per rule,
  each hypothesis, how much of the detection is in Sigma, snapshot latency, limits.
- `RESULTS-RELEASE-ARM-2026-11-16.md` (post-hoc) is the H5 release arm, with its own dated correction: `npx`
  resolved current transitive dependencies for every old release, so part of one transition's schema change is a
  replay artifact.
- `results/scores.json`, `results/sigma-path-{a,b,c}.json` and `results/release-arm-2026-11-16.json` hold the
  numbers; `events/` the OCSF events, labels, null drift and native signatures; `snapshots/` the captured manifests;
  `results/probe-{a,b}.json` the exploratory probe.
- `VERIFICATION.md` is the independent re-run with a second live snapshot session (VERIFIED-WITH-FIXES); its
  outputs are under `verification/` and are not the current result.

## Versions and pins

`requirements.txt` (pySigma 1.5.1, pySigma-backend-duckdb 0.1.4, DuckDB 1.5.3), `requirements-sqlite.txt` (pySigma
2.0.3, pySigma-backend-sqlite 2.1.1) and `requirements-release-arm-2026-11-16.txt` (the release arm's `pip freeze`)
pin every line with `==`. The reference servers are pinned by npm version (`@2026.8.31` for the main run, thirteen
dated versions for the release arm), but `npx` does not pin their transitive dependencies, which is the cause of the
release-arm correction.

## Evidence tier and limits

Tier B (first-party, single host, authored mutations; circularity stated in `RESULTS.md`). Three poisoned and five
benign kinds over three servers, one snapshot cadence on static servers, a manifest differ that cannot see a rug-pull
that changes server code but not the manifest, an OCSF binding on `main` 1.10.0-dev, and a `schema_widened` check that
was only partly exercised. See Limits in both result files.

## Corrections

- 2026-11-09: verifier fixes in `RESULTS.md`, listed in `VERIFICATION.md`.
- 2026-11-16: the protocol column in `RESULTS.md` carries a dated correction, and the release arm carries its own.
- 2026-11-17: the H5 bullet in `RESULTS.md`, which still read "not run", now carries a dated note pointing to the
  release arm and its 1 of 11 result. First-person narration in both result files was recast in neutral voice. This
  README was added.
