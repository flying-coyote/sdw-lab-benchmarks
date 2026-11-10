# T1 shadow-AI discovery (t1-shadow-ai-discovery)

Which of five discovery methods (Zeek on a pcap, a resolver's DNS log, osquery on the endpoint, Syft over the
filesystem, an egress allowlist) sees which of nine planted AI deployment surfaces on a simulated developer
workstation, what each flags among benign controls, and what each structurally cannot see.

- `PREREGISTRATION.md`: question, lab, surfaces, rules, hypotheses, stop rule (frozen before run; hash in `prereg.sha256`, time in `prereg.frozen-at`)
- `RESULTS.md`: surface × method matrix, false positives, structural blind spots, hypothesis outcomes, post-hoc probes, R4 comparison, deviations
- `build_fixtures.sh`: plants the static surfaces into `fixtures/endpoint-home/` (Cline from Open VSX, MCP configs, Chrome
  manifests via `fixtures/make_chrome_fixtures.py`, the pinned ML venv built inside `python:3.12-slim`, benign controls);
  model copies and downloads are recorded in `COMMANDS.log`
- `run_lab.py <n>`: one run — Docker network, dnsmasq resolver sidecar, tcpdump sidecars (eth0 and any), the endpoint
  (`docker/endpoint/Dockerfile`: python:3.12-slim + osquery 5.24.0, Ollama bind-mounted from the host), a peer
  container, `fixtures/activity.sh`, the osquery query set `fixtures/osquery_queries.json`, teardown
- `run_methods.py [runs] [--score-only]`: Zeek 8.0.11 in Docker over each pcap, Syft 1.55.0 over the fixture home, the
  egress check, then the pre-registered rules; writes `results/run<n>/fired.json`, `results/scores.json`, `results/matrix.md`
- `results/posthoc/`: labelled post-hoc osquery probes (hidden-dir glob, SYS_PTRACE socket mapping, vscode columns)
- `results/run0-discarded/`: the shake-out run (logs and osquery JSON in the repo; large files gitignored like every run; see RESULTS Deviations)
- `COMMANDS.log`, `clock-pre-run.txt`, `logs/`: every command, the clock check, image build and run logs

Reproduce: `bash build_fixtures.sh && for i in 1 2 3; do nice -n 10 taskset -c 0-3 python3 -I run_lab.py $i; done && .venv/bin/python -I run_methods.py 1 2 3`.
The fixture home (about 1.7 GB), pcaps, Zeek logs, Syft JSON and the 15k-row osquery file listing are local and gitignored.
