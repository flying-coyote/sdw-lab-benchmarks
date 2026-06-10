import chartstyle as cs
import matplotlib.pyplot as plt

# Source: ocsf-context-collapse-apt29/results/RESULTS-QUERY-COST.md (+ storage line from RESULTS.md / this file)
# Store F (fidelity) vs Store N (coarsened), APT29 corpus.
# Storage:  1.799x bytes (1,888,601 vs 1,049,655)
# Compute:  battery wall-time 1.265x (median per-rule 1.135x)
#           BY CLASS: adversary-tail battery 3.458x (29 rules), routine 0.998x (25 rules)
#           ps_script logsource 12.173x; ps_script ILIKE micro 3.978x
STORAGE = 1.799
COMPUTE_ALL = 1.265
COMPUTE_ADV = 3.458
COMPUTE_ROU = 0.998
PS_LOGSOURCE = 12.173

fig, ax = cs.canvas(
    "Storage is the expensive half of keeping fidelity; compute is cheap, except where it isn't.",
    "Cost of running the SAME Sigma battery against the fidelity store vs the coarsened store, as a "
    "multiple of the coarsened baseline (1.0x = parity). The compute premium is not flat: it concentrates "
    "in exactly the adversary-tail detections the coarsening blinds.",
    source="sdw-lab-benchmarks/ocsf-context-collapse-apt29",
    tier="Tier B · single host · DuckDB-only · APT29 corpus (storage premium 1.80x — never cross with synthetic 1.93x)",
    figsize=(10.4, 5.2), bottom=0.30, top=0.76)

labels = ["Storage\n(bytes on disk)",
          "Query compute\n(full battery)",
          "Compute —\nroutine rules",
          "Compute —\nadversary-tail rules",
          "Compute — ps_script\nlogsource (full-text scan)"]
vals = [STORAGE, COMPUTE_ALL, COMPUTE_ROU, COMPUTE_ADV, PS_LOGSOURCE]
# storage = the headline axis (accent); routine ~ parity (grey/context); adversary + ps_script = the spike (bad)
colors = [cs.ACCENT, cs.ACCENT2, cs.CONTEXT, cs.BAD, cs.BAD]
xpos = list(range(len(vals)))

bars = ax.bar(xpos, vals, color=colors, width=0.62, zorder=3)
for x, v in zip(xpos, vals):
    ax.text(x, v + 0.18, f"{v:.2f}x" if v < 10 else f"{v:.1f}x",
            ha="center", va="bottom", fontsize=13, fontweight="bold", color=cs.BODY)

# parity reference line
ax.axhline(1.0, color=cs.MUTED, lw=1.2, ls="--", zorder=2)
ax.text(1.95, 2.35, "1.0x = parity with the coarsened store",
        ha="center", va="bottom", fontsize=9, color=cs.MUTED, family=cs.MONO)
ax.annotate("", xy=(2.0, 1.05), xytext=(1.95, 2.30),
            arrowprops=dict(arrowstyle="-", color=cs.MUTED, lw=0.8))

ax.set_xticks(xpos)
ax.set_xticklabels(labels, fontsize=9.5)
ax.set_ylim(0, 13.6)
ax.set_ylabel("cost vs coarsened store  (x)")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.spines["left"].set_color(cs.GRID)
ax.grid(axis="y", color=cs.GRID); ax.grid(axis="x", visible=False)
ax.tick_params(axis="both", length=0)

# annotate what the fix buys
ax.text(0, 13.0, "what fidelity buys back:  ~0.35 recall  ·  9 detections un-blinded",
        ha="left", va="top", fontsize=10, color=cs.ACCENT, fontweight="bold")

cs.direction_note(fig, "premium: lower is better", y=1.0, va="bottom")
cs.save(fig, "out/context-collapse-price-of-the-fix.png")
print("rendered r04")
