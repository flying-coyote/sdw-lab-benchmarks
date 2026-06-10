import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np

# Source: sdpp-ingest-throughput/results/RESULTS.md — file mode (full route:
# read+parse+filter+re-serialize+write). 1M Zeek conn.log events.
# events/s (median) and peak RSS MB. rsyslog raw-line-match is a substring matcher,
# NOT a JSON field filter — labelled apart; only json-parse is parse-comparable.
# engine, events/s, peak RSS MB, parse_comparable
data = [
    ("rsyslog (raw-line match *)",  149182,   9, False),
    ("rsyslog (json-parse)",         93740, 230, True),
    ("tenzir 6.0.0 (unstable +)",    89606, 400, True),
    ("otelcol-contrib",              30496, 218, True),
    ("vector",                       26137, 541, True),
    ("alloy",                        22096, 265, True),
]
# sort by events/s ascending so the fastest sits at top of an hbar
data = sorted(data, key=lambda r: r[1])
names = [d[0] for d in data]
eps   = [d[1] for d in data]
rss   = [d[2] for d in data]
comparable = [d[3] for d in data]

y = np.arange(len(names))
# accent the parse-comparable JSON engines; grey the non-comparable raw-line row
ep_colors = [cs.ACCENT if c else cs.CONTEXT for c in comparable]

fig, (axL, axR) = cs.canvas(
    "Throughput and memory split six OSS ingest engines by an order of magnitude.",
    "Full read-parse-filter-write route on 1M Zeek conn.log events — teal bars are JSON-parse comparable; rsyslog raw-line is a substring matcher, shown apart.",
    source="sdw-lab-benchmarks/sdpp-ingest-throughput",
    tier="Tier B · single WSL2 host · warm cache · file mode · Cribl/Splunk-UF are Tier-C docs-only (not shown)",
    figsize=(9.8, 5.1), bottom=0.18, top=0.79, ncols=2,
    gridspec_kw={"width_ratios": [1.15, 1]})

# --- left: throughput ---
axL.barh(y, eps, color=ep_colors, height=0.62, zorder=3)
for yi, v, c in zip(y, eps, comparable):
    axL.text(v + max(eps) * 0.015, yi, f"{v:,}", va="center", ha="left",
             fontsize=10, color=cs.BODY, fontweight="bold")
axL.set_yticks(y)
axL.set_yticklabels(names, fontsize=10)
axL.set_xlim(0, max(eps) * 1.20)
axL.set_xlabel("events / second  (median)")
axL.grid(axis="x", color=cs.GRID); axL.grid(axis="y", visible=False)
axL.set_axisbelow(True)
for s in ("top", "right", "left"):
    axL.spines[s].set_visible(False)
axL.tick_params(length=0)

# --- right: peak RSS (memory) — same engine order, no y labels (shared) ---
rss_colors = [cs.BAD if v >= 400 else (cs.GOOD if v <= 12 else cs.CONTEXT) for v in rss]
axR.barh(y, rss, color=rss_colors, height=0.62, zorder=3)
for yi, v in zip(y, rss):
    axR.text(v + max(rss) * 0.015, yi, f"{v} MB", va="center", ha="left",
             fontsize=10, color=cs.BODY, fontweight="bold")
axR.set_yticks(y)
axR.set_yticklabels([])
axR.set_xlim(0, max(rss) * 1.22)
axR.set_xlabel("peak RSS (MB)")
axR.grid(axis="x", color=cs.GRID); axR.grid(axis="y", visible=False)
axR.set_axisbelow(True)
for s in ("top", "right", "left"):
    axR.spines[s].set_visible(False)
axR.tick_params(length=0)

fig.text(0.012, 0.075,
         "* raw-line match is a lighter, non-parse operation (grey).   + tenzir 6.0.0 has a ~1-in-6 shutdown segfault on this build.",
         fontsize=8.2, color=cs.MUTED, family=cs.MONO, ha="left", va="bottom")

cs.direction_note(fig, "throughput: higher is better", x=0.545, y=0.215, va="bottom")
cs.direction_note(fig, "peak RSS: lower is better", x=0.960, y=0.735, va="center")
cs.save(fig, "out/ingest-engine-throughput-rss.png")
print("rendered; font in use =", cs.SANS)
