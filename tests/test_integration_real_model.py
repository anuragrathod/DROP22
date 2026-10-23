"""
tests/test_integration_real_model.py
=====================================
Integration tests that use the real local Ollama model.

These tests are marked with @pytest.mark.integration and are SKIPPED
automatically in normal test runs.  Run them explicitly when Ollama is
installed and the model is available:

    # Start Ollama first
    ollama serve &

    # Pull the model if not already downloaded
    ollama pull qwen3:4b

    # Run only integration tests
    pytest tests/test_integration_real_model.py -v -m integration

    # Or run everything including integration tests
    pytest tests/ -v -m "not skip"

WARNING: These tests make real HTTP calls to Ollama and will fail if:
  - Ollama is not running
  - The configured model is not pulled
  - The machine has insufficient RAM/VRAM
"""

from __future__ import annotations

import pytest

from src.ai_extractor import AIConfig, AIExtractor, check_model_available, check_ollama_running
from src.document_reader import DocumentReader, ProcessingStatus
from src.resume_parser import ResumeParser
from src.validator import validate_candidate

# ---------------------------------------------------------------------------
# Skip marker — applied to every test in this module
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.integration


def _ollama_available() -> bool:
    """Return True if Ollama is running AND qwen3:4b is available."""
    running, _ = check_ollama_running()
    if not running:
        return False
    available, _ = check_model_available("qwen3:4b")
    return available


SKIP_REASON = (
    "Ollama is not running or qwen3:4b is not available. "
    "Run: ollama serve && ollama pull qwen3:4b"
)

# ---------------------------------------------------------------------------
# Synthetic resume texts for integration testing
# ---------------------------------------------------------------------------

INTEGRATION_RESUME_1 = """
Alice Johnson
alice.johnson@techcorp.com | +1 (650) 555-0101 | Palo Alto, CA
https://linkedin.com/in/alicejohnson | https://github.com/alicejohnson

SUMMARY
Senior Software Engineer with 6 years of experience in distributed systems.

EDUCATION
M.Sc. Computer Science — Stanford University, 2018
B.Sc. Computer Engineering — UC Berkeley, 2016

TECHNICAL SKILLS
Python, Go, Rust, Java, JavaScript

TOOLS & PLATFORMS
Kubernetes, Docker, AWS, GCP, Terraform, Kafka

EXPERIENCE
Senior Software Engineer — DistribCo (Mar 2020 – Present)
  • Led migration from monolith to microservices, reducing latency by 40%.
  • Managed a team of 5 engineers.

Software Engineer — StartupX (Jun 2018 – Feb 2020)
  • Built REST APIs serving 500K daily users.

PROJECTS
OpenTrace — Distributed tracing library (Go, gRPC, Prometheus)
DataPipe — Real-time ETL framework (Python, Kafka, Postgres)

CERTIFICATIONS
Google Cloud Professional Data Engineer (2022)
AWS Certified Solutions Architect Associate (2021)
"""

INTEGRATION_RESUME_2 = """
Ravi Kumar
ravi.kumar@example.in | +91-99887-76655 | Bengaluru, India
linkedin.com/in/ravikumar99

EDUCATION
B.Tech Computer Science — IIT Madras, 2020

SKILLS
Java, Spring Boot, Python, MySQL, Redis, Docker

EXPERIENCE
Software Developer — Infosys Ltd (Aug 2020 – Present)
  • Developed REST APIs for banking clients.
  • Improved query performance by 30%.

PROJECTS
PayGateway — Payment processing microservice (Java, Spring Boot, MySQL)

CERTIFICATIONS
Oracle Certified Professional Java SE 11
"""


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _ollama_available(), reason=SKIP_REASON)
class TestRealModelExtraction:
    """These tests call the real Ollama model — expect ~5–30s per test."""

    def test_model_is_reachable(self):
        extractor = AIExtractor()
        ok, msg = extractor.check_availability()
        assert ok, msg

    def test_extracts_name_from_resume(self):
        extractor = AIExtractor(AIConfig(model="qwen3:4b", temperature=0.0))
        result = extractor.extract(INTEGRATION_RESUME_1, "alice.txt")
        assert result.success, f"Extraction failed: {result.error}"
        assert result.data.get("full_name") is not None
        assert "Alice" in result.data["full_name"]

    def test_extracts_multiple_education_records(self):
        extractor = AIExtractor(AIConfig(model="qwen3:4b", temperature=0.0))
        result = extractor.extract(INTEGRATION_RESUME_1, "alice.txt")
        assert result.success, result.error
        education = result.data.get("education", [])
        assert len(education) >= 2

    def test_extracts_multiple_work_experience(self):
        extractor = AIExtractor(AIConfig(model="qwen3:4b", temperature=0.0))
        result = extractor.extract(INTEGRATION_RESUME_1, "alice.txt")
        assert result.success, result.error
        exp = result.data.get("work_experience", [])
        assert len(exp) >= 2

    def test_extracts_certifications(self):
        extractor = AIExtractor(AIConfig(model="qwen3:4b", temperature=0.0))
        result = extractor.extract(INTEGRATION_RESUME_1, "alice.txt")
        assert result.success, result.error
        certs = result.data.get("certifications", [])
        assert len(certs) >= 1

    def test_full_pipeline_with_real_model(self):
        """End-to-end: text → parser → validated candidate."""
        from src.document_reader import DocumentResult, ProcessingStatus

        doc = DocumentResult(
            filename="alice.txt",
            status=ProcessingStatus.SUCCESS,
            text=INTEGRATION_RESUME_1,
            file_hash="test_hash",
        )

        extractor = AIExtractor(AIConfig(model="qwen3:4b", temperature=0.0))
        parser = ResumeParser(ai_extractor=extractor)
        record = parser.parse(doc)
        record = validate_candidate(record)

        # Rule-based fields should always be present
        assert record.email == "alice.johnson@techcorp.com"
        assert record.phone is not None

        # AI-extracted fields
        assert record.full_name is not None
        assert record.metadata.extraction_method == "rules+ai"
        assert record.metadata.processing_status in ("success", "review_required")

    def test_indian_phone_extracted_by_rules(self):
        """Indian phone with country code should be extracted by rules."""
        from src.resume_parser import extract_phone
        result = extract_phone(INTEGRATION_RESUME_2)
        assert result is not None
        assert "+91" in result or "99887" in result.replace("-", "").replace(" ", "")

    def test_model_returns_valid_json(self):
        """Raw model output should be parseable JSON."""
        extractor = AIExtractor(AIConfig(model="qwen3:4b", temperature=0.0))
        result = extractor.extract(INTEGRATION_RESUME_2, "ravi.txt")
        assert result.success, result.error
        assert isinstance(result.data, dict)
        # Mandatory top-level keys must be present
        for key in ("full_name", "education", "work_experience", "technical_skills"):
            assert key in result.data, f"Key '{key}' missing from model output"

    def test_model_does_not_invent_email(self):
        """Model should not invent an email when none appears in resume."""
        no_email_resume = """
John Smith
New York, NY

EDUCATION
B.Sc. Mathematics — NYU, 2019

SKILLS
R, Python, MATLAB
"""
        from src.resume_parser import extract_email
        assert extract_email(no_email_resume) is None

        extractor = AIExtractor(AIConfig(model="qwen3:4b", temperature=0.0))
        result = extractor.extract(no_email_resume, "noemail.txt")
        if result.success:
            # Model must not invent an email
            assert result.data.get("email") in (None, "")

    def test_duration_is_recorded(self):
        extractor = AIExtractor(AIConfig(model="qwen3:4b", temperature=0.0))
        result = extractor.extract(INTEGRATION_RESUME_2, "ravi.txt")
        assert result.duration_s > 0
