"""Aggregate the v3 raw JSON into results/v3/scorecard.json: per-trial three-arm gate,
freshness (per-trial p50, pooled p50, CV of trial medians), mid-run moving parts, the R1
fault, and the three complexity axes used by the frozen decision rules. S's recovery steps
(4 = S1 2 + S2 2) are the dated v2 result, since B and S faults are not re-run in v3."""
import json
import os
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V3 = os.path.join(ROOT, "results", "v3")
ARMS = ["B", "S", "R"]
V2_STEPS = {"B": 3, "S": 4}  # RESULTS-v2-2026-11-03: B1 1 + B2 0 + B3 2; S1 2 + S2 2


def load(p):
    return json.load(open(p)) if os.path.exists(p) else None


def trial_block(label):
    d = os.path.join(V3, label)
    cmp, lat, smp = load(f"{d}/compare.json"), load(f"{d}/latency.json"), load(f"{d}/samples-summary.json")
    if not cmp:
        return None
    rows = [json.loads(x) for x in open(f"{d}/alerts-risingwave.jsonl")] if os.path.exists(
        f"{d}/alerts-risingwave.jsonl") else []
    rs, rf = (lat or {}).get("replay_start_epoch"), (lat or {}).get("replay_factor")
    decomp = None
    if rows and rs:
        eng = sorted(r["rw_timestamp"] / 1000 - (rs + (r["window_start"] + 60 - 1767225600) / rf) for r in rows)
        adp = sorted(r["alert_emit_wall_ts"] - r["rw_timestamp"] / 1000 for r in rows)
        decomp = {"window_close_to_rw_commit_timestamp_p50_s": round(statistics.median(eng), 4),
                  "window_close_to_rw_commit_timestamp_min_max_s": [round(eng[0], 4), round(eng[-1], 4)],
                  "rw_commit_timestamp_to_drain_write_p50_s": round(statistics.median(adp), 4)}
    return {"gate_pass": cmp["gate_pass"],
            "arms": {a: {k: cmp["arms"][a][k] for k in ("n_distinct_keys", "n_missing", "n_extra", "n_duplicate_keys")}
                     for a in ARMS},
            "latency": {a: lat[a]["summary"] for a in ARMS} if lat else None,
            "latency_samples": {a: [s["latency_s"] for s in lat[a]["samples"]] for a in ARMS} if lat else None,
            "r_latency_decomposition": decomp,
            "moving_parts": smp,
            "risingwave_drain": load(f"{d}/risingwave-drain-state.json"),
            "stream_raw": load(f"{d}/stream-raw.json"),
            "risingwave_deploy": load(f"{d}/risingwave-deploy.json")}


def main():
    sc = {"trials_20x": {n: trial_block(f"trial-20x-{n}") for n in (1, 2, 3)},
          "trial_1x": trial_block("trial-1x")}
    ts = [t for t in sc["trials_20x"].values() if t and t["latency"]]
    fr = {}
    for a in ARMS:
        meds = [t["latency"][a]["median_s"] for t in ts]
        pooled = sorted(x for t in ts for x in t["latency_samples"][a])
        fr[a] = {"trial_medians_s": meds,
                 "pooled_p50_s": round(statistics.median(pooled), 4) if pooled else None,
                 "cv_of_trial_medians_pct": round(100 * statistics.pstdev(meds) / statistics.mean(meds), 1)
                 if len(meds) > 1 else None,
                 "within_trial_cv_pct": [t["latency"][a]["cv_pct"] for t in ts]}
    sc["freshness_20x"] = fr
    mp = {}
    for a in ARMS:
        vals = [t["moving_parts"][a] for t in ts if t["moving_parts"]]
        mp[a] = {k: {"medians": [v[k]["median"] for v in vals], "maxes": [v[k]["max"] for v in vals]}
                 for k in ("n_containers", "n_in_container_processes", "engine_only", "engine_plus_sink")}
        mp[a]["comms_seen"] = vals[-1]["in_container_comms_seen"] if vals else None
    sc["moving_parts_20x"] = mp
    r1 = load(os.path.join(V3, "faults-scored", "R1", "result.json"))
    sc["faults"] = {"R1": r1}
    cx = load(os.path.join(V3, "complexity-v3.json"))
    eps = {a: statistics.median(mp[a]["engine_plus_sink"]["medians"]) if mp[a]["engine_plus_sink"]["medians"] else None
           for a in ARMS}
    steps = dict(V2_STEPS, R=r1["n_recovery_steps"] if r1 else None)
    sc["axes"] = {a: {"moving_parts_engine_plus_sink": eps[a],
                      "config_loc": cx["config_surface"][a]["total_loc"] if cx else None,
                      "recovery_steps": steps[a]} for a in ARMS}
    sc["axes_note"] = "B and S recovery steps are the dated v2 (2026-11-03) fault results; R's is v3 R1"
    json.dump(sc, open(os.path.join(V3, "scorecard.json"), "w"), indent=2, default=str)
    print(json.dumps({"axes": sc["axes"], "freshness": fr}, indent=1))


if __name__ == "__main__":
    main()
