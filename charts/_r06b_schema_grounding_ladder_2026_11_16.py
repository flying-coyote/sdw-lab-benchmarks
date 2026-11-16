"""Corrected r06 (2026-11-16). Supersedes _r06_schema_grounding_ladder.py's frontier bars and wording.

Why: (1) the June scorer validated against a transcribed OCSF 1.8.0 subset missing 24 gold mappings, which
inflated the frontier proxy's silent-error rate; the frontier bars here are re-scored against the full 1.8.0
schema (ocsf-deterministic-mapper/results/RESULTS-FRONTIER-CONSTRAINED-2026-11-16.md, results JSON key
frontier_per_condition_full). (2) the "schema" condition showed the first 80 one-level paths alphabetically
(ocsf-mapping-oracle/run.py l.130-131), so it is labelled a partial path list. (3) the old subtitle said the
control showed "content, not tokens", the reverse of the bench reading. (4) frontier run 3 is omitted because
its schema batch is excluded (possible answer-key exposure, see the same RESULTS file).

Local rungs: June scorer values (ocsf-mapping-oracle/results/RESULTS.md); where cached predictions allowed a
full-schema re-score (gemma4:26b all conditions; phi3 partial-list) they moved by at most 0.01.
Frontier (full 1.8.0 validator, 141 prompts each):
  run 1: none 15/141=0.106  partial 1/141=0.007  wrong-class 7/141=0.050
  run 2: none 14/141=0.099  partial 14/141=0.099 wrong-class 5/141=0.035
"""
import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

models = ["phi3 (3.8B)", "gemma4:26b", "claude-opus-4-8\nfrontier proxy, run 1", "claude-opus-4-8\nfrontier proxy, run 2"]
none = [0.99, 0.83, 0.106, 0.099]
partial = [0.69, 0.18, 0.007, 0.099]
wrong = [0.72, 0.18, 0.050, 0.035]

fig, ax = cs.canvas(
    "A partial path list cuts invented OCSF paths for local models; at the frontier it doesn't replicate.",
    "Silent-error rate (a predicted OCSF path that does not exist; lower is better) with no help vs a partial\n"
    "path list in the prompt (the first 80 one-level paths, alphabetically). \nThe grey diamond is the wrong-class "
    "grounding note, which scores within about a point of the correct-class note,\nand lower on frontier run 2, "
    "so the prose grounding did no measurable work.",
    source="sdw-lab-benchmarks, re-score 2026-11-16",
    tier="Tier B · local: temp-0, June scorer · frontier: batched subagents, full OCSF 1.8.0 re-score · n=141/bar · run 3 omitted",
    figsize=(10.4, 6.0), bottom=0.20, top=0.66)

x = np.arange(len(models))
w = 0.36
b1 = ax.bar(x - w/2, none, w, color=cs.CONTEXT, zorder=3, label="no grounding")
b2 = ax.bar(x + w/2, partial, w, color=cs.ACCENT, zorder=3, label="partial path list")
for xi, v in zip(x - w/2, none):
    ax.text(xi, v + 0.015, f"{v:.2f}", ha="center", va="bottom", fontsize=12, color=cs.BODY)
for xi, v in zip(x + w/2, partial):
    ax.text(xi, v + 0.015, f"{v:.2f}", ha="center", va="bottom", fontsize=12, fontweight="bold", color=cs.ACCENT)
for xi, wv in zip(x + w/2, wrong):
    ax.scatter(xi + 0.12, wv, marker="D", s=55, color=cs.MUTED, zorder=5, edgecolor="white", linewidth=0.8)
for xi, n, s in zip(x, none, partial):
    d = n - s
    ax.text(xi, max(n, s) + 0.085, ("-" if d > 0.0049 else "±") + f"{abs(d):.2f}", ha="center", va="bottom",
            fontsize=10.5, color=cs.GOOD if d > 0.0049 else cs.MUTED, fontweight="bold")

ax.set_xticks(x); ax.set_xticklabels(models, fontsize=10)
ax.set_ylim(0, 1.15)
ax.set_ylabel("silent-error rate  (invented OCSF paths)")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.spines["left"].set_color(cs.GRID)
ax.grid(axis="y", color=cs.GRID); ax.grid(axis="x", visible=False)
ax.tick_params(axis="both", length=0)
handles = [b1, b2, Line2D([0], [0], marker="D", color="none", markerfacecolor=cs.MUTED,
                          markeredgecolor="white", markersize=8, label="wrong-class grounding note (control)")]
ax.legend(handles=handles, loc="upper right", frameon=False, fontsize=9.5, ncol=1,
          bbox_to_anchor=(1.0, 1.03), handletextpad=0.6)
ax.text(2.5, 0.56, "frontier, full-schema re-score:\nthe partial list helped on run 1\nand not on run 2",
        ha="center", va="top", fontsize=8.2, color=cs.MUTED, family=cs.MONO)
cs.direction_note(fig, "silent errors: lower is better", y=0.99, va="bottom")
cs.save(fig, "out/schema-grounding-cuts-invented-paths-2026-11-16.png")
print("rendered r06b")
