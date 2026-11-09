"""Score R5: per rule x mutation x server, from the sigma path outputs + labels. Writes results/scores.json."""
import json, statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
labels = json.loads((HERE / "events/labels.json").read_text())
paths = {p: json.loads((HERE / f"results/sigma-path-{p}.json").read_text()) for p in "abc"}
live = json.loads((HERE / "snapshots/live.json").read_text())
MUT = ["P1_rug_pull", "P2_hidden_instruction", "P3_param_widening",
       "B1_wording_fix", "B2_clarification", "B3_new_tool", "B4_schema_narrowing", "B5_key_reorder"]
servers = sorted({l["server"] for l in labels.values()})


def fired(uids, var):
    """set of (server, mutation) where any event of that mutation matched"""
    return {(labels[u]["server"], labels[u]["mutation"]) for u in uids if labels[u]["variant"] == var}


out = {"agreement": {}, "per_rule": {}, "latency": {}}
rules = sorted(paths["a"]["rules"])
for r in rules:
    sets = {}
    for p in "abc":
        res = paths[p]["rules"][r]["results"]
        sets[p] = {v: (sorted(x["uids"]) if x["ok"] else "ERROR") for v, x in res.items()}
    out["agreement"][r] = {"a_eq_b": sets["a"] == sets["b"], "c_status": "executed" if sets["c"]["D1"] != "ERROR" else "refused-at-execution"}
    for var in ("D1", "D0"):
        f = fired(paths["a"]["rules"][r]["results"][var]["uids"], var)
        grid = {m: [s for s in servers if (s, m) in f] for m in MUT}
        tp = sum(len(grid[m]) for m in MUT if m.startswith("P"))
        fp = sum(len(grid[m]) for m in MUT if m.startswith("B"))
        out["per_rule"].setdefault(r, {})[var] = {"detected": f"{tp} of {3*len(servers)}", "benign_fired": f"{fp} of {5*len(servers)}", "grid": grid}

# composite = S3 or S4 or S5
for var in ("D1", "D0"):
    f = set()
    for r in ("s3_hidden_instruction", "s4_description_rewrite", "s5_schema_widening"):
        f |= fired(paths["a"]["rules"][r]["results"][var]["uids"], var)
    grid = {m: [s for s in servers if (s, m) in f] for m in MUT}
    out["per_rule"].setdefault("composite_s3_s4_s5", {})[var] = {
        "detected": f"{sum(len(grid[m]) for m in MUT if m.startswith('P'))} of {3*len(servers)}",
        "benign_fired": f"{sum(len(grid[m]) for m in MUT if m.startswith('B'))} of {5*len(servers)}", "grid": grid}

for s in servers:
    xs = [x["list_ms"] for x in live if x["server"] == s]
    per_run = [statistics.median([x["list_ms"] for x in live if x["server"] == s and x["run"] == r]) for r in (1, 2, 3)]
    out["latency"][s] = {"n": len(xs), "median_ms": round(statistics.median(xs), 3),
                         "cv_pct": round(100 * statistics.stdev(xs) / statistics.mean(xs), 1),
                         "min_ms": round(min(xs), 3), "max_ms": round(max(xs), 3),
                         "per_run_median_ms": [round(v, 3) for v in per_run],
                         "init_ms_per_run": [round(x["init_ms"], 1) for x in live if x["server"] == s and x["snapshot"] == 0],
                         "tools": len(live[[x["server"] for x in live].index(s)]["tools"])}
(HERE / "results/scores.json").write_text(json.dumps(out, indent=1))
for r, v in out["per_rule"].items():
    print(r, {k: (x["detected"], x["benign_fired"]) for k, x in v.items()})
    print("   D1 grid", {m: len(s) for m, s in v["D1"]["grid"].items()})
print(json.dumps(out["agreement"]))
print(json.dumps(out["latency"]))
