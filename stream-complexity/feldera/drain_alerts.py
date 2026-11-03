"""F arm sink adapter (STREAM-COMPLEXITY v2): read the `alerts` view's HTTP egress change
stream and append each inserted alert to the F arm's alerts file, stamping
`alert_emit_wall_ts` at read time. The streaming-arm counterpart of
streaming/consume_alerts.py, counted as the F arm's sink adapter in moving parts.

Same dedup contract as consume_alerts.py: one output row per (user, src_ip, window_start);
raw inserts, duplicate inserts and deletes are counted in --state-file so engine-level
duplicates stay visible even though the file is deduped. With `emit_final` (primary
output mode) a delete should never appear; a delete count above zero means the fallback
(score final state per key) is needed and is reported as such.

HTTP egress is not durable: rows emitted while no client is connected are lost. The
reader reconnects on connection loss (pipeline or container restart) and records
`connected` in the state file so a recovery script can confirm the sink is attached
before it re-sends input.
"""

import argparse
import json
import os
import sys
import threading
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from compare_answers import canonical_window_start  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="http://localhost:18080")
    ap.add_argument("--pipeline", default="smx-detect")
    ap.add_argument("--out-file", required=True)
    ap.add_argument("--state-file", required=True)
    ap.add_argument("--stop-file", required=True)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    egress = f"{args.url}/v0/pipelines/{args.pipeline}/egress/alerts?format=json"
    lock = threading.Lock()
    st = {"connected": False, "n_connects": 0, "n_raw_inserts": 0, "n_written": 0,
          "n_duplicate_inserts": 0, "n_deletes": 0, "last_row_wall": None,
          "connect_walls": [], "disconnects": []}
    seen = set()

    def save():
        tmp = args.state_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(st, f)
        os.replace(tmp, args.state_file)

    def handle(rec):
        if "delete" in rec:
            st["n_deletes"] += 1
            return
        row = rec.get("insert")
        if row is None:
            return
        st["n_raw_inserts"] += 1
        key = (row["user"], row["src_ip"], canonical_window_start(row["window_start"]))
        if key in seen:
            st["n_duplicate_inserts"] += 1
            return
        seen.add(key)
        out = dict(row, alert_emit_wall_ts=time.time())
        with open(args.out_file, "a") as f:
            f.write(json.dumps(out) + "\n")
            f.flush()
            os.fsync(f.fileno())
        st["n_written"] += 1
        st["last_row_wall"] = time.time()

    def reader():
        while True:
            try:
                with requests.post(egress, stream=True, timeout=(5, None)) as r:
                    if r.status_code != 200:
                        raise requests.ConnectionError(f"HTTP {r.status_code}")
                    with lock:
                        st["connected"] = True
                        st["n_connects"] += 1
                        st["connect_walls"].append(time.time())
                        save()
                    for line in r.iter_lines():
                        if not line:
                            continue
                        msg = json.loads(line)
                        recs = msg.get("json_data") or []
                        if recs:
                            with lock:
                                for rec in recs:
                                    handle(rec)
                                save()
            except (requests.RequestException, ValueError) as e:
                with lock:
                    if st["connected"]:
                        st["disconnects"].append({"wall": time.time(), "error": str(e)[:200]})
                    st["connected"] = False
                    save()
            time.sleep(0.5)

    os.makedirs(os.path.dirname(args.out_file), exist_ok=True)
    save()
    threading.Thread(target=reader, daemon=True).start()
    while True:
        time.sleep(1)
        if os.path.exists(args.stop_file):
            last = st["last_row_wall"] or 0
            if time.time() - last >= 10:
                break
    with lock:
        save()
    if not args.quiet:
        print(f"[drain_alerts] done: {st['n_written']} alerts written, raw inserts "
              f"{st['n_raw_inserts']}, duplicate inserts {st['n_duplicate_inserts']}, "
              f"deletes {st['n_deletes']}", flush=True)


if __name__ == "__main__":
    main()
