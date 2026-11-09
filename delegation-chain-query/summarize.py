"""Summarize results/raw/*.json into results/summary.json and print markdown tables for RESULTS.md.
Applies the pre-registered skip rule (DNF at (N,d) -> SKIPPED for N'>=N, d'>=d, same engine-arm)."""
import glob
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = sys.argv[1] if len(sys.argv) > 1 else "raw"
ARMS = ["A_recursive", "B_selfjoin", "C_materialized", "D_rootonly"]
ENGINES = ["duckdb", "chdb"]

cells = {}
for p in glob.glob(os.path.join(HERE, "results", RAW, "rows*_d*.json")):
    if p.endswith(".pin.json"):
        continue
    j = json.load(open(p))
    c = j["meta"]["cell"]
    cells[(c.get("n_rows_requested", None) or int(os.path.basename(p)[4:].split("_")[0]), c["depth"])] = j

rows = []
dnf = {}
for (n, d), j in sorted(cells.items()):
    for e in ENGINES:
        for a in ARMS:
            r = j["results"].get(f"{e}|{a}", {"status": j.get("cell_status", "MISSING")})
            t = r.get("trials_ms", [])
            status = r["status"]
            if any(n >= n0 and d >= d0 for (n0, d0) in dnf.get((e, a), [])) and status == "OK":
                status = "SKIPPED"
            if r["status"] != "OK":
                dnf.setdefault((e, a), []).append((n, d))
            row = {"rows": n, "depth": d, "engine": e, "arm": a, "status": status, "n_trials": len(t),
                   "error": r.get("error")}
            if t:
                m = st.mean(t)
                row.update(median_ms=st.median(t), min_ms=min(t), max_ms=max(t),
                           cv=(st.stdev(t) / m if len(t) > 1 else None),
                           load_min=min(r["loadavg_1m"]), load_max=max(r["loadavg_1m"]))
            for k in ("warmup_ms", "flagged", "true_pos", "false_pos", "recall", "missed_reacquire",
                      "exact_match", "checksum_mismatch"):
                if k in r:
                    row[k] = r[k]
            rows.append(row)

json.dump({"rows": rows, "meta": {f"{n}_{d}": j["meta"] for (n, d), j in sorted(cells.items())}},
          open(os.path.join(HERE, "results", f"summary_{RAW}.json"), "w"), indent=1)


def get(n, d, e, a):
    for r in rows:
        if (r["rows"], r["depth"], r["engine"], r["arm"]) == (n, d, e, a):
            return r


def fmt(r):
    if r is None:
        return "—"
    if r["status"] != "OK":
        return r["status"]
    cv = f"{100*r['cv']:.1f}%" if r.get("cv") is not None else "n/a"
    return f"{r['median_ms']:.1f} ({cv})"


Ns = sorted({n for n, _ in cells})
Ds = sorted({d for _, d in cells})
for e in ENGINES:
    print(f"\n### {e}: median ms (CV) per arm\n")
    print("| rows | depth | A_recursive | B_selfjoin | C_materialized | D_rootonly | A/B | A/C | load 1m |")
    print("|---|---|---|---|---|---|---|---|---|")
    for n in Ns:
        for d in Ds:
            rs = [get(n, d, e, a) for a in ARMS]
            if all(x is None for x in rs):
                continue
            ab = ac = "—"
            if rs[0] and rs[1] and rs[0]["status"] == rs[1]["status"] == "OK":
                ab = f"{rs[0]['median_ms']/rs[1]['median_ms']:.2f}"
            if rs[0] and rs[2] and rs[0]["status"] == rs[2]["status"] == "OK":
                ac = f"{rs[0]['median_ms']/rs[2]['median_ms']:.1f}"
            loads = [x[k] for x in rs if x and "load_min" in x for k in ("load_min", "load_max")]
            ld = f"{min(loads):.1f}–{max(loads):.1f}" if loads else "—"
            print(f"| {n:.0e} | {d} | " + " | ".join(fmt(x) for x in rs) + f" | {ab} | {ac} | {ld} |")

print("\n### Correctness per engine-arm (all cells)\n")
print("| engine | arm | cells OK | exact match | min recall | false pos total | missed reacquire total |")
print("|---|---|---|---|---|---|---|")
for e in ENGINES:
    for a in ARMS:
        rr = [r for r in rows if r["engine"] == e and r["arm"] == a and "recall" in r]
        if not rr:
            print(f"| {e} | {a} | 0 | — | — | — | — |")
            continue
        print(f"| {e} | {a} | {len(rr)} | {sum(bool(r['exact_match']) for r in rr)}/{len(rr)} | "
              f"{min(r['recall'] for r in rr):.3f} | {sum(r['false_pos'] for r in rr)} | "
              f"{sum(r['missed_reacquire'] for r in rr)} |")

print("\n### Hypothesis checks\n")
for e in ENGINES:
    for n in Ns:
        a2, a12 = get(n, 2, e, "A_recursive"), get(n, 12, e, "A_recursive")
        if a2 and a12 and a2["status"] == a12["status"] == "OK":
            print(f"H1 {e} N={n:.0e}: A d12/d2 = {a12['median_ms']/a2['median_ms']:.2f}")
        bs = [get(n, d, e, "B_selfjoin") for d in Ds]
        bs = [b for b in bs if b and b["status"] == "OK"]
        if len(bs) >= 2:
            meds = [b["median_ms"] for b in bs]
            print(f"H2 {e} N={n:.0e}: B max/min across depth = {max(meds)/min(meds):.2f} "
                  f"(max CV {100*max(b['cv'] or 0 for b in bs):.1f}%)")
    a, b = get(10_000_000, 12, e, "A_recursive"), get(10_000_000, 12, e, "B_selfjoin")
    if a and b and a["status"] == b["status"] == "OK":
        print(f"H3 {e}: A/B at 1e7 d12 = {a['median_ms']/b['median_ms']:.2f}")
