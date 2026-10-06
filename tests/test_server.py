from __future__ import annotations

import json

import pytest

from yuji.embed import concept_text
from yuji.server import build_server


@pytest.fixture
def server(store):
    return build_server(store)


async def call(server, name: str, **args):
    result = await server.call_tool(name, args)
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(result.content[0].text)


async def test_lists_expected_tools(server):
    names = {t.name for t in await server.list_tools()}
    assert names == {
        "read_slides", "find_similar", "create_concept", "attach", "relate",
        "search", "get_concept", "list_decks", "clear_index",
    }


async def test_read_slides_stores_text_but_no_concepts(server, store, tmp_path):
    deck = tmp_path / "lesson.txt"
    deck.write_text("回家 huíjiā: to return home\n---\n去家: go to someone's home\n", encoding="utf-8")
    out = await call(server, "read_slides", path=str(deck), title="Lesson 1")
    assert out["slide_count"] == 2
    assert out["slides"][1]["text"].startswith("去家")
    assert store.count()["total"] == 0
    decks = await call(server, "list_decks")
    assert decks["decks"][0]["id"] == out["deck_id"]
    assert decks["decks"][0]["slide_count"] == 2


async def test_read_slides_missing_file(server):
    out = await call(server, "read_slides", path="/nowhere/none.pptx")
    assert "error" in out


async def test_create_refuses_close_neighbor_until_confirmed(server, embedder):
    home = concept_text("回家 huíjiā", "to return home", "word")
    go = concept_text("去家 qùjiā", "to go to a home", "word")
    embedder.alias(go, home, weight=0.95)

    first = await call(server, "create_concept", label="回家 huíjiā", gloss="to return home")
    assert first["status"] == "created"

    second = await call(server, "create_concept", label="去家 qùjiā", gloss="to go to a home")
    assert second["status"] == "needs_confirmation"
    assert second["neighbors"][0]["concept_id"] == first["concept_id"]

    third = await call(
        server, "create_concept", label="去家 qùjiā", gloss="to go to a home", confirm_new=True
    )
    assert third["status"] == "created"
    assert third["concept_id"] != first["concept_id"]

    rel = await call(server, "relate", id_a=first["concept_id"], id_b=third["concept_id"], note="distinct")
    assert rel["related"] == [first["concept_id"], third["concept_id"]]
    got = await call(server, "get_concept", concept_id=first["concept_id"])
    assert got["related"][0]["id"] == third["concept_id"]


async def test_same_characters_stop_even_when_embeddings_differ(server):
    first = await call(server, "create_concept", label="麻烦 máfan", gloss="troublesome")
    again = await call(server, "create_concept", label="麻烦", gloss="a hassle; to bother someone")
    assert again["status"] == "needs_confirmation"
    assert again["neighbors"][0]["concept_id"] == first["concept_id"]
    assert again["neighbors"][0]["same_characters"] is True

    forced = await call(server, "create_concept", label="麻烦", gloss="to bother someone", confirm_new=True)
    assert forced["status"] == "created"


async def test_create_far_neighbor_is_saved_without_confirmation(server):
    a = await call(server, "create_concept", label="回家", gloss="to return home")
    b = await call(server, "create_concept", label="苹果", gloss="apple")
    assert a["status"] == b["status"] == "created"


async def test_create_with_deck_attaches(server, tmp_path):
    deck = tmp_path / "d.txt"
    deck.write_text("one\n---\ntwo", encoding="utf-8")
    d = await call(server, "read_slides", path=str(deck))
    c = await call(
        server, "create_concept", label="把字句", gloss="the 把 construction",
        kind="language_point", deck_id=d["deck_id"], slide_numbers=[2],
    )
    assert c["attached_slides"] == 1
    got = await call(server, "get_concept", concept_id=c["concept_id"])
    assert got["kind"] == "language_point"
    assert got["slides"][0]["number"] == 2

    more = await call(server, "attach", concept_id=c["concept_id"], deck_id=d["deck_id"], slide_numbers=[1])
    assert more["attached_slides"] == 1
    bad = await call(server, "attach", concept_id=c["concept_id"], deck_id=d["deck_id"], slide_numbers=[5])
    assert "error" in bad


async def test_search_by_kind(server):
    await call(server, "create_concept", label="麻烦", gloss="troublesome")
    await call(server, "create_concept", label="把字句", gloss="把 construction", kind="language_point")
    words = await call(server, "search", kind="word")
    assert [r["label"] for r in words["results"]] == ["麻烦"]
    hit = await call(server, "search", query="trouble")
    assert hit["results"][0]["label"] == "麻烦"
    assert hit["counts"]["total"] == 2
    bad = await call(server, "search", kind="verb")
    assert "error" in bad


async def test_clear_requires_confirmation(server, store):
    await call(server, "create_concept", label="a", gloss="b")
    no = await call(server, "clear_index")
    assert no["status"] == "not_cleared"
    assert store.count()["total"] == 1
    yes = await call(server, "clear_index", confirm=True)
    assert yes["status"] == "cleared"
    assert store.count()["total"] == 0
