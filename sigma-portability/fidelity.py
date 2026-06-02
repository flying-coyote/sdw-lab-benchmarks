"""Disclosed structural checks for correlation-translation fidelity.

These are heuristic substring checks against the *generated query text*. They are
written down here, in full, so the scoring is auditable rather than a black box,
and the runner always records the verbatim output beside the score so a reader can
confirm a check did not misfire. A present element is not proof the target SIEM
executes it as intended, and an absent one might be supplied out of band (a
dashboard time range, a scheduler) — the honest claim is only "this element does /
does not appear in the query the compiler emitted."
"""

import yaml

# Token sets, matched case-insensitively. Edit here = the check is the code.
AGG_TOKENS = ["stats", "count(", "count as", "count()", "event_count",
              "values(", "dc(", "count_distinct", "distinct_count", "cardinality"]
# Time-window constructs across dialects: SPL `bin _time span=5m`, ES|QL
# `date_trunc(5minutes, ...)`, PPL `span(@timestamp, 5m)`. Both `span=` (SPL) and
# `span(` (PPL) are listed — missing the latter would wrongly flag PPL's temporal
# queries as window-less, which they are not.
WINDOW_TOKENS = ["span=", "span(", "bin _time", "| bin", "date_trunc", "timebucket",
                 "earliest=", "latest=", "bucket(", "range="]
DISTINCT_TOKENS = ["dc(", "count_distinct", "distinct_count", "cardinality", "estdc"]
THRESHOLD_OPS = [">=", ">", "gte", "having"]


def parse_correlation(path):
    """Return the correlation meta from a rule file, or None if it has no
    correlation doc (i.e. it is a single-event rule)."""
    with open(path) as f:
        docs = list(yaml.safe_load_all(f.read()))
    for d in docs:
        if isinstance(d, dict) and "correlation" in d:
            c = d["correlation"]
            cond = c.get("condition") or {}
            return {
                "type": c.get("type"),
                "group_by": c.get("group-by") or [],
                "timespan": c.get("timespan"),
                "threshold": cond.get("gte", cond.get("gt")),
                "value_field": cond.get("field"),
            }
    return None


def _has(text, tokens):
    t = text.lower()
    return any(tok.lower() in t for tok in tokens)


def score_correlation(output, meta):
    """Per-element presence in a compiled correlation query."""
    text = output if isinstance(output, str) else " ".join(output)
    gb = {f: (f.split(".")[-1].lower() in text.lower()) for f in meta["group_by"]}
    score = {
        "aggregation": _has(text, AGG_TOKENS),
        "group_by_fields": gb,
        "group_by_preserved": (all(gb.values()) if gb else None),
        "time_window": _has(text, WINDOW_TOKENS),
        "threshold": None,
        "value_field_distinct": None,
    }
    if meta["threshold"] is not None:
        score["threshold"] = (str(meta["threshold"]) in text) and _has(text, THRESHOLD_OPS)
    if meta["value_field"]:
        vf = meta["value_field"].split(".")[-1].lower()
        score["value_field_distinct"] = _has(text, DISTINCT_TOKENS) and (vf in text.lower())
    return score


def applicable_elements(meta):
    """Which elements are in scope for this correlation type, and are scored into
    the fraction.

    The group-by *field name* is deliberately NOT scored: a backend legitimately
    renames it into its own schema (Elasticsearch/OpenSearch map to ECS, e.g.
    IpAddress -> source.ip), so a name match would penalise correct translation.
    The group-by field set is still recorded per cell for inspection, and field
    renaming is discussed qualitatively in METHODOLOGY rather than scored. What is
    scored is the structural machinery a correlation needs: the aggregation, the
    threshold, the distinct-count of the value field, and — the differentiator —
    the time window."""
    t = meta["type"]
    if t in ("temporal", "temporal_ordered"):
        return ["aggregation", "time_window"]
    els = ["aggregation", "threshold", "time_window"]
    if meta["value_field"]:
        els.insert(1, "value_field_distinct")
    return els


def fidelity_fraction(score, meta):
    els = applicable_elements(meta)
    preserved = sum(1 for e in els if score.get(e) is True)
    return preserved, len(els)
