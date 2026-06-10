import chartstyle as cs
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Source: parquet-library-matrix/results/RESULTS.md, Arm 1 (reader x forced encoding).
# 6 reader libraries x forced encodings vs exact ground truth (20k rows/col).
# Status: 0 = correct, 1 = errored-but-CAUGHT (safe), 2 = silent-wrong (NONE here).
# fastparquet errors on BYTE_STREAM_SPLIT (int64+double), DELTA_BYTE_ARRAY,
# DELTA_LENGTH_BYTE_ARRAY; duckdb errors on BYTE_STREAM_SPLIT-for-int64.
readers = ["duckdb", "pyarrow", "polars", "datafusion", "chdb", "fastparquet"]
rows = [
    ("int64 · PLAIN",                  [0, 0, 0, 0, 0, 0]),
    ("int64 · RLE_DICTIONARY",         [0, 0, 0, 0, 0, 0]),
    ("int64 · DELTA_BINARY_PACKED",    [0, 0, 0, 0, 0, 0]),
    ("int64 · BYTE_STREAM_SPLIT",      [1, 0, 0, 0, 0, 1]),
    ("string · PLAIN",                 [0, 0, 0, 0, 0, 0]),
    ("string · RLE_DICTIONARY",        [0, 0, 0, 0, 0, 0]),
    ("string · DELTA_BYTE_ARRAY",      [0, 0, 0, 0, 0, 1]),
    ("string · DELTA_LENGTH_BYTE_ARRAY",[0, 0, 0, 0, 0, 1]),
    ("double · PLAIN",                 [0, 0, 0, 0, 0, 0]),
    ("double · RLE_DICTIONARY",        [0, 0, 0, 0, 0, 0]),
    ("double · BYTE_STREAM_SPLIT",     [0, 0, 0, 0, 0, 1]),
]
labels = [r[0] for r in rows]
M = np.array([r[1] for r in rows])
nrow, ncol = M.shape

# colour map: 0 correct -> green, 1 errored-but-caught -> orange, 2 silent-wrong -> red
cmap = {0: cs.GOOD, 1: cs.WARN, 2: cs.BAD}
glyph = {0: "ok", 1: "err", 2: "X"}

fig, ax = cs.canvas(
    "Tune Parquet for size and the exotic encodings fail loud, not silent.",
    "Each library decoding a forced encoding vs exact ground truth — every miss here is a caught error; zero silently-wrong cells.",
    source="sdw-lab-benchmarks/parquet-library-matrix",
    tier="Tier B · single-host · 20k rows/col · VERSION-BOUND (re-run on any library upgrade)",
    figsize=(9.4, 5.7), bottom=0.20, top=0.80)

for i in range(nrow):
    for j in range(ncol):
        v = M[i, j]
        ax.add_patch(plt.Rectangle((j, nrow - 1 - i), 1, 1,
                     facecolor=cmap[v], edgecolor="white", lw=2))
        if v == 0:
            ax.plot(j + 0.5, nrow - 1 - i + 0.5, marker="o", ms=5,
                    mfc="white", mec="white")
        else:
            ax.text(j + 0.5, nrow - 1 - i + 0.5, "err", ha="center", va="center",
                    color="white", fontsize=8.5, fontweight="bold", family=cs.MONO)

ax.set_xlim(0, ncol)
ax.set_ylim(0, nrow)
ax.set_xticks(np.arange(ncol) + 0.5)
ax.set_xticklabels(readers, fontsize=10)
ax.set_yticks(np.arange(nrow) + 0.5)
ax.set_yticklabels(labels[::-1], fontsize=9.5, family=cs.MONO)
ax.tick_params(length=0)
ax.xaxis.set_ticks_position("top")
ax.xaxis.set_label_position("top")
for s in ax.spines.values():
    s.set_visible(False)
ax.grid(False)
ax.set_aspect("auto")

# legend — the absent category (silent-wrong) named so the "fails safe" point reads.
# Placed as figure text well above the mono footer so nothing collides.
fig.text(0.012, 0.115, "decoded correctly", fontsize=9.5, color=cs.GOOD,
         fontweight="bold", ha="left", va="center")
fig.text(0.012, 0.085, "errored — caught it (NotImplementedError / unsupported)",
         fontsize=9.5, color=cs.WARN, fontweight="bold", ha="left", va="center")
fig.text(0.012, 0.055, "silently wrong — none on these versions",
         fontsize=9.5, color=cs.BAD, fontweight="bold", ha="left", va="center")

cs.save(fig, "out/parquet-encoding-library-matrix.png")
print("rendered; font in use =", cs.SANS)
