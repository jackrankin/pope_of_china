"""Pinyin normalisation and comparison.

Stored form is tone numbers, lowercase, one space between syllables, ü as v:
"wo3", "ni3 hao3", "nv3". Neutral tone has no number. Quiz answers may use
tone numbers or tone marks, with or without spaces.
"""

from __future__ import annotations

import re
import unicodedata

_MARKS = {
    "a": "āáǎà", "e": "ēéěè", "i": "īíǐì",
    "o": "ōóǒò", "u": "ūúǔù", "v": "ǖǘǚǜ",
}
_SYLLABLE = re.compile(r"([a-z]+)([0-5]?)")


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFC", text).strip().lower()
    return text.replace("u:", "v").replace("ü", "v")


def normalize(text: str) -> str:
    """Canonical stored form from tone-number input: "Ni3hao3" -> "ni3 hao3".

    Supports "/" separated alternatives: "le/liao3" -> "le/liao3".
    """
    if "/" in text:
        return "/".join(normalize(r.strip()) for r in text.split("/"))
    return " ".join(
        f"{letters}{tone}" if tone and tone not in "05" else letters
        for chunk in re.split(r"[\s'\-]+", _clean(text))
        for letters, tone in _SYLLABLE.findall(chunk)
    )


def with_marks(numbered: str) -> str:
    """"ni3 hao3" -> "nǐ hǎo". Handles "/" separated alternatives."""
    if "/" in numbered:
        return " / ".join(with_marks(r.strip()) for r in numbered.split("/"))

    def mark(m: re.Match) -> str:
        letters, tone = m.group(1), m.group(2)
        if tone:
            if "a" in letters:
                i = letters.index("a")
            elif "e" in letters:
                i = letters.index("e")
            elif "ou" in letters:
                i = letters.index("o")
            else:
                i = max(letters.rfind(c) for c in "iouv")
            letters = letters[:i] + _MARKS[letters[i]][int(tone) - 1] + letters[i + 1:]
        return letters.replace("v", "ü")
    return _SYLLABLE.sub(mark, numbered)


def _matches_one(answer: str, single: str) -> bool:
    """True if `answer` (numbers or marks, any spacing) reads as `single`."""
    single = normalize(single)
    if any(ch.isdigit() for ch in answer):
        return normalize(answer) == single
    given = re.sub(r"[\s'\-]+", "", _clean(answer))
    return given == with_marks(single).replace("ü", "v").replace(" ", "")


def matches(answer: str, stored: str) -> bool:
    """True if `answer` matches any reading in `stored` (readings separated by /)."""
    return any(_matches_one(answer, reading) for reading in stored.split("/"))
