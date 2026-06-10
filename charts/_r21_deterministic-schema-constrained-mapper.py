import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np

# Source: ocsf-deterministic-mapper/results/RESULTS.md
# Schema-constrained deterministic mapper (only ever emits a path that exists in OCSF 1.8.0)
# vs phi3 under five grounding conditions, same 141-mapping gold key, same scoring.
# silent-error rate (mapping that VALIDATES, ships, and is wrong):
#   deterministic (schema-constrained)  0.00   (by construction)
#   phi3 / skill                        0.60
#   phi3 / schema                       0.69
#   phi3 / formal                       0.72
#   phi3 / wrong_grounding              0.72
#   phi3 / none                         0.99
# deterministic coverage 0.67; path-correct 0.24 among mapped, 0.16 overall.
rows = [
    ("deterministic\n(schema-constrained)", 0.00, cs.ACCENT, True),
    ("phi3 · skill",            0.60, cs.CONTEXT, False),
    ("phi3 · schema",           0.69, cs.CONTEXT, False),
    ("phi3 · formal",           0.72, cs.CONTEXT, False),
    ("phi3 · wrong-grounding",  0.72, cs.CONTEXT, False),
    ("phi3 · no grounding",     0.99, cs.BAD,     False),
]
# order: lowest silent-error at top
rows = sorted(rows, key=lambda r: r[1])
labels = [r[0] for r in rows]
vals   = [r[1] for r in rows]
colors = [r[2] for r in rows]

fig, ax = cs.canvas(
    "Constrain the output to the schema and the silent-error rate goes to zero.",
    "Share of source-to-OCSF mappings that validate, ship, and are wrong. The deterministic mapper can only emit paths that exist in OCSF 1.8.0, so it cannot invent one; phi3 invents 60-99% of the time.",
    source="sdw-lab-benchmarks/ocsf-deterministic-mapper · RESULTS.md · same 141-mapping gold key",
    tier="Tier B · single-host · the harness constraint does the safety work — a model behind the same constraint is also safe",
    figsize=(9.2, 4.9), bottom=0.16, top=0.80)

y = np.arange(len(labels))
ax.barh(y, vals, color=colors, height=0.62, zorder=3)
for yi, v, col in zip(y, vals, colors):
    if v == 0:
        ax.text(0.012, yi, "0.00  by construction", ha="left", va="center",
                fontsize=10.5, color=cs.ACCENT, fontweight="bold")
    else:
        ax.text(v - 0.012, yi, f"{v:.2f}", ha="right", va="center",
                fontsize=10.5, color="white", fontweight="bold")

ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=10)
ax.invert_yaxis()
ax.set_xlim(0, 1.0)
ax.set_xlabel("Silent-error rate  (mapping validates, ships, and is wrong)")
ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
ax.grid(axis="x", color=cs.GRID); ax.grid(axis="y", visible=False)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.tick_params(axis="y", length=0)

# honest framing footer note inside the plot (coverage trade)
ax.text(0.995, len(labels) - 0.4,
        "not 'rules beat models': the deterministic mapper covers only 0.67 of fields\n(rest left unmapped, not guessed) — but invents nothing. Schema-constraint is the lever.",
        ha="right", va="bottom", fontsize=8.5, color=cs.MUTED, family=cs.MONO)

cs.save(fig, "out/deterministic-schema-constrained-mapper.png")
print("rendered r21")
