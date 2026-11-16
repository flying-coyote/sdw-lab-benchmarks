"""T8b rerun (2026-11-15) renderings: same four treatments as render.py, with the per-row character cap replaced
by a per-value middle elision so an appended field suffix (where the plant sits) is never cut, and the
per-observation character cap removed (the pre-registered 15-row cap stays). See PREREGISTRATION-ADDENDUM-2026-11-15.md.
Applied identically to every store, including the control, so the comparison across stores is unchanged."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import FIELD_FOR_TABLE, PROVENANCE_OBS, PROVENANCE_SYS, TABLES, _scrub_val  # noqa: E402,F401

VALUE_HEAD, VALUE_TAIL, VALUE_MAX = 140, 115, 260  # code points; the plant is 100 (visible, with its space) or 99 (tag)
ELIDE = " ... "


def elide(v):
    if isinstance(v, str) and len(v) > VALUE_MAX:
        return v[:VALUE_HEAD] + ELIDE + v[-VALUE_TAIL:]
    return v


def render_row(row, cols, treatment):
    row = tuple(elide(v) for v in row)
    if treatment == "raw":
        return " | ".join("NULL" if v is None else str(v) for v in row)
    if treatment == "repr":
        return str(tuple(row))
    if treatment == "strip":
        return " | ".join("NULL" if v is None else str(_scrub_val(v)) for v in row)
    if treatment == "quoted":
        return json.dumps({c: _scrub_val(v) for c, v in zip(cols, row)}, ensure_ascii=False, default=str)
    raise ValueError(treatment)


def render_rows_list(rows, cols, treatment, max_rows=15):
    """Return (observation text, list of rendered row strings) so the caller can check each row."""
    rendered = [render_row(r, cols, treatment) for r in rows[:max_rows]]
    body = "\n".join(rendered) or "(no rows)"
    if treatment == "quoted":
        body = PROVENANCE_OBS + "\n" + body
    return body, rendered
