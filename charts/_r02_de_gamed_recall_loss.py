import chartstyle as cs
import matplotlib.pyplot as plt

# Source: ocsf-context-collapse-apt29/results/RESULTS.md
# Verbatim SigmaHQ rules, real APT29 (Mordor/OTRF) ~143k events, Store F (fidelity) vs Store N (coarsened).
# adversary-tail (29 rules): mean recall-loss 0.3477, 9 fully blind (31.0%)
# routine (25 rules):        mean recall-loss 0.16,  4 fully blind (16.0%)
# Delta(adversary - routine) = 0.1877
# 9 named adversary-tail rules blinded F-matches -> 0:
ADV_LOSS, ADV_BLIND_PCT = 0.3477, 31.0
ROU_LOSS, ROU_BLIND_PCT = 0.16, 16.0

# (rule label, matches on Store F) -> 0 on Store N
blinded = [
    ("Uncommon Connection to AD Web Services", 10),
    ("Potential Suspicious PowerShell Keywords", 3),
    ("Windows Screen Capture (CopyFromScreen)", 2),
    ("Suspicious FromBase64String on Gzip Archive", 2),
    ("Malicious PowerShell Keywords", 2),
    ("Suspicious New-PSDrive to Admin Share", 1),
    ("PowerShell Base64 FromBase64String Cmdlet", 1),
    ("Malicious Base64 PowerShell Keywords in CmdLine", 1),
    ("Suspicious Execution of PowerShell w/ Base64", 1),
]

fig, (axL, axR) = cs.canvas(
    "Coarsening blinds the adversary-tail detections, not the routine ones.",
    "Verbatim SigmaHQ rules on real APT29 telemetry. Left: the 9 named rules that fired on the fidelity "
    "store and went fully blind—every detection drops to zero matches on the coarsened store. Right: "
    "mean recall lost per class.",
    source="sdw-lab-benchmarks/ocsf-context-collapse-apt29",
    tier="Tier B · single host · real APT29 (~143k events) · verbatim SigmaHQ via pySigma",
    figsize=(11.2, 5.4), bottom=0.16, top=0.74, ncols=2,
    gridspec_kw={"width_ratios": [1.55, 1.0]})

# ---- LEFT: dumbbell F-matches -> 0 ----
ys = list(range(len(blinded)))[::-1]
for y, (label, f) in zip(ys, blinded):
    axL.plot([f, 0], [y, y], color=cs.CONTEXT, lw=2.2, zorder=1)
    axL.scatter([f], [y], s=70, color=cs.ACCENT, zorder=3)           # Store F: detection fires
    axL.scatter([0], [y], s=70, color=cs.BAD, zorder=3)              # Store N: blind
    axL.text(f + 0.28, y, str(f), ha="left", va="center", fontsize=10,
             color=cs.ACCENT, fontweight="bold")
axL.set_yticks(ys)
axL.set_yticklabels([b[0] for b in blinded], fontsize=9.5)
axL.set_xlim(-0.7, 11.6)
axL.set_ylim(-0.7, len(blinded) - 0.3)
axL.set_xlabel("matches: Store F (fidelity, teal) drops to Store N (coarsened, red = blind)")
for s in ("top", "right", "left"):
    axL.spines[s].set_visible(False)
axL.grid(axis="x", color=cs.GRID); axL.grid(axis="y", visible=False)
axL.tick_params(axis="both", length=0)
axL.axvline(0, color=cs.BAD, lw=0.8, alpha=0.5, zorder=0)
axL.text(0, len(blinded) - 0.45, "0 = silently stops firing", ha="left", va="bottom",
         fontsize=9, color=cs.BAD, family=cs.MONO)

# ---- RIGHT: adversary vs routine mean recall-loss ----
cats = ["Adversary-tail\n(29 APT29-technique rules)", "Routine\n(25 other-technique rules)"]
vals = [ADV_LOSS, ROU_LOSS]
colors = [cs.BAD, cs.CONTEXT]
blind = [ADV_BLIND_PCT, ROU_BLIND_PCT]
ypos = [1, 0]
axR.barh(ypos, vals, color=colors, height=0.5, zorder=2)
for y, v, b in zip(ypos, vals, blind):
    axR.text(v + 0.008, y + 0.02, f"{v:.2f}", ha="left", va="center",
             fontsize=14, fontweight="bold", color=cs.BODY)
    axR.text(v + 0.008, y - 0.20, f"{b:.0f}% went fully blind",
             ha="left", va="center", fontsize=8.5, color=cs.MUTED, family=cs.MONO)
axR.set_yticks(ypos); axR.set_yticklabels(cats, fontsize=10)
axR.set_xlim(0, 0.46)
axR.set_xlabel("mean recall lost under coarsening")
cs.bare(axR)
axR.set_yticks(ypos); axR.set_yticklabels(cats, fontsize=10)
axR.grid(axis="x", color=cs.GRID); axR.grid(axis="y", visible=False)
axR.tick_params(axis="x", length=0)
# delta annotation
axR.annotate("", xy=(ADV_LOSS, 1), xytext=(ROU_LOSS, 1),
             arrowprops=dict(arrowstyle="-", color=cs.MUTED, lw=0))
axR.text(0.23, 0.5, "gap = +0.19\nadversary vs routine", ha="center", va="center",
         fontsize=10.5, color=cs.ACCENT, fontweight="bold")

cs.direction_note(fig, "recall loss: lower is better")
cs.save(fig, "out/de-gamed-recall-loss.png")
print("rendered r02")
