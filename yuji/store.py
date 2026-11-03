"""SQLite table of words: characters, pinyin, English meaning.

The characters are the key, so the database itself prevents duplicates.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config, meaning as meaning_mod, pinyin, ranks

SCHEMA = """
CREATE TABLE IF NOT EXISTS words (
    hanzi        TEXT PRIMARY KEY,
    pinyin       TEXT NOT NULL,
    meaning      TEXT NOT NULL,
    level        INTEGER NOT NULL DEFAULT 0,
    quiz_english INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path | None = None):
        self.path = path or config.db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Tools may run on worker threads; one connection, serialized by a lock.
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.lock = threading.RLock()
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        cols = {r["name"] for r in self.db.execute("PRAGMA table_info(words)")}
        with self.lock, self.db:
            if "quiz_english" not in cols:
                self.db.execute("ALTER TABLE words ADD COLUMN quiz_english INTEGER NOT NULL DEFAULT 1")
                for row in self.db.execute("SELECT hanzi, meaning FROM words").fetchall():
                    self.db.execute(
                        "UPDATE words SET quiz_english = ? WHERE hanzi = ?",
                        (int(meaning_mod.quizzable(row["meaning"])), row["hanzi"]),
                    )
            if "level" not in cols:
                self.db.execute("ALTER TABLE words ADD COLUMN level INTEGER NOT NULL DEFAULT 0")
                for row in self.db.execute("SELECT hanzi FROM words").fetchall():
                    self.db.execute(
                        "UPDATE words SET level = ? WHERE hanzi = ?",
                        (ranks.level(row["hanzi"]), row["hanzi"]),
                    )

    def close(self) -> None:
        self.db.close()

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["quiz_english"] = bool(d["quiz_english"])
        return d

    def add(self, hanzi: str, pin: str, meaning: str, quiz_english: bool | None = None) -> dict[str, Any]:
        """Insert or update one word. Returns what happened.

        quiz_english: whether the word belongs in the character-to-English quiz.
        None means decide from the meaning text (grammar descriptions are excluded).
        """
        hanzi, pin, meaning = hanzi.strip(), pinyin.normalize(pin), meaning.strip()
        if not hanzi or not pin or not meaning:
            raise ValueError("hanzi, pinyin, and meaning are all required")
        if quiz_english is None:
            quiz_english = meaning_mod.quizzable(meaning)
        lvl = ranks.level(hanzi)
        new = {"hanzi": hanzi, "pinyin": pin, "meaning": meaning, "quiz_english": quiz_english, "level": lvl}
        with self.lock, self.db:
            old = self.db.execute("SELECT * FROM words WHERE hanzi = ?", (hanzi,)).fetchone()
            now = _now()
            if old is None:
                self.db.execute(
                    "INSERT INTO words (hanzi, pinyin, meaning, level, quiz_english, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (hanzi, pin, meaning, lvl, int(quiz_english), now, now),
                )
                return {"status": "added", **new}
            was = {"pinyin": old["pinyin"], "meaning": old["meaning"], "quiz_english": bool(old["quiz_english"])}
            if was == {k: new[k] for k in was}:
                return {"status": "unchanged", **new}
            self.db.execute(
                "UPDATE words SET pinyin = ?, meaning = ?, level = ?, quiz_english = ?, updated_at = ? WHERE hanzi = ?",
                (pin, meaning, lvl, int(quiz_english), now, hanzi),
            )
            return {"status": "updated", **new, "was": was}

    def get(self, hanzi: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT * FROM words WHERE hanzi = ?", (hanzi.strip(),)).fetchone()
        return self._row(row) if row else None

    def find_by_pinyin(self, pin: str) -> list[str]:
        """Characters of every stored word with exactly this pinyin (homophones)."""
        rows = self.db.execute(
            "SELECT hanzi FROM words WHERE pinyin = ? ORDER BY rowid", (pinyin.normalize(pin),)
        ).fetchall()
        return [r["hanzi"] for r in rows]

    def remove(self, hanzi: str) -> bool:
        with self.lock, self.db:
            cur = self.db.execute("DELETE FROM words WHERE hanzi = ?", (hanzi.strip(),))
        return cur.rowcount > 0

    def list(self, query: str = "", limit: int = 0) -> list[dict[str, Any]]:
        sql = "SELECT hanzi, pinyin, meaning, level, quiz_english, created_at FROM words"
        params: list[Any] = []
        if query:
            like = f"%{query}%"
            sql += " WHERE hanzi LIKE ? OR pinyin LIKE ? OR meaning LIKE ?"
            params += [like, like, like]
        sql += " ORDER BY rowid"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        return [self._row(r) for r in self.db.execute(sql, params).fetchall()]

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM words").fetchone()[0]

    def clear(self) -> int:
        with self.lock, self.db:
            n = self.count()
            self.db.execute("DELETE FROM words")
        return n
