import chartstyle as cs
import matplotlib.pyplot as plt

# Source: ocsf-data-health/results/RESULTS.md — best single (CMDB) 47.7%,
# cross-tool merge 75.6% (+27.9%), residual 24.4%; scored vs naive +25.1pp.
best, lift, residual = 47.7, 27.9, 24.4

fig, ax = cs.canvas(
    "No single tool sees the estate; the cross-tool view does.",
    "Share of 140,000 asset/attribute cells recovered correctly — the merge lifts coverage 47.7% to 75.6%.",
    source="sdw-lab-benchmarks/ocsf-data-health",
    tier="Tier B · single-host · synthetic 20k-asset estate · the order is the claim",
    figsize=(8.8, 3.5), bottom=0.30, top=0.80)

segs = [("Best single tool (CMDB)", best, cs.CONTEXT, cs.BODY),
        ("Recovered by the merge", lift, cs.ACCENT, "white"),
        ("Residual blind spot", residual, cs.BAD, "white")]
left = 0
for label, val, color, tcol in segs:
    ax.barh(0, val, left=left, color=color, height=0.5, edgecolor="white", linewidth=1.5)
    ax.text(left + val/2, 0, f"{val:.1f}%", ha="center", va="center", color=tcol, fontweight="bold", fontsize=15)
    ax.text(left + val/2, -0.42, label, ha="center", va="top", color=cs.BODY, fontsize=10)
    left += val

ax.set_xlim(0, 100); ax.set_ylim(-0.7, 0.4)
cs.bare(ax)
ax.set_xticks([0, 25, 50, 75, 100]); ax.set_xticklabels(["0", "25", "50", "75", "100%"])
ax.tick_params(axis="x", length=0)
ax.grid(axis="x", color=cs.GRID); ax.grid(axis="y", visible=False); ax.set_axisbelow(True)
ax.text(75.6, 0.30, "the scored merge beats a naive authority-of-record merge by +25.1pp",
        ha="right", va="bottom", fontsize=9, color=cs.MUTED, family=cs.MONO)
cs.save(fig, "out/data-health-recovery.png")
print("rendered; font in use =", cs.SANS)
