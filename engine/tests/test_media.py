"""Tests for knowit.media — slide decks, audio overview script, mind-map outline."""
from __future__ import annotations

import os

from knowit.media import (audio_script, build_pptx, mindmap_markdown,
                          script_to_text, slide_outline, synthesize_audio)


def test_slide_outline_styles(idx):
    for style in ("executive", "technical", "architecture"):
        slides = slide_outline(idx, style)
        assert slides
        assert slides[0]["type"] == "title"
        assert slides[0]["title"] == "sample_repo"
        assert all("type" in s for s in slides)


def test_slide_outline_unknown_style_falls_back_to_technical(idx):
    assert slide_outline(idx, "nonexistent") == slide_outline(idx, "technical")


def test_slide_outline_technical_includes_debt(idx):
    titles = [s.get("title") for s in slide_outline(idx, "technical")]
    assert "Technical debt" in titles


def test_audio_script_structural_fallback(idx):
    script = audio_script(idx, model="")     # no LLM -> deterministic fallback
    assert len(script) == 10
    speakers = {t["speaker"] for t in script}
    assert speakers == {"Maya", "Dev"}
    assert "sample_repo" in script[0]["text"]


def test_script_to_text(idx):
    text = script_to_text(audio_script(idx, model=""))
    assert "Maya:" in text and "Dev:" in text


def test_mindmap_markdown(idx):
    md = mindmap_markdown(idx, depth=2)
    lines = md.splitlines()
    assert lines[0] == "- sample_repo (repo)"
    # children are indented beneath the root
    assert any(ln.startswith("  - ") for ln in lines)


def test_build_pptx(idx, tmp_path):
    out = str(tmp_path / "deck.pptx")
    try:
        import pptx  # noqa: F401
    except Exception:
        # python-pptx is optional; building must fail loudly, not silently
        import pytest
        with pytest.raises(ImportError):
            build_pptx(idx, "technical", out)
        return
    result = build_pptx(idx, "technical", out)
    assert result == out
    assert os.path.exists(out) and os.path.getsize(out) > 0


def test_synthesize_audio_contract(idx, tmp_path):
    out = str(tmp_path / "overview.mp3")
    path, msg = synthesize_audio(audio_script(idx, model=""), out)
    assert isinstance(msg, str) and msg
    # backends are all optional: either no audio (None) or a real file was written
    assert path is None or os.path.exists(path)
