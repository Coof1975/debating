"""Heuristics for detecting incomplete LLM output."""

from __future__ import annotations

import re

_COMPLETE_SUFFIX = re.compile(r"[.!?…\"'\)\]}]\s*$")


def text_looks_incomplete(text: str, *, min_complete_chars: int = 30) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if _COMPLETE_SUFFIX.search(stripped):
        return len(stripped) < min_complete_chars
    # Long text without terminal punctuation is still truncated (common with Gemini).
    return True
