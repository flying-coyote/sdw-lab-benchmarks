import chartstyle as cs
import matplotlib.pyplot as plt

# Source: ocsf-storage-endurance/results/RESULTS.md + results.json
# Measured write amplification 0.4325 (compression 4.62x, compaction 2.0x).
# Projected DWPD (drive-writes-per-day) vs daily raw ingest, 4 TB and 8 TB drives.
# Reference tiers: read-intensive drive ~1.0 DWPD, write-intensive tier ~10.0 DWPD.
ingest = [0.1, 0.5, 1.0, 5.0]                     # TB/day raw
dwpd_4tb = [0.0108, 0.0541, 0.1081, 0.5406]
dwpd_8tb = [0.0054, 0.0270, 0.0541, 0.2703]
READ_TIER = 1.0
WRITE_TIER = 10.0

fig, ax = cs.canvas(
    "Security telemetry never spends the endurance NVMe vendors sell.",
    "Projected drive-writes-per-day vs daily raw ingest — even at 5 TB/day the workload stays an order of magnitude under a read-intensive drive.",
    source="sdw-lab-benchmarks/ocsf-storage-endurance",
    tier="Tier B · single-host · write-amp 0.4325 MEASURED, DWPD a re-runnable PROJECTION (Tier-A gate: realized-DWPD run)",
    figsize=(8.8, 4.9), bottom=0.16, top=0.80)

ax.set_yscale("log")

# vendor reference tiers as horizontal bands/lines
ax.axhline(WRITE_TIER, color=cs.BAD, lw=1.4, ls="--", zorder=2)
ax.text(0.1, WRITE_TIER * 1.18, "write-intensive tier  ~10 DWPD  (the premium being sold)",
        color=cs.BAD, fontsize=9.5, va="bottom", ha="left", fontweight="bold")
ax.axhline(READ_TIER, color=cs.WARN, lw=1.4, ls="--", zorder=2)
ax.text(0.1, READ_TIER * 1.18, "read-intensive drive  ~1 DWPD",
        color=cs.WARN, fontsize=9.5, va="bottom", ha="left", fontweight="bold")

# projected curves
ax.plot(ingest, dwpd_4tb, "-o", color=cs.ACCENT, lw=2.4, ms=7, zorder=5, label="4 TB drive")
ax.plot(ingest, dwpd_8tb, "-o", color=cs.CONTEXT, lw=2.0, ms=6, zorder=4, label="8 TB drive")

# direct-label the endpoints (the 5 TB/day worst case is the point)
ax.annotate(f"{dwpd_4tb[-1]:.2f} DWPD\nat 5 TB/day, 4 TB drive",
            xy=(ingest[-1], dwpd_4tb[-1]), xytext=(2.05, 0.95),
            color=cs.ACCENT, fontsize=9.5, fontweight="bold", ha="left", va="center",
            arrowprops=dict(arrowstyle="-", color=cs.ACCENT, lw=1.0))
ax.text(ingest[-1] * 1.05, dwpd_4tb[-1], "4 TB drive", color=cs.ACCENT, fontsize=9.5,
        va="center", ha="left", fontweight="bold")
ax.text(ingest[-1] * 1.05, dwpd_8tb[-1], "8 TB drive", color=cs.MUTED, fontsize=9.5,
        va="center", ha="left", fontweight="bold")

ax.set_xlim(0, 6.4)
ax.set_ylim(0.004, 20)
ax.set_xlabel("daily raw ingest (TB/day)")
ax.set_ylabel("projected DWPD (log)")
ax.set_xticks([0, 1, 2, 3, 4, 5, 6])
ax.set_yticks([0.01, 0.1, 1, 10])
ax.set_yticklabels(["0.01", "0.1", "1", "10"])
ax.grid(axis="both", color=cs.GRID)
ax.set_axisbelow(True)

# shade the headroom between the workload and the read tier
ax.fill_between([0, 5.6], [dwpd_4tb[-1]] * 2, [READ_TIER] * 2, color=cs.SUBTLE, alpha=0.0)

cs.direction_note(fig, "projected DWPD: lower is better", x=0.955, y=0.205, va="bottom")
cs.save(fig, "out/projected-dwpd-vs-ingest.png")
print("rendered; font in use =", cs.SANS)
