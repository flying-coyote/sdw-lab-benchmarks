# charts

The figures the essays and the lab page use, built from this repo's results. Each `_*.py` script draws
one figure (two for the transition map) with the shared style in `chartstyle.py` and writes a PNG to
`out/`; `make_feed_crops.py` then pads selected PNGs into the 1200x627 and 1080x1080 sizes the LinkedIn
feed uses, under `out/feed/`. The fonts the style loads are in `fonts/`.

The script prefix says what kind of figure it is: `_r` for a lab result chart, `_t` for the
transition-program map, `_p` and `_pb` for campaign graphics, and `_bk` for book figures, which carry
numbers from the book and no lab data. [`CHART-MANIFEST.md`](CHART-MANIFEST.md) maps each output file to
its caption, its source results and the essay it serves, and it notes the outputs that have no row yet.

Most result charts hold their numbers as constants copied from the RESULTS file named in the script's
`# Source:` comment, rather than reading the results JSON at render time. So when a bench result is
corrected, the chart only follows once its script is edited and re-rendered, and a chart caption that
quotes a number should be checked against the bench's current RESULTS before it is reused.

To render one figure, run its script from this folder with matplotlib installed, for example
`python _r05_three_mechanisms_flattening.py`. `make_feed_crops.py` also processes a list of deck images
in a directory outside this repo, so on another machine it writes the feed crops for `out/feed/` and then
stops with a missing-file error at the first deck image.
