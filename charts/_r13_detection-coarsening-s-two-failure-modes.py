import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np

# Source: ocsf-sigma-detection/results/STORE-N-PRECISION.md
# Same compiled Sigma over Store F (fidelity) vs Store N (coarse). Two failure modes:
#   c2_domain      recall    1   -> 0       BLIND      (rare-DNS sampling dropped the one resolution)
#   nomfa_privesc  precision 1.0 -> 0.0037  CRY-WOLF   (matches 1 -> 268; absence coerced to false)
#   encoded_powershell  survived 1->1 (cmd-line truncation didn't reach -EncodedCommand)
#   rdp_lateral         unchanged (precision 0.0003->0.0003, matches 2960->2960; flow rollup coalesced nothing)

fig, (axL, axR) = cs.canvas(
    "Coarsening blinds some rules and makes others cry wolf.",
    "Same compiled Sigma, two stores. Store N is the volume-driven coarse store; each rule degrades on the "
    "mechanism that touched its keying field.",
    source="sdw-lab-benchmarks/ocsf-sigma-detection",
    tier="Tier B · single-host · one synthetic chain · magnitudes this corpus's, the two modes transferable",
    figsize=(9.8, 4.8), bottom=0.20, top=0.74, ncols=2)
plt.subplots_adjust(wspace=0.50, left=0.14, right=0.965)

# ---- LEFT: BLIND — recall F->N (c2_domain goes to zero) ----
rules_L = ["c2_domain\n(rare-DNS sampling)", "encoded_powershell\n(cmd-line truncation)"]
recall_F = [1.0, 1.0]
recall_N = [0.0, 1.0]
yL = np.array([1.0, 0.0])

for yi, f, n in zip(yL, recall_F, recall_N):
    axL.plot([n, f], [yi, yi], color=cs.GRID, lw=3, zorder=1, solid_capstyle="round")
    axL.scatter([f], [yi], s=120, color=cs.CONTEXT, zorder=3)
    axL.scatter([n], [yi], s=150, color=(cs.BAD if n < f else cs.GOOD), zorder=3)
axL.text(1.0, yL[0]+0.20, "Store F  1.0", ha="right", va="bottom", fontsize=9.3, color=cs.MUTED)
axL.text(0.0, yL[0]+0.20, "Store N  0  ->  BLIND", ha="left", va="bottom", fontsize=9.8, color=cs.BAD, fontweight="bold")
axL.text(1.0, yL[1]+0.20, "F 1.0 = N 1.0  survived", ha="right", va="bottom", fontsize=9.3, color=cs.GOOD)

axL.set_xlim(-0.08, 1.18); axL.set_ylim(-0.7, 1.85)
axL.set_yticks(yL); axL.set_yticklabels(rules_L, fontsize=9.4)
axL.set_xticks([0, 0.5, 1.0]); axL.tick_params(axis="x", length=0)
axL.set_xlabel("recall  (Store F -> Store N)")
for s in ("top", "right", "left"): axL.spines[s].set_visible(False)
axL.grid(axis="x", color=cs.GRID); axL.grid(axis="y", visible=False); axL.set_axisbelow(True)
axL.text(-0.08, 1.78, "Failure mode 1 — go blind", fontsize=11, color=cs.ACCENT,
         fontweight="bold", ha="left", va="top")

# ---- RIGHT: CRY-WOLF — matches F->N (1 -> 268) ----
match_F, match_N = 1, 268
axR.barh([0], [match_N], height=0.42, color=cs.BAD, edgecolor="white", linewidth=1.4, zorder=2)
axR.barh([0], [match_F], height=0.42, color=cs.CONTEXT, edgecolor="white", linewidth=1.4, zorder=3)
axR.text(match_N - 6, 0, f"N: {match_N} matches\nprecision 1.0 -> 0.0037", ha="right", va="center",
         fontsize=9.6, color="white", fontweight="bold")
axR.text(match_F + 4, 0.30, "F: 1 match (precision 1.0)", ha="left", va="bottom", fontsize=9.3, color=cs.MUTED)

axR.set_xlim(0, 300); axR.set_ylim(-0.7, 1.0)
axR.set_yticks([0]); axR.set_yticklabels(["nomfa_privesc\n(MFA absent->false)"], fontsize=9.4)
axR.set_xticks([0, 100, 200, 300]); axR.tick_params(axis="x", length=0)
axR.set_xlabel("alert matches  (1 true positive, the rest false)")
for s in ("top", "right", "left"): axR.spines[s].set_visible(False)
axR.grid(axis="x", color=cs.GRID); axR.grid(axis="y", visible=False); axR.set_axisbelow(True)
axR.text(0, 0.92, "Failure mode 2 — cry wolf", fontsize=11, color=cs.WARN,
         fontweight="bold", ha="left", va="top")

cs.direction_note(fig, "recall: higher is better", x=0.465, y=0.285, ha="right", va="top")
cs.direction_note(fig, "false alerts: lower is better")
cs.save(fig, "out/detection-coarsening-s-two-failure-modes.png")
print("rendered r13")
