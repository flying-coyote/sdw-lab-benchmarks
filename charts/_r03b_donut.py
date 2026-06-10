import chartstyle as cs
# KPI donut companion to the 13-reader heatmap (MULTI-ENGINE-CORRECTNESS.md): 11 of 13 readers agree.
fig, ax = cs.canvas(
    "11 of 13 Parquet readers return the right answer.",
    "Byte-identical 10M-row data, 24 count(*) WHERE cells per reader checked against ground truth.",
    source="sdw-lab-benchmarks/clickhouse-vs-duckdb",
    tier="Tier B · single-host · version-bound (chDB 4.1.8, fastparquet) · concentrated, not universal",
    figsize=(7.4, 5.0), top=0.82, bottom=0.10)
cs.donut(ax, [11, 2], ["11 readers\nagree", "2 silently\nwrong"], [cs.GOOD, cs.BAD],
         center="11 / 13", center_sub="agree on every cell")
cs.save(fig, "out/answer-equivalence-donut.png")
print("ok")
