"""
src/document_reader.py
======================
Phase 1 document reader for the Resume-to-Excel Automation System.

Responsibilities:
- Accept one or more PDF / DOCX file paths.
- Validate each file (extension, file signature, size, emptiness, duplicates).
- Extract text via MarkItDown, with PyMuPDF as a fallback for PDFs.
- Clean and normalise the extracted text.
- Return a consistent ``DocumentResult`` for every file regardless of outcome.
- Continue processing the remaining files when one fails.
- Never retain uploaded file content beyond the current call.
"""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable

from src.utils import (
    MAX_FILE_SIZE_BYTES,
    SUPPORTED_EXTENSIONS,
    clean_text,
    compute_sha256,
    detect_file_type,
    is_supported_file,
    is_text_empty,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class ProcessingStatus(str, Enum):
    """Possible outcomes for a single file."""

    SUCCESS = "success"
    EMPTY = "empty"  # File existed but contained no usable text
    UNSUPPORTED_FORMAT = "unsupported_format"
    FILE_TOO_LARGE = "file_too_large"
    EMPTY_FILE = "empty_file"  # Zero-byte file
    DUPLICATE = "duplicate"  # Content hash already seen in this batch
    CORRUPT = "corrupt"  # File could not be parsed at all
    PASSWORD_PROTECTED = "password_protected"
    ERROR = "error"  # Unexpected runtime error


@dataclass
class DocumentResult:
    """The result of processing a single document.

    Attributes:
        filename:   Original filename as supplied by the caller.
        status:     Outcome of the processing attempt.
        text:       Cleaned extracted text, or ``""`` on failure.
        error:      Human-readable description of the failure, or ``""``
                    on success.
        file_hash:  SHA-256 of the file contents, or ``""`` if uncomputable.
        char_count: Number of characters in ``text``.
    """

    filename: str
    status: ProcessingStatus
    text: str = ""
    error: str = ""
    file_hash: str = ""
    char_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.char_count = len(self.text)

    @property
    def succeeded(self) -> bool:
        """True when text was successfully extracted."""
        return self.status == ProcessingStatus.SUCCESS

    @property
    def extracted_text(self) -> str:
        """Alias for text for API consistency."""
        return self.text

    def __repr__(self) -> str:
        return (
            f"DocumentResult(filename={self.filename!r}, "
            f"status={self.status.value!r}, "
            f"char_count={self.char_count})"
        )


# ---------------------------------------------------------------------------
# Document reader
# ---------------------------------------------------------------------------


class DocumentReader:
    """Extracts text from multiple PDF and DOCX files.

    Usage::

        reader = DocumentReader()
        results = reader.process_files(["resume1.pdf", "resume2.docx"])
        for r in results:
            print(r.filename, r.status, r.char_count)

    Args:
        max_file_size: Maximum accepted file size in bytes.
                       Defaults to :data:`~src.utils.MAX_FILE_SIZE_BYTES`.
        min_text_chars: Minimum non-whitespace characters required before a
                        document is considered non-empty.
    """

    def __init__(
        self,
        max_file_size: int = MAX_FILE_SIZE_BYTES,
        min_text_chars: int = 50,
    ) -> None:
        self._max_file_size = max_file_size
        self._min_text_chars = min_text_chars

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_files(
        self,
        file_paths: Iterable[str | Path],
    ) -> list[DocumentResult]:
        """Process multiple files and return one result per file.

        Files are processed sequentially. A failure in one file never stops
        the remaining files from being processed.

        Duplicate detection is scoped to this call: if the same file content
        appears twice in the same batch the second occurrence is marked
        :attr:`ProcessingStatus.DUPLICATE`.

        Args:
            file_paths: An iterable of paths (strings or :class:`Path`).

        Returns:
            A list of :class:`DocumentResult` objects, one per input path,
            in the same order as ``file_paths``.
        """
        results: list[DocumentResult] = []
        seen_hashes: set[str] = set()

        for raw_path in file_paths:
            path = Path(raw_path)
            result = self._process_single(path, seen_hashes)
            if result.file_hash:
                seen_hashes.add(result.file_hash)
            results.append(result)
            logger.info(
                "Processed %s → %s (%d chars)",
                path.name,
                result.status.value,
                result.char_count,
            )

        return results

    def process_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        seen_hashes: set[str] | None = None,
    ) -> DocumentResult:
        """Process a file supplied as raw bytes (e.g., from a Streamlit uploader).

        The bytes are written to a temporary file, processed, and the temp
        file is deleted immediately afterwards.

        Args:
            file_bytes: Raw content of the uploaded file.
            filename:   Original filename, used for extension detection and
                        for the result.
            seen_hashes: Optional set of previously seen SHA-256 hashes for
                         duplicate detection within a batch.

        Returns:
            A :class:`DocumentResult`.
        """
        if seen_hashes is None:
            seen_hashes = set()

        suffix = Path(filename).suffix.lower()
        tmp_path: str | None = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False
            ) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            result = self._process_single(
                Path(tmp_path), seen_hashes, display_name=filename
            )
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_single(
        self,
        path: Path,
        seen_hashes: set[str],
        display_name: str | None = None,
    ) -> DocumentResult:
        """Validate and extract text from a single file.

        Args:
            path:         Filesystem path to the file.
            seen_hashes:  Hashes already encountered in this batch.
            display_name: Name to record in the result (defaults to the
                          file's own name).

        Returns:
            A :class:`DocumentResult`.
        """
        filename = display_name or path.name

        # ---- 1. File must exist ----------------------------------------
        if not path.exists():
            return DocumentResult(
                filename=filename,
                status=ProcessingStatus.ERROR,
                error=f"File not found: {path}",
            )

        # ---- 2. Extension check ----------------------------------------
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return DocumentResult(
                filename=filename,
                status=ProcessingStatus.UNSUPPORTED_FORMAT,
                error=(
                    f"Unsupported file type '{path.suffix}'. "
                    f"Accepted formats: PDF, DOCX."
                ),
            )

        # ---- 3. Zero-byte check ----------------------------------------
        try:
            file_size = path.stat().st_size
        except OSError as exc:
            return DocumentResult(
                filename=filename,
                status=ProcessingStatus.ERROR,
                error=f"Cannot read file metadata: {exc}",
            )

        if file_size == 0:
            return DocumentResult(
                filename=filename,
                status=ProcessingStatus.EMPTY_FILE,
                error="File is empty (0 bytes).",
            )

        # ---- 4. Size limit ---------------------------------------------
        if file_size > self._max_file_size:
            limit_mb = self._max_file_size / (1024 * 1024)
            size_mb = file_size / (1024 * 1024)
            return DocumentResult(
                filename=filename,
                status=ProcessingStatus.FILE_TOO_LARGE,
                error=(
                    f"File is {size_mb:.1f} MB; the limit is {limit_mb:.0f} MB."
                ),
            )

        # ---- 5. File-signature (magic bytes) check ---------------------
        if not is_supported_file(path):
            detected = detect_file_type(path)
            return DocumentResult(
                filename=filename,
                status=ProcessingStatus.UNSUPPORTED_FORMAT,
                error=(
                    f"File content does not match the declared extension "
                    f"(detected: {detected or 'unknown'}). "
                    f"The file may be corrupt or its extension may be wrong."
                ),
            )

        # ---- 6. Duplicate detection ------------------------------------
        try:
            file_hash = compute_sha256(path)
        except OSError as exc:
            file_hash = ""
            logger.warning("Could not hash %s: %s", filename, exc)

        if file_hash and file_hash in seen_hashes:
            return DocumentResult(
                filename=filename,
                status=ProcessingStatus.DUPLICATE,
                error="A file with identical content has already been processed in this batch.",
                file_hash=file_hash,
            )

        # ---- 7. Text extraction ----------------------------------------
        raw_text, extraction_error = self._extract_text(path)

        if extraction_error:
            # Distinguish password-protected PDFs from generic corruption
            if "password" in extraction_error.lower() or "encrypted" in extraction_error.lower():
                return DocumentResult(
                    filename=filename,
                    status=ProcessingStatus.PASSWORD_PROTECTED,
                    error=extraction_error,
                    file_hash=file_hash,
                )
            return DocumentResult(
                filename=filename,
                status=ProcessingStatus.CORRUPT,
                error=extraction_error,
                file_hash=file_hash,
            )

        # ---- 8. Empty-text detection ------------------------------------
        cleaned = clean_text(raw_text)

        if is_text_empty(cleaned, self._min_text_chars):
            return DocumentResult(
                filename=filename,
                status=ProcessingStatus.EMPTY,
                error=(
                    "No readable text could be extracted. "
                    "The file may be a scanned image or contain only graphics."
                ),
                file_hash=file_hash,
                text=cleaned,
            )

        return DocumentResult(
            filename=filename,
            status=ProcessingStatus.SUCCESS,
            text=cleaned,
            file_hash=file_hash,
        )

    def _extract_text(self, path: Path) -> tuple[str, str]:
        """Attempt text extraction, returning ``(text, error_message)``.

        Strategy:
        1. Try Docling (handles PDF and DOCX with advanced layout awareness).
        2. Fallback to MarkItDown if Docling yields no usable text or errors.
        3. For PDFs, fallback to PyMuPDF if MarkItDown also fails.

        Returns:
            A 2-tuple: ``(extracted_text, error_message)``.
            On success the error string is empty; on failure the text is empty.
        """
        suffix = path.suffix.lower()

        # --- Primary: Docling (docling-main) ----------------------------
        docling_text, docling_error = self._try_docling(path)
        if not docling_error and not is_text_empty(docling_text, self._min_text_chars):
            return docling_text, ""

        logger.debug(
            "Docling extraction failed or empty for %s: %s; trying MarkItDown.",
            path.name,
            docling_error,
        )

        # --- Secondary Fallback: MarkItDown -----------------------------
        md_text, md_error = self._try_markitdown(path)
        if not md_error and not is_text_empty(md_text, self._min_text_chars):
            return md_text, ""

        # --- Tertiary Fallback: PyMuPDF (PDFs only) ---------------------
        if suffix == ".pdf":
            logger.debug(
                "MarkItDown insufficient for %s; trying PyMuPDF fallback.",
                path.name,
            )
            pymupdf_text, pymupdf_error = self._try_pymupdf(path)
            if not pymupdf_error and not is_text_empty(pymupdf_text, self._min_text_chars):
                return pymupdf_text, ""
            if pymupdf_error:
                return "", pymupdf_error

        # If both primary and fallback failed, preserve password-protected status if present
        for err in (docling_error, md_error):
            if "password" in err.lower() or "encrypt" in err.lower():
                return "", err

        return docling_text or md_text, docling_error or md_error

    @classmethod
    def _get_docling_converter(cls):
        """Lazy initialization of the Docling DocumentConverter instance."""
        if not hasattr(cls, "_docling_converter_instance"):
            try:
                # pyrefly: ignore[missing-import]
                from docling.datamodel.base_models import InputFormat
                from docling.document_converter import (  # type: ignore[import-untyped]
                    DocumentConverter,
                    NativePdfFormatOption,
                )

                cls._docling_converter_instance = DocumentConverter(
                    format_options={
                        InputFormat.PDF: NativePdfFormatOption()
                    }
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("Docling converter initialization skipped: %s", exc)
                cls._docling_converter_instance = None
        return cls._docling_converter_instance

    @classmethod
    def _try_docling(cls, path: Path) -> tuple[str, str]:
        """Extract text via Docling (docling-main).

        Returns:
            ``(text, error_message)``
        """
        try:
            converter = cls._get_docling_converter()
            if converter is None:
                return "", "Docling converter not available"

            conv_res = converter.convert(str(path))
            # Export structured markdown text preserving layout
            markdown_text = conv_res.document.export_to_markdown()
            return markdown_text or "", ""
        except Exception as exc:  # noqa: BLE001
            error_str = str(exc).lower()
            if "password" in error_str or "encrypted" in error_str:
                return "", f"Document is password-protected: {exc}"
            return "", f"Docling extraction failed: {exc}"

    @staticmethod
    def _try_markitdown(path: Path) -> tuple[str, str]:
        """Extract text via MarkItDown.

        Returns:
            ``(text, error_message)``
        """
        try:
            from markitdown import MarkItDown  # type: ignore[import-untyped]

            md = MarkItDown()
            result = md.convert(str(path))
            return result.text_content or "", ""
        except Exception as exc:  # noqa: BLE001
            # MarkItDown raises different exceptions depending on the problem
            error_str = str(exc).lower()
            if "password" in error_str or "encrypted" in error_str:
                return "", f"Document is password-protected: {exc}"
            return "", f"MarkItDown extraction failed: {exc}"

    @staticmethod
    def _try_pymupdf(path: Path) -> tuple[str, str]:
        """Extract text from a PDF via PyMuPDF.

        Supports both the legacy ``fitz`` import (PyMuPDF < 2.0) and the
        new ``pymupdf`` import (PyMuPDF 2.0+).

        Returns:
            ``(text, error_message)``
        """
        try:
            try:
                import pymupdf as _pdf_lib  # type: ignore[import-untyped]
            except ImportError:
                import fitz as _pdf_lib  # type: ignore[import-untyped]

            doc = _pdf_lib.open(str(path))

            # PyMuPDF 2.0 uses needs_pass; older versions use is_encrypted.
            is_locked = getattr(doc, "needs_pass", False) or getattr(doc, "is_encrypted", False)
            if is_locked:
                doc.close()
                return "", "PDF is password-protected or encrypted."

            pages: list[str] = []
            for page in doc:
                pages.append(page.get_text())
            doc.close()

            return "\n".join(pages), ""

        except Exception as exc:  # noqa: BLE001
            error_str = str(exc).lower()
            if "password" in error_str or "encrypt" in error_str:
                return "", f"PDF is password-protected: {exc}"
            return "", f"PyMuPDF extraction failed: {exc}"
