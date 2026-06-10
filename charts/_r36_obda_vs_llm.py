import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np

# Source: ocsf-semantic-query/results/RESULTS.md  (PRELIMINARY — one arm of three)
# Adversary-tail concept queries.
#  text-to-SQL (phi4): attempted A1,A2,A6,A8 -> 2 correct, 2 loud, 0 silent (acc 0.50)
#  OBDA/Ontop 5.5.0 (OWL2QL): of 8 adversary queries, 3 expressible (A2,A4,A6) all correct,
#    5 out-of-OWL2QL = loud-by-design (A1,A3,A5,A7,A9). 0 silent. 100% correct on expressible.
# Both fail LOUDLY here; the distinction the bench targets (silent error) needs a
# frontier LLM leg (pending). The honest contrast is coverage vs how it fails.
# Express each as count out of its full adversary-query attempt set (LLM 4 attempted; OBDA 8 scoped).
# To compare on a common denominator, show shares of the 8-query adversary set OBDA scopes;
# for the LLM, chart its 4 attempted as-is and label the denominator.

labels = ["OBDA / Ontop\n(OWL2QL rewrite)", "Text-to-SQL\n(local LLM, phi4)"]
# segments: correct, loud-fail (refused / errored), silent-wrong
correct  = [3, 2]
loud     = [5, 2]   # OBDA out-of-expressivity (loud by design); LLM hallucinated cols -> error/empty
silent   = [0, 0]
denom    = ["of 8 adversary queries", "of 4 attempted"]

fig, ax = cs.canvas(
    "Neither is silently wrong here — they differ in coverage and how they fail",
    "Adversary-tail outcomes. OBDA answers a narrow set exactly and refuses the rest loudly; the local LLM is broader-attempted but loud-broken.",
    source="sdw-lab-benchmarks/ocsf-semantic-query",
    tier="Tier B · single-host · PRELIMINARY (1 of 3 arms; frontier-LLM + GraphRAG legs pending)",
    figsize=(8.8, 4.9), bottom=0.24, top=0.78)

y = np.arange(len(labels))[::-1] + 0.35   # lift bars to leave room for a bottom legend row
h = 0.46

left = [0, 0]
segs = [("Correct", correct, cs.ACCENT, "white"),
        ("Loud failure (refused / errored)", loud, cs.CONTEXT, cs.BODY),
        ("Silently wrong", silent, cs.BAD, "white")]
for name, vals, color, tcol in segs:
    bars = ax.barh(y, vals, left=left, height=h, color=color,
                   edgecolor="white", linewidth=1.4, zorder=3)
    for yi, v, l in zip(y, vals, left):
        if v > 0:
            ax.text(l + v / 2, yi, str(v), ha="center", va="center",
                    color=tcol, fontweight="bold", fontsize=12)
    left = [a + b for a, b in zip(left, vals)]

# the silent=0 callout (the integrity point)
ax.text(left[0] + 0.15, y[0], "0 silently wrong", ha="left", va="center",
        fontsize=9.5, color=cs.GOOD, family=cs.MONO, fontweight="bold")
ax.text(left[1] + 0.15, y[1], "0 silently wrong", ha="left", va="center",
        fontsize=9.5, color=cs.GOOD, family=cs.MONO, fontweight="bold")

# denominators (just under each bar's left edge)
for yi, d in zip(y, denom):
    ax.text(0.08, yi - 0.32, d, ha="left", va="top", fontsize=8.5,
            color=cs.MUTED, family=cs.MONO)

ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=11)
ax.set_xlim(0, 9.2)
ax.set_ylim(-0.55, max(y) + h)
ax.set_xlabel("queries")
cs.bare(ax)
ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=11)
ax.tick_params(axis="y", length=0)
ax.tick_params(axis="x", length=0)
ax.set_xticks(range(0, 10))
ax.grid(axis="x", color=cs.GRID)
ax.grid(axis="y", visible=False)
ax.set_axisbelow(True)

# horizontal color key along the bottom, inside the plot, clear of the bars
legy = -0.42
keyx = 0.1
for name, color in [("Correct", cs.ACCENT), ("Loud failure (refused / errored)", cs.CONTEXT), ("Silently wrong", cs.BAD)]:
    ax.add_patch(plt.Rectangle((keyx, legy - 0.07), 0.18, 0.14, color=color, clip_on=False, zorder=5))
    ax.text(keyx + 0.30, legy, name, ha="left", va="center", fontsize=9, color=cs.BODY)
    keyx += 0.30 + len(name) * 0.105 + 0.55

cs.save(fig, "out/obda-ontop-vs-llm-text-to-sql-on-adversary.png")
print("rendered obda")
