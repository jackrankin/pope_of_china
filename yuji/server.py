"""语迹 MCP server: a word list the chat agent fills in."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel, Field

from .store import Store

INSTRUCTIONS = """\
语迹 (yuji) is the user's Chinese vocabulary list. Each entry is characters,
pinyin, and an English meaning, e.g. 我 / wo3 / I, me.

When the user pastes words, call add_words once with every word. Supply the
pinyin yourself using tone numbers with a space between syllables ("ni3 hao3",
"nv3" for nǚ, no number for neutral tone). Keep meanings short; separate
alternatives with ";" or "," (e.g. "to have; there is").

Set quiz_english=false for words with no typeable English equivalent
(particles like 了/的, measure words, suffixes) so they stay out of the
character-to-English quiz. Everything else: quiz_english=true.

The characters are the key: adding a word that already exists updates it and
the result says so (with the old values). Prefer merging meanings over
overwriting when both are valid. Use list_words to see or search what is stored.
"""


class Word(BaseModel):
    hanzi: str = Field(description="The Chinese characters, e.g. 你好")
    pinyin: str = Field(description="Tone-number pinyin, e.g. ni3 hao3")
    meaning: str = Field(description="Short English meaning; alternatives separated by ';' or ','")
    quiz_english: bool | None = Field(
        default=None,
        description="Include in the character-to-English quiz. false for particles, measure "
                    "words, suffixes. Omit to decide from the meaning text.",
    )


def build_server(store: Store) -> MCPServer:
    server = MCPServer(name="yuji", instructions=INSTRUCTIONS, version="0.2.0")

    @server.tool()
    def add_words(words: list[Word]) -> dict[str, Any]:
        """Add or update words. Returns each word's outcome: added, updated, or unchanged.

        Duplicate characters update the existing entry; "updated" results include
        the previous pinyin and meaning in `was`.
        """
        results, errors = [], []
        for w in words:
            try:
                results.append(store.add(w.hanzi, w.pinyin, w.meaning, w.quiz_english))
            except ValueError as e:
                errors.append({"hanzi": w.hanzi, "error": str(e)})
        summary = {s: sum(1 for r in results if r["status"] == s) for s in ("added", "updated", "unchanged")}
        out: dict[str, Any] = {"summary": summary, "results": results, "total_words": store.count()}
        if errors:
            out["errors"] = errors
        return out

    @server.tool()
    def list_words(query: str = "", limit: int = 0) -> dict[str, Any]:
        """List stored words. `query` matches characters, pinyin, or meaning; empty lists all."""
        return {"words": store.list(query, limit), "total_words": store.count()}

    @server.tool()
    def remove_word(hanzi: str) -> dict[str, Any]:
        """Delete one word by its characters."""
        return {"hanzi": hanzi, "removed": store.remove(hanzi), "total_words": store.count()}

    @server.tool()
    def clear_words(confirm: bool = False) -> dict[str, Any]:
        """Delete every word. Requires confirm=true."""
        if not confirm:
            return {"status": "not_cleared", "message": "Pass confirm=true to delete all words."}
        return {"status": "cleared", "removed": store.clear()}

    return server
