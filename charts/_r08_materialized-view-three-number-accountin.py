import chartstyle as cs
import matplotlib.pyplot as plt

# Source: ocsf-mv-acceleration/results/RESULTS.md  (20M OCSF events, 3 SOC panels)
# read speedup:           class_rollup 76.8x, time_series_5m 53.6x, failed_auth 45.3x
# incremental vs recompute: 2.9x, 1.9x, 1.0x (break-even)
# MV storage overhead:    +0.0%, +0.001%, +0.002%
panels = ["class_rollup", "time_series_5m", "failed_auth_by_user"]
speedup = [76.8, 53.6, 45.3]
incr    = [2.9, 1.9, 1.0]
storage = [0.0, 0.001, 0.002]
y = list(range(len(panels)))  # 0=class_rollup; inverted below so it sits on top

fig, axes = cs.canvas(
    "The MV's read win is 45–77×; the compute win fades to break-even; storage is ~nothing.",
    "20M OCSF events, three always-on SOC panels: read speedup, incremental vs full recompute, MV storage overhead.",
    source="sdw-lab-benchmarks/ocsf-mv-acceleration",
    tier="Tier B · single-host · 20M synthetic · an MV only answers pre-decided questions",
    figsize=(9.6, 4.3), bottom=0.18, top=0.78, ncols=3)

ax1, ax2, ax3 = axes

# --- panel 1: read speedup (the win) ---
ax1.barh(y, speedup, color=cs.ACCENT, height=0.6)
for yi, v in zip(y, speedup):
    ax1.text(v - 2, yi, f"{v:.1f}×", ha="right", va="center", color="white", fontweight="bold", fontsize=11)
ax1.set_xlim(0, 85)
ax1.set_title("Read speedup", fontsize=11.5, color=cs.BODY, fontweight="bold", pad=8, loc="left")

# --- panel 2: incremental vs recompute (collapses to break-even) ---
colors2 = [cs.ACCENT2, cs.ACCENT2, cs.WARN]
ax2.barh(y, incr, color=colors2, height=0.6)
ax2.axvline(1.0, color=cs.MUTED, lw=1.0, ls="--", zorder=1)
for yi, v in zip(y, incr):
    lbl = f"{v:.1f}×" + ("  break-even" if v <= 1.0 else "")
    off = 0.06
    ax2.text(v + off, yi, lbl, ha="left", va="center", color=cs.BODY, fontsize=10)
ax2.set_xlim(0, 3.6)
ax2.set_title("Incremental vs recompute", fontsize=11.5, color=cs.BODY, fontweight="bold", pad=8, loc="left")

# --- panel 3: storage overhead (~0) ---
ax3.barh(y, storage, color=cs.CONTEXT, height=0.6)
for yi, v in zip(y, storage):
    ax3.text(0.0006, yi, f"+{v:.3f}%", ha="left", va="center", color=cs.BODY, fontsize=10)
ax3.set_xlim(0, 0.006)
ax3.set_title("Storage overhead", fontsize=11.5, color=cs.BODY, fontweight="bold", pad=8, loc="left")

for ax in axes:
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.invert_yaxis()
    ax.grid(axis="x", visible=False)
    ax.grid(axis="y", visible=False)
    ax.tick_params(length=0)
    ax.set_xticks([])

# panel (row) labels on the leftmost axis only — set AFTER styling so they survive
ax1.set_yticks(y)
ax1.set_yticklabels(panels, fontsize=10.5, color=cs.BODY)
for ax in (ax2, ax3):
    ax.set_yticks(y); ax.set_yticklabels([])

cs.direction_note(fig, "speedup: higher is better", x=0.377, y=0.135, ha="center", va="top")
cs.direction_note(fig, "overhead: lower is better", x=0.8435, y=0.135, ha="center", va="top")
cs.save(fig, "out/materialized-view-three-number-accountin.png")
print("rendered r08")
