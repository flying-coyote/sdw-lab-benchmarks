import chartstyle as cs
import matplotlib.pyplot as plt

# Source: ocsf-data-health/results/RESULTS.md:16 (20,000 assets x 7 attributes = 140,000 cells),
# :22-26 (best single tool cmdb 47.7%, cross-tool 75.6%, cross minus best single +27.9, residual 24.4%,
# scored merge minus naive authority merge +25.1), :47 (naive merge 50.5%).
# 27.9 is percentage points of the 140,000 cells, so the middle segment is labelled as points and the
# 75.6% the pages quote is marked at the segment's right edge.
best, lift, residual = 47.7, 27.9, 24.4

fig, ax = cs.canvas(
    "Merging tools recovers far more than any single tool sees.",
    "Share of 140,000 asset/attribute cells recovered correctly: the merge lifts coverage from 47.7% to 75.6%,\n"
    "and 24.4% is reported correctly by no tool.",
    source="sdw-lab-benchmarks/ocsf-data-health",
    tier="Tier B · single-host · synthetic environment of 20,000 assets · the order is the claim",
    figsize=(8.8, 3.9), bottom=0.30, top=0.72)

segs = [("Best single tool (CMDB)", best, f"{best:.1f}%", cs.CONTEXT, cs.BODY),
        ("Added by the merge", lift, f"+{lift:.1f} pts", cs.ACCENT, "white"),
        ("Residual blind spot", residual, f"{residual:.1f}%", cs.BAD, "white")]
left = 0
for label, val, txt, color, tcol in segs:
    ax.barh(0, val, left=left, color=color, height=0.5, edgecolor="white", linewidth=1.5)
    ax.text(left + val/2, 0, txt, ha="center", va="center", color=tcol, fontweight="bold", fontsize=15)
    ax.text(left + val/2, -0.42, label, ha="center", va="top", color=cs.BODY, fontsize=10,
            bbox=dict(facecolor="white", edgecolor="none", pad=1.5))  # keeps the gridlines out of the label
    left += val

# cumulative marker at the merge's ceiling (75.6% = 47.7 + 27.9 = 100 - 24.4)
merged = best + lift
ax.plot([merged, merged], [-0.27, 0.36], color=cs.INK, lw=1.4, zorder=4)
ax.text(merged - 1.2, 0.38, f"{merged:.1f}% after the scored merge", ha="right", va="bottom",
        fontsize=10, color=cs.INK, fontweight="bold", bbox=dict(facecolor="white", edgecolor="none", pad=1.5))
# RESULTS.md:30 (corrected 2026-11-17): the scored merge equals the any-tool-correct ceiling by construction of the
# flaw model, so the 25.1-pt gap is ceiling minus naive merge and is not drawn as a measured win for the merge.
fig.text(0.012, 0.115, "A naive authority-of-record merge reaches 50.5%, 25.1 pts under the ceiling this flaw model allows.",
         ha="left", va="bottom", fontsize=9, color=cs.MUTED, family=cs.SANS)

ax.set_xlim(0, 100); ax.set_ylim(-0.7, 0.75)
cs.bare(ax)
ax.set_xticks([0, 25, 50, 75, 100]); ax.set_xticklabels(["0", "25", "50", "75", "100%"])
ax.tick_params(axis="x", length=0)
ax.grid(axis="x", color=cs.GRID); ax.grid(axis="y", visible=False); ax.set_axisbelow(True)
cs.direction_note(fig, "recovered: higher is better")
cs.save(fig, "out/data-health-recovery.png")
print("rendered; font in use =", cs.SANS)
