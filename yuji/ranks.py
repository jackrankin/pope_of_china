"""Frequency-rank lookup for individual Chinese characters.

Data is from Jun Da's character frequency list (top 1000). Rank 1 = most common
(的), rank 1000 = least common in the file. Characters not in the file get
rank 9999.
"""

from __future__ import annotations

import re
from functools import lru_cache
from importlib import resources

NOT_FOUND = 9999
_HANZI = re.compile(r"[\u4e00-\u9fff]")


@lru_cache(maxsize=1)
def _table() -> dict[str, int]:
    text = resources.files("yuji.data").joinpath("ranks.tsv").read_text(encoding="utf-8")
    table: dict[str, int] = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].strip().isdigit():
            table[parts[1].strip()] = int(parts[0].strip())
    return table


def rank(hanzi: str) -> int:
    """Rank of a single character (1 = most common), or NOT_FOUND."""
    return _table().get(hanzi, NOT_FOUND)


def level(text: str) -> int:
    """Level for a word: the max rank of its Chinese characters.

    Multi-character words are as hard as their hardest character.
    Single characters get their exact rank. Returns NOT_FOUND if none of the
    characters appear in the frequency list.
    """
    chars = _HANZI.findall(text)
    if not chars:
        return NOT_FOUND
    return max(rank(c) for c in chars)
