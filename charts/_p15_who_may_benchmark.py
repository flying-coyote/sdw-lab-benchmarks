import chartstyle as cs
import matplotlib.pyplot as plt

# Campaign closing visual: static table of who may run and publish an
# independent benchmark, per each vendor's current license text.
# License facts only — no Matrix scores, no performance numbers.

fig, ax = cs.canvas(
    "The SIEM you'd leave forbids the benchmark; the lakehouse you'd move to doesn't.",
    "Who may run and publish an independent comparison, per each vendor's current license text.",
    source="Splunk General Terms §1.2(v) · Splunk SLA §3(f) · Snowflake AUP · Databricks MCSA — license texts verified 2026-06",
    tier="primary license text",
    figsize=(8.8, 4.2), top=0.80, bottom=0.12)

ax.axis("off")
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)

# column anchor x-positions (axes fraction)
COLS = [0.00, 0.21, 0.575, 0.93]  # Vendor · Governing text · What it restricts · verdict
HEADERS = ["Vendor", "Governing text", "What it restricts", ""]

rows = [
    ("Splunk", "General Terms §1.2(v)\n+ SLA §3(f)",
     "running the comparison\nand sharing results", "✗", cs.BAD),
    ("Oracle Database", "“DeWitt clause”\n(since the 1980s)",
     "publishing comparative results", "✗", cs.BAD),
    ("Snowflake", "Acceptable Use Policy",
     "no benchmark restriction", "✓", cs.GOOD),
    ("Databricks", "Master Cloud Services\nAgreement",
     "no comparable clause", "✓", cs.GOOD),
]

header_y = 0.96
row_h = 0.215
top_y = 0.84  # center of first data row

# header
for x, h in zip(COLS, HEADERS):
    if h:
        ax.text(x, header_y, h, ha="left", va="center", fontsize=10.5,
                color=cs.MUTED, fontweight="bold")
ax.plot([0, 1], [header_y - 0.075] * 2, color=cs.GRID, lw=1.2,
        transform=ax.transAxes, clip_on=False)

for i, (vendor, clause, restricts, glyph, vcolor) in enumerate(rows):
    y = top_y - i * row_h
    if i % 2 == 0:
        ax.axhspan(y - row_h / 2 + 0.01, y + row_h / 2 - 0.01,
                   color=cs.SUBTLE, zorder=0)
    ax.text(COLS[0], y, vendor, ha="left", va="center", fontsize=12.5,
            fontweight="bold", color=cs.INK, zorder=3)
    ax.text(COLS[1], y, clause, ha="left", va="center", fontsize=9.5,
            family=cs.MONO, color=cs.BODY, zorder=3, linespacing=1.35)
    ax.text(COLS[2], y, restricts, ha="left", va="center", fontsize=10.5,
            color=cs.BODY, zorder=3, linespacing=1.35)
    # DejaVu Sans carries U+2713/U+2717 (DM Sans does not)
    ax.text(COLS[3] + 0.035, y, glyph, ha="center", va="center", fontsize=22,
            fontweight="bold", color=vcolor, zorder=3, family="DejaVu Sans")

cs.save(fig, "out/who-may-benchmark.png")
print("rendered p15")
