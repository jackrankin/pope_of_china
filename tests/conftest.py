from __future__ import annotations

import hashlib

import numpy as np
import pytest

from yuji import config
from yuji.embed import normalize
from yuji.store import Store


class FakeEmbedder:
    """Deterministic embeddings for tests: same text → same vector.

    `pairs` lets a test declare that two texts should land close together.
    """

    def __init__(self, dim: int = 16):
        self.dim = dim
        self.aliases: dict[str, str] = {}

    def alias(self, text: str, like: str, weight: float = 0.95) -> None:
        self.aliases[text] = (like, weight)

    def _base(self, text: str) -> np.ndarray:
        seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
        rng = np.random.default_rng(seed)
        return normalize(rng.standard_normal(self.dim).astype(np.float32))

    def embed(self, text: str) -> np.ndarray:
        if text in self.aliases:
            like, w = self.aliases[text]
            return normalize(w * self._base(like) + (1 - w) * self._base(text))
        return self._base(text)


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("YUJI_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def embedder():
    return FakeEmbedder()


@pytest.fixture
def store(home, embedder):
    s = Store(embedder, path=config.db_path())
    yield s
    s.close()
