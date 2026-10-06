"""Pull per-slide text out of PPTX, PDF, and plain-text decks."""

from __future__ import annotations

import re
from pathlib import Path


def extract(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".pptx":
        return _pptx(path)
    if suffix == ".pdf":
        return _pdf(path)
    if suffix in {".txt", ".md"}:
        return _text(path)
    raise ValueError(f"unsupported file type {suffix!r}; use .pptx, .pdf, .txt, or .md")


def _pptx(path: Path) -> list[str]:
    from pptx import Presentation

    out: list[str] = []
    for slide in Presentation(str(path)).slides:
        chunks: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    line = "".join(run.text for run in para.runs).strip()
                    if line:
                        chunks.append(line)
            if getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    cells = [c.text.strip() for c in row.cells if c.text.strip()]
                    if cells:
                        chunks.append(" | ".join(cells))
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                chunks.append(f"[notes] {notes}")
        out.append("\n".join(chunks))
    return out


def _pdf(path: Path) -> list[str]:
    from pypdf import PdfReader

    return [(page.extract_text() or "").strip() for page in PdfReader(str(path)).pages]


_SEPARATOR = re.compile(r"^\s*(?:---+|\*\*\*+|\f)\s*$", re.MULTILINE)


def _text(path: Path) -> list[str]:
    """A `---` line or form feed separates slides. Without one, the file is one slide."""
    body = path.read_text(encoding="utf-8")
    parts = [p.strip() for p in _SEPARATOR.split(body)]
    return [p for p in parts if p] or [""]
