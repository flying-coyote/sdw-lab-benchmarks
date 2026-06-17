#!/usr/bin/env python3
"""BENCH-C v2.1 Arm #1 — score the agentic execute-and-self-correct text-to-SQL arm.

Reads the agentic predictions (3 tiers, {qid, trial, sql}) produced by the agentic generation
workflow, executes each FINAL SQL against the same raw Store F tables the one-shot arm uses, and
scores through the ONE shared scorer (scoring.classify, byte-identical) — reusing
bench_c_v2_headtohead.score_llm_arm so the agentic arm is scored identically to its control. The
CONTROL is the one-shot `text_to_sql` arm already scored in results/v2_headtohead{,_haiku,_opus}.json.

Pre-registered falsifier (BENCH-C-PREREGISTRATION-v2.1-arm-extension.md): execution feedback reduces
LOUD failures but does NOT substantially reduce TAIL SILENT failures (a wrong-but-runnable aggregate
returns plausible rows, so the loop has no error signal to correct against). If the agentic tail
silent rate drops materially below the one-shot tail silent rate, self-correction fixes silent error.

Usage:
  ONTOP_HOME=~/tools/ontop-cli python3 bench_c_v2_1_agentic_score.py \
      --agentic _frontier/v2_1/agentic_haiku.json _frontier/v2_1/agentic_sonnet.json _frontier/v2_1/agentic_opus.json
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bench_c_v2_config as CFG  # noqa: E402
import bench_c_v2_headtohead as H  # noqa: E402  (reuse score_llm_arm + QMETA + truth loader)

LOOKUP = sorted(CFG.LOOKUP_CLASS)
TAIL = [q for q in sorted(CFG.TAIL_CLASS) if q != "A4"]
CONTROL_FILES = {"haiku": "results/v2_headtohead_haiku.json",
                 "sonnet": "results/v2_headtohead.json",
                 "opus": "results/v2_headtohead_opus.json"}


def duck_raw():
    import duckdb
    c = duckdb.connect()
    for t in ("auth", "session", "network", "dns", "process", "api"):
        c.execute(f"CREATE VIEW f_{t} AS SELECT * FROM read_parquet('{CFG.STORE_F}/{t}.parquet')")
    c.execute(f"CREATE VIEW f_asset AS SELECT * FROM read_parquet('{CFG.STORE_F_V2_ASSET}')")
    return c


def tier_of(path):
    name = os.path.basename(path).lower()
    for t in ("haiku", "sonnet", "opus"):
        if t in name:
            return t
    return name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agentic", nargs="+", required=True, help="agentic predictions JSONs (per tier)")
    ap.add_argument("--out", default=os.path.join(HERE, "results", "v2_1_agentic.json"))
    args = ap.parse_args()

    truth = H.load_truth_v2()
    con = duck_raw()

    def t2s_cells(p):
        sql = p.get("sql", "")
        if not sql.strip():
            return None
        try:
            rows = con.execute(sql).fetchall()
        except Exception:
            return None
        return [str(c) for r in rows for c in r]

    report = {
        "bench": "BENCH-C v2.1 Arm #1 — agentic execute-and-self-correct text-to-SQL vs one-shot control",
        "hypotheses": ["H-CONCEPT-GRAPH-03"], "tier": "B",
        "k_rounds": 5, "a4_excluded_ill_posed": True,
        "scorer": "scoring.classify (shared, byte-identical) via bench_c_v2_headtohead.score_llm_arm",
        "control": "one-shot text_to_sql arm (results/v2_headtohead*.json)",
        "tiers": {},
    }
    for path in args.agentic:
        tier = tier_of(path)
        preds = json.load(open(path))
        agp = preds.get("text2sql", preds.get("agentic", []))
        agentic = {
            "lookup": H.score_llm_arm(agp, truth, t2s_cells, qids=set(LOOKUP)),
            "tail": H.score_llm_arm(agp, truth, t2s_cells, qids=set(TAIL)),
            "rounds_used": [p.get("rounds_used") for p in agp if "rounds_used" in p],
        }
        # control (one-shot) read back from the v2 head-to-head
        ctrl = json.load(open(os.path.join(HERE, CONTROL_FILES[tier])))["arms"]["text_to_sql"]
        report["tiers"][tier] = {
            "agentic": agentic,
            "control_oneshot": {"lookup": ctrl["lookup"], "tail": ctrl["tail"]},
        }
    con.close()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(report, open(args.out, "w"), indent=2, sort_keys=True, default=str)

    # console: the falsifier comparison on the TAIL
    print("=== BENCH-C v2.1 Arm #1 agentic vs one-shot (TAIL silent rate — the falsifier) ===")
    for tier in ("haiku", "sonnet", "opus"):
        if tier not in report["tiers"]:
            continue
        a = report["tiers"][tier]["agentic"]["tail"]["trial_rates"]
        c = report["tiers"][tier]["control_oneshot"]["tail"]["trial_rates"]
        print(f"  {tier:7s}  agentic  c/s/l = {a['correct']['mean']}/{a['silent']['mean']}/{a['loud']['mean']}"
              f"   ||  one-shot  c/s/l = {c['correct']['mean']}/{c['silent']['mean']}/{c['loud']['mean']}")
    print(f"\n-> {args.out}")
    return report


if __name__ == "__main__":
    main()
