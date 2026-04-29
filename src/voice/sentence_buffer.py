"""Incremental sentence chunker for streaming LLM output.

Consumes token deltas from the LLM SSE stream and emits TTS-ready sentences
as soon as a natural boundary is reached. Keeps latency to first audio low
without cutting mid-word.

No external dependencies — pure string state machine, deterministic and
cheap enough to run on every delta.
"""
from __future__ import annotations

from typing import Iterator

_ENDERS = ".!?…"
# Emit any sentence past ~20 chars. Low enough that short replies like
# "That sounds tough." (19 chars, wait for a space or another char) go
# through promptly, high enough that "Hi." alone is not a TTS call.
_MIN_CHUNK = 20
# If the model refuses to emit a sentence boundary, force-flush at this
# buffer size on the nearest soft boundary (comma/semicolon/space).
_MAX_BUFFER = 240


def _first_hard_boundary(text: str, min_len: int) -> int:
    """Return the index of the FIRST `.`/`!`/`?`/`…` that is followed by
    whitespace or end-of-string AND produces a chunk of at least `min_len`
    characters. Returns -1 if no suitable boundary exists yet.

    We want the earliest boundary so TTS starts speaking as soon as a
    complete thought is ready — not the latest, which would batch multiple
    sentences together and defeat streaming."""
    for i, ch in enumerate(text):
        if ch not in _ENDERS:
            continue
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if nxt in ("", " ", "\n", "\t") and (i + 1) >= min_len:
            return i
    return -1


def _last_soft_boundary(text: str) -> int:
    """Fallback split point: last comma/semicolon, then last space."""
    i = max(text.rfind(","), text.rfind(";"))
    if i > 0:
        return i
    return text.rfind(" ")


class SentenceChunker:
    """Accumulate token deltas and yield sentences as soon as they are ready."""

    def __init__(self) -> None:
        self._buf: str = ""
        self._first = True

    def push(self, delta: str) -> Iterator[str]:
        if not delta:
            return
        self._buf += delta
        while True:
            # Strip a leaked JSON-wrapper prefix on the very first emit.
            if self._first:
                self._strip_json_prefix()

            cut = _first_hard_boundary(self._buf, _MIN_CHUNK)
            if cut < 0:
                # No natural boundary yet. Only force-flush if the buffer
                # has grown past _MAX_BUFFER.
                if len(self._buf) < _MAX_BUFFER:
                    return
                cut = _last_soft_boundary(self._buf)
                if cut < 0 or cut + 1 < _MIN_CHUNK:
                    return

            chunk = self._buf[: cut + 1].strip()
            self._buf = self._buf[cut + 1 :].lstrip()
            if chunk:
                self._first = False
                yield chunk

    def flush(self) -> Iterator[str]:
        """Emit whatever is left in the buffer when the stream ends."""
        if self._first:
            self._strip_json_prefix()
        tail = self._buf.strip()
        # Defensive strip of a trailing JSON-wrapper tail like `"}` if the
        # model leaked JSON despite the plain-text instruction.
        while tail and tail[-1] in '"}':
            tail = tail[:-1].rstrip()
        self._buf = ""
        if tail:
            self._first = False
            yield tail

    def _strip_json_prefix(self) -> None:
        """If the model ignored the plain-text instruction and leaked a
        leading `{"Response": "` or `Response:` prefix, strip it so the TTS
        doesn't speak it aloud."""
        import re
        self._buf = re.sub(r'^[\s{"\']*"?response"?\s*:\s*"?', "", self._buf, flags=re.IGNORECASE)
