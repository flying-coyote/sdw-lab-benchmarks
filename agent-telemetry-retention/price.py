"""R6 pricing + summary tables. Reuses the price inputs from ../cost-to-serve-retention/cost_model.py.

    python price.py > results/tables.md
Method (cost_model.py): steady-state monthly storage cost at a retention of D days = stored GB x $/GB-month,
decimal GB, storage only. Here D = 365 calendar days holding ACTIVE_DAYS active days of telemetry.
"""
import importlib.util
import json
import os
import statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
spec = importlib.util.spec_from_file_location("cost_model", os.path.join(HERE, "..", "cost-to-serve-retention", "cost_model.py"))
cm = importlib.util.module_from_spec(spec); spec.loader.exec_module(cm)
PRICES = cm.PRICES_PER_GB_MONTH  # verified 2026-06-10, re-verified 2026-06-14 (see that file)
PRICE_DATE = "AWS us-east-1 list, verified 2026-06-10, re-verified 2026-06-14 (cost-to-serve-retention/cost_model.py)"

ACTIVE_DAYS = 185
USERS = 1000
VOLUME = {  # billed tokens per active day (PREREGISTRATION.md, volume model)
    ("coding", "avg"): 23_500_000,
    ("coding", "p90"): 54_000_000,
    ("chat", "avg"): 200_000,
}


def load(name):
    p = os.path.join(RES, name)
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def spread(xs):
    m = st.median(xs)
    cv = (st.pstdev(xs) / st.mean(xs) * 100) if len(xs) > 1 and st.mean(xs) else 0.0
    return m, min(xs), max(xs), cv


def gb_year(bpm, tokens_day):
    return bpm * tokens_day / 1e6 * ACTIVE_DAYS * USERS / 1e9


def main():
    pq_rows = load("parquet.jsonl")
    g = defaultdict(list)
    for r in pq_rows:
        g[(r["tier"], r["corpus_kind"], r["arm"], r["order"], r["variant"])].append(r)
    summary = {}
    for k, rs in g.items():
        bpm = [r["bytes_per_mtok"] for r in rs]
        m, lo, hi, cv = spread(bpm)
        summary["|".join(k)] = dict(n_seeds=len(rs), bytes_per_mtok_median=m, min=lo, max=hi, cv_pct=cv,
                                    text_share_median=st.median(r["text_share"] for r in rs),
                                    bytes_per_record_median=st.median(r["bytes_per_record"] for r in rs),
                                    jsonl_bytes_per_mtok_median=st.median(r["jsonl_bytes_per_mtok"] for r in rs))
    json.dump(summary, open(os.path.join(RES, "summary.json"), "w"), indent=1)

    print(f"Prices: {PRICE_DATE}: " + ", ".join(f"{k} ${v}/GB-mo" for k, v in PRICES.items()))
    print(f"Pricing frame: {USERS:,} users, {ACTIVE_DAYS} active days in a 365-day retention window; "
          "steady-state $/month at 365-day retention (cost_model method), annual run rate = 12x, "
          "year-1 accrual from empty = 6.5x monthly.\n")

    for tier, corpus in [("coding", "real"), ("chat", "real"), ("coding", "high_entropy"), ("chat", "high_entropy")]:
        print(f"\n### {tier} tier, {corpus} text, zstd default (level 1), Parquet\n")
        print("| Arm | Order | bytes / M tokens (median, min-max, CV) | text share | raw JSONL bytes / M tokens | "
              "GB / yr per 1k users (avg vol) | S3 Std $/mo | Glacier IR $/mo | gp3 $/mo |")
        print("|---|---|---|---|---|---|---|---|---|")
        for arm in ["T0_metadata", "T1_hash", "T2_delta", "T3_full"]:
            for order in ["session_sorted", "random"]:
                s = summary.get(f"{tier}|{corpus}|{arm}|{order}|zstd_default")
                if not s:
                    continue
                gb = gb_year(s["bytes_per_mtok_median"], VOLUME[(tier, "avg")])
                print(f"| {arm} | {order} | {s['bytes_per_mtok_median']:,.0f} ({s['min']:,.0f}-{s['max']:,.0f}, "
                      f"{s['cv_pct']:.1f}%) | {s['text_share_median']:.1%} | {s['jsonl_bytes_per_mtok_median']:,.0f} | "
                      f"{gb:,.1f} | ${gb * PRICES['s3_standard']:,.2f} | ${gb * PRICES['s3_glacier_ir']:,.2f} | "
                      f"${gb * PRICES['ebs_gp3']:,.2f} |")

    print("\n### Codec / dictionary variants (median bytes per M tokens over seeds; real text)\n")
    variants = ["snappy_default", "zstd_default", "zstd_1", "zstd_3", "zstd_9", "zstd_19", "zstd_default_nodict_text",
                "zstd_default_page8m"]
    print("| Tier | Arm | Order | " + " | ".join(variants) + " |")
    print("|---|---|---|" + "---|" * len(variants))
    for tier in ["coding", "chat"]:
        for arm in ["T0_metadata", "T1_hash", "T2_delta", "T3_full"]:
            for order in ["session_sorted", "random"]:
                cells = []
                for v in variants:
                    s = summary.get(f"{tier}|real|{arm}|{order}|{v}")
                    cells.append(f"{s['bytes_per_mtok_median']:,.0f}" if s else "-")
                print(f"| {tier} | {arm} | {order} | " + " | ".join(cells) + " |")

    print("\n### Coding tier one-year bill, 1,000 users, real text (S3 Standard steady state at 365 d; run rate 12x)\n")
    print("| Arm | Order | Variant | Volume | GB held | S3 Std $/mo | S3 Std $/yr run rate | Glacier IR $/mo | year-1 accrual S3 $ |")
    print("|---|---|---|---|---|---|---|---|---|")
    for arm in ["T0_metadata", "T1_hash", "T2_delta", "T3_full"]:
        for order in ["session_sorted", "random"]:
            for v in ["zstd_default", "zstd_19"]:
                s = summary.get(f"coding|real|{arm}|{order}|{v}")
                if not s:
                    continue
                for vol in ["avg", "p90"]:
                    gb = gb_year(s["bytes_per_mtok_median"], VOLUME[("coding", vol)])
                    mo = gb * PRICES["s3_standard"]
                    print(f"| {arm} | {order} | {v} | {vol} | {gb:,.0f} | ${mo:,.0f} | ${mo * 12:,.0f} | "
                          f"${gb * PRICES['s3_glacier_ir']:,.0f} | ${mo * 6.5:,.0f} |")

    ice = load("iceberg.jsonl")
    if ice:
        print("\n### Iceberg (pyiceberg 0.12.0) vs plain Parquet zstd default, session-sorted, median over seeds\n")
        print("| Tier | Corpus | Arm | plain Parquet | Iceberg default (data) | Iceberg parity (data) | Iceberg parity (data+metadata) | "
              "EXPLORATORY plain, write_batch_size 20000 | parity vs plain |")
        print("|---|---|---|---|---|---|---|---|---|")
        gi = defaultdict(list)
        for r in ice:
            gi[(r["tier"], r["corpus_kind"], r["arm"], r["variant"])].append(r)
        for tier in ["coding", "chat"]:
            for corpus in ["real", "high_entropy"]:
                for arm in ["T0_metadata", "T1_hash", "T2_delta", "T3_full"]:
                    plain = summary.get(f"{tier}|{corpus}|{arm}|session_sorted|zstd_default")
                    if not plain:
                        continue
                    med = lambda v, f="data_bytes_per_mtok": st.median(r[f] for r in gi[(tier, corpus, arm, v)]) if gi[(tier, corpus, arm, v)] else float("nan")
                    par = med("iceberg_parity_zstd_default")
                    print(f"| {tier} | {corpus} | {arm} | {plain['bytes_per_mtok_median']:,.0f} | {med('iceberg_default'):,.0f} | "
                          f"{par:,.0f} | {med('iceberg_parity_zstd_default', 'total_bytes_per_mtok'):,.0f} | "
                          f"{med('EXPLORATORY_plain_parquet_zstd_default_wbs20000'):,.0f} | "
                          f"{(par / plain['bytes_per_mtok_median'] - 1) * 100:+.1f}% |")

    d = load("dict.jsonl")
    if d:
        print("\n### Trained zstd dictionary, per-record prompt_text at level 3 (held-out seed 99 training), vs Parquet column\n")
        print("| Tier | Corpus | Column | per-record zstd-3 bytes/M tok | + trained dict | dict gain | Parquet zstd default prompt_text column bytes/M tok (sorted / random) |")
        print("|---|---|---|---|---|---|---|")
        gd = defaultdict(list)
        for r in d:
            gd[(r["tier"], r["corpus_kind"], r["column"])].append(r)
        for (tier, corpus, col), rs in sorted(gd.items()):
            arm = "T2_delta" if col == "prompt_text_delta" else "T3_full"
            pcol = []
            for order in ["session_sorted", "random"]:
                vals = [r["col_bytes"]["prompt_text"] / r["billed_tokens"] * 1e6 for r in pq_rows
                        if r["tier"] == tier and r["corpus_kind"] == corpus and r["arm"] == arm
                        and r["order"] == order and r["variant"] == "zstd_default"]
                pcol.append(f"{st.median(vals):,.0f}" if vals else "-")
            pr = st.median(r["per_record_zstd3"] / r["billed_tokens"] * 1e6 for r in rs)
            dr = st.median(r["per_record_zstd3_dict"] / r["billed_tokens"] * 1e6 for r in rs)
            gains = [r["dict_gain"] for r in rs]
            print(f"| {tier} | {corpus} | {col} | {pr:,.0f} | {dr:,.0f} | {st.median(gains):.2f}x "
                  f"({min(gains):.2f}-{max(gains):.2f}) | {pcol[0]} / {pcol[1]} |")


if __name__ == "__main__":
    main()
