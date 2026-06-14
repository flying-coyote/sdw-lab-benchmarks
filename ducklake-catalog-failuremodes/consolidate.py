#!/usr/bin/env python3
"""Aggregate the per-arm BENCH-E result JSONs into results/summary.json — one place
that states each verified-real OPEN DuckLake issue and whether it reproduces on the
current stack vs the version it was filed against."""
import glob
import json
import os

HERE = os.path.dirname(__file__)
RES = os.path.join(HERE, "results")


def load(name):
    p = os.path.join(RES, name)
    return json.load(open(p)) if os.path.exists(p) else None


def main():
    e1 = load("e1.json")
    e2 = load("e2.json")
    e3_old = load("e3_v1.5.2.json")
    e3_new = load("e3_v1.5.3.json")

    arms = []
    if e1:
        arms.append({
            "arm": "E1", "issue": e1["issue"], "title": e1["issue_title"],
            "kind": e1["kind"], "verdict": e1["verdict"],
            "evidence": f"both commit orders: {e1['arms'][0]['deleted_range_survivors']} "
                        f"survivors vs {e1['arms'][0]['expected_survivors']} expected, "
                        f"no conflict raised",
            "run_versions": e1["run_versions"],
        })
    if e2:
        ctrl = next((p for p in e2["probes"] if p["n_cols"] == 1500), {})
        over = next((p for p in e2["probes"] if p["n_cols"] == 1700 and p["inlining_off"]), {})
        arms.append({
            "arm": "E2", "issue": e2["issue"], "title": e2["issue_title"],
            "kind": e2["kind"], "verdict": e2["verdict"],
            "evidence": f"1500 cols created={ctrl.get('created')}; 1700 cols (inlining off) "
                        f"-> {over.get('error')}",
            "run_versions": e2["run_versions"],
        })
    if e3_old and e3_new:
        verdict = "FIXED-BETWEEN-1.5.2-AND-1.5.3" if (
            e3_old["verdict"] == "PERSISTS" and e3_new["verdict"] == "NOT-REPRODUCED"
        ) else f"{e3_old['verdict']}/{e3_new['verdict']}"
        arms.append({
            "arm": "E3", "issue": e3_old["issue"], "title": e3_old["issue_title"],
            "kind": e3_old["kind"], "verdict": verdict,
            "evidence": {
                "duckdb_1.5.2": {
                    "ducklake": e3_old["run_versions"]["ducklake"],
                    "probe_wall_s": e3_old["probe_wall_s"],
                    "pool_timeout_fired": e3_old["pool_timeout_fired"],
                    "probe_error": e3_old["probe_error"],
                },
                "duckdb_1.5.3": {
                    "ducklake": e3_new["run_versions"]["ducklake"],
                    "probe_wall_s": e3_new["probe_wall_s"],
                    "pool_timeout_fired": e3_new["pool_timeout_fired"],
                },
            },
        })

    summary = {
        "bench": "BENCH-E — DuckLake catalog failure modes",
        "tier": "B",
        "host": "single host (Beelink 5800H, WSL2 48GB/14t)",
        "discipline": "all three issue numbers verified real + OPEN at duckdb/ducklake "
                      "before reproduction; versions recorded per arm; verify-don't-assume",
        "arms": arms,
        "headline": "2 of 3 verified-OPEN catalog bugs reproduce on the current stack "
                    "(DuckDB 1.5.3 + DuckLake e6a3bd0a); the pool-timeout (#1031, labeled "
                    "'PR submitted') reproduces on 1.5.2 and is fixed on 1.5.3.",
    }
    out = os.path.join(RES, "summary.json")
    with open(out, "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
