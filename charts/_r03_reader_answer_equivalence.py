import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

# Source: clickhouse-vs-duckdb/results/MULTI-ENGINE-CORRECTNESS.md
# 13 Parquet readers (shared-bytes) + 2 controls, 24 cells each = 8 probe values x 3 predicates (=, IN, LIKE).
# Every cell checked against generator ground truth. Pass = correct count; fail = silent wrong answer.
# 11 of 13 readers pass all 24; chdb_parquet 11/24; fastparquet 0/24.
# Divergence map from the per-value table: which (value,predicate) cells each failer got WRONG.

values = ["user7", "user42", "user64", "user256", "user999",
          "user1023", "user1337", "user1500"]
preds = ["=", "IN", "LIKE"]
cells = [f"{v} {p}" for v in values for p in preds]  # 24 columns

# chdb_parquet: exact wrong (value,predicate) cells re-derived from the source per-value table.
# 13 wrong / 11 correct. Note user1500 is wrong on '=' ONLY (IN and LIKE correct).
chdb_wrong = {
    ("user42", "="), ("user42", "IN"),
    ("user1337", "="), ("user1337", "IN"),
    ("user7", "="), ("user7", "IN"),
    ("user1500", "="),
    ("user256", "="), ("user256", "IN"),
    ("user1023", "="), ("user1023", "IN"),
    ("user64", "="), ("user64", "IN"),
}
def chdb_pass(v, p):
    return (v, p) not in chdb_wrong

# fastparquet: wrong on ALL 24 cells.
def fast_pass(v, p):
    return False

# the 11 readers that pass everything (named as loudly as the failers)
clean_readers = [
    "duckdb  (DuckDB C++)",
    "datafusion  (arrow-rs)",
    "polars  (polars-parquet)",
    "pyarrow  (Arrow C++)",
    "daft  (arrow-rs I/O)",
    "clickhouse_server 25.10",
    "spark  (parquet-mr)",
    "starrocks  (C++)",
    "trino  (Java)",
    "dremio  (Java vectorized)",
    "postgres  (heap executor)",
]
# the 2 readers that return a silently wrong answer
fail_readers = [
    ("chdb_parquet  (ClickHouse C++ v3)", chdb_pass),
    ("fastparquet  (pure-Python)", fast_pass),
]

# Build a row per reader; rows ordered failers on top (the story) then clean block.
rows = []
labels = []
for name, fn in fail_readers:
    rows.append([1 if fn(v, p) else 0 for v in values for p in preds])
    labels.append(name)
for name in clean_readers:
    rows.append([1] * 24)
    labels.append(name)

M = np.array(rows)
nrow, ncol = M.shape

fig, ax = cs.canvas(
    "11 of 13 Parquet readers agree on the answer; 2 are silently wrong.",
    "Same byte-identical Parquet file (10M rows), 24 count(*) WHERE cells per reader, every count checked "
    "against ground truth. Red = a silently wrong count returned with no error. The passers are named as "
    "loudly as the failers: this is concentrated, not universal.",
    source="sdw-lab-benchmarks/clickhouse-vs-duckdb",
    tier="Tier B · single host · ground-truth-verified · version-bound (chDB 4.1.8, fastparquet 2026.5.0)",
    figsize=(12.2, 6.2), bottom=0.255, top=0.75)

green = cs.GOOD
red = cs.BAD
cmap_arr = np.empty(M.shape + (3,))
for i in range(nrow):
    for j in range(ncol):
        c = green if M[i, j] == 1 else red
        cmap_arr[i, j] = tuple(int(c[k:k+2], 16) / 255 for k in (1, 3, 5))

ax.imshow(cmap_arr, aspect="auto", interpolation="nearest")
ax.set_xticks(range(ncol))
ax.set_xticklabels(preds * len(values), rotation=0, fontsize=7.5, family=cs.MONO)
ax.set_yticks(range(nrow))
ax.set_yticklabels(labels, fontsize=9.0)
# white gridlines between cells
ax.set_xticks(np.arange(-0.5, ncol, 1), minor=True)
ax.set_yticks(np.arange(-0.5, nrow, 1), minor=True)
ax.grid(which="minor", color="white", linewidth=1.4)
ax.grid(which="major", visible=False)
ax.tick_params(which="both", length=0)
for s in ax.spines.values():
    s.set_visible(False)

# per-reader cells-correct tally on the right edge
for i in range(nrow):
    n_ok = int(M[i].sum())
    col = cs.BODY if n_ok == 24 else cs.BAD
    ax.text(ncol - 0.3, i, f"{n_ok}/24", ha="left", va="center",
            fontsize=9.5, fontweight="bold", color=col, family=cs.MONO)

# divider line under the 2 failers + value-group separators
ax.axhline(1.5, color=cs.INK, lw=1.6)
for g in range(1, len(values)):
    ax.axvline(g * 3 - 0.5, color=cs.MUTED, lw=1.0, ymin=0, ymax=1)
ax.text(-0.5, -1.0, "the 2 silently wrong readers", ha="left", va="bottom",
        fontsize=9, color=cs.BAD, fontweight="bold")

# value-group labels just below the predicate ticks
for gi, v in enumerate(values):
    ax.text(gi * 3 + 1, nrow + 0.05, v, ha="center", va="top",
            fontsize=8.0, color=cs.MUTED, family=cs.MONO, rotation=0)

ax.set_xlim(-0.5, ncol + 1.1)
ax.set_xlabel("8 user_name values  x  3 predicates ( = · IN · LIKE )  =  24 count(*) WHERE cells per reader",
              fontsize=10, labelpad=30)

legend = [Patch(facecolor=green, label="correct count"),
          Patch(facecolor=red, label="silently wrong (no error raised)")]
ax.legend(handles=legend, loc="upper left", bbox_to_anchor=(0.0, -0.42),
          ncol=2, frameon=False, fontsize=9.5)

cs.save(fig, "out/13-reader-answer-equivalence.png")
print("rendered r03")
