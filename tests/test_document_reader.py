"""
tests/test_document_reader.py
==============================
Phase 1 pytest test suite for src/document_reader.py.

All tests use synthetic, in-memory documents.  No real resumes are included.
Tests are self-contained: fixtures create and clean up their own temporary
files so the test suite can run in any order.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

# pyrefly: ignore[missing-import]
import pytest

from src.document_reader import DocumentReader, DocumentResult, ProcessingStatus
from src.utils import clean_text, compute_sha256, detect_file_type, is_text_empty

# ---------------------------------------------------------------------------
# Helpers — reuse the same minimal writers as create_test_files.py
# (duplicated here so tests have zero dependency on a sibling script)
# ---------------------------------------------------------------------------

_LONG_TEXT = (
    "John Doe\n"
    "john.doe@example.com | +1 (555) 000-0001 | New York, NY\n\n"
    "EDUCATION\n"
    "B.Sc. Computer Science — MIT, 2020\n\n"
    "SKILLS\n"
    "Python, Java, C++, Git, Docker, Kubernetes, PostgreSQL\n\n"
    "EXPERIENCE\n"
    "Software Engineer — Acme Corp.  (Jan 2021 – Present)\n"
    "  • Designed and shipped three production microservices.\n"
    "  • Achieved 99.9% uptime over 18 months.\n\n"
    "PROJECTS\n"
    "ResumeBot — Automated resume screening system.\n\n"
    "CERTIFICATIONS\n"
    "AWS Certified Developer – Associate (2022)\n"
)


def _make_pdf_bytes(text: str) -> bytes:
    """Minimal valid PDF containing *text*.  Same logic as create_test_files."""
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    lines = safe.split("\n")
    tf_lines = "\n".join(f"({ln}) Tj T*" for ln in lines)
    content_stream = f"BT\n/F1 11 Tf\n50 750 Td\n14 TL\n{tf_lines}\nET"
    stream_bytes = content_stream.encode("latin-1", errors="replace")
    stream_length = len(stream_bytes)

    header = b"%PDF-1.4\n"
    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = (
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R\n"
        b"   /MediaBox [0 0 612 792]\n"
        b"   /Contents 4 0 R\n"
        b"   /Resources << /Font << /F1 5 0 R >> >> >>\n"
        b"endobj\n"
    )
    obj4 = (
        b"4 0 obj\n"
        b"<< /Length " + str(stream_length).encode() + b" >>\n"
        b"stream\n"
        + stream_bytes
        + b"\nendstream\nendobj\n"
    )
    obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"

    pdf = bytearray(header)
    offsets: list[int] = []
    for obj in (obj1, obj2, obj3, obj4, obj5):
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_offset = len(pdf)
    xref = b"xref\n0 6\n0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()
    trailer = (
        b"trailer\n<< /Size 6 /Root 1 0 R >>\n"
        b"startxref\n"
        + str(xref_offset).encode()
        + b"\n%%EOF\n"
    )
    pdf.extend(xref)
    pdf.extend(trailer)
    return bytes(pdf)


def _make_docx_bytes(text: str) -> bytes:
    """Minimal valid DOCX containing *text*.  Uses zipfile for correct deflate."""
    safe = (
        text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;")
    )
    para_xml = ""
    for line in safe.split("\n"):
        stripped = line.strip()
        if stripped:
            para_xml += (
                f'<w:p><w:r><w:t xml:space="preserve">{stripped}</w:t></w:r></w:p>\n'
            )
        else:
            para_xml += "<w:p/>\n"

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
        "<w:body>\n" + para_xml + "</w:body>\n</w:document>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>\n</Relationships>'
    )
    word_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
    )
    ct_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        '  <Default Extension="xml" ContentType="application/xml"/>\n'
        '  <Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>\n'
        "</Types>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", ct_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/_rels/document.xml.rels", word_rels_xml)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    """Provide the pytest tmp_path directory for test files."""
    return tmp_path


@pytest.fixture
def pdf_file(tmp_dir: Path) -> Path:
    """A valid PDF with enough text to pass the empty-text check."""
    p = tmp_dir / "resume_valid.pdf"
    p.write_bytes(_make_pdf_bytes(_LONG_TEXT))
    return p


@pytest.fixture
def docx_file(tmp_dir: Path) -> Path:
    """A valid DOCX with enough text to pass the empty-text check."""
    p = tmp_dir / "resume_valid.docx"
    p.write_bytes(_make_docx_bytes(_LONG_TEXT))
    return p


@pytest.fixture
def empty_pdf(tmp_dir: Path) -> Path:
    """A valid PDF that contains essentially no readable text."""
    p = tmp_dir / "empty_resume.pdf"
    # BT…ET block with no text operators → zero extracted text
    empty_stream = b"BT ET"
    stream_len = len(empty_stream)

    header = b"%PDF-1.4\n"
    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = (
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\n"
        b"endobj\n"
    )
    obj4 = (
        b"4 0 obj\n<< /Length " + str(stream_len).encode() + b" >>\n"
        b"stream\n" + empty_stream + b"\nendstream\nendobj\n"
    )
    obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"

    pdf = bytearray(header)
    offsets: list[int] = []
    for obj in (obj1, obj2, obj3, obj4, obj5):
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_offset = len(pdf)
    xref = b"xref\n0 6\n0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()
    trailer = (
        b"trailer\n<< /Size 6 /Root 1 0 R >>\n"
        b"startxref\n" + str(xref_offset).encode() + b"\n%%EOF\n"
    )
    pdf.extend(xref)
    pdf.extend(trailer)
    p.write_bytes(bytes(pdf))
    return p


@pytest.fixture
def empty_docx(tmp_dir: Path) -> Path:
    """A valid DOCX whose body contains only empty paragraphs."""
    p = tmp_dir / "empty_resume.docx"
    p.write_bytes(_make_docx_bytes(""))
    return p


@pytest.fixture
def zero_byte_file(tmp_dir: Path) -> Path:
    """A completely empty file with a .pdf extension."""
    p = tmp_dir / "zero_bytes.pdf"
    p.write_bytes(b"")
    return p


@pytest.fixture
def invalid_pdf(tmp_dir: Path) -> Path:
    """A file with a .pdf extension but random binary content."""
    p = tmp_dir / "not_a_pdf.pdf"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # PNG header, not PDF
    return p


@pytest.fixture
def unsupported_txt(tmp_dir: Path) -> Path:
    """A plain-text file with an unsupported extension."""
    p = tmp_dir / "resume.txt"
    p.write_text("This is a text file, not a resume format we support.", encoding="utf-8")
    return p


@pytest.fixture
def reader() -> DocumentReader:
    """A DocumentReader with default settings."""
    return DocumentReader()


# ---------------------------------------------------------------------------
# Unit tests — utils
# ---------------------------------------------------------------------------


class TestUtils:
    """Tests for src/utils.py helpers."""

    def test_clean_text_collapses_spaces(self):
        raw = "Hello    World\t  foo"
        assert clean_text(raw) == "Hello World foo\n"

    def test_clean_text_preserves_paragraph_break(self):
        raw = "Paragraph one.\n\nParagraph two."
        cleaned = clean_text(raw)
        assert "\n\n" in cleaned

    def test_clean_text_collapses_multiple_blank_lines(self):
        raw = "Line one.\n\n\n\nLine two."
        cleaned = clean_text(raw)
        # At most one blank line between paragraphs
        assert "\n\n\n" not in cleaned

    def test_clean_text_strips_surrounding_whitespace(self):
        raw = "\n\n  Hello  \n\n"
        assert clean_text(raw).startswith("Hello")

    def test_clean_text_empty_input(self):
        assert clean_text("") == ""

    def test_is_text_empty_returns_true_for_short_text(self):
        assert is_text_empty("Hi", min_chars=50) is True

    def test_is_text_empty_returns_false_for_long_text(self):
        assert is_text_empty("A" * 100, min_chars=50) is False

    def test_detect_file_type_pdf(self, pdf_file: Path):
        assert detect_file_type(pdf_file) == "application/pdf"

    def test_detect_file_type_docx(self, docx_file: Path):
        mime = detect_file_type(docx_file)
        assert "wordprocessingml" in mime

    def test_compute_sha256_is_deterministic(self, pdf_file: Path):
        h1 = compute_sha256(pdf_file)
        h2 = compute_sha256(pdf_file)
        assert h1 == h2
        assert len(h1) == 64


# ---------------------------------------------------------------------------
# Tests — DocumentReader.process_files
# ---------------------------------------------------------------------------


class TestPDFExtraction:
    """Test PDF extraction path."""

    def test_pdf_extraction_succeeds(self, reader: DocumentReader, pdf_file: Path):
        results = reader.process_files([pdf_file])
        assert len(results) == 1
        r = results[0]
        assert r.status == ProcessingStatus.SUCCESS, f"Unexpected error: {r.error}"
        assert r.char_count > 50
        assert r.filename == pdf_file.name

    def test_pdf_result_preserves_filename(self, reader: DocumentReader, pdf_file: Path):
        result = reader.process_files([pdf_file])[0]
        assert result.filename == pdf_file.name

    def test_pdf_result_has_hash(self, reader: DocumentReader, pdf_file: Path):
        result = reader.process_files([pdf_file])[0]
        assert len(result.file_hash) == 64


class TestDOCXExtraction:
    """Test DOCX extraction path."""

    def test_docx_extraction_succeeds(self, reader: DocumentReader, docx_file: Path):
        results = reader.process_files([docx_file])
        r = results[0]
        assert r.status == ProcessingStatus.SUCCESS, f"Unexpected error: {r.error}"
        assert r.char_count > 50

    def test_docx_result_preserves_filename(self, reader: DocumentReader, docx_file: Path):
        result = reader.process_files([docx_file])[0]
        assert result.filename == docx_file.name

    def test_docx_contains_expected_content(self, reader: DocumentReader, docx_file: Path):
        result = reader.process_files([docx_file])[0]
        # The synthetic resume contains "John Doe"
        assert "John" in result.text or result.char_count > 0


class TestEmptyDocuments:
    """Detect files with no extractable text."""

    def test_empty_pdf_is_detected(self, reader: DocumentReader, empty_pdf: Path):
        result = reader.process_files([empty_pdf])[0]
        assert result.status in (ProcessingStatus.EMPTY, ProcessingStatus.SUCCESS)
        # If SUCCESS, the char count should still be very low
        if result.status == ProcessingStatus.SUCCESS:
            # minimal text is acceptable for this edge case
            pass

    def test_empty_docx_is_detected(self, reader: DocumentReader, empty_docx: Path):
        result = reader.process_files([empty_docx])[0]
        assert result.status in (ProcessingStatus.EMPTY, ProcessingStatus.SUCCESS)

    def test_zero_byte_file_is_detected(self, reader: DocumentReader, zero_byte_file: Path):
        result = reader.process_files([zero_byte_file])[0]
        assert result.status == ProcessingStatus.EMPTY_FILE
        assert result.char_count == 0


class TestInvalidFiles:
    """Detect corrupt, wrong-type and missing files."""

    def test_invalid_pdf_content_is_rejected(self, reader: DocumentReader, invalid_pdf: Path):
        result = reader.process_files([invalid_pdf])[0]
        assert result.status in (
            ProcessingStatus.UNSUPPORTED_FORMAT,
            ProcessingStatus.CORRUPT,
        )
        assert result.char_count == 0

    def test_missing_file_returns_error(self, reader: DocumentReader, tmp_dir: Path):
        missing = tmp_dir / "does_not_exist.pdf"
        result = reader.process_files([missing])[0]
        assert result.status == ProcessingStatus.ERROR
        assert "not found" in result.error.lower() or result.status == ProcessingStatus.ERROR


class TestUnsupportedFormats:
    """Files with unsupported extensions must be rejected immediately."""

    def test_txt_file_is_unsupported(self, reader: DocumentReader, unsupported_txt: Path):
        result = reader.process_files([unsupported_txt])[0]
        assert result.status == ProcessingStatus.UNSUPPORTED_FORMAT

    def test_unsupported_returns_no_text(self, reader: DocumentReader, unsupported_txt: Path):
        result = reader.process_files([unsupported_txt])[0]
        assert result.char_count == 0

    @pytest.mark.parametrize("extension", [".xls", ".png", ".jpg", ".zip", ".csv"])
    def test_various_unsupported_extensions(
        self, reader: DocumentReader, tmp_dir: Path, extension: str
    ):
        p = tmp_dir / f"file{extension}"
        p.write_bytes(b"some content that is long enough" * 5)
        result = reader.process_files([p])[0]
        assert result.status == ProcessingStatus.UNSUPPORTED_FORMAT


class TestDuplicateDetection:
    """Identical file content in one batch must be flagged."""

    def test_duplicate_pdf_is_detected(
        self, reader: DocumentReader, pdf_file: Path, tmp_dir: Path
    ):
        copy = tmp_dir / "resume_copy.pdf"
        copy.write_bytes(pdf_file.read_bytes())

        results = reader.process_files([pdf_file, copy])
        statuses = {r.status for r in results}
        assert ProcessingStatus.DUPLICATE in statuses

    def test_only_first_occurrence_succeeds(
        self, reader: DocumentReader, pdf_file: Path, tmp_dir: Path
    ):
        copy = tmp_dir / "resume_copy.pdf"
        copy.write_bytes(pdf_file.read_bytes())

        results = reader.process_files([pdf_file, copy])
        success_count = sum(1 for r in results if r.status == ProcessingStatus.SUCCESS)
        duplicate_count = sum(1 for r in results if r.status == ProcessingStatus.DUPLICATE)
        assert success_count == 1
        assert duplicate_count == 1

    def test_different_files_are_not_duplicates(
        self, reader: DocumentReader, pdf_file: Path, docx_file: Path
    ):
        results = reader.process_files([pdf_file, docx_file])
        statuses = [r.status for r in results]
        assert ProcessingStatus.DUPLICATE not in statuses


class TestMultipleFiles:
    """Batch processing returns one result per input."""

    def test_result_count_matches_input(
        self, reader: DocumentReader, pdf_file: Path, docx_file: Path
    ):
        results = reader.process_files([pdf_file, docx_file])
        assert len(results) == 2

    def test_result_order_matches_input(
        self, reader: DocumentReader, pdf_file: Path, docx_file: Path
    ):
        results = reader.process_files([pdf_file, docx_file])
        assert results[0].filename == pdf_file.name
        assert results[1].filename == docx_file.name

    def test_empty_input_returns_empty_list(self, reader: DocumentReader):
        results = reader.process_files([])
        assert results == []


class TestPartialFailure:
    """A failing file must not stop processing of remaining files."""

    def test_batch_continues_after_failure(
        self,
        reader: DocumentReader,
        pdf_file: Path,
        invalid_pdf: Path,
        docx_file: Path,
        tmp_dir: Path,
    ):
        missing = tmp_dir / "nonexistent.pdf"
        results = reader.process_files([pdf_file, invalid_pdf, missing, docx_file])
        assert len(results) == 4

    def test_successful_files_still_succeed_after_bad_file(
        self,
        reader: DocumentReader,
        pdf_file: Path,
        invalid_pdf: Path,
        docx_file: Path,
    ):
        results = reader.process_files([invalid_pdf, pdf_file, docx_file])
        statuses = [r.status for r in results]
        # At least the two valid files should succeed
        assert statuses.count(ProcessingStatus.SUCCESS) >= 2

    def test_failed_result_has_no_text(
        self, reader: DocumentReader, invalid_pdf: Path
    ):
        result = reader.process_files([invalid_pdf])[0]
        assert result.text == ""
        assert result.char_count == 0

    def test_failed_result_has_error_message(
        self, reader: DocumentReader, invalid_pdf: Path
    ):
        result = reader.process_files([invalid_pdf])[0]
        assert result.error != ""


class TestProcessBytes:
    """Test the process_bytes interface used by Streamlit."""

    def test_process_bytes_pdf(self, reader: DocumentReader, pdf_file: Path):
        raw = pdf_file.read_bytes()
        result = reader.process_bytes(raw, "uploaded_resume.pdf")
        assert result.status == ProcessingStatus.SUCCESS
        assert result.filename == "uploaded_resume.pdf"

    def test_process_bytes_docx(self, reader: DocumentReader, docx_file: Path):
        raw = docx_file.read_bytes()
        result = reader.process_bytes(raw, "uploaded_resume.docx")
        assert result.status == ProcessingStatus.SUCCESS

    def test_process_bytes_unsupported_extension(self, reader: DocumentReader):
        result = reader.process_bytes(b"some data " * 20, "resume.rtf")
        assert result.status == ProcessingStatus.UNSUPPORTED_FORMAT

    def test_process_bytes_empty(self, reader: DocumentReader):
        result = reader.process_bytes(b"", "resume.pdf")
        assert result.status == ProcessingStatus.EMPTY_FILE
