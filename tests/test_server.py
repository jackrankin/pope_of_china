from __future__ import annotations

import json

import pytest

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
    assert names == {"add_words", "list_words", "remove_word", "clear_words"}


async def test_add_words_reports_each_outcome(server, store):
    out = await call(server, "add_words", words=[
        {"hanzi": "我", "pinyin": "wo3", "meaning": "I, me"},
        {"hanzi": "你", "pinyin": "ni3", "meaning": "you"},
    ])
    assert out["summary"] == {"added": 2, "updated": 0, "unchanged": 0}
    assert out["total_words"] == 2

    out = await call(server, "add_words", words=[
        {"hanzi": "我", "pinyin": "wo3", "meaning": "I, me"},
        {"hanzi": "你", "pinyin": "ni3", "meaning": "you (singular)"},
        {"hanzi": "好", "pinyin": "hao3", "meaning": "good"},
    ])
    assert out["summary"] == {"added": 1, "updated": 1, "unchanged": 1}
    updated = next(r for r in out["results"] if r["status"] == "updated")
    assert updated["hanzi"] == "你"
    assert updated["was"]["meaning"] == "you"
    assert store.count() == 3


async def test_add_words_passes_quiz_english_flag(server, store):
    out = await call(server, "add_words", words=[
        {"hanzi": "了", "pinyin": "le", "meaning": "completed-action particle"},
        {"hanzi": "吗", "pinyin": "ma", "meaning": "question particle", "quiz_english": True},
        {"hanzi": "马", "pinyin": "ma3", "meaning": "horse", "quiz_english": False},
    ])
    flags = {r["hanzi"]: r["quiz_english"] for r in out["results"]}
    assert flags == {"了": False, "吗": True, "马": False}
    assert store.get("马")["quiz_english"] is False


async def test_add_words_collects_errors_without_aborting(server, store):
    out = await call(server, "add_words", words=[
        {"hanzi": "我", "pinyin": "", "meaning": "me"},
        {"hanzi": "你", "pinyin": "ni3", "meaning": "you"},
    ])
    assert out["summary"]["added"] == 1
    assert out["errors"][0]["hanzi"] == "我"
    assert store.count() == 1


async def test_list_search_remove_clear(server):
    await call(server, "add_words", words=[
        {"hanzi": "我", "pinyin": "wo3", "meaning": "me"},
        {"hanzi": "你", "pinyin": "ni3", "meaning": "you"},
    ])
    out = await call(server, "list_words")
    assert [w["hanzi"] for w in out["words"]] == ["我", "你"]
    out = await call(server, "list_words", query="you")
    assert [w["hanzi"] for w in out["words"]] == ["你"]

    out = await call(server, "remove_word", hanzi="我")
    assert out["removed"] is True and out["total_words"] == 1

    out = await call(server, "clear_words")
    assert out["status"] == "not_cleared"
    out = await call(server, "clear_words", confirm=True)
    assert out == {"status": "cleared", "removed": 1}
