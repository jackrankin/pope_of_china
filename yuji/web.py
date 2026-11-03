"""`yuji web`: a local quiz page over the word list. Standard library only."""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources

from . import meaning, pinyin
from .store import Store


def make_handler(store: Store) -> type[BaseHTTPRequestHandler]:
    page = resources.files(__package__).joinpath("static/index.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):  # keep the terminal quiet
            pass

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data: object, status: int = 200) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def do_GET(self) -> None:
            if self.path == "/" or self.path == "/index.html":
                self._send(200, page, "text/html; charset=utf-8")
            elif self.path == "/api/words":
                self._json({"words": [
                    {"hanzi": w["hanzi"], "marks": pinyin.with_marks(w["pinyin"]),
                     "level": w["level"], "has_english": w["quiz_english"]}
                    for w in store.list()
                ]})
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self) -> None:
            if self.path != "/api/check":
                self._json({"error": "not found"}, 404)
                return
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                hanzi, answer = str(body["hanzi"]), str(body.get("answer", ""))
                mode = str(body.get("mode", "pinyin"))
            except (ValueError, KeyError):
                self._json({"error": "expected {hanzi, answer, mode?}"}, 400)
                return
            if mode not in ("pinyin", "english", "hanzi"):
                self._json({"error": "mode must be 'pinyin', 'english', or 'hanzi'"}, 400)
                return
            word = store.get(hanzi)
            if word is None:
                self._json({"error": f"unknown word {hanzi}"}, 404)
                return
            homophones = store.find_by_pinyin(word["pinyin"])
            if mode == "pinyin":
                correct = pinyin.matches(answer, word["pinyin"])
            elif mode == "english":
                correct = meaning.matches(answer, word["meaning"])
            else:
                correct = answer.strip() in homophones
            self._json({
                "correct": correct,
                "hanzi": word["hanzi"],
                "pinyin": word["pinyin"],
                "marks": pinyin.with_marks(word["pinyin"]),
                "meaning": word["meaning"],
                "homophones": [h for h in homophones if h != word["hanzi"]],
            })

    return Handler


def serve(store: Store, host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = ThreadingHTTPServer((host, port), make_handler(store))
    print(f"语迹 quiz: http://{host}:{port}  ({store.count()} words)  Ctrl-C to stop", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
