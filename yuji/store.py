"""SQLite index of concepts, decks, slides, and per-concept embeddings.

Every concept has a stable ID. Characters are a label, not a key: 回家 and 去家
are two rows. Embeddings exist only to surface neighbors; nothing here merges.
"""

from __future__ import annotations

import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from . import config
from .embed import Embedder, concept_text, hanzi, normalize

SCHEMA = """
CREATE TABLE IF NOT EXISTS concepts (
    id         TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    label      TEXT NOT NULL,
    hanzi      TEXT NOT NULL DEFAULT '',
    gloss      TEXT NOT NULL,
    notes      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS embeddings (
    concept_id TEXT PRIMARY KEY REFERENCES concepts(id) ON DELETE CASCADE,
    dim        INTEGER NOT NULL,
    vector     BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS decks (
    id         TEXT PRIMARY KEY,
    path       TEXT NOT NULL,
    title      TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS slides (
    deck_id TEXT NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    number  INTEGER NOT NULL,
    text    TEXT NOT NULL,
    PRIMARY KEY (deck_id, number)
);
CREATE TABLE IF NOT EXISTS concept_slides (
    concept_id TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    deck_id    TEXT NOT NULL,
    number     INTEGER NOT NULL,
    PRIMARY KEY (concept_id, deck_id, number),
    FOREIGN KEY (deck_id, number) REFERENCES slides(deck_id, number) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS relations (
    id_a TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    id_b TEXT NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    note TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (id_a, id_b)
);
"""


class NotFound(KeyError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


class Store:
    def __init__(self, embedder: Embedder, path: Path | None = None):
        self.path = path or config.db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder
        # Tools may run on worker threads; one connection, serialized by a lock.
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.lock = threading.RLock()
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Bring an index created by an older version up to the current schema."""
        cols = {r["name"] for r in self.db.execute("PRAGMA table_info(concepts)")}
        with self.lock, self.db:
            if "hanzi" not in cols:
                self.db.execute("ALTER TABLE concepts ADD COLUMN hanzi TEXT NOT NULL DEFAULT ''")
                self.db.execute("UPDATE concepts SET hanzi = ''")
                for row in self.db.execute("SELECT id, label FROM concepts").fetchall():
                    self.db.execute("UPDATE concepts SET hanzi = ? WHERE id = ?", (hanzi(row["label"]), row["id"]))
            self.db.execute("CREATE INDEX IF NOT EXISTS concepts_hanzi ON concepts(hanzi)")

    def close(self) -> None:
        self.db.close()

    # ---- decks and slides -------------------------------------------------

    def add_deck(self, path: str, title: str, slides: list[str]) -> str:
        deck_id = _new_id("d")
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO decks (id, path, title, created_at) VALUES (?, ?, ?, ?)",
                (deck_id, path, title, _now()),
            )
            self.db.executemany(
                "INSERT INTO slides (deck_id, number, text) VALUES (?, ?, ?)",
                [(deck_id, i + 1, text) for i, text in enumerate(slides)],
            )
        return deck_id

    def list_decks(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT d.*, COUNT(s.number) AS slide_count FROM decks d "
            "LEFT JOIN slides s ON s.deck_id = d.id GROUP BY d.id ORDER BY d.created_at"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_deck(self, deck_id: str) -> dict[str, Any]:
        deck = self.db.execute("SELECT * FROM decks WHERE id = ?", (deck_id,)).fetchone()
        if deck is None:
            raise NotFound(f"no deck {deck_id}")
        slides = self.db.execute(
            "SELECT number, text FROM slides WHERE deck_id = ? ORDER BY number", (deck_id,)
        ).fetchall()
        return {**dict(deck), "slides": [dict(s) for s in slides]}

    # ---- concepts ---------------------------------------------------------

    def create_concept(self, label: str, gloss: str, kind: str, notes: str = "") -> str:
        if kind not in config.KINDS:
            raise ValueError(f"kind must be one of {config.KINDS}, got {kind!r}")
        concept_id = _new_id("c")
        vec = self.embedder.embed(concept_text(label, gloss, kind))
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO concepts (id, kind, label, hanzi, gloss, notes, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (concept_id, kind, label, hanzi(label), gloss, notes, _now()),
            )
            self.db.execute(
                "INSERT INTO embeddings (concept_id, dim, vector) VALUES (?, ?, ?)",
                (concept_id, int(vec.shape[0]), vec.astype(np.float32).tobytes()),
            )
        return concept_id

    def get_concept(self, concept_id: str) -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM concepts WHERE id = ?", (concept_id,)).fetchone()
        if row is None:
            raise NotFound(f"no concept {concept_id}")
        slides = self.db.execute(
            "SELECT cs.deck_id, d.title AS deck_title, cs.number, s.text "
            "FROM concept_slides cs "
            "JOIN decks d ON d.id = cs.deck_id "
            "JOIN slides s ON s.deck_id = cs.deck_id AND s.number = cs.number "
            "WHERE cs.concept_id = ? ORDER BY d.created_at, cs.number",
            (concept_id,),
        ).fetchall()
        related = self.db.execute(
            "SELECT CASE WHEN r.id_a = ? THEN r.id_b ELSE r.id_a END AS id, r.note, "
            "c.label, c.gloss, c.kind FROM relations r "
            "JOIN concepts c ON c.id = CASE WHEN r.id_a = ? THEN r.id_b ELSE r.id_a END "
            "WHERE r.id_a = ? OR r.id_b = ?",
            (concept_id, concept_id, concept_id, concept_id),
        ).fetchall()
        return {
            **dict(row),
            "slides": [dict(s) for s in slides],
            "related": [dict(r) for r in related],
        }

    def find_by_hanzi(self, label: str) -> list[dict[str, Any]]:
        """Concepts whose label has exactly the same Chinese characters."""
        chars = hanzi(label)
        if not chars:
            return []
        rows = self.db.execute(
            "SELECT id, kind, label, gloss FROM concepts WHERE hanzi = ? ORDER BY created_at",
            (chars,),
        ).fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str = "", kind: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        sql = "SELECT id, kind, label, gloss, notes, created_at FROM concepts WHERE 1=1"
        params: list[Any] = []
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        if query:
            sql += " AND (label LIKE ? OR gloss LIKE ? OR notes LIKE ?)"
            like = f"%{query}%"
            params += [like, like, like]
        sql += " ORDER BY created_at DESC, label LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self.db.execute(sql, params).fetchall()]

    def count(self) -> dict[str, int]:
        rows = self.db.execute("SELECT kind, COUNT(*) AS n FROM concepts GROUP BY kind").fetchall()
        counts = {r["kind"]: r["n"] for r in rows}
        counts["total"] = sum(counts.values())
        counts["decks"] = self.db.execute("SELECT COUNT(*) FROM decks").fetchone()[0]
        return counts

    # ---- neighbors --------------------------------------------------------

    def find_similar(self, description: str, limit: int = 5) -> list[dict[str, Any]]:
        query = self.embedder.embed(description)
        return self._neighbors(query, limit)

    def find_similar_concept(self, label: str, gloss: str, kind: str, limit: int = 5) -> list[dict[str, Any]]:
        query = self.embedder.embed(concept_text(label, gloss, kind))
        return self._neighbors(query, limit)

    def _neighbors(self, query: np.ndarray, limit: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT c.id, c.kind, c.label, c.gloss, e.dim, e.vector FROM embeddings e "
            "JOIN concepts c ON c.id = e.concept_id"
        ).fetchall()
        if not rows:
            return []
        query = normalize(query.astype(np.float32))
        scored = []
        for r in rows:
            vec = np.frombuffer(r["vector"], dtype=np.float32)
            if vec.shape[0] != query.shape[0]:
                continue  # indexed with a different model; skip rather than guess
            scored.append((float(vec @ query), r))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [
            {"concept_id": r["id"], "kind": r["kind"], "label": r["label"],
             "gloss": r["gloss"], "score": round(score, 4)}
            for score, r in scored[:limit]
        ]

    # ---- links ------------------------------------------------------------

    def attach(self, concept_id: str, deck_id: str, numbers: list[int]) -> int:
        self.get_concept(concept_id)
        deck = self.get_deck(deck_id)
        valid = {s["number"] for s in deck["slides"]}
        bad = [n for n in numbers if n not in valid]
        if bad:
            raise NotFound(f"deck {deck_id} has no slide(s) {bad}")
        with self.lock, self.db:
            self.db.executemany(
                "INSERT OR IGNORE INTO concept_slides (concept_id, deck_id, number) VALUES (?, ?, ?)",
                [(concept_id, deck_id, n) for n in numbers],
            )
        return len(numbers)

    def relate(self, id_a: str, id_b: str, note: str = "") -> None:
        if id_a == id_b:
            raise ValueError("a concept cannot be related to itself")
        self.get_concept(id_a)
        self.get_concept(id_b)
        a, b = sorted((id_a, id_b))
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO relations (id_a, id_b, note) VALUES (?, ?, ?) "
                "ON CONFLICT(id_a, id_b) DO UPDATE SET note = excluded.note",
                (a, b, note),
            )

    # ---- wipe -------------------------------------------------------------

    def clear(self) -> None:
        with self.lock, self.db:
            for table in ("relations", "concept_slides", "embeddings", "concepts", "slides", "decks"):
                self.db.execute(f"DELETE FROM {table}")
        self.db.execute("VACUUM")
