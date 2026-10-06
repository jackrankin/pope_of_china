from __future__ import annotations

import pytest

from yuji import config
from yuji.embed import concept_text, hanzi
from yuji.store import NotFound


def test_create_and_get(store):
    cid = store.create_concept("回家 huíjiā", "to return home", "word")
    assert cid.startswith("c_")
    got = store.get_concept(cid)
    assert got["label"] == "回家 huíjiā"
    assert got["kind"] == "word"
    assert got["slides"] == []
    assert got["related"] == []


def test_same_characters_are_separate_rows(store):
    a = store.create_concept("回家", "to return home", "word")
    b = store.create_concept("回家", "to return home", "word")
    assert a != b
    assert store.count()["total"] == 2


def test_kinds_are_distinct_and_filterable(store):
    store.create_concept("麻烦", "troublesome", "word")
    store.create_concept("把字句", "the 把 construction", "language_point")
    assert [r["label"] for r in store.search(kind="language_point")] == ["把字句"]
    assert [r["label"] for r in store.search(kind="word")] == ["麻烦"]
    assert len(store.search()) == 2
    with pytest.raises(ValueError):
        store.create_concept("x", "y", "noun")


def test_find_similar_ranks_neighbors(store, embedder):
    text_home = concept_text("回家", "to return home", "word")
    embedder.alias("go home-ish", text_home, weight=0.97)
    home = store.create_concept("回家", "to return home", "word")
    store.create_concept("苹果", "apple", "word")
    hits = store.find_similar("go home-ish", limit=2)
    assert hits[0]["concept_id"] == home
    assert hits[0]["score"] > 0.9
    assert hits[1]["score"] < config.SIMILAR_THRESHOLD


def test_find_similar_on_empty_index(store):
    assert store.find_similar("anything") == []


def test_decks_attach_and_relate(store):
    deck = store.add_deck("/tmp/l3.pptx", "Lesson 3", ["回家 to return home", "去家 go to a home"])
    home = store.create_concept("回家", "to return home", "word")
    go = store.create_concept("去家", "to go to (someone's) home", "word")
    assert store.attach(home, deck, [1]) == 1
    store.relate(home, go, "same characters 家, different verbs")

    got = store.get_concept(home)
    assert got["slides"][0]["deck_title"] == "Lesson 3"
    assert got["slides"][0]["number"] == 1
    assert got["related"][0]["id"] == go
    # relation is symmetric
    assert store.get_concept(go)["related"][0]["id"] == home

    with pytest.raises(NotFound):
        store.attach(home, deck, [9])
    with pytest.raises(NotFound):
        store.attach("c_nope", deck, [1])
    with pytest.raises(ValueError):
        store.relate(home, home)


def test_clear_empties_everything(store):
    deck = store.add_deck("/tmp/x.txt", "x", ["a"])
    cid = store.create_concept("a", "b", "word")
    store.attach(cid, deck, [1])
    store.clear()
    assert store.count()["total"] == 0
    assert store.count()["decks"] == 0
    assert store.find_similar("a") == []


def test_hanzi_strips_pinyin_and_punctuation():
    assert hanzi("回家 huíjiā") == "回家"
    assert hanzi("把字句 (bǎ-sentence)") == "把字句"
    assert hanzi("just english") == ""


def test_find_by_hanzi(store):
    cid = store.create_concept("回家 huíjiā", "to return home", "word")
    assert [r["id"] for r in store.find_by_hanzi("回家")] == [cid]
    assert store.find_by_hanzi("去家") == []
    assert store.find_by_hanzi("no chinese") == []
