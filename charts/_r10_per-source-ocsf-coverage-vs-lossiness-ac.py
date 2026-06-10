import chartstyle as cs
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# Source: ocsf-mapping-fidelity/results/RESULTS.md  (OCSF 1.8.0, schema-validated)
# per source: total fields, typed, coerced, unmapped
rows = [
    ("CrowdStrike",      "detection_finding 2004", 43, 30, 9, 4),
    ("Cisco ASA",        "network_activity 4001",  26, 16, 3, 7),
    ("Okta",             "authentication 3002",    50, 29, 7, 14),
    ("Zscaler",          "http_activity 4002",     36, 21, 4, 11),
    ("Palo Alto",        "network_activity 4001",  83, 46, 8, 29),
    ("Cisco Umbrella",   "dns_activity 4003",      13, 6,  2, 5),
]
# sort by typed-coverage ascending so best (most typed) lands at top after invert
rows = sorted(rows, key=lambda r: r[3] / r[2])
names = [r[0] for r in rows]
y = list(range(len(rows)))

fig, ax = cs.canvas(
    "OCSF carries most fields cleanly — but a third to a half lose something.",
    "Per-source field disposition into OCSF 1.8.0: typed (clean), coerced (a boundary crossed), unmapped (no typed home). Share of each source's scoped field set.",
    source="sdw-lab-benchmarks/ocsf-mapping-fidelity",
    tier="Tier B · schema-validated against OCSF 1.8.0 · coverage is over each source's scoped field set",
    figsize=(9.4, 5.0), bottom=0.16, top=0.79)

for i, (name, cls, total, typed, coerced, unmapped) in enumerate(rows):
    t, c, u = typed / total * 100, coerced / total * 100, unmapped / total * 100
    ax.barh(i, t, color=cs.ACCENT, height=0.62, zorder=3)
    ax.barh(i, c, left=t, color=cs.WARN, height=0.62, zorder=3)
    ax.barh(i, u, left=t + c, color=cs.CONTEXT, height=0.62, zorder=3)
    ax.text(t / 2, i, f"{t:.0f}%", ha="center", va="center", color="white", fontweight="bold", fontsize=10)
    if c >= 7:
        ax.text(t + c / 2, i, f"{c:.0f}", ha="center", va="center", color="white", fontsize=9)
    ax.text(t + c + u / 2, i, f"{u:.0f}%", ha="center", va="center", color=cs.BODY, fontsize=9.5)
    # field count at far right
    ax.text(101.5, i, f"{total} fields", ha="left", va="center", color=cs.MUTED, fontsize=9)

ax.set_yticks(y)
ax.set_yticklabels([r[0] for r in rows], fontsize=10.5)

ax.set_xlim(0, 112)
ax.set_xticks([0, 25, 50, 75, 100])
ax.set_xticklabels(["0", "25", "50", "75", "100%"])
cs.bare(ax)
ax.grid(axis="x", color=cs.GRID); ax.grid(axis="y", visible=False)
ax.set_axisbelow(True); ax.tick_params(length=0)

handles = [
    Patch(facecolor=cs.ACCENT, label="typed (clean OCSF home)"),
    Patch(facecolor=cs.WARN,   label="coerced (a boundary crossed)"),
    Patch(facecolor=cs.CONTEXT, label="unmapped (no typed home)"),
]
ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.30),
          ncol=3, frameon=False, fontsize=9.5, handlelength=1.2)

# Okta shipped-mapper callout — text in clear space top-right, arrow to the Okta bar
okta_i = names.index("Okta")
ax.annotate("Okta is the only source with a public shipped mapper:\nOCSF can hold 36 of 50 fields — it carries only 18",
            xy=(70, okta_i), xytext=(58, len(rows) - 0.35),
            ha="left", va="center", fontsize=9.2, color=cs.BAD, family=cs.MONO,
            arrowprops=dict(arrowstyle="->", color=cs.BAD, lw=1.2,
                            connectionstyle="arc3,rad=-0.2"))

cs.save(fig, "out/per-source-ocsf-coverage-vs-lossiness-ac.png")
print("rendered r10")
