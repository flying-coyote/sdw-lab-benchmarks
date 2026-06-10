import chartstyle as cs
import matplotlib.pyplot as plt
import numpy as np

# Source: ocsf-catalog-contention/results/RESULTS.md
# N writers [1,4,8,16] share one Postgres catalog, commit 20x200 rows concurrently.
writers = [1, 4, 8, 16]
# DuckLake: serialize on the SQL catalog — p95 grows, 0 retries, 0 errors.
dl_p95   = [14.47, 19.67, 303.83, 662.38]   # commit p95 ms
dl_err   = [0, 0, 0, 0]
dl_retry = [0, 0, 0, 0]
# Iceberg: optimistic concurrency — retry storm + hard errors.
ic_p95   = [25.58, 52.6, 109.54, 185.57]
ic_err   = [0, 3, 23, 116]                  # hard errors per step (total 142)
ic_retry = [0, 45, 303, 1505]               # retries per step (total 1505)

fig, (axL, axR) = cs.canvas(
    "Under concurrent writers, each catalog fails in a different shape.",
    "One to sixteen writers, one shared Postgres catalog. DuckLake serializes (latency climbs, nothing errors); "
    "Iceberg retries and eventually hard-errors.",
    source="sdw-lab-benchmarks/ocsf-catalog-contention",
    tier="Tier B · single-host · one Postgres catalog · small batches to maximize commit pressure · shape, not absolute ms",
    figsize=(10.2, 4.9), bottom=0.18, top=0.72, ncols=2)
plt.subplots_adjust(wspace=0.42, left=0.085, right=0.965)

# ---- LEFT: commit p95 latency vs writers ----
axL.plot(writers, dl_p95, "-o", color=cs.ACCENT, lw=2.4, ms=7, zorder=3, label="DuckLake")
axL.plot(writers, ic_p95, "-o", color=cs.CONTEXT, lw=2.4, ms=7, zorder=2, label="Iceberg")
axL.text(16, dl_p95[-1]+8, "DuckLake\n662 ms  (45.8× of 1-writer)", va="top", ha="right",
         fontsize=9.4, color=cs.ACCENT, fontweight="bold")
axL.text(16, ic_p95[-1]-22, "Iceberg  186 ms  (7.3×)", va="top", ha="right",
         fontsize=9.4, color=cs.MUTED, fontweight="bold")
axL.set_xscale("log", base=2)
axL.set_xticks(writers); axL.set_xticklabels([str(w) for w in writers])
axL.set_xlim(0.9, 19)
axL.set_ylim(0, 760)
axL.set_xlabel("concurrent writers")
axL.set_ylabel("commit p95 latency (ms)")
axL.grid(axis="y", color=cs.GRID); axL.set_axisbelow(True)
axL.tick_params(length=0)
axL.text(0.9, 760, "DuckLake serializes — latency grows, no errors", fontsize=10.4, color=cs.ACCENT,
         fontweight="bold", ha="left", va="bottom")

# ---- RIGHT: Iceberg retry storm + hard errors vs writers ----
x = np.arange(len(writers)); w = 0.40
axR.bar(x - w/2, ic_retry, width=w, color=cs.WARN, edgecolor="white", linewidth=1.2, label="retries")
axR.bar(x + w/2, ic_err,   width=w, color=cs.BAD, edgecolor="white", linewidth=1.2, label="hard errors")
for xi, r, e in zip(x, ic_retry, ic_err):
    if r: axR.text(xi - w/2, r + 28, str(r), ha="center", va="bottom", fontsize=9, color=cs.WARN, fontweight="bold")
    if e: axR.text(xi + w/2, e + 28, str(e), ha="center", va="bottom", fontsize=9, color=cs.BAD, fontweight="bold")
axR.text(x[0], 1330, "DuckLake: 0 retries, 0 errors\nat every writer count",
         ha="left", va="top", fontsize=9.2, color=cs.ACCENT, fontweight="bold")
axR.set_xticks(x); axR.set_xticklabels([str(w_) for w_ in writers])
axR.set_xlabel("concurrent writers")
axR.set_ylabel("count (Iceberg)")
axR.set_ylim(0, 1700)
axR.grid(axis="y", color=cs.GRID); axR.set_axisbelow(True)
axR.tick_params(length=0)
for s in ("top", "right"): axR.spines[s].set_visible(False)
axR.text(-0.5, 1760, "Iceberg retry-storms — 1,505 retries, 142 hard errors",
         fontsize=10.4, color=cs.BAD, fontweight="bold", ha="left", va="bottom")
# direct legend in the empty upper-mid band
axR.text(x[1]+0.15, 980, "retries", color=cs.WARN, fontsize=9.5, ha="left", va="center", fontweight="bold")
axR.text(x[1]+0.15, 870, "hard errors", color=cs.BAD, fontsize=9.5, ha="left", va="center", fontweight="bold")

cs.direction_note(fig, "Lower is better")
cs.save(fig, "out/concurrent-writer-degradation-shape.png")
print("rendered r15")
