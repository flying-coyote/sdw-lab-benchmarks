"""Strip invisible and control characters from untrusted external text.

Why this exists: ingestion (LinkedIn, RSS, Substack, Medium) writes captured
external text into markdown notes and dedup/state JSON that LLM sessions later
read. On 2026-11-04 a captured LinkedIn display name was found carrying 21
invisible Unicode tag characters (U+E0000-U+E007F) that decode to
" enter goal here __", which is a prompt-injection channel: invisible to a human
reviewer, readable by a model. Every ingestion write point runs external text
through ``sanitize_text`` (or ``sanitize_record``) before it touches disk.

What is removed:
  * Unicode tag block U+E0000-U+E007F (matched by range, because many of those
    code points are unassigned, category Cn, so a category check misses them)
  * zero-width U+200B-U+200D, U+2060-U+2064, U+FEFF
  * bidi controls U+202A-U+202E, U+2066-U+2069, U+200E, U+200F
  * every other format character (category Cf), e.g. U+00AD soft hyphen,
    U+180E, U+FFF9-U+FFFB; this keeps the rule a superset of the Cc/Cf strip
    rss_handler already applied, so swapping it in is not a regression
  * C0 and C1 control characters plus DEL (category Cc), EXCEPT \\n and \\t
  * variation selectors that can smuggle bytes after a visible character:
    U+E0100-U+E01EF and U+FE00-U+FE0D always, and any U+FE0E/U+FE0F that
    follows another selector (a lone VS15/VS16 after a base is kept, so emoji
    presentation survives). Added 2026-11-04 after a security review.

Deliberate trade-offs (decided 2026-11-04, security over fidelity):
  * U+200D ZERO WIDTH JOINER is stripped. Emoji ZWJ sequences degrade to their
    component emoji (a family glyph becomes three people side by side); the
    individual emoji, skin-tone modifiers and U+FE0F variation selectors are kept.
  * Subdivision flag emoji (e.g. the Scotland flag) are built from tag
    characters, so they degrade to a plain black flag.
  * U+200C ZWNJ is stripped, so Persian/Urdu/Indic text can lose a joiner hint;
    the letters themselves are untouched.
  * \\r is a C0 control and is stripped, so CRLF becomes LF.

Non-Latin scripts (CJK, Arabic, Cyrillic, Devanagari, ...) and ordinary emoji
pass through unchanged. stdlib only.
"""
from __future__ import annotations

import re
import sys
import unicodedata

_EXPLICIT = re.compile(
    "["
    "\U000E0000-\U000E007F"   # tag block
    "\U000E0100-\U000E01EF"   # variation selectors supplement (VS17-VS256)
    "\uFE00-\uFE0D"           # variation selectors VS1-VS14
    "\u180B-\u180D\u180F"     # Mongolian free variation selectors
    "​-‏"           # ZWSP, ZWNJ, ZWJ, LRM, RLM
    "‪-‮"           # bidi embeddings / overrides
    "⁠-⁤"           # word joiner, invisible operators
    "⁦-⁩"           # bidi isolates
    "﻿"                  # BOM / ZWNBSP
    "]"
)

# VS15/VS16 (text/emoji presentation) are kept, but only one per base
# character: a run of selectors is how "emoji smuggling" encodes bytes.
_SELECTOR_RUN = re.compile("(?<=[\uFE0E\uFE0F])[\uFE0E\uFE0F]+")

_KEEP_CONTROLS = {"\n", "\t"}


def _strip_category(ch: str) -> bool:
    if ch in _KEEP_CONTROLS:
        return False
    return unicodedata.category(ch) in ("Cc", "Cf")


def scrub(text) -> tuple[str, int]:
    """Return (clean_text, number_of_characters_removed). None -> ("", 0)."""
    if text is None:
        return "", 0
    if not isinstance(text, str):
        text = str(text)
    if not text:
        return text, 0
    cleaned = "".join(ch for ch in _EXPLICIT.sub("", text) if not _strip_category(ch))
    # Collapse selector runs LAST, so stripping a soft hyphen or control char
    # between two selectors cannot leave a fresh run behind.
    cleaned = _SELECTOR_RUN.sub("", cleaned)
    return cleaned, len(text) - len(cleaned)


def sanitize_text(text, context: str = "") -> str:
    """Strip invisible/control characters; log a count to stderr when any were removed.

    Does not trim whitespace, so it is safe to apply to whole documents.
    """
    cleaned, removed = scrub(text)
    if removed:
        where = f" in {context}" if context else ""
        print(f"   [sanitize] stripped {removed} invisible/control char(s){where}",
              file=sys.stderr)
    return cleaned


def sanitize_record(obj, context: str = ""):
    """Recursively sanitize every str in a dict/list/tuple/set (keys included).

    Non-string scalars are returned unchanged. Returns a new object; the input is
    not mutated.
    """
    if isinstance(obj, str):
        return sanitize_text(obj, context)
    if isinstance(obj, dict):
        return {
            (sanitize_text(k, context) if isinstance(k, str) else k): sanitize_record(v, context)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [sanitize_record(v, context) for v in obj]
    if isinstance(obj, tuple):
        return tuple(sanitize_record(v, context) for v in obj)
    if isinstance(obj, (set, frozenset)):
        return type(obj)(sanitize_record(v, context) for v in obj)
    return obj
