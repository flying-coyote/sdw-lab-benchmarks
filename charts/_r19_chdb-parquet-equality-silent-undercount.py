import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np

# Source: clickhouse-vs-duckdb/results/CORRECTNESS-DIVERGENCE.md
# DuckDB 1.5.3 vs chDB 4.1.8, SAME 10M-row Parquet (814 row groups). Ground truth = generator.
# chDB '=' over Parquet undercount per probe value (rows missed, all silent, no error):
#   user42 -7 · user1337 -6 · user7 -7 · user999 0 · user1500 -10 · user256 -12 · user1023 -10 · user64 0
# Diverged on 6 of 8; total undercount 52 rows. chDB LIKE, chDB MergeTree, DuckDB all correct.
probes = ["user42", "user1337", "user7", "user999",
          "user1500", "user256", "user1023", "user64"]
truth  = [5099, 4972, 5108, 5055, 5106, 5000, 5022, 5144]
miss   = [-7, -6, -7, 0, -10, -12, -10, 0]   # chDB '=' minus ground truth

# sort by miss magnitude (worst at top), keep the two correct ones at the bottom
order = sorted(range(len(probes)), key=lambda i: miss[i])  # most-negative first
probes = [probes[i] for i in order]
truth  = [truth[i]  for i in order]
miss   = [miss[i]   for i in order]

fig, ax = cs.canvas(
    "chDB's Parquet equality filter drops matching rows silently — fast and wrong.",
    "count(*) WHERE user_name = ? on a 10M-row Parquet file. chDB 4.1.8 undercounts 6 of 8 probe values; DuckDB, chDB LIKE and chDB MergeTree all return the true count.",
    source="sdw-lab-benchmarks/clickhouse-vs-duckdb · CORRECTNESS-DIVERGENCE.md",
    tier="Tier B · single-host · ground-truth-verified · chDB 4.1.8 Parquet '=' path only (LIKE + MergeTree correct)",
    figsize=(9.0, 4.9), bottom=0.16, top=0.80)

y = np.arange(len(probes))
colors = [cs.BAD if m < 0 else cs.GOOD for m in miss]
ax.barh(y, miss, color=colors, height=0.62, zorder=3)
for yi, m, t in zip(y, miss, truth):
    if m < 0:
        ax.text(m - 0.4, yi, f"{m}", ha="right", va="center", fontsize=10,
                color=cs.BAD, fontweight="bold")
        ax.text(0.3, yi, f"true {t:,}", ha="left", va="center", fontsize=8.5,
                color=cs.MUTED, family=cs.MONO)
    else:
        ax.text(0.3, yi, "exact", ha="left", va="center", fontsize=9,
                color=cs.GOOD, fontweight="bold")

ax.set_yticks(y); ax.set_yticklabels(probes, fontsize=10.5, family=cs.MONO)
ax.set_xlim(-14, 6)
ax.set_xlabel("Rows missed by chDB '=' vs ground truth")
ax.set_xticks([-12, -9, -6, -3, 0])
ax.axvline(0, color=cs.MUTED, linewidth=1.0, zorder=4)
ax.grid(axis="x", color=cs.GRID); ax.grid(axis="y", visible=False)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.tick_params(axis="y", length=0)

# headline: 52 rows total, returned with no error
ax.text(-13.5, len(probes) - 0.35,
        "52 rows short overall — no exception, no warning,\njust a confident count that is wrong",
        ha="left", va="top", fontsize=9.5, color=cs.BAD, family=cs.MONO)

cs.save(fig, "out/chdb-parquet-equality-silent-undercount.png")
print("rendered r19")
