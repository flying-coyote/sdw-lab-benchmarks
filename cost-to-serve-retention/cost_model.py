#!/usr/bin/env python3
"""Layer 2 (PRICED, desk-derived — never blend with Layer 1): steady-state monthly storage
cost at retention, for a reference 1 TB/day raw workload, from the measured byte ratios.

Prices are AWS us-east-1 list, as recorded below; re-verify before any publication. The
realization→storage-class mapping is part of the model and stated explicitly: hot indexes
and hot OLAP tables run on block storage, lakehouse tables run on object storage.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
RESULTS = HERE / "results"

PRICES_PER_GB_MONTH = {
    # VERIFIED 2026-06-10 against AWS's live rate-card JSON feeds (the source the official
    # pricing pages render from): b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/{ec2,s3}/USD/current
    # gp3 unchanged since 12/2020; S3 Standard (first 50TB) since 12/2016; Glacier IR since 11/2021.
    # Storage only — Glacier IR additionally charges $0.03/GB on retrieval, so cold-tier math
    # must stay storage-only or model retrieval frequency explicitly.
    "ebs_gp3": 0.08,
    "s3_standard": 0.023,
    "s3_glacier_ir": 0.004,
}

# realization -> (storage class it actually runs on, rationale)
CLASS_MAP = {
    "opensearch_index": ("ebs_gp3", "hot search index requires block storage"),
    "ch_native_lz4": ("ebs_gp3", "hot OLAP MergeTree on block storage"),
    "ch_zstd22": ("ebs_gp3", "tuned-hot OLAP on block storage"),
    "iceberg_zstd_default": ("s3_standard", "lakehouse warm tier on object storage"),
    "parquet_zstd19_cold": ("s3_standard", "compacted cold tier on object storage"),
    "parquet_zstd19_cold_glacier": ("s3_glacier_ir", "same cold artifact on Glacier Instant Retrieval"),
}

RAW_GB_PER_DAY = 1000.0  # reference workload, decimal GB
RETENTION_DAYS = [30, 90, 365, 2555]


def main():
    measured = json.loads((RESULTS / "measured_footprints.json").read_text())["measured_2026_06_10"]
    ratios = {k: v["ratio_vs_raw"] for k, v in measured.items() if k != "raw_jsonl"}
    ratios["parquet_zstd19_cold_glacier"] = ratios["parquet_zstd19_cold"]

    curves = {}
    for name, (cls, why) in CLASS_MAP.items():
        r = ratios[name]
        price = PRICES_PER_GB_MONTH[cls]
        rows = {}
        for d in RETENTION_DAYS:
            stored_gb = RAW_GB_PER_DAY * d / r
            rows[str(d)] = {"stored_gb": round(stored_gb), "monthly_usd": round(stored_gb * price)}
        curves[name] = {"ratio_vs_raw": r, "storage_class": cls, "class_rationale": why,
                        "price_per_gb_month": price, "by_retention_days": rows}

    # compounded multipliers (retention-independent: both layers linear in D)
    def monthly(name, d=365):
        return curves[name]["by_retention_days"][str(d)]["monthly_usd"]

    multipliers = {
        "opensearch_gp3_vs_iceberg_s3": round(monthly("opensearch_index") / monthly("iceberg_zstd_default"), 1),
        "opensearch_gp3_vs_cold_s3": round(monthly("opensearch_index") / monthly("parquet_zstd19_cold"), 1),
        "opensearch_gp3_vs_cold_glacier_ir": round(monthly("opensearch_index") / monthly("parquet_zstd19_cold_glacier"), 1),
        "ch_lz4_gp3_vs_iceberg_s3": round(monthly("ch_native_lz4") / monthly("iceberg_zstd_default"), 1),
        "note": "bytes multiplier x $/byte multiplier; constant across retention because both layers are linear in days",
    }

    out = {"reference_workload_gb_per_day_raw": RAW_GB_PER_DAY,
           "prices_as_of": "2026-06-10 AWS us-east-1 list — verified against the live AWS rate-card feeds (see PRICES comment)",
           "curves": curves, "compounded_multipliers": multipliers}
    (RESULTS / "cost_curves.json").write_text(json.dumps(out, indent=2))

    print(f"{'realization':38s} {'ratio':>6s} {'class':>12s} " + "".join(f"{d:>12d}d" for d in RETENTION_DAYS))
    for name, c in curves.items():
        cells = "".join(f"  ${c['by_retention_days'][str(d)]['monthly_usd']:>9,}/mo" for d in RETENTION_DAYS)
        print(f"{name:38s} {c['ratio_vs_raw']:>6.2f} {c['storage_class']:>12s}{cells}")
    print(json.dumps(multipliers, indent=2))


if __name__ == "__main__":
    main()
