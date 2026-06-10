import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np

# Source: ocsf-mapping-oracle/results/RESULTS.md  (Tier B, local model ladder + claude-opus-4-8 frontier proxy,
#         single-shot temp-0, n=141 mappings, OCSF 1.8.0 path-validated).
# METRIC = silent-error rate (a predicted path that does not exist). Lower is better.
# Model ladder ordered weakest -> strongest:
#   phi3:latest        none 0.99  schema 0.69  formal 0.72  wrong_grounding 0.72
#   gemma4:26b         none 0.83  schema 0.18  formal 0.19  wrong_grounding 0.18   (note: source names it gemma4:26b)
#   claude-opus-4-8    none 0.24  schema 0.13  formal 0.15  wrong_grounding 0.17
# THE NULL (control): formal - wrong_grounding ~ 0 to +0.01 across models -> the lift is CONTENT, not tokens.
models = ["phi3", "gemma4:26b", "claude-opus-4-8\n(frontier proxy)"]
none   = [0.99, 0.83, 0.24]
schema = [0.69, 0.18, 0.13]
formal = [0.72, 0.19, 0.15]
wrong  = [0.72, 0.18, 0.17]   # wrong-grounding control

fig, ax = cs.canvas(
    "Schema grounding cuts invented OCSF paths — and the lift shrinks toward the frontier.",
    "Silent-error rate (a predicted OCSF path that doesn't exist; lower is better) with no grounding vs a "
    "schema given to the model, across a capability ladder. The grey diamond is the wrong-grounding "
    "control: it lands on top of the schema bar, so the grounding content is doing the work, not the extra tokens.",
    source="sdw-lab-benchmarks/ocsf-mapping-oracle",
    tier="Tier B · single host · local ladder + claude-opus-4-8 proxy · single-shot temp-0 · n=141 · OCSF 1.8.0-validated",
    figsize=(10.6, 5.4), bottom=0.20, top=0.74)

x = np.arange(len(models))
w = 0.36
b1 = ax.bar(x - w/2, none,   w, color=cs.CONTEXT, zorder=3, label="no grounding")
b2 = ax.bar(x + w/2, schema, w, color=cs.ACCENT,  zorder=3, label="schema grounding")

for xi, v in zip(x - w/2, none):
    ax.text(xi, v + 0.015, f"{v:.2f}", ha="center", va="bottom", fontsize=12, color=cs.BODY)
for xi, v in zip(x + w/2, schema):
    ax.text(xi, v + 0.015, f"{v:.2f}", ha="center", va="bottom", fontsize=12, fontweight="bold", color=cs.ACCENT)

# wrong-grounding control diamond, on the schema bar (the null: ~ same as formal/schema)
for xi, wv in zip(x + w/2, wrong):
    ax.scatter(xi, wv, marker="D", s=55, color=cs.MUTED, zorder=5,
               edgecolor="white", linewidth=0.8)

# lift arrows (none -> schema) with the delta
for xi, n, s in zip(x, none, schema):
    ax.annotate("", xy=(xi + w/2, s + 0.04), xytext=(xi - w/2, n - 0.02),
                arrowprops=dict(arrowstyle="->", color=cs.BODY, lw=1.0, alpha=0.5))
    ax.text(xi, max(n, s) + 0.085, f"-{n - s:.2f}", ha="center", va="bottom",
            fontsize=10.5, color=cs.GOOD, fontweight="bold")

ax.set_xticks(x); ax.set_xticklabels(models, fontsize=10.5)
ax.set_ylim(0, 1.15)
ax.set_ylabel("silent-error rate  (invented OCSF paths)")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.spines["left"].set_color(cs.GRID)
ax.grid(axis="y", color=cs.GRID); ax.grid(axis="x", visible=False)
ax.tick_params(axis="both", length=0)

from matplotlib.lines import Line2D
handles = [b1, b2,
           Line2D([0], [0], marker="D", color="none", markerfacecolor=cs.MUTED,
                  markeredgecolor="white", markersize=8,
                  label="wrong-grounding control (the null)")]
ax.legend(handles=handles, loc="upper right", frameon=False, fontsize=9.5, ncol=1,
          bbox_to_anchor=(1.0, 1.03), handletextpad=0.6)

# the null, called out compactly under the frontier model where there's clear space
ax.text(2.0, 0.62, "the control diamond sits on the\nschema bar at every rung:\nformal - wrong_grounding ~ 0,\nso it's grounding content, not tokens",
        ha="center", va="top", fontsize=8.2, color=cs.MUTED, family=cs.MONO)

cs.save(fig, "out/schema-grounding-cuts-invented-paths.png")
print("rendered r06")
