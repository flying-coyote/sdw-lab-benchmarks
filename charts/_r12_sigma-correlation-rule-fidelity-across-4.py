import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

# Source: sigma-portability/results/RESULTS.md:43-48 (per-backend summary), re-derivable from
# results/results.json summary.per_backend. pySigma 1.3.3, 5 correlation rules, 6 single-event rules.
# Per-backend correlation fidelity as the compiler-output scorer counts it (full / partial / refused):
#   Splunk SPL 4/0/1 · ES|QL 4/0/1 · Lucene 0/0/5 · OpenSearch PPL 2/3/0 (3 silent window-drops).
# Ordering caveat (sigma-portability/README.md:45-55, corrected 2026-11-17): the scorer checks a temporal
# rule's aggregation and window only (fidelity.py:84-85), so PPL's 2/2 on logon_exec_temporal_ordered does
# not test order. Executed by ../ocsf-sigma-detection (RESULTS-temporal-execution-2026-06-16.md), that emit
# fired on reversed sequences. The chart keeps the scorer's 2 full for PPL and hatches the one that loses
# order, so the counts still match RESULTS.md and the ordering loss is visible.
backends = ["Splunk SPL", "Elasticsearch ES|QL", "Elasticsearch Lucene", "OpenSearch PPL"]
full    = [4, 4, 0, 2]
partial = [0, 0, 0, 3]
refused = [1, 1, 5, 0]

fig, ax = cs.canvas(
    "Sigma correlations don't survive the trip to every SIEM.",
    "Of 5 correlation rules compiled by pySigma 1.3.3, how many keep full semantics, go partial, or get refused.\n"
    "(All 6 single-event rules compile on all four backends.)",
    source="sdw-lab-benchmarks/sigma-portability",
    tier="Tier B · single-host · scores the compiled queries without running them on a SIEM · pySigma 1.3.3",
    figsize=(9.4, 5.4), bottom=0.25, top=0.70)

y = np.arange(len(backends))[::-1]   # Splunk on top
h = 0.62

left = np.zeros(len(backends))
for seg, color in [(full, cs.ACCENT), (partial, cs.WARN), (refused, cs.CONTEXT)]:
    ax.barh(y, seg, left=left, height=h, color=color, edgecolor="white", linewidth=1.4)
    for yi, v, l in zip(y, seg, left):
        if v > 0 and not (color == cs.ACCENT and yi == y[3]):
            tcol = "white" if color in (cs.ACCENT, cs.WARN) else cs.BODY
            ax.text(l + v/2, yi, f"{v}", ha="center", va="center",
                    color=tcol, fontweight="bold", fontsize=13)
    left += np.array(seg)

# PPL's second "full" unit is the ordered-sequence rule: scored full, but the emit has no ordering step.
ppl_y = y[3]
ax.barh(ppl_y, 1, left=1, height=h, color="none", edgecolor="white", hatch="///", linewidth=0)
ax.text(0.5, ppl_y, "2", ha="center", va="center", color="white", fontweight="bold", fontsize=13,
        bbox=dict(boxstyle="round,pad=0.25", facecolor=cs.ACCENT, edgecolor="none"))

ax.set_xlim(0, 5)
cs.bare(ax)
ax.set_yticks(y)            # bare() cleared them; restore labels
ax.set_yticklabels(backends, fontsize=11.5)
ax.set_xticks(range(0, 6)); ax.tick_params(axis="both", length=0)
ax.set_xlabel("correlation rules (of 5)")
ax.grid(axis="x", color=cs.GRID); ax.grid(axis="y", visible=False); ax.set_axisbelow(True)
ax.set_ylim(-0.55, 3.45)

# legend in its own row under the plot, clear of bars and ticks
handles = [Patch(facecolor=cs.ACCENT, label="full fidelity"),
           Patch(facecolor=cs.ACCENT, hatch="///", edgecolor="white", label="scored full, loses order when run"),
           Patch(facecolor=cs.WARN, label="partial"),
           Patch(facecolor=cs.CONTEXT, label="refused (raised, no query)")]
ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.45, -0.17), ncol=4,
          frameon=False, fontsize=9.3, handlelength=1.6, columnspacing=1.2)

# the security-relevant cells, called out in the clear band above the plot area
fig.text(0.012, 0.79,
         "OpenSearch PPL: all 3 partials silently drop the time window, so the rule runs over the whole search range;\n"
         "the ordered-sequence rule (hatched) compiles to a co-occurrence count with no ordering step.",
         fontsize=9.3, color=cs.BAD, family=cs.SANS, ha="left", va="top")

cs.direction_note(fig, "full fidelity: higher is better")
cs.save(fig, "out/sigma-correlation-rule-fidelity-across-4.png")
print("rendered r12")
