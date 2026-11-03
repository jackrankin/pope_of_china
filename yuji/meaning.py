"""Matching a typed English answer against a stored meaning.

A meaning like "to have; there is" or "person, people" lists alternatives.
Any one of them counts. Grammar-only descriptions such as "completed-action
particle" have no English equivalent, so such words are left out of the
character-to-English quiz.
"""

from __future__ import annotations

import re

# An alternative containing any of these is a description, not a translation.
_GRAMMAR = ("particle", "suffix", "prefix", "measure word", "classifier", "marker")
_ARTICLES = re.compile(r"^(to|a|an|the)\s+")


def _clean(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = text.strip(".!?")
    return _ARTICLES.sub("", text).strip()


def alternatives(meaning: str) -> list[str]:
    """Acceptable normalised answers for a stored meaning; empty if none."""
    bare = re.sub(r"\([^)]*\)", "", meaning)
    out = []
    for segment in bare.split(";"):
        if any(g in segment.lower() for g in _GRAMMAR):
            continue  # a description like "possessive / adjective particle"
        for part in re.split(r"[,/]", segment):
            alt = _clean(part)
            if alt:
                out.append(alt)
    return out


def quizzable(meaning: str) -> bool:
    return bool(alternatives(meaning))


def matches(answer: str, meaning: str) -> bool:
    given = _clean(answer)
    return bool(given) and given in alternatives(meaning)
