"""
Security Data Works — shared chart style for benchmark visualizations.

Design rules (FT Visual Vocabulary + Cleveland-McGill graphical perception):
- Encode quantity with POSITION on a common scale (bars/dots/lines) over angle/area/color.
- Bars start at zero, always. Direct-label values; avoid legends where a label fits.
- One accent (teal-700) carries the point; everything else is grey context.
- Heatmaps use the brand diverging score palette (poor->best), colorblind-checked.
- No pie, no 3D, no dual-axis-for-effect. Caption + source + Tier caveat in the footer.

Intent -> chart map (apply per-result):
  magnitude comparison            -> hbar (zero baseline, labeled)
  before/after per item           -> dumbbell or slope
  change over continuous variable -> line
  matrix / grid                   -> heatmap (diverging) or binary pass/fail
  part-to-whole / progression     -> stacked bar (never pie)
  correctness/portability matrix  -> static table (separate, not here)

Use cs.canvas(...) for every figure: it reserves margins and places the
title/subtitle/footer so nothing overlaps the plot.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

_HERE = os.path.dirname(os.path.abspath(__file__))

# Feed preset: CHARTSTYLE_FEED_SCALE > 0 bumps type for phone-feed renders and
# routes save() to out/feed/. Unset/0 leaves behavior byte-identical to default.
FEED_SCALE = float(os.environ.get("CHARTSTYLE_FEED_SCALE", "0") or 0)


def _register(fname, fallback):
    p = os.path.join(_HERE, "fonts", fname)
    if os.path.exists(p):
        fm.fontManager.addfont(p)
        try:
            return fm.FontProperties(fname=p).get_name()
        except Exception:
            return fallback
    return fallback


SANS = _register("DMSans.ttf", "DejaVu Sans")
MONO = _register("JetBrainsMono.ttf", "DejaVu Sans Mono")

# --- brand palette (light theme, matches the Astro site + deck) ---
INK     = "#0c1620"   # text-display
BODY    = "#1f2933"   # text-primary
MUTED   = "#67768a"   # text-muted
ACCENT  = "#2c4f74"   # teal-700 (the point)
ACCENT2 = "#5c8dc5"   # teal-400 (secondary series)
TEAL600 = "#36608f"
GRID    = "#e2e6ea"   # border-subtle
SUBTLE  = "#f4f6f8"   # bg-subtle
WHITE   = "#ffffff"
CONTEXT = "#b8c1cc"   # grey "context" series (de-emphasized)
GOOD    = "#6f9a4f"   # score-4 green
BAD     = "#c14a4a"   # score-1 red
WARN    = "#d6824a"   # score-2 orange
# diverging score ramp poor -> best (heatmaps)
SCORE = ["#c14a4a", "#d6824a", "#d6b94a", "#6f9a4f", "#36608f"]

plt.rcParams.update({
    "font.family": SANS,
    "font.size": 13,
    "text.color": BODY,
    "axes.edgecolor": GRID,
    "axes.labelcolor": BODY,
    "axes.labelsize": 12,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "xtick.color": MUTED,
    "ytick.color": BODY,
    "xtick.labelsize": 11,
    "ytick.labelsize": 12,
    "figure.facecolor": WHITE,
    "axes.facecolor": WHITE,
    "savefig.facecolor": WHITE,
    "savefig.dpi": 200,
})

if FEED_SCALE > 0:
    plt.rcParams.update({
        "font.size": plt.rcParams["font.size"] * FEED_SCALE,
        "axes.labelsize": plt.rcParams["axes.labelsize"] * FEED_SCALE,
        "xtick.labelsize": plt.rcParams["xtick.labelsize"] * FEED_SCALE,
        "ytick.labelsize": plt.rcParams["ytick.labelsize"] * FEED_SCALE,
    })


def canvas(head, sub=None, source="", tier="Tier B · single-host · reproducible",
           figsize=(8.8, 4.6), nrows=1, ncols=1, top=0.80, bottom=0.17, **kw):
    """Figure + axes with reserved margins; title/subtitle (top-left) and
    source/caveat footer (bottom-left) placed so they never touch the plot."""
    _s = FEED_SCALE if FEED_SCALE > 0 else 1.0
    fig, ax = plt.subplots(nrows, ncols, figsize=figsize, **kw)
    fig.subplots_adjust(top=top, bottom=bottom, left=0.10, right=0.965, hspace=0.45, wspace=0.28)
    fig.text(0.012, 0.965, head, fontsize=15.5 * _s, fontweight="bold", color=INK,
             family=SANS, ha="left", va="top")
    if sub:
        fig.text(0.012, 0.885, sub, fontsize=11 * _s, color=MUTED, family=SANS,
                 ha="left", va="top", wrap=True)
    if source:
        fig.text(0.012, 0.028, f"{tier}   ·   {source}", fontsize=8 * _s, family=MONO,
                 color=MUTED, ha="left", va="bottom")
    return fig, ax


def bare(ax):
    """Strip spines/ticks for label-only axes (stacked single bar etc.)."""
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_yticks([])


def donut(ax, values, labels, colors, center=None, center_sub=None, startangle=90):
    """Part-to-whole DONUT. Right for FEW slices where the whole is the message
    (and a single-value KPI donut). A bar still wins for ranking / precise
    slice-to-slice comparison (Cleveland-McGill: position > angle/area)."""
    import numpy as np
    wedges, _ = ax.pie(values, colors=colors, startangle=startangle, counterclock=False,
                       wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2))
    for w, val, lab in zip(wedges, values, labels):
        ang = np.deg2rad((w.theta2 + w.theta1) / 2.0)
        ax.text(1.22*np.cos(ang), 1.22*np.sin(ang), f"{lab}\n{val:.1f}%",
                ha="center", va="center", fontsize=10.5, color=BODY)
    if center:
        ax.text(0, 0.10, center, ha="center", va="center", fontsize=23, fontweight="bold", color=INK)
    if center_sub:
        ax.text(0, -0.24, center_sub, ha="center", va="center", fontsize=9.5, color=MUTED)
    ax.set(aspect="equal")


def direction_note(fig, text="Higher is better", x=0.985, y=0.985, color=ACCENT,
                   ha="right", va="top"):
    """Scanning-reviewer popout: a highlighted box stating the metric direction
    ('Higher is better' / 'Lower is better' / 'recall: higher is better').
    A quickly-scanning reviewer looks for this on any technically dense chart —
    add one per measurement figure (twice with custom x/y for mixed-direction
    panels). Figure coordinates; default top-right, clear of the head/sub text."""
    _s = FEED_SCALE if FEED_SCALE > 0 else 1.0
    low = text.lower()
    arrow = "↑" if "high" in low else ("↓" if "low" in low else "")
    label = f"{arrow} {text}" if arrow else text
    fig.text(x, y, label, fontsize=10 * _s, fontweight="bold", color=WHITE,
             family=SANS, ha=ha, va=va,
             bbox=dict(boxstyle="round,pad=0.45", facecolor=color, edgecolor="none"))


def save(fig, path):
    if FEED_SCALE > 0:
        feed_dir = os.path.join(os.path.dirname(path) or ".", "feed")
        os.makedirs(feed_dir, exist_ok=True)
        path = os.path.join(feed_dir, os.path.basename(path))
    fig.savefig(path, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    return path
