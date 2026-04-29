"""Backchannel filter for voice turns.

Recognizes short filler / acknowledgement utterances ("mm-hmm", "yeah", "ok")
that should NOT trigger RAG retrieval or be treated as meaningful topic shifts.
Used by the conversation manager's RAG gate.

Crisis detection runs independently; this filter never suppresses the crisis
pipeline — a short utterance still flows through `detect_and_maybe_alert`.
"""
from __future__ import annotations

_BACKCHANNELS = {
    "mm", "mmm", "mm-hmm", "mmhmm", "mm hmm",
    "uh", "uh huh", "uhuh", "uh-huh",
    "yeah", "yes", "yep", "yup", "nope", "no",
    "ok", "okay", "k",
    "right", "sure", "hm", "hmm", "huh",
    "cool", "nice", "wow", "oh",
}


def is_backchannel(text: str) -> bool:
    """Return True if `text` is an empty string, a 1–2 char utterance, or a
    known backchannel/filler phrase."""
    if not text:
        return True
    t = text.strip().lower().rstrip("?.!,")
    if not t:
        return True
    if len(t) <= 2:
        return True
    return t in _BACKCHANNELS
