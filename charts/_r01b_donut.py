import chartstyle as cs
# Same source: ocsf-data-health/results/RESULTS.md:16, :22-25 (part-to-whole of 140,000 cells).
fig, ax = cs.canvas(
    "The cross-tool merge recovers 75.6% of the environment, and no tool gets the last 24.4% right.",
    "140,000 asset/attribute cells: what the best single tool sees, what the merge adds, what no tool gets right.",
    source="sdw-lab-benchmarks/ocsf-data-health",
    tier="Tier B · single-host · synthetic environment of 20,000 assets",
    figsize=(7.6, 5.2), top=0.82, bottom=0.10)
cs.donut(ax,
    [47.7, 27.9, 24.4],
    ["Best single\ntool (CMDB)", "Added by the\ncross-tool merge", "Residual\nblind spot"],
    [cs.CONTEXT, cs.ACCENT, cs.BAD],
    center="75.6%", center_sub="recovered by the\ncross-tool view")
# push the slice labels clear of the ring: cs.donut centres them at r=1.22, where 2-3 line labels overlap the
# ring's outer edge, so anchor each one outside the ring on its own side instead
import math
for t in ax.texts:
    x, y = t.get_position()
    r = math.hypot(x, y)
    if 1.1 < r < 1.3:
        c, sn = x / r, y / r
        t.set_position((1.12 * c, 1.12 * sn))
        t.set_ha("left" if c > 0.2 else "right" if c < -0.2 else "center")
        t.set_va("bottom" if sn > 0.7 else "top" if sn < -0.7 else "center")
cs.direction_note(fig, "recovered: higher is better", y=0.80)
cs.save(fig, "out/data-health-recovery-donut.png")
print("ok")
