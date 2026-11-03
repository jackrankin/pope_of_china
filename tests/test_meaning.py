from __future__ import annotations

import pytest

from yuji.meaning import alternatives, matches, quizzable


@pytest.mark.parametrize("meaning, alts", [
    ("me", ["me"]),
    ("to have; there is", ["have", "there is"]),
    ("person, people", ["person", "people"]),
    ("middle, center; China", ["middle", "center", "china"]),
    ("(literary) of, 's", ["of", "'s"]),
    ("plural suffix (我们, 他们)", []),
    ("completed-action particle", []),
    ("possessive / adjective particle", []),
    ("general measure word", []),
    ("question particle; horse", ["horse"]),
])
def test_alternatives(meaning, alts):
    assert alternatives(meaning) == alts
    assert quizzable(meaning) is bool(alts)


@pytest.mark.parametrize("answer, meaning, ok", [
    ("me", "me", True),
    ("Me ", "me", True),
    ("I", "me", False),
    ("have", "to have; there is", True),
    ("to have", "to have; there is", True),
    ("there is", "to have; there is", True),
    ("has", "to have; there is", False),
    ("people", "person, people", True),
    ("a person", "person, people", True),
    ("china", "middle, center; China", True),
    ("big", "big, large", True),
    ("", "big, large", False),
    ("suffix", "plural suffix (我们, 他们)", False),
])
def test_matches(answer, meaning, ok):
    assert matches(answer, meaning) is ok
