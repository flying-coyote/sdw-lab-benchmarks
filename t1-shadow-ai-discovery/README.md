# T1 shadow-AI discovery (t1-shadow-ai-discovery)

## What it measures

Which of five discovery methods (Zeek on a pcap, a resolver's DNS log, osquery on the endpoint, Syft over the
filesystem, an egress allowlist) sees which of nine planted AI deployment surfaces on a simulated developer
workstation, what each flags among benign controls, and what each structurally cannot see.

## Result

Across ten scored cells, the union of the five methods reached eight at "found", one only partially (the local
OpenAI-compatible server) and missed the model weights in the Ollama store outright; osquery scored six of ten at
"found" and was the only method to reach the IDE extension, the MCP configs and the browser extension, while the
three network methods each reached the two remote surfaces and Syft reached packages and named model files
(`RESULTS.md`, Headline and matrix). The visibility pattern is measured, since a method could have missed a surface
it was predicted to find and two hypotheses (H5, H7) were in fact falsified, but the "found" grades also depend on
rules written by the same agent that planted the surfaces, so they show what each method can see with a competent
query rather than what a team would see with the queries it already has. Two of osquery's six finds rest on
post-run harness changes, so under the literally frozen query text it scores four (`RESULTS.md`, H5 row and
Deviations 2 and 3).

## What would have made it fail

Every hypothesis carries a stated falsifier in `PREREGISTRATION.md`, and the run falsified two of them. Six benign
controls (C1 to C6) were planted in the same home as false-positive bait, and the only control any rule fired on was
the pre-registered one, the Python file server on port 8080.

## Pre-registration

`PREREGISTRATION.md`, frozen by agent before the run and not owner-reviewed. Its sha256 in `prereg.sha256`
(`bc2920c9…7060d`) still matches the file, and `prereg.frozen-at` records 2026-11-10T00:55:54Z, before the first lab
run at 01:05Z that `RESULTS.md` reports. `fixture-sha256.txt` hashes only the two downloaded artefacts (the osquery
5.24.0 deb and the Cline 4.1.26 vsix); the planted fixture home itself was not hashed, and neither download is in the
repo, so that file cannot be re-checked from this tree. Deviations are listed at the end of `RESULTS.md`.

## Reproduce

`bash build_fixtures.sh && for i in 1 2 3; do nice -n 10 taskset -c 0-3 python3 -I run_lab.py $i; done && .venv/bin/python -I run_methods.py 1 2 3`.

The fixture home (about 1.7 GB), pcaps, Zeek logs, Syft JSON and the 15k-row osquery file listing are local and
gitignored. The `fixtures/` directory that `build_fixtures.sh` and `run_lab.py` read (`activity.sh`,
`make_chrome_fixtures.py`, `osquery_queries.json`, `ml-requirements.txt`, `ml-venv-freeze.txt`) and the
`COMMANDS.log` and `logs/` the run wrote are not committed, so the run cannot be repeated from this tree alone, and
the frozen osquery query list is readable only through the queries quoted in `PREREGISTRATION.md`.

What the scripts do:

- `build_fixtures.sh` plants the static surfaces into `fixtures/endpoint-home/` (Cline from Open VSX, MCP configs,
  Chrome manifests via `fixtures/make_chrome_fixtures.py`, the pinned ML venv built inside `python:3.12-slim`, benign
  controls).
- `run_lab.py <n>` runs one lab pass: Docker network, dnsmasq resolver sidecar, tcpdump sidecars (eth0 and any), the
  endpoint (`docker/endpoint/Dockerfile`, python:3.12-slim with osquery 5.24.0 and Ollama bind-mounted from the
  host), a peer container, the activity script, the osquery query set, then teardown.
- `run_methods.py [runs] [--score-only]` runs Zeek 8.0.11 in Docker over each pcap, Syft 1.55.0 over the fixture home
  and the egress check, then applies the pre-registered rules, writing `results/run<n>/fired.json`,
  `results/scores.json` and `results/matrix.md`.
- `posthoc_glob_probe_2026_11_16.sh` is the labelled post-hoc probe behind `POSTHOC-GLOB-2026-11-16.md`.

## Results

- `RESULTS.md` is the entry point: matrix, false positives, structural blind spots, hypothesis outcomes, post-hoc
  probes, the comparison with `ai-artifact-sbom/` (R4), timing and deviations.
- `results/run1/` to `results/run3/` hold the scored runs, `results/run0-discarded/` the shake-out run, and
  `results/posthoc/` the labelled post-hoc osquery probes.
- `POSTHOC-GLOB-2026-11-16.md` (post-hoc, not pre-registered) narrows the hidden-directory mechanism: osquery's `%%`
  skips dot-directories only at the first level under the query's base path.
- `VERIFICATION.md` is the independent re-run (VERIFIED-WITH-FIXES). Under `verify/`, `RESULTS.pre-verification.md`,
  `matrix.original.md` and `scores.original.json` are superseded copies kept for the audit trail, and `verify/run*/`
  holds the verifier's own runs; none of them is the current result.

## Versions and pins

`requirements.txt` pins nothing, because the harness is standard library only. The endpoint and sidecar images are
referenced by floating tag (`python:3.12-slim` in `docker/endpoint/Dockerfile`, `alpine:3.22` in
`docker/sidecar/Dockerfile`), not by digest; Zeek runs as `zeek/zeek:8.0.11`. The instruments as run are listed at
the top of `RESULTS.md`.

## Evidence tier and limits

`RESULTS.md` states no evidence tier letter for the main run; the 2026-11-16 post-hoc probe file labels itself Tier B
(first-party, one container, agent-run). One host, one simulated endpoint, one version of each instrument, surfaces
planted by the agent that wrote the rules, and a Docker capability set that removed osquery's socket-to-process join.
The full list is under Limits in `RESULTS.md`.

## Corrections

- 2026-11-16: `RESULTS.md` carries dated notes narrowing the `%%` hidden-directory claim to the first level under the
  base path (see `POSTHOC-GLOB-2026-11-16.md`).
- 2026-11-17: this README was restructured to the lab layout, and now says that `fixtures/`, `COMMANDS.log` and
  `logs/` are not committed and that the fixture hash file covers only two downloads.
