"""Paths and tunables for 语迹."""

from __future__ import annotations

import os
from pathlib import Path

# Multilingual sentence model served by fastembed (ONNX, no torch).
EMBED_MODEL = os.environ.get(
    "YUJI_EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

# Cosine similarity at or above this is "very close": create_concept refuses to
# write unless the agent passes confirm_new=True. With the default model,
# 回家/去家 scores ~0.78, 回家/苹果 ~0.26, and a reworded duplicate 0.7-0.97
# (duplicates with identical characters are caught separately, by hanzi match).
SIMILAR_THRESHOLD = float(os.environ.get("YUJI_SIMILAR_THRESHOLD", "0.75"))

KINDS = ("word", "language_point", "other")


def home() -> Path:
    """Directory that holds the index. Override with YUJI_HOME."""
    return Path(os.environ.get("YUJI_HOME", Path.home() / ".yuji")).expanduser()


def db_path() -> Path:
    return home() / "yuji.db"


def model_dir() -> Path:
    return home() / "models"
