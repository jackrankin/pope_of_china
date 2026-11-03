from __future__ import annotations

from yuji.ranks import NOT_FOUND, level, rank


def test_known_ranks():
    assert rank("的") == 1
    assert rank("我") == 9
    assert rank("你") == 32
    assert rank("好") == 82


def test_unknown_character():
    assert rank("㐀") == NOT_FOUND


def test_level_single_char():
    assert level("我") == 9


def test_level_multi_char():
    assert level("你好") == 82  # max(你=32, 好=82)


def test_level_unknown():
    assert level("xyz") == NOT_FOUND
