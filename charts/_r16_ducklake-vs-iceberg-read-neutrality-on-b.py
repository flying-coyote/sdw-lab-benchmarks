import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np

# Source: ocsf-read-scan/results/SAME-FILES.md (byte-identical, 1B rows) + PARITY.md (codec x format)
# LEFT  — SAME-FILES: bytes literally identical (11.41 GB each), Iceberg/DuckLake ratio per query.
#   filtered 1.00x, byte_rollup 1.01x, subnet_rollup 1.01x (parity within CV); topn_src 1.30x = CANDIDATE spill.
# RIGHT — PARITY decomposition (matched row-group, vary one knob): format effect vs codec effect.
#   format effect (zstd) 0.95-1.14x; codec effect up to 1.51x (byte_rollup, ducklake) — the bigger lever.

# ----- LEFT data -----
q_sf      = ["filtered", "byte_rollup", "subnet_rollup", "topn_src"]
ratio_sf  = [1.00, 1.01, 1.01, 1.30]
cv_flag   = [False, False, False, True]   # topn_src is the candidate-spill outlier

# ----- RIGHT data (PARITY decomposition tables) -----
q_p       = ["filtered", "topn_src", "byte_rollup", "subnet_rollup"]
fmt_zstd  = [0.95, 1.14, 1.07, 1.13]      # format effect (Iceberg/DuckLake) at matched zstd
codec_dl  = [1.19, 1.05, 1.51, 1.09]      # codec effect (Snappy/ZSTD) within DuckLake

fig, (axL, axR) = cs.canvas(
    "On byte-identical Parquet, the format is read-neutral; the codec isn't.",
    "When the same bytes register into both catalogs, latency is at parity. The apparent format 'speedup' decomposes "
    "to the writer's codec choice.",
    source="sdw-lab-benchmarks/ocsf-read-scan",
    tier="Tier B · single-host · hot/warm · 1B rows byte-identical · read each query against its own CV",
    figsize=(10.0, 4.9), bottom=0.22, top=0.74, ncols=2)
plt.subplots_adjust(wspace=0.50, left=0.10, right=0.965)

# ---- LEFT: byte-identical per-query ratio (Iceberg / DuckLake) ----
y = np.arange(len(q_sf))[::-1]
cols = [cs.WARN if f else cs.ACCENT for f in cv_flag]
axL.barh(y, ratio_sf, height=0.6, color=cols, edgecolor="white", linewidth=1.4, zorder=3)
axL.axvline(1.0, color=cs.MUTED, lw=1.2, ls="--", zorder=2)
for yi, v, f in zip(y, ratio_sf, cv_flag):
    axL.text(v + 0.012, yi, f"{v:.2f}×", ha="left", va="center",
             color=(cs.WARN if f else cs.ACCENT), fontweight="bold", fontsize=11.5)
axL.set_xlim(0.9, 1.42)
axL.set_yticks(y); axL.set_yticklabels(q_sf, fontsize=10.5)
axL.set_xticks([0.9, 1.0, 1.1, 1.2, 1.3, 1.4])
axL.set_xlabel("Iceberg ÷ DuckLake  (>1 = DuckLake faster)")
for s in ("top", "right", "left"): axL.spines[s].set_visible(False)
axL.grid(axis="x", color=cs.GRID); axL.grid(axis="y", visible=False); axL.set_axisbelow(True)
axL.tick_params(length=0)
axL.text(1.0, y[0]+0.45, "parity", color=cs.MUTED, fontsize=8.6, ha="center", va="bottom")
axL.annotate("1.30× is a candidate spill effect —\ndid NOT reproduce at 100M rows",
             xy=(1.30, y[3]+0.30), xytext=(1.03, y[3]-0.95),
             fontsize=8.6, color=cs.WARN, ha="left", va="top",
             arrowprops=dict(arrowstyle="-|>", color=cs.WARN, lw=1.1, connectionstyle="arc3,rad=-0.25"))
axL.set_ylim(-1.35, len(q_sf)+0.05)
axL.text(0.9, len(q_sf)-0.02, "Byte-identical: 3 of 4 queries at parity", fontsize=10.4,
         color=cs.ACCENT, fontweight="bold", ha="left", va="bottom")

# ---- RIGHT: decomposition — format effect vs codec effect ----
x = np.arange(len(q_p)); w = 0.4
axR.bar(x - w/2, fmt_zstd, width=w, color=cs.CONTEXT, edgecolor="white", linewidth=1.2, label="format effect", zorder=3)
axR.bar(x + w/2, codec_dl, width=w, color=cs.ACCENT2, edgecolor="white", linewidth=1.2, label="codec effect", zorder=3)
axR.axhline(1.0, color=cs.MUTED, lw=1.0, ls="--", zorder=2)
# label the biggest codec lever
imax = int(np.argmax(codec_dl))
axR.text(x[imax] + w/2, codec_dl[imax] + 0.02, f"{codec_dl[imax]:.2f}×", ha="center", va="bottom",
         fontsize=9.3, color=cs.ACCENT2, fontweight="bold")
axR.text(x[1] - w/2, fmt_zstd[1] + 0.02, f"{fmt_zstd[1]:.2f}×", ha="center", va="bottom",
         fontsize=9.3, color=cs.MUTED, fontweight="bold")
axR.set_xticks(x); axR.set_xticklabels(q_p, fontsize=9.5, rotation=18, ha="right")
axR.set_ylim(0.8, 1.72)
axR.set_ylabel("read-latency ratio (>1 = faster)")
for s in ("top", "right"): axR.spines[s].set_visible(False)
axR.grid(axis="y", color=cs.GRID); axR.set_axisbelow(True)
axR.tick_params(axis="x", length=0)
axR.text(-0.5, 1.72, "The codec moves reads more than the format does", fontsize=10.4,
         color=cs.ACCENT, fontweight="bold", ha="left", va="bottom")
# compact swatch legend in the empty upper-left band (above the ~0.95-1.19 filtered bars)
lx, ly = x[0]-w*0.95, 1.58
axR.add_patch(plt.Rectangle((lx, ly), 0.10, 0.045, color=cs.CONTEXT, transform=axR.transData, clip_on=False))
axR.text(lx+0.16, ly+0.022, "format effect (matched codec)", color=cs.MUTED, fontsize=8.3, va="center", ha="left")
axR.add_patch(plt.Rectangle((lx, ly-0.085), 0.10, 0.045, color=cs.ACCENT2, transform=axR.transData, clip_on=False))
axR.text(lx+0.16, ly-0.063, "codec effect (Snappy vs ZSTD)", color=cs.ACCENT2, fontsize=8.3, va="center", ha="left", fontweight="bold")

cs.direction_note(fig, "read ratios: 1.0× = parity")
cs.save(fig, "out/ducklake-vs-iceberg-read-neutrality-on-b.png")
print("rendered r16")
