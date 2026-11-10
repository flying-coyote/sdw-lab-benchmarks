#!/usr/bin/env python3
"""Stability pass (PREREGISTRATION.md, H0): 3 repeats of A1, B1, B2 at T0 and T1 for one model.
Thin wrapper over run.py so the scoring code path is identical."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
model = sys.argv[1]
cmd = [sys.executable, str(HERE / "run.py"), model, "--sets", "A1-deepset-test,B1-deepset-test,B2-notinject",
       "--transforms", "T0,T1", "--repeat", "3", "--out", str(HERE / "results" / f"stability-{model}.jsonl")]
print(" ".join(cmd), flush=True)
sys.exit(subprocess.call(cmd))
