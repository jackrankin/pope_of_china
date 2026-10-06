from __future__ import annotations

import pytest

from yuji import slides


def test_text_splits_on_separator(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("one\n\n---\n\ntwo\n***\nthree", encoding="utf-8")
    assert slides.extract(f) == ["one", "two", "three"]


def test_text_without_separator_is_one_slide(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("just one", encoding="utf-8")
    assert slides.extract(f) == ["just one"]


def test_pptx_text_and_notes(tmp_path):
    from pptx import Presentation

    prs = Presentation()
    layout = prs.slide_layouts[1]  # title + content
    s1 = prs.slides.add_slide(layout)
    s1.shapes.title.text = "回家 huíjiā"
    s1.placeholders[1].text = "to return home"
    s1.notes_slide.notes_text_frame.text = "contrast with 去家"
    s2 = prs.slides.add_slide(layout)
    s2.shapes.title.text = "把字句"
    s2.placeholders[1].text = "S 把 O V"
    f = tmp_path / "deck.pptx"
    prs.save(str(f))

    out = slides.extract(f)
    assert len(out) == 2
    assert "回家 huíjiā" in out[0] and "to return home" in out[0]
    assert "[notes] contrast with 去家" in out[0]
    assert out[1].startswith("把字句")


def test_unsupported_type(tmp_path):
    f = tmp_path / "x.docx"
    f.write_bytes(b"")
    with pytest.raises(ValueError):
        slides.extract(f)
