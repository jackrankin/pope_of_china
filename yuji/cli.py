"""`yuji` starts the stdio MCP server. `yuji clear` wipes the index."""

from __future__ import annotations

import argparse
import sys

from . import config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="yuji", description="语迹 MCP server")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the MCP server over stdio (default)")
    sub.add_parser("clear", help="delete every concept and deck; keep the model cache")
    sub.add_parser("status", help="show where the index lives and what it holds")
    args = parser.parse_args(argv)

    if args.command == "clear":
        return _clear()
    if args.command == "status":
        return _status()
    return _serve()


def _serve() -> int:
    import logging

    from .server import build_server, default_store

    # stdout is the MCP transport; keep stderr readable in Cursor's MCP log.
    for noisy in ("httpx", "huggingface_hub", "filelock"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    store = default_store()
    try:
        build_server(store).run(transport="stdio")
    finally:
        store.close()
    return 0


def _clear() -> int:
    from .server import default_store

    store = default_store()
    before = store.count()
    store.clear()
    store.close()
    print(
        f"Cleared {before['total']} concept(s) and {before['decks']} deck(s) from {config.db_path()}",
        file=sys.stderr,
    )
    return 0


def _status() -> int:
    from .server import default_store

    store = default_store()
    counts = store.count()
    store.close()
    print(f"index:  {config.db_path()}")
    print(f"models: {config.model_dir()}")
    print(f"model:  {config.EMBED_MODEL}")
    print(f"threshold: {config.SIMILAR_THRESHOLD}")
    print(
        f"concepts: {counts['total']} "
        f"(word={counts.get('word', 0)}, language_point={counts.get('language_point', 0)}, "
        f"other={counts.get('other', 0)}); decks: {counts['decks']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
