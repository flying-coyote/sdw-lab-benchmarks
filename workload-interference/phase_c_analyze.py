#!/usr/bin/env python3
"""#23 Phase C analyzer — combine the 3 independent knee observations into a
reproducibility verdict, plus the starrocks_mv (P5) result.

The 3 runs (the README's "3x reproduction is across runs"):
  run-1 = extend-ladder (full ladder 0.125->64; documented in INTERFERENCE-FINDINGS).
  run-2 = phase-C rep3 (knee ladder 16/32/64; salvaged — reps 1-2 were lost to a
          capture bug, docker run without -i, so phase-C yielded one clean rep).
  run-3 = the clean single-rep finish pass (knee ladder 16/32/64; host-side capture).
A knee is claimable when all 3 runs trip the stop rule at the SAME ladder step. The p95
band shows run-to-run spread so no single value is quoted as stable.

Reads _work/phase_c/run2_<arm>.json + run3_<arm>.json (+ mv_starrocks_mv.json), folds in
run-1 as documented constants, writes PHASE-C-SUMMARY.json + PHASE-C-FINDINGS-2026-06-14.md
to the bench dir (results/ is root-owned and unwritable in this session)."""
import json
import statistics
from pathlib import Path

HERE = Path(__file__).parent
PC = HERE / "_work" / "phase_c"
ARMS = ["clickhouse_iceberg", "clickhouse_native", "starrocks", "dremio"]

# run-1 (extend-ladder) — from the committed INTERFERENCE-FINDINGS-2026-06-14.md table.
# knee demand + the p95 at the 64x step; the ladder there was flat through 16-32x.
RUN1 = {
    "clickhouse_iceberg": {"knee": 64.0, "p95_64": 4.05},
    "clickhouse_native":  {"knee": 64.0, "p95_64": 3.11},
    "starrocks":          {"knee": 64.0, "p95_64": 4.93},
    "dremio":             {"knee": 32.0, "p95_64": 5.78},  # findings: dremio knees ~16-32x
}


def load(tag, arm):
    p = PC / f"{tag}_{arm}.json"
    return json.loads(p.read_text()) if p.exists() else None


def step_p95(record, demand):
    for s in record.get("ladder", []):
        if abs(s["demand"] - demand) < 1e-9:
            return s["probe"].get("p95_s")
    return None


def knee_of(record):
    return (record.get("knee") or {}).get("demand")


def main():
    arms_out = {}
    md = ["# Phase C — knee 3x reproduction + starrocks_mv (P5) — 2026-06-14", "",
          "Tier B, single host (Beelink 5800H, WSL2 48 GB/14t, cpuset 12/2). A knee is "
          "claimable only when all 3 independent runs trip the mechanical stop rule at the "
          "SAME ladder step (README). run-1 = extend-ladder; run-2 = phase-C rep3 (salvaged; "
          "reps 1-2 lost to a `docker run` missing `-i` so its heredoc capture never ran); "
          "run-3 = clean finish pass (host-side capture).", ""]

    for arm in ARMS:
        r2 = load("run2", arm)
        r3 = load("run3", arm)
        knees = [RUN1[arm]["knee"]]
        if r2: knees.append(knee_of(r2["record"]))
        if r3: knees.append(knee_of(r3["record"]))
        present = [k for k in knees if k is not None]
        reproduced = len(present) == 3 and len(set(present)) == 1
        # p95 band per step (run2+run3 full; run1 only at 64x)
        band = {}
        for d in (16.0, 32.0, 64.0):
            vals = []
            for r in (r2, r3):
                if r:
                    v = step_p95(r["record"], d)
                    if v is not None:
                        vals.append(v)
            if d == 64.0:
                vals.append(RUN1[arm]["p95_64"])
            if vals:
                band[str(d)] = {"min_s": round(min(vals), 3),
                                "median_s": round(statistics.median(vals), 3),
                                "max_s": round(max(vals), 3), "n": len(vals)}
        arms_out[arm] = {"knee_per_run": knees, "knee_reproduced_3x": reproduced,
                         "reproduced_knee_demand": present[0] if reproduced else None,
                         "p95_band_by_step": band}
        md.append(f"## {arm}")
        md.append("")
        verdict = (f"**knee reproduced 3× at U={present[0]}**" if reproduced
                   else f"knee NOT 3×-confirmed (per-run: {knees})")
        md.append(f"- knee per run [run1, run2, run3]: {knees} — {verdict}")
        md.append("")
        md.append("| step (U) | p95 min | p95 median | p95 max | n runs |")
        md.append("|--:|--:|--:|--:|--:|")
        for d in ("16.0", "32.0", "64.0"):
            b = band.get(d)
            if b:
                md.append(f"| {d} | {b['min_s']} s | {b['median_s']} s | {b['max_s']} s | {b['n']} |")
        md.append("")

    # starrocks_mv (P5)
    mv = load("mv", "starrocks_mv")
    p5 = None
    if mv:
        rec = mv["record"]
        mv_knee = knee_of(rec)
        base_knee = arms_out.get("starrocks", {}).get("reproduced_knee_demand") or 64.0
        # ladder steps: 16 32 64 128 256; >=2 steps right of 64 = 256
        steps_right = None
        if mv_knee is not None and base_knee:
            ladder = [16.0, 32.0, 64.0, 128.0, 256.0]
            try:
                steps_right = ladder.index(mv_knee) - ladder.index(base_knee)
            except ValueError:
                steps_right = None
        elif mv_knee is None:
            steps_right = "no knee through 256x (>= the ladder top)"
        p5 = {"scored": rec.get("scored"), "mv_knee_demand": mv_knee,
              "base_starrocks_knee": base_knee, "steps_shifted_right": steps_right,
              "p95_by_step": {str(s["demand"]): (round(s["probe"]["p95_s"], 3)
                              if s["probe"].get("p95_s") is not None else None)
                              for s in rec.get("ladder", [])},
              "verdict_P5_ge2_right": (isinstance(steps_right, int) and steps_right >= 2)
                                      or (isinstance(steps_right, str))}
        md.append("## starrocks_mv (P5 — does the MV shift the knee right >=2 steps?)")
        md.append("")
        md.append(f"- scored: {p5['scored']}  · base starrocks knee U={base_knee}  · "
                  f"MV knee U={mv_knee}  · shift: {steps_right}")
        md.append(f"- P5 (>=2 steps right): **{p5['verdict_P5_ge2_right']}**")
        md.append(f"- p95 by step: {p5['p95_by_step']}")
        md.append("")

    summary = {"bench": "workload-interference", "phase": "C — knee 3x repro + P5",
               "tier": "B", "host": "Beelink 5800H, WSL2 48GB/14t (cpuset 12/2)",
               "arms": arms_out, "starrocks_mv_P5": p5}
    (HERE / "PHASE-C-SUMMARY.json").write_text(json.dumps(summary, indent=2))
    (HERE / "PHASE-C-FINDINGS-2026-06-14.md").write_text("\n".join(md))
    print(json.dumps(summary, indent=2))
    print("\nwrote PHASE-C-SUMMARY.json + PHASE-C-FINDINGS-2026-06-14.md")


if __name__ == "__main__":
    main()
