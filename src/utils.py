"""
src/utils.py
============
Shared utility helpers for the Resume-to-Excel Automation System.

Phase 1: file hashing, text cleaning, file-signature detection.
"""

from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# File-type magic-byte signatures
# ---------------------------------------------------------------------------
# Mapping of supported MIME types to their leading byte sequences.
# We check actual file content, not the extension, to detect spoofed files.

_MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    "application/pdf": [b"%PDF"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
        b"PK\x03\x04"  # ZIP-based format (DOCX is a zip archive)
    ],
}

# Extension → MIME type mapping for the supported formats.
SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    "application/pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
}

# Maximum accepted file size (10 MB).
MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024


def compute_sha256(file_path: str | Path) -> str:
    """Return the SHA-256 hex digest of a file's contents.

    Args:
        file_path: Absolute or relative path to the file.

    Returns:
        Lowercase hex string (64 characters).

    Raises:
        OSError: If the file cannot be read.
    """
    sha = hashlib.sha256()
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def detect_file_type(file_path: str | Path) -> str | None:
    """Detect the MIME type of a file by reading its leading bytes.

    Falls back to ``None`` when the signature is not recognised.

    Args:
        file_path: Path to the file.

    Returns:
        MIME type string, or ``None`` if the file type is unsupported or
        the file is too short to contain a valid signature.
    """
    try:
        with open(file_path, "rb") as fh:
            header = fh.read(8)
    except OSError:
        return None

    for mime_type, signatures in _MAGIC_SIGNATURES.items():
        for sig in signatures:
            if header.startswith(sig):
                return mime_type

    return None


def is_supported_file(file_path: str | Path) -> bool:
    """Return True when the file has a supported extension *and* a matching
    file-type signature.

    A file that claims to be a PDF via its extension but whose bytes do not
    start with ``%PDF`` will return False.

    Args:
        file_path: Path to the file.

    Returns:
        ``True`` if the file is a supported, readable format.
    """
    path = Path(file_path)
    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        return False

    detected = detect_file_type(path)
    expected = SUPPORTED_EXTENSIONS.get(extension)
    return detected == expected


def clean_text(raw: str) -> str:
    """Normalise whitespace in extracted resume text.

    Rules:
    - Collapse runs of spaces and tabs within a line to a single space.
    - Preserve paragraph breaks (blank lines between non-empty lines).
    - Strip leading and trailing whitespace from each line.
    - Remove lines that are entirely whitespace.
    - Return a single trailing newline.

    This avoids destroying heading / bullet structure while removing the
    clutter that document converters often introduce.

    Args:
        raw: Raw text as returned by a document converter.

    Returns:
        Cleaned text string.
    """
    if not raw:
        return ""

    raw = html.unescape(raw)
    raw = raw.replace("\xa0", " ")

    lines = raw.splitlines()

    cleaned_lines: list[str] = []
    for line in lines:
        # Collapse internal horizontal whitespace
        line = re.sub(r"[ \t]+", " ", line).strip()
        cleaned_lines.append(line)

    # Merge consecutive blank lines into a single blank line
    result_lines: list[str] = []
    previous_blank = False
    for line in cleaned_lines:
        is_blank = line == ""
        if is_blank and previous_blank:
            continue  # skip extra blank lines
        result_lines.append(line)
        previous_blank = is_blank

    # Strip leading/trailing blank lines
    while result_lines and result_lines[0] == "":
        result_lines.pop(0)
    while result_lines and result_lines[-1] == "":
        result_lines.pop()

    return "\n".join(result_lines) + "\n" if result_lines else ""


def is_text_empty(text: str, min_chars: int = 50) -> bool:
    """Return True when the extracted text is too short to be a real resume.

    Args:
        text: The extracted (and cleaned) text.
        min_chars: Minimum number of non-whitespace characters required.

    Returns:
        ``True`` if the text is effectively empty.
    """
    return len(text.strip()) < min_chars
