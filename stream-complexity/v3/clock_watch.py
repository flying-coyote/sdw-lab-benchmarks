"""v3 harness (not an arm): log host wall-clock steps during a trial. Every --interval s it
compares the change in time.time() with the change in time.monotonic(); a difference beyond
--threshold s is a wall-clock step (e.g. a WSL2 time resync), written as one JSON line.
Added 2026-11-07 after an R1 smoke showed RisingWave entering internal recovery on
`Hummock error: unexpected decreasing now` and dropping acknowledged INSERTs."""
import argparse, json, os, time

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--out", required=True)
ap.add_argument("--stop-file", required=True)
ap.add_argument("--interval", type=float, default=0.5)
ap.add_argument("--threshold", type=float, default=0.2)
a = ap.parse_args()
w0, m0 = time.time(), time.monotonic()
n = 0
with open(a.out, "a") as f:
    while not os.path.exists(a.stop_file):
        time.sleep(a.interval)
        w, m = time.time(), time.monotonic()
        step = (w - w0) - (m - m0)
        n += 1
        if abs(step) > a.threshold:
            f.write(json.dumps({"wall": w, "step_s": round(step, 3)}) + "\n"); f.flush()
        w0, m0 = w, m
    f.write(json.dumps({"done": True, "n_checks": n}) + "\n")
