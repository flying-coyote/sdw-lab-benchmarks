import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import TwoSlopeNorm, LinearSegmentedColormap

# Source: ocsf-rls-overhead/results/RESULTS.md:24-27 (1%), :33-36 (10%), :42-45 (50%)  (predicate-overhead % column)
# rows = query shape, cols = tenant selectivity (visible share)
# count_all:    +81 / +67 / +54
# top_talkers:  -86 / -69 / -32   (predicate reads fewer rows -> FASTER)
# group_by_act: +30 /  -3 / +12
# needle:       +11 /  -1 /  +5
queries = ["count_all", "top_talkers", "group_by_act", "needle"]
sel     = ["1%", "10%", "50%"]
data = np.array([
    [ 81,  67,  54],
    [-86, -69, -32],
    [ 30,  -3,  12],
    [ 11,  -1,   5],
], dtype=float)

fig, ax = cs.canvas(
    "Row-level security is not a flat tax: its cost depends on the query shape.",
    "Engine-side overhead % of an RLS predicate vs no filter (DuckDB), by query × tenant visibility.\n"
    "Red = slower under RLS, green = faster (fewer rows scanned). Grey italic numbers sit inside the\n"
    "run-to-run CV, so they are noise; count_all's +81% is 0.7 ms rising to 1.3 ms.",
    source="sdw-lab-benchmarks/ocsf-rls-overhead",
    tier="Tier B · single-host · DuckDB engine-side ONLY (lower bound; catalog-layer RLS adds more)",
    figsize=(8.8, 5.2), bottom=0.21, top=0.74)
fig.subplots_adjust(right=0.80)

# diverging red(slower) -> white(0) -> green(faster), 0-centered
cmap = LinearSegmentedColormap.from_list("rls", [cs.GOOD, "#e9f0e3", cs.WHITE, "#f6e4e0", cs.BAD])
vmax = float(np.abs(data).max())
norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)

im = ax.imshow(data, cmap=cmap, norm=norm, aspect="auto")

# RESULTS.md:18: "A delta below the CV is not a real difference." Larger of the baseline and predicate CV per cell
# (RESULTS.md:24-27, :33-36, :42-45); a cell whose |overhead| is under it is drawn as noise.
cv = np.array([
    [17, 36, 36],
    [28,  9,  8],
    [22, 12, 14],
    [17, 12, 21],
], dtype=float)
for i in range(data.shape[0]):
    for j in range(data.shape[1]):
        v = data[i, j]
        noise = abs(v) < cv[i, j]
        ax.text(j, i, f"{v:+.0f}%", ha="center", va="center",
                fontsize=12.5, fontweight=("normal" if noise else "bold"),
                style=("italic" if noise else "normal"),
                color=(cs.MUTED if noise else cs.INK if abs(v) < 0.70 * vmax else "white"))

ax.set_xticks(range(len(sel)))
ax.set_xticklabels([f"{s}\nvisible" for s in sel])
ax.set_yticks(range(len(queries)))
ax.set_yticklabels(queries)
ax.set_xlabel("tenant selectivity (share of tenants visible)", labelpad=8)
for s in ("top", "right", "left", "bottom"):
    ax.spines[s].set_visible(False)
ax.tick_params(length=0)
ax.grid(False)

# annotate the one counter-intuitive row (in the reserved right margin)
ax.text(2.60, 1, "predicate reads\nfewer rows, so\nfaster than\nno filter", ha="left", va="center",
        fontsize=8.5, color=cs.GOOD, family=cs.SANS)

cs.direction_note(fig, "RLS overhead: lower is better", y=0.14, va="bottom")
cs.save(fig, "out/engine-side-rls-overhead-by-query-shape.png")
print("rendered rls")
