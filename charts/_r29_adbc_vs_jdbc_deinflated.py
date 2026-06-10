import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np

# Source: ocsf-arrow-transport/results/RESULTS.md — same DuckDB query, only the
# connectivity API varies. Latency ms (machine-specific medians).
#   rows     ADBC   JDBC native-JVM   JDBC Python/JPype   ADBCvsNative  ADBCvsPython
#   100k     35     222               3049                6.3x          86.9x
#   1M       158    1285              32505               8.1x          205.2x
# The honest columnar-vs-row advantage is ADBC vs native-JVM JDBC: single digits.
groups = ["100k rows", "1M rows"]
adbc        = [35, 158]
jdbc_native = [222, 1285]
jdbc_python = [3049, 32505]
ratio_native = [6.3, 8.1]      # the honest single-digit
ratio_python = [86.9, 205.2]   # the bridge-inflated number

x = np.arange(len(groups))
w = 0.26

fig, ax = cs.canvas(
    "The honest columnar-vs-row win is single digits, not hundreds.",
    "DuckDB fetch latency over three connectivity APIs — the Python/JPype bridge inflates the gap ~40x by measuring the JNI crossing, not the transport.",
    source="sdw-lab-benchmarks/ocsf-arrow-transport",
    tier="Tier B · single-host · medians · ADBC is Python-Arrow, native JDBC is Java-rows (paradigm ratio, not single-language)",
    figsize=(9.2, 5.0), bottom=0.16, top=0.80)

ax.set_yscale("log")

b1 = ax.bar(x - w, adbc,        w, color=cs.ACCENT,  zorder=3, label="ADBC (Arrow, columnar)")
b2 = ax.bar(x,     jdbc_native, w, color=cs.CONTEXT, zorder=3, label="JDBC native-JVM (the fair baseline)")
b3 = ax.bar(x + w, jdbc_python, w, color=cs.BAD,     zorder=3, label="JDBC Python/JPype bridge (cautionary)")

def lab(bars, vals):
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v * 1.07,
                f"{v:,} ms", ha="center", va="bottom", fontsize=9, color=cs.BODY)
lab(b1, adbc); lab(b2, jdbc_native); lab(b3, jdbc_python)

# the two ratios that matter, drawn as bracketed annotations over ADBC vs native
for i in range(len(groups)):
    top = jdbc_native[i]
    ax.annotate(f"{ratio_native[i]}x\nthe honest win",
                xy=(x[i] - w / 2, top * 1.9),
                ha="center", va="bottom", fontsize=10.5, color=cs.ACCENT, fontweight="bold")
    ax.text(x[i] + w, jdbc_python[i] * 2.3, f"~{ratio_python[i]:.0f}x\n(bridge-inflated)",
            ha="center", va="bottom", fontsize=9, color=cs.BAD)

ax.set_xticks(x)
ax.set_xticklabels(groups, fontsize=11.5)
ax.set_ylim(10, 120000)
ax.set_ylabel("fetch latency (ms, log)")
ax.set_yticks([10, 100, 1000, 10000, 100000])
ax.set_yticklabels(["10", "100", "1k", "10k", "100k"])
ax.grid(axis="y", color=cs.GRID); ax.grid(axis="x", visible=False)
ax.set_axisbelow(True)
ax.tick_params(length=0)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)

ax.legend(loc="upper left", frameon=False, fontsize=9.5, ncol=1,
          handlelength=1.1, labelcolor=cs.BODY)

cs.direction_note(fig, "latency: lower is better")
cs.save(fig, "out/adbc-vs-jdbc-deinflated.png")
print("rendered; font in use =", cs.SANS)
