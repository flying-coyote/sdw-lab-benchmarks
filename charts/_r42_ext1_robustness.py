import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, Normalize

# Source: ocsf-data-health/results/RESULTS.md (EXT-1 parameter sweep, 9-point grid)
# rows = staleness x (0.6, 1.0, 1.4); cols = coverage x (0.8, 1.0, 1.15)
# Primary plotted value: lever gain (scored merge - naive authority merge), %.
# cross-minus-best shown as a second number per cell so the order is legible.
#   staleness 0.6: lever [17.0, 21.4, 23.0]  cross-best [19.4, 24.3, 26.4]
#   staleness 1.0: lever [20.1, 25.1, 27.0]  cross-best [22.5, 27.9, 30.4]
#   staleness 1.4: lever [21.5, 26.7, 28.6]  cross-best [23.9, 29.8, 31.9]
cov = ["×0.8", "×1.0", "×1.15"]
stale = ["×0.6", "×1.0", "×1.4"]
lever = np.array([
    [17.0, 21.4, 23.0],
    [20.1, 25.1, 27.0],
    [21.5, 26.7, 28.6],
])
crossbest = np.array([
    [19.4, 24.3, 26.4],
    [22.5, 27.9, 30.4],
    [23.9, 29.8, 31.9],
])

fig, ax = cs.canvas(
    "Every cell of the parameter grid keeps the same ordering",
    "Lever gain (scored − naive merge), % recovered, across a 3×3 staleness × coverage sweep. cross > best-single, residual > 0, and lever > 0 hold at all 9 cells.",
    source="sdw-lab-benchmarks/ocsf-data-health",
    tier="Tier B · single-host · synthetic · the ordering is the parameter-independent claim, the magnitudes move",
    figsize=(8.8, 4.9), bottom=0.16, top=0.78)

# sequential teal ramp (low -> high lever)
cmap = LinearSegmentedColormap.from_list("lever", ["#eef3f8", cs.ACCENT2, cs.ACCENT])
norm = Normalize(vmin=lever.min() - 2, vmax=lever.max())
im = ax.imshow(lever, cmap=cmap, norm=norm, aspect="auto")

for i in range(3):
    for j in range(3):
        v = lever[i, j]
        cb = crossbest[i, j]
        tcol = "white" if v > 24.5 else cs.INK
        ax.text(j, i - 0.13, f"+{v:.1f}%", ha="center", va="center",
                fontsize=13, fontweight="bold", color=tcol)
        ax.text(j, i + 0.22, f"cross−best +{cb:.1f}%", ha="center", va="center",
                fontsize=8.2, color=(("#dfe9f2") if v > 24.5 else cs.MUTED), family=cs.MONO)

ax.set_xticks(range(3)); ax.set_xticklabels([f"coverage {c}" for c in cov])
ax.set_yticks(range(3)); ax.set_yticklabels([f"staleness {s}" for s in stale])
for s in ("top", "right", "left", "bottom"):
    ax.spines[s].set_visible(False)
ax.tick_params(length=0)
ax.grid(False)

# the integrity headline below the grid
ax.text(1.0, 2.78,
        "cross-tool > best-single at every cell (min margin +19.4%) · residual gap > 0 everywhere · lever > 0 everywhere",
        ha="center", va="top", fontsize=8.6, color=cs.BODY, family=cs.MONO)

cs.save(fig, "out/ext-1-robustness-parameter-sweep.png")
print("rendered ext-1")
