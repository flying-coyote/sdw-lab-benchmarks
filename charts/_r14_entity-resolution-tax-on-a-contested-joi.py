import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np

# Source: ocsf-data-health/results/RESULTS.md (EXT-2)
# 12,000 planted identities x 5 attrs = 60,000 cells. Three join regimes:
#   clean-key oracle (planted person_id)         96.3%   <- IDENTITY oracle, first-party.
#   contested-key (resolve from disagreeing keys) 86.2%   -> resolution tax -10.1pp
#   naive single-key join (employee_id only)      60.0%
# NOTE: this 96.3% is the clean-key identity oracle — unrelated to the do-not-cite
#       ch08 ClickHouse/Cloudflare 96.3% fabrication (coincidental collision).
labels = ["Clean-key oracle\n(if the join key were never contested)",
          "Contested-key merge\n(link records by disagreeing key values)",
          "Naive single-key join\n(employee_id only — drops every non-HR tool)"]
vals  = [96.3, 86.2, 60.0]
cols  = [cs.CONTEXT, cs.ACCENT, cs.BAD]
tcols = [cs.BODY, "white", "white"]

fig, ax = cs.canvas(
    "Contesting the join key is itself part of the assurance gap.",
    "Share of the 60,000-cell identity estate recovered, by how the four tools' disagreeing key columns are reconciled.",
    source="sdw-lab-benchmarks/ocsf-data-health",
    tier="Tier B · single-host · synthetic 12,000 identities × 5 attributes · the ordering is the claim",
    figsize=(9.4, 4.7), bottom=0.20, top=0.80)

y = np.arange(len(vals))[::-1]
ax.barh(y, vals, height=0.56, color=cols, edgecolor="white", linewidth=1.4)
for yi, v, t in zip(y, vals, tcols):
    ax.text(v - 1.6, yi, f"{v:.1f}%", ha="right", va="center", color=t, fontweight="bold", fontsize=14)

ax.set_xlim(0, 100)
ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=10.2)
cs.bare(ax)
ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=10.2)
ax.set_xticks([0, 25, 50, 75, 100]); ax.set_xticklabels(["0", "25", "50", "75", "100%"])
ax.tick_params(axis="x", length=0)
ax.grid(axis="x", color=cs.GRID); ax.grid(axis="y", visible=False); ax.set_axisbelow(True)

# annotate the resolution tax in the clear space ABOVE the top (oracle) bar
ax.annotate("", xy=(86.2, y[0]+0.40), xytext=(96.3, y[0]+0.40),
            arrowprops=dict(arrowstyle="<->", color=cs.MUTED, lw=1.2))
ax.text((86.2+96.3)/2, y[0]+0.52, "resolution tax  -10.1pp", ha="center", va="bottom",
        fontsize=9.5, color=cs.MUTED, family=cs.MONO)

# resolution diagnostics on their own line beneath the bars (no bar overlap)
ax.text(0, -0.95, "16,073 clusters resolved from 12,000 people  ·  0 over-merged  ·  3,770 fragmented (under-merge)",
        ha="left", va="center", fontsize=8.8, color=cs.MUTED, family=cs.MONO)

ax.set_ylim(-1.25, 2.7)
cs.save(fig, "out/entity-resolution-tax-on-a-contested-joi.png")
print("rendered r14")
