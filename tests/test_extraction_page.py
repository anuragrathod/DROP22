"""
tests/test_extraction_page.py
==============================
Tests for the Extraction Inspector page (pages/e.py).
"""

from __future__ import annotations

from pathlib import Path
# pyrefly: ignore[missing-import]
from streamlit.testing.v1 import AppTest

_PAGE_PATH = str(Path(__file__).parent.parent / "pages" / "e.py")


def test_extraction_page_loads_without_error():
    at = AppTest.from_file(_PAGE_PATH, default_timeout=30).run()
    assert not at.exception, f"Extraction page raised: {at.exception}"


def test_extraction_page_has_uploader():
    at = AppTest.from_file(_PAGE_PATH, default_timeout=30).run()
    assert len(at.file_uploader) >= 1


def test_extraction_page_no_ollama():
    at = AppTest.from_file(_PAGE_PATH, default_timeout=30).run()
    all_text = " ".join(str(m.value) for m in at.markdown if hasattr(m, "value"))
    assert "ollama" not in all_text.lower()


def test_extraction_page_upload_and_display_text():
    at = AppTest.from_file(_PAGE_PATH, default_timeout=30).run()
    sample_pdf = Path(__file__).parent.parent / "sample_resumes" / "alice_chen_resume.pdf"
    if sample_pdf.exists():
        at.file_uploader[0].upload("alice_chen_resume.pdf", sample_pdf.read_bytes(), mime_type="application/pdf").run()
        assert not at.exception, f"App raised exception on upload: {at.exception}"
        # Assert code block with extracted text exists
        assert len(at.code) >= 1
        assert "Alice Chen" in at.code[0].value
