"""Aggregate the v2 raw JSON into results/v2/scorecard.json: per-trial gate, freshness
(per-trial p50, pooled p50, CV of trial medians), mid-run moving parts, fault battery,
and the three complexity axes per arm used by the frozen decision rules."""
import glob
import json
import os
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2 = os.path.join(ROOT, "results", "v2")
ARMS = ["B", "S", "F", "BC"]


def load(p):
    return json.load(open(p)) if os.path.exists(p) else None


def trial_block(label):
    d = os.path.join(V2, label)
    cmp, lat, smp = load(f"{d}/compare.json"), load(f"{d}/latency.json"), load(f"{d}/samples-summary.json")
    if not cmp:
        return None
    return {"gate_pass": cmp["gate_pass"],
            "arms": {a: {k: cmp["arms"][a][k] for k in ("n_distinct_keys", "n_missing", "n_extra", "n_duplicate_keys")}
                     for a in ARMS},
            "latency": {a: lat[a]["summary"] for a in ARMS} if lat else None,
            "latency_samples": {a: [s["latency_s"] for s in lat[a]["samples"]] for a in ARMS} if lat else None,
            "moving_parts": smp,
            "feldera_drain": load(f"{d}/feldera-drain-state.json"),
            "stream_raw": load(f"{d}/stream-raw.json"),
            "feldera_deploy": load(f"{d}/feldera-deploy.json")}


def main():
    sc = {"trials_20x": {}, "trial_1x": None}
    for n in (1, 2, 3):
        sc["trials_20x"][n] = trial_block(f"trial-20x-{n}")
    sc["trial_1x"] = trial_block("trial-1x")
    fr = {}
    ts = [t for t in sc["trials_20x"].values() if t and t["latency"]]
    for a in ARMS:
        meds = [t["latency"][a]["median_s"] for t in ts]
        pooled = sorted(x for t in ts for x in t["latency_samples"][a])
        fr[a] = {"trial_medians_s": meds,
                 "pooled_p50_s": round(statistics.median(pooled), 4) if pooled else None,
                 "median_of_trial_medians_s": round(statistics.median(meds), 4) if meds else None,
                 "cv_of_trial_medians_pct": round(100 * statistics.pstdev(meds) / statistics.mean(meds), 1)
                 if len(meds) > 1 else None,
                 "within_trial_cv_pct": [t["latency"][a]["cv_pct"] for t in ts]}
        if a in ("B", "BC") and fr[a]["pooled_p50_s"] is not None:
            fr[a]["pooled_p50_real_time_equivalent_s"] = round(fr[a]["pooled_p50_s"] * 20, 2)
    sc["freshness_20x"] = fr
    mp = {}
    for a in ARMS:
        vals = [t["moving_parts"][a] for t in ts if t["moving_parts"]]
        mp[a] = {k: {"medians": [v[k]["median"] for v in vals], "maxes": [v[k]["max"] for v in vals]}
                 for k in ("n_containers", "n_in_container_processes", "engine_only", "engine_plus_sink")}
        mp[a]["comms_seen"] = vals[-1]["in_container_comms_seen"] if vals else None
    sc["moving_parts_20x"] = mp
    faults = {}
    for p in sorted(glob.glob(os.path.join(V2, "faults-scored", "*", "result.json"))):
        r = json.load(open(p))
        faults[r["fault"]] = r
    sc["faults"] = {k: {kk: v.get(kk) for kk in (
        "n_recovery_steps", "step_count_method", "wall_kill_to_infra_restored_s", "wall_recovery_script_s",
        "wall_kill_to_new_correct_alert_s", "output_exists", "output_grew_after_recovery", "rows_at_recovery_done",
        "rows_at_end", "post_recovery", "raw_engine_duplicates", "recompiled", "job_exit_code_after_truncated_file",
        "window_under_fault_has_gt_alert", "flink_job_restarts_in_jm_log")} for k, v in faults.items()}
    steps = lambda ids: sum(faults[i]["n_recovery_steps"] for i in ids if i in faults)  # noqa: E731
    cx = load(os.path.join(V2, "complexity-v2.json"))
    eps = {a: statistics.median(mp[a]["engine_plus_sink"]["medians"]) if mp[a]["engine_plus_sink"]["medians"] else None
           for a in ARMS}
    sc["axes"] = {a: {"moving_parts_engine_plus_sink": eps[a],
                      "config_loc": cx["config_surface"][a]["total_loc"] if cx else None,
                      "recovery_steps": steps({"B": ["B1", "B2", "B3"], "S": ["S1", "S2"],
                                               "F": ["F1", "F2"], "BC": ["BC1"]}[a])} for a in ARMS}
    json.dump(sc, open(os.path.join(V2, "scorecard.json"), "w"), indent=2)
    print(json.dumps({"axes": sc["axes"], "freshness": {a: {k: v for k, v in fr[a].items()} for a in ARMS}}, indent=1))


if __name__ == "__main__":
    main()
