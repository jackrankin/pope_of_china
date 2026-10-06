"""Embedding model. Loaded lazily so `yuji clear` and server startup stay fast."""

from __future__ import annotations

from typing import Protocol

import numpy as np

from . import config


class Embedder(Protocol):
    def embed(self, text: str) -> np.ndarray: ...


class FastEmbedder:
    """Wraps a fastembed TextEmbedding, downloading the model on first use."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or config.EMBED_MODEL
        self._model = None

    def _load(self):
        if self._model is None:
            from fastembed import TextEmbedding

            cache = config.model_dir()
            cache.mkdir(parents=True, exist_ok=True)
            self._model = TextEmbedding(model_name=self.model_name, cache_dir=str(cache))
        return self._model

    def embed(self, text: str) -> np.ndarray:
        model = self._load()
        vec = next(iter(model.embed([text])))
        return normalize(np.asarray(vec, dtype=np.float32))


class HashEmbedder:
    """Offline stand-in used by tests (YUJI_FAKE_EMBEDDER=1). Not semantic."""

    def __init__(self, dim: int = 32):
        self.dim = dim

    def embed(self, text: str) -> np.ndarray:
        import hashlib

        seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
        rng = np.random.default_rng(seed)
        return normalize(rng.standard_normal(self.dim).astype(np.float32))


def default_embedder() -> Embedder:
    import os

    if os.environ.get("YUJI_FAKE_EMBEDDER"):
        return HashEmbedder()
    return FastEmbedder()


def normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    return vec / norm if norm else vec


def hanzi(label: str) -> str:
    """Only the CJK characters of a label: "回家 huíjiā" -> "回家"."""
    return "".join(ch for ch in label if "\u3400" <= ch <= "\u9fff" or "\uf900" <= ch <= "\ufaff")


def concept_text(label: str, gloss: str, kind: str) -> str:
    """The string that stands for a concept in vector space."""
    kind_word = {"word": "word", "language_point": "grammar point", "other": "note"}.get(kind, kind)
    return f"{label} ({kind_word}): {gloss}"
