from __future__ import annotations

import pytest

from yuji.pinyin import matches, normalize, with_marks


@pytest.mark.parametrize("raw, canon", [
    ("wo3", "wo3"),
    ("Wo3", "wo3"),
    ("ni3hao3", "ni3 hao3"),
    ("ni3  hao3", "ni3 hao3"),
    ("nü3", "nv3"),
    ("nu:3", "nv3"),
    ("ma5", "ma"),
    ("ma0", "ma"),
    ("xi'an1", "xi an1"),
    ("le/liao3", "le/liao3"),
])
def test_normalize(raw, canon):
    assert normalize(raw) == canon


@pytest.mark.parametrize("numbered, marked", [
    ("wo3", "wǒ"),
    ("ni3 hao3", "nǐ hǎo"),
    ("zhong1 guo2", "zhōng guó"),
    ("hao3", "hǎo"),        # a takes the mark
    ("xie4", "xiè"),        # e takes the mark
    ("gou3", "gǒu"),        # ou: o takes the mark
    ("liu2", "liú"),        # otherwise the last vowel
    ("nv3", "nǚ"),
    ("ma", "ma"),
    ("lv", "lü"),
    ("le/liao3", "le / liǎo"),
])
def test_with_marks(numbered, marked):
    assert with_marks(numbered) == marked


@pytest.mark.parametrize("answer, stored, ok", [
    ("wo3", "wo3", True),
    ("wǒ", "wo3", True),
    ("WO3", "wo3", True),
    ("wo2", "wo3", False),
    ("wo", "wo3", False),
    ("nihao", "ni3 hao3", False),
    ("ni3hao3", "ni3 hao3", True),
    ("ni3 hao3", "ni3 hao3", True),
    ("nǐhǎo", "ni3 hao3", True),
    ("nǐ hǎo", "ni3 hao3", True),
    ("nǐ hào", "ni3 hao3", False),
    ("nü3", "nv3", True),
    ("nǚ", "nv3", True),
    ("ma", "ma", True),
    ("ma5", "ma", True),
    ("xi1'an1", "xi1 an1", True),
    ("xī'ān", "xi1 an1", True),
    ("xian1", "xi1 an1", False),
    ("", "wo3", False),
    ("le", "le/liao3", True),
    ("liao3", "le/liao3", True),
    ("liǎo", "le/liao3", True),
    ("la1", "le/liao3", False),
])
def test_matches(answer, stored, ok):
    assert matches(answer, stored) is ok
