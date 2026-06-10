import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np

# Source: sigma-portability/results/RESULTS.md — pySigma 1.3.3, 5 correlation rules.
# Per-backend correlation fidelity (full / partial / refused). 6/6 single-event on all 4.
# OpenSearch PPL: 2 full / 3 partial, and 3 of those partials are SILENT window-drops.
backends = ["Splunk SPL", "Elasticsearch ES|QL", "Elasticsearch Lucene", "OpenSearch PPL"]
full    = [4, 4, 0, 2]
partial = [0, 0, 0, 3]
refused = [1, 1, 5, 0]
window_drop = [0, 0, 0, 3]   # subset of partial that silently dropped the time window

fig, ax = cs.canvas(
    "Sigma correlations don't survive the trip to every SIEM.",
    "Of 5 correlation rules compiled by pySigma 1.3.3, how many keep full semantics, go partial, or get refused. "
    "(All 6 single-event rules compile on all four backends.)",
    source="sdw-lab-benchmarks/sigma-portability",
    tier="Tier B · single-host · compiler-output fidelity, not SIEM execution · pySigma 1.3.3",
    figsize=(9.4, 4.9), bottom=0.16, top=0.80)

y = np.arange(len(backends))[::-1]   # Splunk on top
h = 0.62

# stacked: full (accent) | partial (orange) | refused (grey context)
left = np.zeros(len(backends))
for seg, color, name in [(full, cs.ACCENT, "full fidelity"),
                         (partial, cs.WARN, "partial"),
                         (refused, cs.CONTEXT, "refused")]:
    ax.barh(y, seg, left=left, height=h, color=color, edgecolor="white", linewidth=1.4)
    for yi, v, l in zip(y, seg, left):
        if v > 0:
            tcol = "white" if color in (cs.ACCENT, cs.WARN) else cs.BODY
            ax.text(l + v/2, yi, f"{v}", ha="center", va="center",
                    color=tcol, fontweight="bold", fontsize=13)
    left += np.array(seg)

ax.set_xlim(0, 5)
ax.set_yticks(y); ax.set_yticklabels(backends, fontsize=11.5)
cs.bare(ax)
ax.set_yticks(y)            # bare() cleared them; restore labels
ax.set_yticklabels(backends, fontsize=11.5)
ax.set_xticks(range(0, 6)); ax.tick_params(axis="x", length=0)
ax.set_xlabel("correlation rules (of 5)")
ax.grid(axis="x", color=cs.GRID); ax.grid(axis="y", visible=False); ax.set_axisbelow(True)

# inline legend (direct labels, no separate box)
ax.text(0.5, 3.55, "full fidelity", color=cs.ACCENT, fontsize=9.5, fontweight="bold", va="bottom")
ax.text(2.15, 3.55, "partial", color=cs.WARN, fontsize=9.5, fontweight="bold", va="bottom")
ax.text(3.35, 3.55, "refused (raised, no query)", color=cs.MUTED, fontsize=9.5, fontweight="bold", va="bottom")

# the security-relevant cell: PPL's 3 partials are SILENT window-drops
ppl_y = y[3]
ax.annotate("all 3 PPL partials silently DROP the time window —\nthe correlation runs, but not over the window it asked for",
            xy=(3.5, ppl_y), xytext=(2.55, ppl_y - 0.95),
            fontsize=9.3, color=cs.BAD, family=cs.SANS, ha="left", va="top",
            arrowprops=dict(arrowstyle="-|>", color=cs.BAD, lw=1.3,
                            connectionstyle="arc3,rad=-0.25"))

ax.set_ylim(-1.15, 4.0)
cs.direction_note(fig, "full fidelity: higher is better")
cs.save(fig, "out/sigma-correlation-rule-fidelity-across-4.png")
print("rendered r12")
