#!/usr/bin/env python3
"""QUIET REPLICATION 2026-11-16 wrapper around the unchanged run_engines.py (imported, not edited).
Only paths and one stamp change:
  * WORK    -> _work_quiet_2026-11-16 (table_locations.json from register_quiet.py, same tables/metadata as 11-15)
  * RESULTS -> results/quiet-2026-11-16 (oracle.json there is a byte copy of results/oracle.json)
  * loadavg() returns [load1, load5, load15, unix_epoch_at_execution_start] so every execution carries a
    timestamp for cron-overlap tagging (the 4th element is the only addition).
No --resume against the 11-15 raw files is possible from here: the output dir is new.
  python -B run_engines_quiet.py --arm <arm> [--set all] [--resume]
"""
import sys, time
from pathlib import Path
sys.dont_write_bytecode = True
import run_engines as R

R.WORK = R.HERE / "_work_quiet_2026-11-16"
R.RESULTS = R.HERE / "results" / "quiet-2026-11-16"
_orig_loadavg = R.loadavg


def loadavg_stamped():
    la = _orig_loadavg()
    return (la or [None, None, None]) + [round(time.time(), 3)]


R.loadavg = loadavg_stamped

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=R.ARMS, required=True)
    ap.add_argument("--set", default="all", choices=["anchor", "corpus", "all"])
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    R.run(a.arm, a.set, a.trials, a.resume)
