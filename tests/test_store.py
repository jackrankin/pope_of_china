from __future__ import annotations

import pytest

from yuji import config
from yuji.store import Store


def test_add_then_get(store):
    out = store.add("我", "wo3", "I, me")
    assert out["status"] == "added"
    assert (out["hanzi"], out["pinyin"], out["meaning"], out["quiz_english"]) == ("我", "wo3", "I, me", True)
    assert out["level"] == 9  # 我 is rank 9 in the frequency list
    got = store.get("我")
    assert (got["hanzi"], got["pinyin"], got["meaning"], got["quiz_english"]) == ("我", "wo3", "I, me", True)
    assert got["level"] == 9
    assert store.count() == 1


def test_quiz_english_defaults_from_meaning_and_can_be_forced(store):
    assert store.add("了", "le", "completed-action particle")["quiz_english"] is False
    assert store.add("吗", "ma", "question particle", quiz_english=True)["quiz_english"] is True
    assert store.add("马", "ma3", "horse", quiz_english=False)["quiz_english"] is False
    assert store.get("了")["quiz_english"] is False
    assert store.get("吗")["quiz_english"] is True
    assert store.get("马")["quiz_english"] is False


def test_changing_only_the_flag_counts_as_update(store):
    store.add("马", "ma3", "horse")
    out = store.add("马", "ma3", "horse", quiz_english=False)
    assert out["status"] == "updated"
    assert out["was"] == {"pinyin": "ma3", "meaning": "horse", "quiz_english": True}
    assert store.get("马")["quiz_english"] is False


def test_level_auto_set_from_ranks(store):
    store.add("的", "de", "of")
    store.add("你好", "ni3 hao3", "hello")
    store.add("zzz", "z", "unknown", quiz_english=False)  # not Chinese chars
    assert store.get("的")["level"] == 1
    assert store.get("你好")["level"] == 82  # max(你=rank32, 好=rank82)
    assert store.get("zzz")["level"] == 9999


def test_migrates_old_table_without_flag_or_level(home):
    import sqlite3
    path = config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE words (hanzi TEXT PRIMARY KEY, pinyin TEXT NOT NULL, meaning TEXT NOT NULL, "
        "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    db.execute("INSERT INTO words VALUES ('马', 'ma3', 'horse', 't', 't')")
    db.execute("INSERT INTO words VALUES ('了', 'le', 'completed-action particle', 't', 't')")
    db.commit()
    db.close()
    s = Store(path=path)
    assert s.get("马")["quiz_english"] is True
    assert s.get("了")["quiz_english"] is False
    assert s.get("马")["level"] > 0
    assert s.get("了")["level"] == 5  # 了 is rank 5
    s.close()


def test_pinyin_is_normalised_on_write(store):
    store.add("你好", "Ni3Hao3", "hello")
    assert store.get("你好")["pinyin"] == "ni3 hao3"


def test_duplicate_characters_update_rather_than_duplicate(store):
    store.add("好", "hao3", "good")
    same = store.add("好", "hao3", "good")
    assert same["status"] == "unchanged"
    changed = store.add("好", "hao3", "good; well")
    assert changed["status"] == "updated"
    assert changed["was"] == {"pinyin": "hao3", "meaning": "good", "quiz_english": True}
    assert store.count() == 1
    assert store.get("好")["meaning"] == "good; well"


def test_blank_fields_rejected(store):
    with pytest.raises(ValueError):
        store.add("我", "", "me")
    with pytest.raises(ValueError):
        store.add("  ", "wo3", "me")
    assert store.count() == 0


def test_list_and_search(store):
    store.add("我", "wo3", "I, me")
    store.add("你", "ni3", "you")
    store.add("好", "hao3", "good")
    assert [w["hanzi"] for w in store.list()] == ["我", "你", "好"]
    assert [w["hanzi"] for w in store.list("you")] == ["你"]
    assert [w["hanzi"] for w in store.list("hao")] == ["好"]
    assert [w["hanzi"] for w in store.list("我")] == ["我"]
    assert len(store.list(limit=2)) == 2


def test_find_by_pinyin_lists_homophones(store):
    store.add("他", "ta1", "he")
    store.add("她", "ta1", "she")
    store.add("它", "TA1", "it")
    store.add("大", "da4", "big")
    assert store.find_by_pinyin("ta1") == ["他", "她", "它"]
    assert store.find_by_pinyin("TA1") == ["他", "她", "它"]  # normalised before lookup
    assert store.find_by_pinyin("ta4") == []


def test_remove_and_clear(store):
    store.add("我", "wo3", "me")
    store.add("你", "ni3", "you")
    assert store.remove("我") is True
    assert store.remove("我") is False
    assert store.clear() == 1
    assert store.count() == 0


def test_persists_across_connections(home):
    a = Store(path=config.db_path())
    a.add("我", "wo3", "me")
    a.close()
    b = Store(path=config.db_path())
    assert b.get("我")["pinyin"] == "wo3"
    b.close()
