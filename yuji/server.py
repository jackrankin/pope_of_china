"""语迹 MCP server: tools over the concept index. The chat model does the thinking."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from . import config, slides
from .embed import default_embedder
from .store import NotFound, Store

INSTRUCTIONS = """\
语迹 (yuji) remembers Chinese words and language points by stable concept ID.

Workflow for anything new (a word typed in chat, or each item in a deck):
1. find_similar(description) to see the closest existing concepts.
2. Decide: is this the same concept as a neighbor, or distinct?
   - Same: attach(concept_id, deck_id, slide_numbers) if it came from a deck.
   - Distinct: create_concept(...). If a neighbor scores at or above the
     threshold the tool refuses and returns the neighbors; re-call with
     confirm_new=true only after judging they really are different concepts
     (e.g. 回家 "return home" vs 去家 "go to a home" are two concepts).
   - Related but distinct: relate(id_a, id_b, note) after creating.
read_slides stores a deck's text and never creates concepts.
Use search/get_concept to answer questions or quiz from the index.
"""


def build_server(store: Store) -> MCPServer:
    server = MCPServer(name="yuji", instructions=INSTRUCTIONS, version="0.1.0")

    @server.tool()
    def read_slides(path: str, title: str = "") -> dict[str, Any]:
        """Read a PPTX, PDF, .txt, or .md deck, store its slide text, and return it.

        Does NOT create concepts. Returns deck_id plus every slide's text so the
        agent can propose words and language points, then run find_similar on each.
        """
        file = Path(path).expanduser()
        if not file.is_file():
            return {"error": f"no such file: {file}"}
        texts = slides.extract(file)
        deck_id = store.add_deck(str(file), title or file.stem, texts)
        return {
            "deck_id": deck_id,
            "title": title or file.stem,
            "slide_count": len(texts),
            "slides": [{"number": i + 1, "text": t} for i, t in enumerate(texts)],
        }

    @server.tool()
    def find_similar(description: str, limit: int = 5) -> dict[str, Any]:
        """Embed a description and return the closest stored concepts with scores.

        Describe the concept as label plus meaning, e.g. "回家 huíjiā: to return home".
        Scores are cosine similarity; at or above `threshold` is "very close".
        Looks across all kinds; each neighbor reports its own kind.
        """
        return {
            "threshold": config.SIMILAR_THRESHOLD,
            "neighbors": store.find_similar(description, limit=limit),
        }

    @server.tool()
    def create_concept(
        label: str,
        gloss: str,
        kind: str = "word",
        notes: str = "",
        deck_id: str = "",
        slide_numbers: list[int] | None = None,
        confirm_new: bool = False,
    ) -> dict[str, Any]:
        """Mint a new concept ID and store it.

        label: the Chinese (and optionally pinyin), e.g. "回家 huíjiā".
        gloss: the meaning in English.
        kind: "word" (vocabulary), "language_point" (grammar), or "other".
        deck_id + slide_numbers: optionally attach to slides in one step.

        If an existing concept scores at or above the threshold, or has exactly
        the same Chinese characters, nothing is written and those concepts are
        returned with status "needs_confirmation". Call again with
        confirm_new=true once you have judged this to be a distinct concept.
        """
        if kind not in config.KINDS:
            return {"error": f"kind must be one of {list(config.KINDS)}"}
        neighbors = store.find_similar_concept(label, gloss, kind)
        close = [n for n in neighbors if n["score"] >= config.SIMILAR_THRESHOLD]
        seen = {n["concept_id"] for n in close}
        for same in store.find_by_hanzi(label):
            if same["id"] not in seen:
                close.append({"concept_id": same["id"], "kind": same["kind"], "label": same["label"],
                              "gloss": same["gloss"], "score": None, "same_characters": True})
        if close and not confirm_new:
            return {
                "status": "needs_confirmation",
                "message": (
                    "A very close concept (or one with the same characters) already "
                    "exists. Either attach to one of these IDs, or call create_concept "
                    "again with confirm_new=true if this is a distinct concept."
                ),
                "threshold": config.SIMILAR_THRESHOLD,
                "neighbors": close,
            }
        concept_id = store.create_concept(label, gloss, kind, notes)
        attached = 0
        if deck_id and slide_numbers:
            try:
                attached = store.attach(concept_id, deck_id, slide_numbers)
            except NotFound as e:
                return {"status": "created", "concept_id": concept_id, "attach_error": str(e)}
        return {
            "status": "created",
            "concept_id": concept_id,
            "attached_slides": attached,
            "nearest": neighbors[:3],
        }

    @server.tool()
    def attach(concept_id: str, deck_id: str, slide_numbers: list[int]) -> dict[str, Any]:
        """Link an existing concept to slides in a stored deck."""
        try:
            n = store.attach(concept_id, deck_id, slide_numbers)
        except NotFound as e:
            return {"error": str(e)}
        return {"concept_id": concept_id, "deck_id": deck_id, "attached_slides": n}

    @server.tool()
    def relate(id_a: str, id_b: str, note: str = "") -> dict[str, Any]:
        """Record that two concepts are related and still distinct (e.g. 回家 / 去家)."""
        try:
            store.relate(id_a, id_b, note)
        except (NotFound, ValueError) as e:
            return {"error": str(e)}
        return {"related": [id_a, id_b], "note": note}

    @server.tool()
    def search(query: str = "", kind: str = "", limit: int = 20) -> dict[str, Any]:
        """Text search over labels, glosses, and notes. Empty query lists everything.

        kind: "word", "language_point", or "other" to restrict; empty for all.
        """
        if kind and kind not in config.KINDS:
            return {"error": f"kind must be one of {list(config.KINDS)} or empty"}
        return {"results": store.search(query, kind or None, limit), "counts": store.count()}

    @server.tool()
    def get_concept(concept_id: str) -> dict[str, Any]:
        """Full record for one concept: fields, linked slides, and related concepts."""
        try:
            return store.get_concept(concept_id)
        except NotFound as e:
            return {"error": str(e)}

    @server.tool()
    def list_decks() -> dict[str, Any]:
        """Decks that have been read, with their IDs and slide counts."""
        return {"decks": store.list_decks()}

    @server.tool()
    def clear_index(confirm: bool = False) -> dict[str, Any]:
        """Delete every concept, deck, slide, and relation. Requires confirm=true.

        The downloaded embedding model is kept.
        """
        if not confirm:
            return {"status": "not_cleared", "message": "Pass confirm=true to wipe the index."}
        before = store.count()
        store.clear()
        return {"status": "cleared", "removed": before}

    return server


def default_store() -> Store:
    return Store(default_embedder())
