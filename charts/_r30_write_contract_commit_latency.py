import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np

# Source: ocsf-write-contract/results/RESULTS.md + results.json (BENCH-D).
# Commit p50 latency (ms) and files-per-commit, Iceberg file-write vs DuckLake SQL-txn.
#   small_batch (50 x 100):  Iceberg p50 27.04, 4.02 files  | DuckLake p50 11.66, 1.0 file  (2.32x)
#   large_batch (10 x 5000): Iceberg p50 18.43, 4.1 files   | DuckLake p50 13.43, 1.0 file  (1.37x)
# The metadata tax bites at the SMALL commit (streaming); narrows on bulk.
batches = ["small batch\n(50 x 100 rows)", "large batch\n(10 x 5000 rows)"]
ice_p50 = [27.04, 18.43]
dl_p50  = [11.66, 13.43]
ice_files = [4.02, 4.1]
dl_files  = [1.0, 1.0]
ratios = [ice_p50[i] / dl_p50[i] for i in range(2)]   # 2.32x, 1.37x

x = np.arange(len(batches))
w = 0.34

fig, ax = cs.canvas(
    "The file-write tax bites the small streaming commit, not the bulk load.",
    "Median commit latency, Iceberg (a data file + manifest + metadata.json per commit) vs DuckLake (one SQL transaction) — the gap closes as rows-per-commit rises.",
    source="sdw-lab-benchmarks/ocsf-write-contract",
    tier="Tier B · single-host · synthetic OCSF · medians on this host · ISK never-write arm unmeasured (vendor-blocked)",
    figsize=(9.0, 5.0), bottom=0.18, top=0.80)

bi = ax.bar(x - w / 2, ice_p50, w, color=cs.ACCENT,  zorder=3, label="Iceberg (file-write contract)")
bd = ax.bar(x + w / 2, dl_p50,  w, color=cs.CONTEXT, zorder=3, label="DuckLake (SQL-transaction)")

# latency labels on bars
for b, v in zip(bi, ice_p50):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.6, f"{v:.1f} ms", ha="center", va="bottom",
            fontsize=10, color=cs.BODY, fontweight="bold")
for b, v in zip(bd, dl_p50):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.6, f"{v:.1f} ms", ha="center", va="bottom",
            fontsize=10, color=cs.BODY, fontweight="bold")

# files/commit inside the foot of each bar (the mechanism)
for b, f in zip(bi, ice_files):
    ax.text(b.get_x() + b.get_width() / 2, 1.0, f"{f:.2f}\nfiles/commit", ha="center", va="bottom",
            fontsize=8.5, color="white", fontweight="bold")
for b, f in zip(bd, dl_files):
    ax.text(b.get_x() + b.get_width() / 2, 1.0, f"{f:.1f}\nfile/commit", ha="center", va="bottom",
            fontsize=8.5, color=cs.BODY, fontweight="bold")

# the ratio over each batch group
for i in range(len(batches)):
    top = max(ice_p50[i], dl_p50[i])
    ax.text(x[i], top + 4.0, f"{ratios[i]:.2f}x", ha="center", va="bottom",
            fontsize=13, color=cs.ACCENT if i == 0 else cs.MUTED, fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(batches, fontsize=10.5)
ax.set_ylim(0, 34)
ax.set_ylabel("commit latency, p50 (ms)")
ax.grid(axis="y", color=cs.GRID); ax.grid(axis="x", visible=False)
ax.set_axisbelow(True)
ax.tick_params(length=0)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(loc="upper right", frameon=False, fontsize=9.5, labelcolor=cs.BODY)

ax.text(0.5, 31.2, "read-contract coherence: one engine reads both tiers, identical answers (True)",
        ha="center", va="center", fontsize=9, color=cs.GOOD, family=cs.MONO,
        transform=ax.get_xaxis_transform()) if False else None
fig.text(0.012, 0.085,
         "Read-contract coherence verified: one engine reads both tiers and returns identical answers.",
         fontsize=8.4, color=cs.GOOD, family=cs.MONO, ha="left", va="bottom")

cs.save(fig, "out/write-contract-commit-latency.png")
print("rendered; font in use =", cs.SANS)
