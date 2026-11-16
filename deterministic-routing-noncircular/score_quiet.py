#!/usr/bin/env python3
"""QUIET REPLICATION 2026-11-16: the unchanged score.py, imported, with RESULTS pointed at
results/quiet-2026-11-16 (reads raw_*.json there, writes scores.json there). No logic change.
  ../.venv/bin/python -B score_quiet.py"""
import sys
sys.dont_write_bytecode = True
import score as S
S.RESULTS = S.HERE / "results" / "quiet-2026-11-16"
S.main()
