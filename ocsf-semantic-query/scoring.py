"""BENCH-C shared scorer — the ONE definition of correct / silent / loud.

The text-to-SQL arm (`run.py:score`) and the OBDA arm (`run_obda.py`) each carry a private
copy of the substring/uid/uidset/count kind-dispatch. To keep the three-way comparison
honest the GraphRAG arm must score the same kinds identically AND add the kinds the other
arms don't yet dispatch (scalar / order / set), so this module defines every kind once.

`classify(kind, cells, truth, ...)` returns "correct" or "silent" for a NON-EMPTY answer;
the *loud* outcome (empty answer / parse failure / refusal) is decided by the caller before
it ever gets here, exactly as `run.py:run_text_to_sql` and `run_obda.py:main` already do.
That split is the metric BENCH-C exists to measure: a confident-but-wrong answer is silent;
a visible failure is loud.

Migration note: `run.py:score` and `run_obda.py`'s inline dispatch should be refactored to
import `classify` here so there is exactly one definition. That refactor touches the two
working arms, so it is deliberately NOT done in the GraphRAG readiness pass — the substring /
uid / uidset / count semantics below are kept byte-identical to those arms so nothing drifts
in the meantime.
"""

import re

# stage_label -> the keyword that identifies the stage in a free-text answer. Used by the
# `order` scorer (A3). Pre-registered before the scored run, per the fairness contract.
STAGE_KEYWORDS = {
    "stage0_oauth": "oauth",
    "stage1_powershell": "powershell",
    "stage2_beacon": "beacon",
    "stage3_lateral_conn": "lateral",
    "stage4_nomfa": "mfa",
    "stage5_assumerole": "assumerole",
    "stage6_exfil": "exfil",
}
# A7 dwell-time tolerance: the model derives dwell from event timestamps, so allow a small
# absolute window rather than demanding the exact second. Fixed before the scored run.
DWELL_TOLERANCE_SEC = 60


def _numbers(cells):
    """Every integer-ish number appearing in any answer cell, as ints."""
    out = []
    for c in cells:
        for m in re.findall(r"-?\d+", str(c)):
            try:
                out.append(int(m))
            except ValueError:
                pass
    return out


def classify(kind, cells, truth, *, dwell_tolerance=DWELL_TOLERANCE_SEC):
    """correct | silent for a non-empty answer. `cells` is a flat list of returned strings."""
    flat = [str(c) for c in cells]
    text = " ".join(flat).lower()

    # --- kinds shared with run.py / run_obda.py (kept byte-identical) ---
    if kind == "substring":
        return "correct" if any(str(truth) in c for c in flat) else "silent"
    if kind == "uid":
        return "correct" if str(truth) in flat else "silent"
    if kind == "uidset":
        truth_set = set(truth)
        got = truth_set & set(flat)
        return ("correct" if len(got) >= 0.5 * len(truth_set) and len(flat) <= 4 * len(truth_set)
                else "silent")
    if kind == "count":
        # correct iff the count is recovered: either the integer len(truth) appears as a
        # returned value, or the answer is itself a list of exactly len(truth) items.
        target = len(truth) if isinstance(truth, (list, set, tuple)) else int(truth)
        return "correct" if (target in _numbers(flat) or len(flat) == target) else "silent"

    # --- kinds the GraphRAG arm adds (OBDA refuses these; text-to-SQL doesn't dispatch them) ---
    if kind == "scalar":
        target = int(truth)
        return ("correct" if any(abs(n - target) <= dwell_tolerance for n in _numbers(flat))
                else "silent")
    if kind == "exact_scalar":
        target = int(truth)
        return "correct" if target in _numbers(flat) else "silent"
    if kind == "order":
        # truth is the stage-label sequence; correct iff every stage keyword appears AND
        # their first-occurrence order in the answer matches the truth order.
        seq = [STAGE_KEYWORDS[s] for s in truth]
        pos = {kw: text.find(kw) for kw in seq}
        if any(p < 0 for p in pos.values()):
            return "silent"  # gave an answer but didn't name every stage
        return "correct" if all(pos[seq[i]] < pos[seq[i + 1]] for i in range(len(seq) - 1)) else "silent"
    if kind == "set":
        # truth is the identity-link dict; correct iff every leaf identifier is recovered
        # (each appears as a substring of some returned cell). A strict ⊇ requirement.
        ids = _identity_strings(truth)
        return "correct" if all(any(i in c for c in flat) for i in ids) else "silent"

    return "silent"


def _identity_strings(identity_links):
    """Flatten truth_identity_links to the set of leaf identifier strings the closure must
    recover (account, principals, role, SID, UPN, human handle, and each asset's hostname /
    ip / instance_id)."""
    ids = set()
    for k, v in identity_links.items():
        if k == "assets" and isinstance(v, list):
            for a in v:
                for ak in ("hostname", "ip", "instance_id"):
                    if a.get(ak):
                        ids.add(str(a[ak]))
        elif isinstance(v, str):
            ids.add(v)
    return ids
