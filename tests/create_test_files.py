"""
tests/create_test_files.py
==========================
Generates a set of synthetic PDF and DOCX resume files for Phase 1 testing.

Run from the project root:

    python tests/create_test_files.py

Files are written to the ``sample_resumes/`` directory.  These are invented
documents — they do not represent real people.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

# Project root is one level up from this file.
PROJECT_ROOT = Path(__file__).parent.parent
SAMPLE_DIR = PROJECT_ROOT / "sample_resumes"

# ---------------------------------------------------------------------------
# Synthetic resume content
# ---------------------------------------------------------------------------

RESUMES: list[dict] = [
    {
        "filename": "alice_chen_resume.pdf",
        "format": "pdf",
        "text": (
            "Alice Chen\n"
            "alice.chen@example.com | +1 (555) 234-5678 | San Francisco, CA\n"
            "linkedin.com/in/alicechen | github.com/alicechen\n\n"
            "EDUCATION\n"
            "B.Sc. Computer Science — Stanford University, 2022\n\n"
            "SKILLS\n"
            "Python, JavaScript, React, PostgreSQL, Docker, AWS\n\n"
            "EXPERIENCE\n"
            "Software Engineer — TechCorp Inc.  (Jan 2023 – Present)\n"
            "  • Designed and maintained REST APIs serving 2M requests/day.\n"
            "  • Reduced latency by 40% through query optimisation.\n\n"
            "PROJECTS\n"
            "ResumeParser — Open-source tool for extracting structured data\n"
            "from PDF resumes using Python and spaCy.\n\n"
            "CERTIFICATIONS\n"
            "AWS Certified Solutions Architect — Associate (2023)\n"
        ),
    },
    {
        "filename": "bob_patel_resume.docx",
        "format": "docx",
        "text": (
            "Bob Patel\n"
            "bob.patel@example.com | +44 7700 900123 | London, UK\n\n"
            "EDUCATION\n"
            "M.Sc. Data Science — University of Edinburgh, 2021\n"
            "B.Eng. Electronics — IIT Bombay, 2019\n\n"
            "SKILLS\n"
            "Python, R, TensorFlow, PyTorch, SQL, Tableau, Git\n\n"
            "EXPERIENCE\n"
            "Data Scientist — Analytics Ltd.  (Sep 2021 – Present)\n"
            "  • Built predictive churn model (AUC 0.91) for 500k users.\n"
            "  • Automated weekly reporting pipeline, saving 8 hours/week.\n\n"
            "PROJECTS\n"
            "SentimentBot — Twitter sentiment analyser using BERT fine-tuning.\n\n"
            "CERTIFICATIONS\n"
            "Google Professional Data Engineer (2022)\n"
        ),
    },
    {
        "filename": "carol_smith_resume.docx",
        "format": "docx",
        "text": (
            "Carol Smith\n"
            "carol.smith@example.com | +1 (416) 555-9012 | Toronto, Canada\n\n"
            "EDUCATION\n"
            "B.B.A. Information Systems — University of Toronto, 2020\n\n"
            "SKILLS\n"
            "Java, Spring Boot, MySQL, Kubernetes, Jira, Agile\n\n"
            "EXPERIENCE\n"
            "Backend Engineer — FinTech Solutions  (Jul 2020 – Dec 2022)\n"
            "  • Delivered payment microservices processing $50M/month.\n"
            "  • Mentored two junior developers.\n\n"
            "Backend Engineer — CloudBase Inc.  (Jan 2023 – Present)\n"
            "  • Migrated monolith to Kubernetes; improved deploy frequency 3×.\n"
        ),
    },
]


# ---------------------------------------------------------------------------
# Minimal PDF writer (no external dependencies)
# ---------------------------------------------------------------------------

def _pdf_bytes(text: str) -> bytes:
    """Create a minimal but valid single-page PDF containing ``text``.

    This avoids a dependency on reportlab or fpdf at test-file-creation time.
    The PDF is intentionally simple; it starts with ``%PDF-1.4`` so that the
    magic-byte check in utils.py passes.
    """
    # Escape PDF special characters
    safe = (
        text.replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
    )

    # Split into lines; PDF text operators work per line
    lines = safe.split("\n")
    tf_lines = "\n".join(f"({ln}) Tj T*" for ln in lines)

    content_stream = (
        f"BT\n"
        f"/F1 11 Tf\n"
        f"50 750 Td\n"
        f"14 TL\n"  # leading
        f"{tf_lines}\n"
        f"ET"
    )
    stream_bytes = content_stream.encode("latin-1", errors="replace")
    stream_length = len(stream_bytes)

    objects: list[bytes] = []
    offsets: list[int] = []

    header = b"%PDF-1.4\n"

    # Object 1: Catalog
    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    # Object 2: Pages
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    # Object 3: Page
    obj3 = (
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R\n"
        b"   /MediaBox [0 0 612 792]\n"
        b"   /Contents 4 0 R\n"
        b"   /Resources << /Font << /F1 5 0 R >> >> >>\n"
        b"endobj\n"
    )
    # Object 4: Content stream
    obj4 = (
        b"4 0 obj\n"
        b"<< /Length " + str(stream_length).encode() + b" >>\n"
        b"stream\n"
        + stream_bytes
        + b"\nendstream\nendobj\n"
    )
    # Object 5: Font
    obj5 = (
        b"5 0 obj\n"
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n"
        b"endobj\n"
    )

    pdf = bytearray(header)
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


def _docx_bytes(text: str) -> bytes:
    """Create a minimal DOCX (Open XML) file containing ``text``.

    Uses Python's standard :mod:`zipfile` module to guarantee a valid ZIP
    archive.  A DOCX is simply a ZIP containing a small set of XML files.
    """
    # Escape XML special characters
    safe = (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )

    # Build paragraph XML for each line
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
        '<w:document '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
        "<w:body>\n"
        + para_xml
        + "</w:body>\n</w:document>"
    )

    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        '  <Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>\n'
        "</Relationships>"
    )

    word_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
    )

    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        '  <Default Extension="xml" ContentType="application/xml"/>\n'
        '  <Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>\n'
        "</Types>"
    )

    # Build the ZIP archive using the standard library (correct deflate format)
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", rels_xml)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/_rels/document.xml.rels", word_rels_xml)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def create_test_files() -> None:
    """Generate all synthetic resume files in ``sample_resumes/``."""
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    for spec in RESUMES:
        dest = SAMPLE_DIR / spec["filename"]
        fmt = spec["format"]
        text = spec["text"]

        if fmt == "pdf":
            data = _pdf_bytes(text)
        else:
            data = _docx_bytes(text)

        dest.write_bytes(data)
        print(f"  Created: {dest.name}  ({len(data):,} bytes)")

    print(f"\n  {len(RESUMES)} synthetic resume(s) written to {SAMPLE_DIR}/")


if __name__ == "__main__":
    print("Generating synthetic test resumes …\n")
    create_test_files()
