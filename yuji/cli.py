"""`yuji` starts the stdio MCP server. `yuji web` starts the quiz page."""

from __future__ import annotations

import argparse
import sys

from . import config
from .store import Store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="yuji", description="语迹 — Chinese word list")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the MCP server over stdio (default)")
    web = sub.add_parser("web", help="serve the pinyin quiz page")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--host", default="127.0.0.1")
    add = sub.add_parser("add", help="add a word: yuji add 我 wo3 'I, me'")
    add.add_argument("hanzi")
    add.add_argument("pinyin")
    add.add_argument("meaning")
    rm = sub.add_parser("rm", help="delete a word: yuji rm 我")
    rm.add_argument("hanzi")
    sub.add_parser("list", help="print every stored word")
    sub.add_parser("clear", help="delete every word")
    args = parser.parse_args(argv)

    if args.command == "web":
        return _web(args.host, args.port)
    if args.command == "add":
        return _add(args.hanzi, args.pinyin, args.meaning)
    if args.command == "rm":
        return _rm(args.hanzi)
    if args.command == "list":
        return _list()
    if args.command == "clear":
        return _clear()
    return _serve()


def _serve() -> int:
    from .server import build_server

    store = Store()
    try:
        build_server(store).run(transport="stdio")
    finally:
        store.close()
    return 0


def _web(host: str, port: int) -> int:
    from .web import serve

    store = Store()
    try:
        serve(store, host, port)
    finally:
        store.close()
    return 0


def _add(hanzi: str, pin: str, meaning: str) -> int:
    store = Store()
    r = store.add(hanzi, pin, meaning)
    store.close()
    print(f"{r['status']}: {r['hanzi']}\t{r['pinyin']}\t{r['meaning']}\t(level {r['level']})")
    if r.get("was"):
        print(f"  was: {r['was']['pinyin']}\t{r['was']['meaning']}")
    return 0


def _rm(hanzi: str) -> int:
    store = Store()
    word = store.get(hanzi)
    if word is None:
        print(f"not found: {hanzi}", file=sys.stderr)
        store.close()
        return 1
    store.remove(hanzi)
    store.close()
    print(f"removed: {word['hanzi']}\t{word['pinyin']}\t{word['meaning']}")
    return 0


def _list() -> int:
    store = Store()
    for w in store.list():
        flag = "" if w["quiz_english"] else "\t(no english quiz)"
        print(f"{w['hanzi']}\t{w['pinyin']}\t{w['meaning']}{flag}")
    print(f"{store.count()} words in {config.db_path()}", file=sys.stderr)
    store.close()
    return 0


def _clear() -> int:
    store = Store()
    n = store.clear()
    store.close()
    print(f"Deleted {n} word(s) from {config.db_path()}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
