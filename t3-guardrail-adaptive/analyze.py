#!/usr/bin/env python3
"""Metrics per (model, set, transform): rates with Wilson 95% CIs, paired-bootstrap drops, truncation,
throughput, stability. Writes results/summary.json and results/tables.md."""
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
SEED = 20261109
Z = 1.959963984540054


def wilson(k, n):
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def paired_boot(a, b, rng, n=2000):
    """95% percentile interval for mean(a) - mean(b) over paired items."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    m = len(a)
    idx = rng.integers(0, m, size=(n, m))
    d = (a[idx].mean(axis=1) - b[idx].mean(axis=1))
    return float(a.mean() - b.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def load_scores(path):
    meta, rows, end = None, [], None
    with path.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if "_meta" in r:
                meta = r["_meta"]
            elif "_end" in r:
                end = r["_end"]
            else:
                rows.append(r)
    return meta, rows, end


def main():
    summary = {"models": {}, "stability": {}}
    md = []
    # group score files per model (the split design writes several files per model; rows are deterministic,
    # so duplicates across files are identical and the first occurrence is kept)
    files_by_model = defaultdict(list)
    for path in sorted(RES.glob("scores-*.jsonl")):
        meta, rows, end = load_scores(path)
        files_by_model[meta["model_id"]].append((path, meta, rows, end))
    for model, parts in files_by_model.items():
        meta = parts[0][1]
        rng = np.random.default_rng(SEED)
        by = defaultdict(dict)  # (set, transform) -> {src_idx: row}
        strata = defaultdict(dict)
        rows = []
        wall = 0.0
        n_scored = 0
        for path, m, rws, end in parts:
            rows += rws
            if end:
                wall += end["wall_s"]
                n_scored += end["n_scored"]
        for r in rows:
            if r["rep"] != 0:
                continue
            key = (r["set"], r["transform"])
            if str(r["src_idx"]) in by[key]:
                continue
            by[key][str(r["src_idx"])] = r
            strata[(r["set"], r["stratum"], r["transform"])][str(r["src_idx"])] = r
        transforms = sorted({t for _, t in by})
        sets = sorted({s for s, _ in by})
        end = {"wall_s": round(wall, 1), "n_scored": n_scored, "files": [str(p_.name) for p_, *_ in parts]}
        out = {"meta": meta, "end": end, "cells": {}, "strata": {}, "throughput": {}}
        # cells
        for s in sets:
            base = by[(s, "T0")]
            for t in transforms:
                cell = by.get((s, t))
                if not cell:
                    continue
                keys = sorted(k for k in cell if k in base)
                flags = [cell[k]["flag"] for k in keys]
                k_ = sum(flags)
                n = len(flags)
                p, lo, hi = wilson(k_, n)
                b_flags = [base[k]["flag"] for k in keys]
                if t == "T0":
                    drop = (0.0, 0.0, 0.0)
                else:
                    drop = paired_boot(b_flags, flags, rng)  # T0 - Tk (positive = fewer flags under transform)
                out["cells"][f"{s}|{t}"] = {
                    "n": n, "flagged": k_, "rate": p, "lo": lo, "hi": hi,
                    "delta_T0_minus_Tk": drop[0], "delta_lo": drop[1], "delta_hi": drop[2],
                    "mean_p_pos": statistics.fmean(cell[k]["p_pos"] for k in keys),
                    "truncated_share": sum(cell[k]["truncated"] for k in keys) / n,
                    "median_tokens": statistics.median(cell[k]["n_tok"] for k in keys),
                }
        for (s, st, t), cell in strata.items():
            if s == "B2-notinject":
                k_ = sum(r["flag"] for r in cell.values())
                n = len(cell)
                p, lo, hi = wilson(k_, n)
                out["strata"][f"{s}|{st}|{t}"] = {"n": n, "flagged": k_, "rate": p, "lo": lo, "hi": hi}
        # throughput per transform (items/s per batch)
        per_t = defaultdict(list)
        seen = set()
        for r in rows:
            key = (r["rep"], r["set"], r["transform"], r["batch_ms"], r["batch_n"], r["src_idx"])
            # one entry per batch: dedupe on (rep, transform, batch_ms) approx
            bk = (r["rep"], r["transform"], r["batch_ms"])
            if bk in seen:
                continue
            seen.add(bk)
            per_t[r["transform"]].append(r["batch_n"] / (r["batch_ms"] / 1000))
        for t, v in per_t.items():
            out["throughput"][t] = {"batches": len(v), "items_per_s_median": statistics.median(v),
                                    "items_per_s_cv": statistics.pstdev(v) / statistics.fmean(v) if len(v) > 1 else 0.0}
        # post-hoc (not pre-registered): discrimination under each transform, J = TPR(attack set) - FPR(benign set),
        # for the clean short-prompt pair A2 (Gandalf) vs B3 (Dolly) and pooled over all attack vs all benign cells.
        out["discrimination"] = {}
        for t in transforms:
            a2 = out["cells"].get(f"A2-gandalf|{t}")
            b3 = out["cells"].get(f"B3-dolly|{t}")
            att = [c for k, c in out["cells"].items() if k.startswith("A") and k.endswith(f"|{t}")]
            ben = [c for k, c in out["cells"].items() if k.startswith("B") and k.endswith(f"|{t}")]
            tpr_pool = sum(c["flagged"] for c in att) / max(1, sum(c["n"] for c in att))
            fpr_pool = sum(c["flagged"] for c in ben) / max(1, sum(c["n"] for c in ben))
            out["discrimination"][t] = {
                "J_gandalf_vs_dolly": (a2["rate"] - b3["rate"]) if a2 and b3 else None,
                "tpr_pooled": tpr_pool, "fpr_pooled": fpr_pool, "J_pooled": tpr_pool - fpr_pool,
                "n_attack": sum(c["n"] for c in att), "n_benign": sum(c["n"] for c in ben)}
        summary["models"][model] = out

        # markdown tables
        md.append(f"\n### {model} (`{meta['repo']}` @ `{meta['revision'][:8]}`)\n")
        md.append("Rate = share flagged as attack. Attack sets (A*): detection rate. Benign sets (B*): false-positive rate. "
                  "Δ = rate(T0) − rate(Tk) on the same items, paired bootstrap 95%. trunc = share of items over 512 tokens.\n")
        md.append("| set | T | n | flagged | rate [95% CI] | Δ vs T0 [95% CI] | mean p | trunc |")
        md.append("|---|---|---|---|---|---|---|---|")
        for s in sets:
            for t in transforms:
                c = out["cells"].get(f"{s}|{t}")
                if not c:
                    continue
                d = "" if t == "T0" else f"{c['delta_T0_minus_Tk']:+.3f} [{c['delta_lo']:+.3f}, {c['delta_hi']:+.3f}]"
                md.append(f"| {s} | {t} | {c['n']} | {c['flagged']} | {c['rate']:.3f} [{c['lo']:.3f}, {c['hi']:.3f}] | {d} | {c['mean_p_pos']:.3f} | {c['truncated_share']:.2f} |")
        if out["strata"]:
            md.append(f"\nNotInject strata, {model} (T0 only):\n")
            md.append("| subset | n | flagged | FPR [95% CI] |")
            md.append("|---|---|---|---|")
            for st in ("NotInject_one", "NotInject_two", "NotInject_three"):
                c = out["strata"].get(f"B2-notinject|{st}|T0")
                if c:
                    md.append(f"| {st} | {c['n']} | {c['flagged']} | {c['rate']:.3f} [{c['lo']:.3f}, {c['hi']:.3f}] |")
        md.append(f"\nDiscrimination under each transform, {model} (post-hoc, not pre-registered): J = detection − false-positive rate.\n")
        md.append("| T | TPR Gandalf | FPR Dolly | J (Gandalf−Dolly) | pooled TPR (n) | pooled FPR (n) | pooled J |")
        md.append("|---|---|---|---|---|---|---|")
        for t, d in sorted(out["discrimination"].items()):
            a2 = out["cells"].get(f"A2-gandalf|{t}"); b3 = out["cells"].get(f"B3-dolly|{t}")
            md.append(f"| {t} | {a2['rate'] if a2 else float('nan'):.3f} | {b3['rate'] if b3 else float('nan'):.3f} | "
                      f"{d['J_gandalf_vs_dolly'] if d['J_gandalf_vs_dolly'] is not None else float('nan'):+.3f} | "
                      f"{d['tpr_pooled']:.3f} ({d['n_attack']}) | {d['fpr_pooled']:.3f} ({d['n_benign']}) | {d['J_pooled']:+.3f} |")
        md.append(f"\nThroughput under contention (4 threads, nice 10), {model}: " + "; ".join(
            f"{t} median {v['items_per_s_median']:.1f} items/s (CV {v['items_per_s_cv']:.0%}, {v['batches']} batches)"
            for t, v in sorted(out["throughput"].items())) + f". Wall {end['wall_s'] if end else '?'} s for {end['n_scored'] if end else '?'} forward passes.\n")

    # stability files
    for path in sorted(RES.glob("stability-*.jsonl")):
        meta, rows, end = load_scores(path)
        model = meta["model_id"]
        per_item = defaultdict(list)
        for r in rows:
            per_item[(r["set"], str(r["src_idx"]), r["transform"])].append((r["flag"], r["p_pos"]))
        flips = 0
        maxdp = 0.0
        n_items = 0
        reps = meta["repeat"]
        for k, v in per_item.items():
            if len(v) != reps:
                continue
            n_items += 1
            fl = [f for f, _ in v]
            modal = max(set(fl), key=fl.count)
            flips += sum(1 for f in fl if f != modal)
            ps = [p for _, p in v]
            maxdp = max(maxdp, max(ps) - min(ps))
        summary["stability"][model] = {"repeats": reps, "items": n_items, "verdicts": n_items * reps,
                                       "flips": flips, "flip_rate": flips / (n_items * reps) if n_items else None,
                                       "max_abs_p_diff": maxdp}
        md.append(f"\nStability, {model}: {reps} repeats × {n_items} items; verdict flips {flips} of {n_items * reps} "
                  f"(flip rate {flips / (n_items * reps) if n_items else float('nan'):.4f}); max |Δp| {maxdp:.2e}.")

    (RES / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    (RES / "tables.md").write_text("# T3 tables (generated by analyze.py)\n" + "\n".join(md) + "\n", encoding="utf-8")
    print("wrote", RES / "summary.json", RES / "tables.md")


if __name__ == "__main__":
    main()
