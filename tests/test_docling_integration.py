"""
tests/test_docling_integration.py
==================================
Tests verifying Docling integration for PDF and DOCX text extraction.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from src.document_reader import DocumentReader, ProcessingStatus

_SAMPLE_DIR = Path(__file__).parent.parent / "sample_resumes"


class TestDoclingIntegration:

    @pytest.fixture
    def reader(self) -> DocumentReader:
        return DocumentReader()

    def test_docling_extracts_sample_pdf(self, reader: DocumentReader):
        pdf_path = _SAMPLE_DIR / "alice_chen_resume.pdf"
        assert pdf_path.exists()

        results = reader.process_files([pdf_path])
        assert len(results) == 1
        res = results[0]
        assert res.status == ProcessingStatus.SUCCESS
        assert "Alice Chen" in res.text
        assert "Stanford" in res.text
        assert res.char_count > 100

    def test_docling_extracts_sample_docx(self, reader: DocumentReader):
        docx_path = _SAMPLE_DIR / "bob_patel_resume.docx"
        assert docx_path.exists()

        results = reader.process_files([docx_path])
        assert len(results) == 1
        res = results[0]
        assert res.status == ProcessingStatus.SUCCESS
        assert "Bob Patel" in res.text
        assert "Edinburgh" in res.text
        assert res.char_count > 100

    def test_docling_converter_initialization(self, reader: DocumentReader):
        converter = DocumentReader._get_docling_converter()
        assert converter is not None
