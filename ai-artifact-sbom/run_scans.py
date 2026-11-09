#!/usr/bin/env python3
"""R4 harness: run each pinned tool against each pre-registered fixture, 3 runs, monotonic timing.

Writes raw tool output to results/raw/<tool>/<fixture>/run<N>.json and a run log
(command, exit code, monotonic seconds) to results/runlog.jsonl. No scoring here; see score.py.
"""
import json, os, subprocess, sys, time
from pathlib import Path

D = Path(__file__).resolve().parent
F = D / "fixtures"
B = D / "tools" / "bin"
RAW = D / "results" / "raw"
RUNS = int(os.environ.get("R4_RUNS", "3"))
ENV = dict(os.environ, GRYPE_DB_CACHE_DIR=str(D / "cache/grype"), GRYPE_DB_AUTO_UPDATE="false",
           GRYPE_CHECK_FOR_APP_UPDATE="false", SYFT_CHECK_FOR_APP_UPDATE="false",
           TRIVY_CACHE_DIR=str(D / "cache/trivy"), NO_COLOR="1")

FIXTURES = ["models-gguf", "ollama-store", "models-hf", "mcp-npm", "mcp-pip", "vscode",
            "controls-npm", "controls-pip"] + [f"variants/V{i}" for i in range(1, 9)] + ["."]

def fx_name(fx):
    return "ALL" if fx == "." else fx.replace("/", "_")

def tools_for(fx, path, out):
    """Return list of (tool, argv, outfile). Default configs; Trivy rootfs is a labelled extra mode."""
    t = [
        ("syft", [str(B / "syft"), "scan", f"dir:{path}", "-q", "-o", f"syft-json={out('syft')}",
                  "-o", f"cyclonedx-json={out('syft-cdx')}"], out("syft")),
        ("trivy-fs", [str(B / "trivy"), "fs", "-q", "--skip-db-update", "--scanners", "vuln",
                      "--list-all-pkgs", "--format", "json", "-o", out("trivy-fs"), str(path)], out("trivy-fs")),
        ("trivy-rootfs", [str(B / "trivy"), "rootfs", "-q", "--skip-db-update", "--scanners", "vuln",
                          "--list-all-pkgs", "--format", "json", "-o", out("trivy-rootfs"), str(path)], out("trivy-rootfs")),
        ("trivy-fs-cdx", [str(B / "trivy"), "fs", "-q", "--skip-db-update", "--format", "cyclonedx",
                          "-o", out("trivy-fs-cdx"), str(path)], out("trivy-fs-cdx")),
        ("ai-bom", [str(D / ".venv/bin/ai-bom"), "scan", str(path), "-f", "cyclonedx", "-q", "--no-color",
                    "-o", out("ai-bom")], out("ai-bom")),
    ]
    return t

def main():
    log = (D / "results" / "runlog.jsonl").open("a")
    for run in range(1, RUNS + 1):
        for fx in FIXTURES:
            path = (F / fx).resolve()
            def out(tool, run=run, fx=fx):
                p = RAW / tool / fx_name(fx) / f"run{run}.json"
                p.parent.mkdir(parents=True, exist_ok=True)
                return str(p)
            steps = tools_for(fx, path, out)
            # grype consumes the syft SBOM from the same run
            steps.append(("grype", [str(B / "grype"), f"sbom:{out('syft')}", "-q", "-o", "json",
                                    "--file", out("grype")], out("grype")))
            if fx in ("mcp-pip", "controls-pip", "variants/V7"):
                py = path / "venv/bin/python"
                steps.append(("cyclonedx-py", [str(D / ".venv/bin/cyclonedx-py"), "environment", str(py),
                                               "--output-format", "JSON", "-o", out("cyclonedx-py")], out("cyclonedx-py")))
            for tool, argv, outfile in steps:
                for attempt in (1, 2):
                    t0 = time.monotonic()
                    p = subprocess.run(argv, env=ENV, capture_output=True, text=True, cwd=str(D))
                    dt = time.monotonic() - t0
                    rec = dict(run=run, fixture=fx_name(fx), tool=tool, attempt=attempt, rc=p.returncode,
                               seconds=round(dt, 4), argv=argv, stderr_tail=p.stderr[-600:])
                    log.write(json.dumps(rec) + "\n"); log.flush()
                    if p.returncode == 0 and Path(outfile).exists():
                        break
                print(f"run{run} {fx_name(fx):14s} {tool:13s} rc={p.returncode} {dt:7.2f}s", flush=True)

if __name__ == "__main__":
    main()
