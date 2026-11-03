from __future__ import annotations

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from yuji.web import make_handler


@pytest.fixture
def url(store):
    store.add("我", "wo3", "I, me")
    store.add("你好", "ni3 hao3", "hello")
    store.add("了", "le", "completed-action particle")
    store.add("马", "ma3", "horse", quiz_english=False)  # explicit flag wins over the text
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(store))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def get(url: str):
    with urllib.request.urlopen(url) as r:
        return r.status, r.headers.get("Content-Type"), r.read()


def post(url: str, data: dict):
    req = urllib.request.Request(
        url, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_serves_page(url):
    status, ctype, body = get(url + "/")
    assert status == 200
    assert ctype.startswith("text/html")
    assert b"<title>" in body and "语迹".encode() in body


def test_words_endpoint_includes_level_and_flags(url):
    _, _, body = get(url + "/api/words")
    words = json.loads(body)["words"]
    for w in words:
        assert "hanzi" in w and "level" in w and "has_english" in w and "marks" in w
        assert "pinyin" not in w  # pinyin hidden; marks are for hanzi mode prompt
    assert words[0]["hanzi"] == "我" and words[0]["has_english"] is True
    le = next(w for w in words if w["hanzi"] == "了")
    assert le["has_english"] is False


def test_check_english_mode(url):
    _, out = post(url + "/api/check", {"hanzi": "我", "answer": "me", "mode": "english"})
    assert out["correct"] is True and out["pinyin"] == "wo3"
    _, out = post(url + "/api/check", {"hanzi": "我", "answer": "wo3", "mode": "english"})
    assert out["correct"] is False
    _, out = post(url + "/api/check", {"hanzi": "你好", "answer": "Hello", "mode": "english"})
    assert out["correct"] is True
    status, out = post(url + "/api/check", {"hanzi": "我", "answer": "me", "mode": "klingon"})
    assert status == 400


def test_check_right_and_wrong(url):
    status, out = post(url + "/api/check", {"hanzi": "你好", "answer": "nǐhǎo"})
    assert status == 200
    assert out["correct"] is True and out["pinyin"] == "ni3 hao3" and out["marks"] == "nǐ hǎo"
    assert out["hanzi"] == "你好" and isinstance(out["homophones"], list)
    _, out = post(url + "/api/check", {"hanzi": "我", "answer": "wo4"})
    assert out["correct"] is False and out["pinyin"] == "wo3"


def test_check_errors(url):
    status, out = post(url + "/api/check", {"hanzi": "猫", "answer": "mao1"})
    assert status == 404
    status, out = post(url + "/api/check", {"answer": "mao1"})
    assert status == 400


def test_unknown_path_404(url):
    with pytest.raises(urllib.error.HTTPError) as e:
        get(url + "/nope")
    assert e.value.code == 404
