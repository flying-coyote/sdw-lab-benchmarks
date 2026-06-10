import chartstyle as cs
# Same source: ocsf-data-health — part-to-whole of 140,000 cells.
fig, ax = cs.canvas(
    "The cross-tool merge recovers 75.6% of the estate; the last 24.4% no tool sees.",
    "140,000 asset/attribute cells: what the best single tool sees, what the merge adds, what no tool gets right.",
    source="sdw-lab-benchmarks/ocsf-data-health",
    tier="Tier B · single-host · synthetic 20k-asset estate",
    figsize=(7.6, 5.2), top=0.82, bottom=0.10)
cs.donut(ax,
    [47.7, 27.9, 24.4],
    ["Best single\ntool (CMDB)", "Added by the\ncross-tool merge", "Residual\nblind spot"],
    [cs.CONTEXT, cs.ACCENT, cs.BAD],
    center="75.6%", center_sub="recovered by the\ncross-tool view")
cs.save(fig, "out/data-health-recovery-donut.png")
print("ok")
