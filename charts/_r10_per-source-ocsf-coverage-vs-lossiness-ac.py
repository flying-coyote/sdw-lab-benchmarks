import chartstyle as cs
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# Source: ocsf-mapping-fidelity/results/RESULTS.md:27-34  (OCSF 1.8.0, transcribed-subset validator)
# per source: total fields, typed, coerced, unmapped
# Palo Alto uses the strict full-schema re-score: 44 typed / 8 coerced / 31 unmapped of 83 (53.01%),
# ocsf-1.9-rescore/RESULTS.md:84 and ocsf-mapping-fidelity/results/RESULTS.md:49 (two PAN-OS hw_info.model
# targets do not exist in 1.8.0). The other five sources are unchanged under the strict re-score (:82-87).
# Okta callout: ocsf-mapping-fidelity/results/RESULTS.md:39 (36 of 50 have a typed or coercible home;
# okta/okta-ocsf-syslog carries 18 of 50).
# Title range (2026-11-23): typed share runs 46% (Umbrella 6/13) to 70% (CrowdStrike 30/43); coerced + unmapped
# runs 30% (CrowdStrike 13/43) to 54% (Umbrella 7/13).
rows = [
    ("CrowdStrike",      "detection_finding 2004", 43, 30, 9, 4),
    ("Cisco ASA",        "network_activity 4001",  26, 16, 3, 7),
    ("Okta",             "authentication 3002",    50, 29, 7, 14),
    ("Zscaler",          "http_activity 4002",     36, 21, 4, 11),
    ("Palo Alto",        "network_activity 4001",  83, 44, 8, 31),
    ("Cisco Umbrella",   "dns_activity 4003",      13, 6,  2, 5),
]
# sort by typed-coverage ascending so best (most typed) lands at top after invert
rows = sorted(rows, key=lambda r: r[3] / r[2])
names = [r[0] for r in rows]
y = list(range(len(rows)))

fig, ax = cs.canvas(
    "OCSF types 46–70% of fields cleanly; 30–54% lose something.",
    "Per-source field disposition into OCSF 1.8.0: typed (clean), coerced (a boundary crossed), unmapped (no typed home). Share of each source's scoped field set.",
    source="sdw-lab-benchmarks/ocsf-mapping-fidelity",
    tier="Tier B · strict re-score against the full OCSF 1.8.0 schema · coverage is over each source's scoped field set",
    figsize=(9.4, 5.4), bottom=0.23, top=0.74)

for i, (name, cls, total, typed, coerced, unmapped) in enumerate(rows):
    t, c, u = typed / total * 100, coerced / total * 100, unmapped / total * 100
    ax.barh(i, t, color=cs.ACCENT, height=0.62, zorder=3)
    ax.barh(i, c, left=t, color=cs.WARN, height=0.62, zorder=3)
    ax.barh(i, u, left=t + c, color=cs.CONTEXT, height=0.62, zorder=3)
    ax.text(t / 2, i, f"{t:.0f}%", ha="center", va="center", color="white", fontweight="bold", fontsize=10)
    if c >= 7:
        ax.text(t + c / 2, i, f"{c:.0f}%", ha="center", va="center", color="white", fontsize=9)
    ax.text(t + c + u / 2, i, f"{u:.0f}%", ha="center", va="center", color=cs.BODY, fontsize=9.5)
    # field count at far right
    ax.text(101.5, i, f"{total} fields", ha="left", va="center", color=cs.MUTED, fontsize=9)

ax.set_xlim(0, 112)
ax.set_xticks([0, 25, 50, 75, 100])
ax.set_xticklabels(["0", "25", "50", "75", "100%"])
cs.bare(ax)
ax.set_yticks(y)            # bare() clears the y ticks; restore the source names after it
ax.set_yticklabels([r[0] for r in rows], fontsize=10.5)
ax.grid(axis="x", color=cs.GRID); ax.grid(axis="y", visible=False)
ax.set_axisbelow(True); ax.tick_params(length=0)
ax.spines["bottom"].set_bounds(0, 100)   # the axis ends at 100%; the space past it holds the field counts

handles = [
    Patch(facecolor=cs.ACCENT, label="typed (clean OCSF home)"),
    Patch(facecolor=cs.WARN,   label="coerced (a boundary crossed)"),
    Patch(facecolor=cs.CONTEXT, label="unmapped (no typed home)"),
]
ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.45, -0.09),
          ncol=3, frameon=False, fontsize=9.5, handlelength=1.2)

# Okta shipped-mapper note: a starred row label plus a note line in the band above the plot,
# so no arrow crosses the other bars
okta_i = names.index("Okta")
ax.set_yticklabels([("Okta *" if n == "Okta" else n) for n in names], fontsize=10.5)
ax.get_yticklabels()[okta_i].set_color(cs.BAD)
fig.text(0.012, 0.785,
         "* Okta is the only source with a public shipped mapper: OCSF can hold 36 of its 50 fields, "
         "and the mapper carries only 18.",
         fontsize=9.3, color=cs.BAD, family=cs.SANS, ha="left", va="top")

cs.direction_note(fig, "typed share: higher is better")
cs.save(fig, "out/per-source-ocsf-coverage-vs-lossiness-ac.png")
print("rendered r10")
