#!/usr/bin/env python3
"""QUIET REPLICATION 2026-11-16: compare quiet results against 11-15 using the addendum's definitions.
Written after the freeze, during the engine passes, before any quiet result was read; it applies the frozen
definitions and adds none. Reads results/scores.json + raw_*.json (11-15) and results/quiet-2026-11-16/*.
Writes results/quiet-2026-11-16/comparison.json.   ../.venv/bin/python -B compare_quiet.py"""
import json, statistics, sys, time
sys.dont_write_bytecode = True
from pathlib import Path
from collections import Counter
HERE = Path(__file__).parent
R0, RQ = HERE / "results", HERE / "results" / "quiet-2026-11-16"
JUNE = HERE.parent / "engine-join-specialization" / "results"
ARMS = ["starrocks", "clickhouse_iceberg", "clickhouse_native", "trino"]
ANCH = ["tpch_q3", "tpch_q5", "tpch_q9", "tpch_q18", "tpch_q21", "soc_j1_dim_enrichment", "soc_j4_ioc_semijoin"]  # corrected 2026-11-16 after verification (was "soc_j4", which matched no anchor)
CRON = [(6 * 3600, 7.5 * 3600), (8 * 3600, 8.5 * 3600), (9.5 * 3600, 9.75 * 3600)]


def J(p): return json.loads(Path(p).read_text())


def in_cron(epoch):
    s = epoch % 86400
    return any(a <= s < b for a, b in CRON)


s0, sq = J(R0 / "scores.json"), J(RQ / "scores.json")
raw0 = {a: J(R0 / f"raw_{a}.json") for a in ARMS}
rawq = {a: J(RQ / f"raw_{a}.json") for a in ARMS if (RQ / f"raw_{a}.json").exists()}
out = {"generated_utc": time.strftime("%FT%TZ", time.gmtime())}

# gate 2: per-arm valid counts
g = {}
for a in ARMS:
    def cnt(raw, setname):
        qs = {k: v for k, v in raw["queries"].items() if v["set"] == setname}
        return sum(1 for v in qs.values() if v.get("matches_oracle")), sum(1 for v in qs.values() if "dnf" in v), len(qs)
    g[a] = {"1115": {s: cnt(raw0[a], s) for s in ("corpus", "anchor")},
            "quiet": {s: cnt(rawq[a], s) for s in ("corpus", "anchor")} if a in rawq else None}
    if a in rawq:
        dnf0 = {k for k, v in raw0[a]["queries"].items() if "dnf" in v}
        ok0 = {k for k, v in raw0[a]["queries"].items() if v.get("matches_oracle")}
        okq = {k for k, v in rawq[a]["queries"].items() if v.get("matches_oracle")}
        lost = sorted(ok0 - okq)
        g[a]["valid_in_1115_not_quiet"] = lost
        g[a]["valid_in_quiet_not_1115"] = sorted(okq - ok0)
        g[a]["gate2_pass"] = len([k for k in lost if k not in dnf0]) <= 1 and \
            all(abs(g[a]["1115"][s][0] - g[a]["quiet"][s][0]) <= 1 + sum(1 for k in dnf0 if k.startswith(s))
                for s in ("corpus", "anchor"))
out["gate2"] = g

# per-arm timing: medians quiet/1115 on queries valid in both, load stats over timed runs, cron executions
tim = {}
for a, rq in rawq.items():
    ratios, loads, cron, tstamps = [], [], 0, []
    for k, v in rq["queries"].items():
        for r in v["runs"]:
            if r.get("load") and len(r["load"]) >= 4:
                tstamps.append(r["load"][3])
                cron += in_cron(r["load"][3])
                if r["i"] > 0:
                    loads.append(r["load"][0])
        v0 = raw0[a]["queries"].get(k, {})
        if v.get("matches_oracle") and v0.get("matches_oracle"):
            ratios.append(v["median_s"] / v0["median_s"])
    loads0 = [r["load"][0] for v in raw0[a]["queries"].values() for r in v["runs"] if r["i"] > 0 and r.get("load")]
    tim[a] = {"n_both_valid": len(ratios), "median_ratio_quiet_over_1115": round(statistics.median(ratios), 3),
              "ratio_p10_p90": [round(sorted(ratios)[int(0.1 * (len(ratios) - 1))], 3), round(sorted(ratios)[int(0.9 * (len(ratios) - 1))], 3)],
              "load1_timed_quiet_min_med_max": [min(loads), statistics.median(loads), max(loads)],
              "load1_timed_1115_min_med_max": [min(loads0), statistics.median(loads0), max(loads0)],
              "executions_in_cron_window": cron,
              "first_last_utc": [time.strftime("%FT%TZ", time.gmtime(min(tstamps))), time.strftime("%FT%TZ", time.gmtime(max(tstamps)))]}
out["timing"] = tim

# decision-level comparison (primary universe truth)
t0, tq = s0["truth"], sq["truth"]
flips, outside, close = [], [], []
for key in sorted(set(t0) | set(tq)):
    if not key.startswith("corpus:"):
        continue
    a, b = t0.get(key), tq.get(key)
    if a is None or b is None:
        flips.append({"key": key, "1115": a and a["best"], "quiet": b and b["best"], "note": "truth missing on one date"})
        continue
    if a["best"] != b["best"]:
        flips.append({"key": key, "1115": a["best"], "quiet": b["best"], "1115_best_s": a["best_s"], "quiet_best_s": b["best_s"],
                      "1115_accept": a["accept"], "quiet_accept": b["accept"]})
    if a["best"] not in b["accept"]:
        outside.append(key)
    if key.endswith("|hot"):
        oks = sorted(x[1] for x in a["view"].values() if x[0] == "ok")
        if len(oks) >= 2 and oks[1] - oks[0] < 0.100:
            close.append({"key": key, "margin_ms_1115": round(1000 * (oks[1] - oks[0]), 1), "1115": a["best"], "quiet": b["best"],
                          "quiet_margin_ms": round(1000 * (sorted(x[1] for x in b["view"].values() if x[0] == "ok")[1] - b["best_s"]), 1)
                          if sum(1 for x in b["view"].values() if x[0] == "ok") >= 2 else None})
out["strict_winner_flips"] = {"n": len(flips), "hot": sum(f["key"].endswith("|hot") for f in flips),
                              "cold": sum(f["key"].endswith("|cold") for f in flips), "rows": flips}
out["1115_winner_outside_quiet_accept"] = {"n": len(outside), "keys": outside}
out["hot_close_decisions_lt100ms_1115"] = {"n": len(close), "same_winner_quiet": sum(c["1115"] == c["quiet"] for c in close), "rows": close}
# cliffs per decision
cl0 = {k: v["cliffs"] for k, v in t0.items() if v["cliffs"] and k.startswith("corpus")}
clq = {k: v["cliffs"] for k, v in tq.items() if v["cliffs"] and k.startswith("corpus")}
out["cliffs"] = {"1115": cl0, "quiet": clq}


def head(s):
    S2 = s["scorings"]["primary:S2"]
    rows = [r for r in S2["rows"] if r["set"] == "corpus"]
    cat = [f'{r["id"]}|{r["cell"]}' for r in rows if r["outcome"] == "catastrophic"]
    ex = [r for r in rows if r["id"] != "join_3to4_09"]
    acc_ex = {c: round(sum(r["outcome"] == "correct" for r in ex if r["cell"] == c) / sum(1 for r in ex if r["cell"] == c), 3) for c in ("hot", "cold")}
    b = s["baselines"]
    sr = b["primary:always_starrocks"]["cold"]
    stab = s["within_shape_winner_stability"]
    h5_fail = {c: {k: v["modal_share"] for k, v in stab[c].items() if v["n"] >= 4 and v["modal_share"] < 0.8} for c in ("hot", "cold")}
    ueba = [r for r in rows if r["family"] == "ueba_two_level" and r["cell"] == "cold"]
    return {"S1": s["scorings"]["primary:S1"]["corpus"], "S2": S2["corpus"], "S3": s["scorings"]["primary:S3"]["corpus"],
            "S2_catastrophic_as_scored": cat, "S2_catastrophic_registered_excl_09": [c for c in cat if not c.startswith("join_3to4_09")],
            "S2_acc_excl_09": acc_ex, "baselines": {k: {c: v.get(c) for c in ("hot", "cold")} for k, v in b.items() if k.startswith("primary")},
            "H1_holds": S2["corpus"]["hot"]["accuracy_tie_tolerant"] >= 0.9 and S2["corpus"]["cold"]["accuracy_tie_tolerant"] >= 0.9,
            "H2_holds": len(cat) == 0,
            "H3_holds": sr.get("catastrophic", 0) == 0 and sr["regret_mean_s"] <= 0.25, "H3_detail": sr,
            "H4": {"shapes": dict(Counter(r["shape"] for r in ueba)), "cold_best": dict(Counter(r["best"] for r in ueba)),
                   "outcomes": dict(Counter(r["outcome"] for r in ueba))},
            "H5_classes_below_0.8": h5_fail, "H5_holds": not (h5_fail["hot"] or h5_fail["cold"]),
            "within_shape_stability": stab, "S2_by_family": {f: {c: v[c]["accuracy_tie_tolerant"] for c in ("hot", "cold")} for f, v in S2["by_family"].items()}}


out["date_1115"], out["quiet"] = head(s0), head(sq)


# H6: anchor strict winners over the 4 arms, valid only; June from engine-join-specialization raw files
def anchor_winners(raws, okkey):
    w = {}
    for q in ANCH:
        ok = {}
        for a, r in raws.items():
            v = r["queries"].get(q) or r["queries"].get(f"anchor:{q}")
            if v and v.get("median_s") and v.get(okkey):
                ok[a] = v["median_s"]
        w[q] = (min(ok, key=ok.get), ok) if ok else (None, ok)
    return w


june = {a: J(JUNE / f"raw_{a}.json") for a in ARMS}
wj, w0, wq = anchor_winners(june, "matches_ground_truth"), anchor_winners(raw0, "matches_oracle"), anchor_winners(rawq, "matches_oracle")
q5n = rawq.get("clickhouse_native", {}).get("queries", {}).get("anchor:tpch_q5", {})
out["H6"] = {"june": {q: wj[q][0] for q in ANCH}, "1115": {q: w0[q][0] for q in ANCH}, "quiet": {q: wq[q][0] for q in ANCH},
             "quiet_match_june": sum(wq[q][0] == wj[q][0] for q in ANCH), "1115_match_june": sum(w0[q][0] == wj[q][0] for q in ANCH),
             "quiet_medians": {q: wq[q][1] for q in ANCH},
             "native_q5_quiet": {"dnf": q5n.get("dnf"), "median_s": q5n.get("median_s"), "runs": [{k: r.get(k) for k in ("i", "s", "err")} for r in q5n.get("runs", [])]}}
out["H6"]["H6_holds"] = bool(q5n.get("dnf")) and out["H6"]["quiet_match_june"] >= 6

# StarRocks attempts
srq = rawq.get("starrocks", {}).get("queries", {}).get("corpus:join_3to4_04", {})
main_att = [{"i": r["i"], "s": r["s"], "err": r.get("err", "")[:120]} for r in srq.get("runs", [])]
probe = J(RQ / "sr_attempts_probe.json") if (RQ / "sr_attempts_probe.json").exists() else {"runs": []}
fails = sum(1 for r in main_att if r["err"]) + sum(1 for r in probe["runs"] if r.get("err"))
out["starrocks_join_3to4_04"] = {"main_pass": main_att, "main_outcome": srq.get("dnf") or srq.get("median_s"),
                                 "probe": probe["runs"], "attempts": len(main_att) + len(probe["runs"]), "failures": fails}
(RQ / "comparison.json").write_text(json.dumps(out, indent=1, default=str))
for k in ("gate2", "timing", "strict_winner_flips", "1115_winner_outside_quiet_accept", "hot_close_decisions_lt100ms_1115", "H6", "starrocks_join_3to4_04"):
    v = out[k]
    print(k, json.dumps({kk: vv for kk, vv in v.items() if kk != "rows"} if isinstance(v, dict) else v, default=str)[:1500])
for d in ("date_1115", "quiet"):
    h = out[d]
    print(d, json.dumps({k: h[k] for k in ("S2", "S2_catastrophic_as_scored", "S2_catastrophic_registered_excl_09", "S2_acc_excl_09", "H1_holds", "H2_holds", "H3_holds", "H3_detail", "H4", "H5_classes_below_0.8")}, default=str))
