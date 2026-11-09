"""Driver: for each (rows, depth) cell, generate the seeded artifact, pin it, run run_cell.py in a fresh
subprocess (an OOM or hang kills one cell, not the harness), then delete the Parquet (the pin record and
the seed reproduce it). Skip rule from the pre-registration is applied by summarize.py from the raw
records: a DNF engine-arm at (N, d) means larger-N / deeper-d cells for that engine-arm are reported
as SKIPPED rather than trusted.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
import importlib.util  # noqa: E402
# Load the lab's lib/common.py by path: a `lib` package elsewhere on PYTHONPATH shadows `lib.common`.
_spec = importlib.util.spec_from_file_location("lab_common", os.path.join(os.path.dirname(HERE), "lib", "common.py"))
_common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_common)
pin_artifact = _common.pin_artifact
import duckdb  # noqa: E402

from gen import generate  # noqa: E402

ROWS = [int(x) for x in os.environ.get("ROWS", "100000,1000000,10000000").split(",")]
DEPTHS = [int(x) for x in os.environ.get("DEPTHS", "2,4,6,8,10,12").split(",")]
CELL_TIMEOUT = 3600


def main():
    data = os.path.join(HERE, "data")
    raw = os.path.join(HERE, "results", "raw")
    os.makedirs(raw, exist_ok=True)
    log = open(os.path.join(HERE, "results", "run.log"), "a")
    for n in ROWS:
        for d in DEPTHS:
            out = os.path.join(raw, f"rows{n}_d{d}.json")
            if os.path.exists(out):
                continue
            t = time.perf_counter_ns()
            base = generate(n, d, data)
            gen_ms = (time.perf_counter_ns() - t) / 1e6
            pin = pin_artifact(duckdb.connect(), base + ".parquet")
            cmd = [sys.executable, os.path.join(HERE, "run_cell.py"), base + ".parquet", base + ".truth.json", out]
            print(time.strftime("%FT%TZ", time.gmtime()), "RUN", " ".join(cmd), file=log, flush=True)
            t = time.perf_counter_ns()
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=CELL_TIMEOUT)
                status, err = ("OK" if p.returncode == 0 else f"EXIT {p.returncode}"), p.stderr[-2000:]
            except subprocess.TimeoutExpired:
                status, err = "CELL_TIMEOUT", ""
            cell_ms = (time.perf_counter_ns() - t) / 1e6
            side = {"gen_ms": gen_ms, "cell_ms": cell_ms, "status": status, "stderr": err, "pin": pin}
            json.dump(side, open(out.replace(".json", ".pin.json"), "w"), indent=1)
            print(time.strftime("%FT%TZ", time.gmtime()), status, f"rows={n} d={d} cell_s={cell_ms/1e3:.1f}",
                  file=log, flush=True)
            if not os.path.exists(out):  # whole cell died: record it so it is reported, not dropped
                json.dump({"meta": {"cell": {"n_rows": n, "depth": d}}, "results": {}, "cell_status": status},
                          open(out, "w"))
            os.remove(base + ".parquet")


if __name__ == "__main__":
    main()
