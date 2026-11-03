"""Paths for 语迹."""

from __future__ import annotations

import os
from pathlib import Path


def home() -> Path:
    """Directory that holds the database. Override with YUJI_HOME."""
    return Path(os.environ.get("YUJI_HOME", Path.home() / ".yuji")).expanduser()


def db_path() -> Path:
    return home() / "yuji.db"
