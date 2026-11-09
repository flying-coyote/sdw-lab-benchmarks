# R4 AI artifact inventory (ai-artifact-sbom)

Can Syft, Grype, Trivy and a CycloneDX AI-BOM generator (ai-bom 3.6.0) see model weights, MCP servers and a
VS Code extension, attach identifiers and advisories, and tell a renamed or re-registered copy from the original?

- `PREREGISTRATION.md`: question, fixtures, metrics, hypotheses, stop rule (frozen before run; hash in `prereg.sha256`)
- `RESULTS.md`: results, hypothesis outcomes, limits
- `build_fixtures.sh`: builds `fixtures/` (TinyLlama GGUF from the local Ollama store, all-MiniLM-L6-v2 at a pinned HF
  revision, two MCP servers with known advisories, prettier-vscode 12.4.0 from Open VSX, two controls, eight variants)
- `run_scans.py`: 3 runs of every tool against every fixture; raw output in `results/raw/`, log in `results/runlog.jsonl`
- `score.py`: computes `results/scores.json`
- `posthoc.sh`: labelled post-hoc runs E1 (MCP client config) and E2 (Syft hashing every file), output in `results/posthoc/`
- `tools/`: pinned release binaries and `checksum-verify.txt`; `requirements.txt`: pinned Python deps
- `logs/`: `bash -x` traces of fixture build and post-hoc runs
- `VERIFICATION.md` and `verify/`: independent re-run (scans, scoring, post-hoc) and the verdict

Reproduce: `bash build_fixtures.sh && .venv/bin/python -I run_scans.py && .venv/bin/python -I score.py`.
Fixtures (about 2.2 GB) and vulnerability DB caches are local and should not be committed.
