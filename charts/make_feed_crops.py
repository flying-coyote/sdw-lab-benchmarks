"""
Feed-format derivatives for LinkedIn: 1200x627 link-card and 1080x1080 square.

For every base PNG in out/feed/ (and the listed deck PNGs in
project1/.../linkedin-assets/), scale the image to FIT inside the target box
(LANCZOS, aspect preserved) and paste it centered on a white canvas of exactly
the target size. Pad-only — never crops content, never re-renders.

Run: venv/bin/python make_feed_crops.py
"""
import os
from PIL import Image

_HERE = os.path.dirname(os.path.abspath(__file__))

TARGETS = [(1200, 627), (1080, 1080)]

DECK_DIR = os.path.expanduser(
    "~/project1/02-projects/securitydataworks/content/linkedin-assets")
DECK_PNGS = [
    "roles-venn.png",
    "benchmark-8-engine.png",
    "capability-matrix-method.png",
    "format-convergence-timeline.png",
    "data-health-heatmap.png",
]


def fit_on_white(src_path, out_path, size):
    """Scale src to fit inside `size` (LANCZOS), centered on a white canvas."""
    w, h = size
    im = Image.open(src_path).convert("RGB")
    scale = min(w / im.width, h / im.height)
    new_w = max(1, round(im.width * scale))
    new_h = max(1, round(im.height * scale))
    im = im.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (w, h), (255, 255, 255))
    canvas.paste(im, ((w - new_w) // 2, (h - new_h) // 2))
    canvas.save(out_path)
    return out_path


def crop_dir(src_dir, out_dir, names=None):
    os.makedirs(out_dir, exist_ok=True)
    made = []
    files = names if names is not None else sorted(
        f for f in os.listdir(src_dir) if f.lower().endswith(".png"))
    for fname in files:
        stem = os.path.splitext(fname)[0]
        # skip already-derived outputs if re-run over the same dir
        if any(stem.endswith(f"-{w}x{h}") for w, h in TARGETS):
            continue
        src = os.path.join(src_dir, fname)
        for w, h in TARGETS:
            out = os.path.join(out_dir, f"{stem}-{w}x{h}.png")
            made.append(fit_on_white(src, out, (w, h)))
    return made


if __name__ == "__main__":
    feed_dir = os.path.join(_HERE, "out", "feed")
    made = crop_dir(feed_dir, feed_dir)
    made += crop_dir(DECK_DIR, os.path.join(DECK_DIR, "feed"), names=DECK_PNGS)
    for p in made:
        print(p)
    print(f"{len(made)} derivatives written")
