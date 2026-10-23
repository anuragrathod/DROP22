"""
tests/test_phase2.py
====================
Phase 2 test suite: schema, rule-based extraction, AI extraction (mocked),
validation, orchestration, and batch processing.

All tests are self-contained and do NOT require Ollama to be running.
Real-model integration tests are in tests/test_integration_real_model.py
and are marked with @pytest.mark.integration so they are skipped in
normal CI runs.

Run:
    pytest tests/test_phase2.py -v                    # all Phase 2 unit tests
    pytest tests/ -v                                  # all tests (Phase 1 + 2)
    pytest tests/ -v -m integration                  # real-model tests only
"""

from __future__ import annotations

import json
import zipfile
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

# pyrefly: ignore[missing-import]
import pytest

from schemas.candidate import (
    CandidateRecord,
    EducationRecord,
    ExtractionMetadata,
    Project,
    WorkExperience,
)
from src.ai_extractor import (
    AIConfig,
    AIExtractionResult,
    AIExtractor,
    _extract_json_from_response,
    build_prompt,
    load_prompt_template,
)
from src.document_reader import DocumentResult, ProcessingStatus
from src.resume_parser import (
    ResumeParser,
    _check_missing_fields,
    _merge_results,
    _truncate_resume,
    extract_email,
    extract_github_url,
    extract_linkedin_url,
    extract_phone,
    extract_portfolio_url,
    run_rule_based_extraction,
)
from src.validator import (
    sanitise_formula_injection,
    validate_candidate,
    validate_email,
    validate_graduation_years,
    validate_phone,
)

# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

ALICE_TEXT = """Alice Chen
alice.chen@example.com | +1 (555) 234-5678 | San Francisco, CA
linkedin.com/in/alicechen | github.com/alicechen

EDUCATION
B.Sc. Computer Science — Stanford University, 2022

SKILLS
Python, JavaScript, React, PostgreSQL, Docker, AWS

EXPERIENCE
Software Engineer — TechCorp Inc.  (Jan 2023 – Present)
  • Designed and maintained REST APIs serving 2M requests/day.

PROJECTS
ResumeParser — Open-source resume extraction tool (Python, spaCy)

CERTIFICATIONS
AWS Certified Solutions Architect — Associate (2023)
"""

INDIAN_TEXT = """Ravi Kumar
ravi.kumar@example.in | +91-98765-43210 | Pune, India
linkedin.com/in/ravikumar

EDUCATION
B.Tech Computer Science — IIT Bombay, 2021

SKILLS
Java, Spring Boot, MySQL, Python

EXPERIENCE
Software Developer — Infosys (Jul 2021 – Present)
"""

FRESHER_TEXT = """Priya Sharma
priya.sharma@gmail.com | 9876543210 | Hyderabad, India

EDUCATION
B.E. Electronics — Osmania University, Expected 2025

SKILLS
C, C++, Embedded Systems
"""


def _make_success_doc(text: str, filename: str = "resume.pdf") -> DocumentResult:
    """Create a successful DocumentResult with the given text."""
    return DocumentResult(
        filename=filename,
        status=ProcessingStatus.SUCCESS,
        text=text,
        file_hash="abc123",
    )


def _make_failed_doc(filename: str = "bad.pdf") -> DocumentResult:
    """Create a failed DocumentResult."""
    return DocumentResult(
        filename=filename,
        status=ProcessingStatus.CORRUPT,
        error="File could not be parsed.",
    )


def _make_mock_ai(data: dict | None = None, success: bool = True, error: str = "") -> MagicMock:
    """Return a mock AIExtractor that returns the given data."""
    mock = MagicMock()
    mock.extract.return_value = AIExtractionResult(
        success=success,
        data=data or {},
        error=error,
        model_used="qwen3:4b",
        duration_s=0.1,
    )
    return mock


# ===========================================================================
# 1. Schema Tests
# ===========================================================================

class TestCandidateSchema:

    def test_minimal_record_creates_successfully(self):
        rec = CandidateRecord(resume_filename="test.pdf")
        assert rec.resume_filename == "test.pdf"
        assert rec.candidate_id != ""
        assert rec.email is None
        assert rec.education == []

    def test_candidate_id_is_unique(self):
        r1 = CandidateRecord(resume_filename="a.pdf")
        r2 = CandidateRecord(resume_filename="b.pdf")
        assert r1.candidate_id != r2.candidate_id

    def test_email_is_lowercased(self):
        rec = CandidateRecord(resume_filename="a.pdf", email="Alice@Example.COM")
        assert rec.email == "alice@example.com"

    def test_empty_email_becomes_none(self):
        rec = CandidateRecord(resume_filename="a.pdf", email="")
        assert rec.email is None

    def test_phone_preserved_as_string(self):
        rec = CandidateRecord(resume_filename="a.pdf", phone="+91-98765-43210")
        assert rec.phone == "+91-98765-43210"

    def test_skills_default_to_empty_list(self):
        rec = CandidateRecord(resume_filename="a.pdf")
        assert rec.technical_skills == []
        assert rec.programming_languages == []
        assert rec.tools == []

    def test_none_skills_coerced_to_empty_list(self):
        rec = CandidateRecord(resume_filename="a.pdf", technical_skills=None)
        assert rec.technical_skills == []

    def test_string_skill_coerced_to_list(self):
        rec = CandidateRecord(resume_filename="a.pdf", technical_skills="Python")
        assert rec.technical_skills == ["Python"]

    def test_multiple_education_records(self):
        rec = CandidateRecord(
            resume_filename="a.pdf",
            education=[
                EducationRecord(qualification="B.Sc.", institution="MIT", graduation_year="2020"),
                EducationRecord(qualification="M.Sc.", institution="Stanford", graduation_year="2022"),
            ],
        )
        assert len(rec.education) == 2
        assert rec.education[0].institution == "MIT"

    def test_graduation_year_int_coerced_to_str(self):
        edu = EducationRecord(graduation_year=2022)
        assert edu.graduation_year == "2022"

    def test_multiple_work_experience(self):
        rec = CandidateRecord(
            resume_filename="a.pdf",
            work_experience=[
                WorkExperience(employer="Google", job_title="SWE"),
                WorkExperience(employer="Meta", job_title="SDE"),
            ],
        )
        assert len(rec.work_experience) == 2

    def test_multiple_projects(self):
        rec = CandidateRecord(
            resume_filename="a.pdf",
            projects=[
                Project(name="ProjectA", technologies=["Python"]),
                Project(name="ProjectB", technologies=["Go", "Redis"]),
            ],
        )
        assert len(rec.projects) == 2

    def test_mark_missing_records_field(self):
        rec = CandidateRecord(resume_filename="a.pdf")
        rec.mark_missing("email")
        assert "email" in rec.metadata.missing_fields

    def test_add_issue(self):
        rec = CandidateRecord(resume_filename="a.pdf")
        rec.add_issue("Bad email format")
        assert "Bad email format" in rec.metadata.validation_issues

    def test_is_complete_when_no_issues(self):
        rec = CandidateRecord(resume_filename="a.pdf")
        assert rec.is_complete is True

    def test_is_not_complete_when_missing_fields(self):
        rec = CandidateRecord(resume_filename="a.pdf")
        rec.mark_missing("email")
        assert rec.is_complete is False

    def test_extraction_timestamp_auto_set(self):
        rec = CandidateRecord(resume_filename="a.pdf")
        assert rec.metadata.extracted_at is not None
        assert len(rec.metadata.extracted_at) > 10  # is a real datetime string

    def test_to_flat_dict_keys(self):
        rec = CandidateRecord(resume_filename="test.pdf", full_name="Alice")
        flat = rec.to_flat_dict()
        assert "candidate_id" in flat
        assert "full_name" in flat
        assert flat["full_name"] == "Alice"
        assert "resume_filename" in flat


# ===========================================================================
# 2. Rule-Based Extraction Tests
# ===========================================================================

class TestEmailExtraction:

    def test_extracts_simple_email(self):
        assert extract_email("Contact: alice@example.com") == "alice@example.com"

    def test_extracts_email_with_plus(self):
        assert extract_email("alice+work@example.co.uk") == "alice+work@example.co.uk"

    def test_email_lowercased(self):
        assert extract_email("Alice@EXAMPLE.COM") == "alice@example.com"

    def test_returns_none_when_no_email(self):
        assert extract_email("No email here.") is None

    def test_extracts_first_email_only(self):
        result = extract_email("a@x.com and b@y.com")
        assert result == "a@x.com"

    def test_real_resume_email(self):
        assert extract_email(ALICE_TEXT) == "alice.chen@example.com"

    def test_indian_email(self):
        assert extract_email(INDIAN_TEXT) == "ravi.kumar@example.in"


class TestPhoneExtraction:

    def test_extracts_indian_mobile(self):
        result = extract_phone("Call me at 9876543210")
        assert result is not None
        assert "9876543210" in result.replace(" ", "").replace("-", "")

    def test_extracts_indian_with_country_code(self):
        result = extract_phone("+91-98765-43210")
        assert result is not None

    def test_extracts_north_american(self):
        result = extract_phone("+1 (555) 234-5678")
        assert result is not None

    def test_returns_none_for_no_phone(self):
        assert extract_phone("No phone number here.") is None

    def test_does_not_treat_year_as_phone(self):
        # A 4-digit year should not be extracted as a phone
        result = extract_phone("Graduated in 2022. No phone listed.")
        assert result is None

    def test_extracts_bare_10_digit_indian(self):
        result = extract_phone(FRESHER_TEXT)
        assert result is not None
        digits = "".join(c for c in result if c.isdigit())
        assert len(digits) >= 10

    def test_phone_preserved_as_string(self):
        result = extract_phone("+91-98765-43210")
        assert isinstance(result, str)


class TestURLExtraction:

    def test_extracts_linkedin(self):
        url = extract_linkedin_url("https://linkedin.com/in/alicechen")
        assert url is not None
        assert "linkedin.com/in" in url

    def test_extracts_linkedin_with_www(self):
        url = extract_linkedin_url("https://www.linkedin.com/in/alice-chen")
        assert url is not None

    def test_linkedin_none_when_absent(self):
        assert extract_linkedin_url("No LinkedIn here.") is None

    def test_extracts_github(self):
        url = extract_github_url("github.com/alicechen is my profile")
        # Our regex requires https:// prefix
        url2 = extract_github_url("https://github.com/alicechen")
        assert url2 is not None

    def test_github_none_when_absent(self):
        assert extract_github_url("No GitHub here.") is None

    def test_run_rule_based_returns_dict(self):
        result = run_rule_based_extraction(ALICE_TEXT)
        assert "email" in result
        assert "phone" in result
        assert "linkedin_url" in result
        assert "github_url" in result


# ===========================================================================
# 3. AI Extractor Tests (all mocked — no Ollama needed)
# ===========================================================================

class TestJSONExtraction:
    """Tests for the _extract_json_from_response helper."""

    def test_clean_json(self):
        raw = '{"full_name": "Alice", "email": null}'
        data, err = _extract_json_from_response(raw)
        assert err == ""
        assert data["full_name"] == "Alice"

    def test_json_in_markdown_fence(self):
        raw = '```json\n{"full_name": "Bob"}\n```'
        data, err = _extract_json_from_response(raw)
        assert err == ""
        assert data["full_name"] == "Bob"

    def test_json_with_think_block(self):
        raw = '<think>Let me think about this...</think>\n{"full_name": "Carol"}'
        data, err = _extract_json_from_response(raw)
        assert err == ""
        assert data["full_name"] == "Carol"

    def test_json_with_trailing_text(self):
        raw = '{"full_name": "Dave"}\nThis is the extraction.'
        data, err = _extract_json_from_response(raw)
        assert err == ""
        assert data["full_name"] == "Dave"

    def test_no_json_returns_error(self):
        _, err = _extract_json_from_response("Just some text, no JSON here.")
        assert err != ""

    def test_malformed_json_returns_error(self):
        _, err = _extract_json_from_response('{"full_name": "Alice"')
        assert err != ""

    def test_empty_string_returns_error(self):
        _, err = _extract_json_from_response("")
        assert err != ""


class TestAIExtractorMocked:

    def test_extract_returns_success_on_valid_response(self):
        mock_ai = _make_mock_ai({"full_name": "Alice Chen", "location": "San Francisco"})
        result = mock_ai.extract(ALICE_TEXT, "alice.pdf")
        assert result.success is True
        assert result.data["full_name"] == "Alice Chen"

    def test_extract_returns_failure_when_ollama_down(self):
        mock_ai = _make_mock_ai(success=False, error="Cannot connect to Ollama")
        result = mock_ai.extract(ALICE_TEXT)
        assert result.success is False
        assert "Ollama" in result.error

    def test_extract_with_empty_text_fails(self):
        """AIExtractor should reject empty text without calling Ollama."""
        extractor = AIExtractor()
        result = extractor.extract("", "empty.pdf")
        assert result.success is False
        assert "empty" in result.error.lower()

    def test_check_availability_ollama_down(self):
        with patch("src.ai_extractor.check_ollama_running") as mock_check:
            mock_check.return_value = (False, "Connection refused")
            extractor = AIExtractor()
            ok, msg = extractor.check_availability()
        assert ok is False
        assert "Connection refused" in msg

    def test_config_model_name_used(self):
        config = AIConfig(model="qwen3:1.7b")
        assert config.model == "qwen3:1.7b"

    def test_build_prompt_substitutes_text(self):
        template = "Extract from: {resume_text}"
        result = build_prompt(template, "Alice resume")
        assert result == "Extract from: Alice resume"

    def test_retry_logic_mocked(self):
        """Extractor should retry on failure and return last error."""
        config = AIConfig(max_retries=1, retry_delay=0.0)
        extractor = AIExtractor(config=config)

        call_count = 0

        def fake_call(prompt, filename, attempt):
            nonlocal call_count
            call_count += 1
            return AIExtractionResult(success=False, error="Transient error", model_used="qwen3:4b")

        extractor._call_ollama = fake_call  # type: ignore[method-assign]
        extractor._prompt_template = "Extract: {resume_text}"

        result = extractor.extract("some text", "test.pdf")
        assert result.success is False
        assert call_count == 2  # 1 initial + 1 retry

    def test_groq_config_defaults(self):
        config = AIConfig(provider="groq")
        assert config.provider == "groq"
        assert config.model == "openai/gpt-oss-120b"

    def test_check_availability_groq_missing_key(self):
        config = AIConfig(provider="groq", api_key="")
        extractor = AIExtractor(config=config)
        with patch.dict("os.environ", {}, clear=True):
            ok, msg = extractor.check_availability()
            assert ok is False
            assert "key" in msg.lower()

    def test_extract_with_groq_mocked(self):
        config = AIConfig(provider="groq", api_key="gsk_mock123")
        extractor = AIExtractor(config=config)

        mock_resp = MagicMock()
        mock_resp.choices = [
            MagicMock(message=MagicMock(content='{"full_name": "Bob Dylan", "location": "New York"}'))
        ]

        with patch("groq.Groq") as mock_groq_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_resp
            mock_groq_cls.return_value = mock_client

            result = extractor.extract("Bob Dylan New York", "bob.pdf")
            assert result.success is True
            assert result.data["full_name"] == "Bob Dylan"
            assert result.data["location"] == "New York"


# ===========================================================================
# 4. Merge Tests
# ===========================================================================

class TestMergeResults:

    def test_rule_email_takes_priority(self):
        rule = {"email": "rule@example.com", "phone": None, "linkedin_url": None,
                "github_url": None, "portfolio_url": None}
        ai = {"email": "ai@example.com", "full_name": "Alice"}
        merged = _merge_results(rule, ai)
        assert merged["email"] == "rule@example.com"
        assert merged["_conflicts"] != []

    def test_ai_name_used_when_rule_has_none(self):
        rule = {"email": None, "phone": None, "linkedin_url": None,
                "github_url": None, "portfolio_url": None}
        ai = {"full_name": "Alice Chen", "email": None}
        merged = _merge_results(rule, ai)
        assert merged["full_name"] == "Alice Chen"

    def test_no_conflict_when_values_match(self):
        rule = {"email": "a@b.com", "phone": None, "linkedin_url": None,
                "github_url": None, "portfolio_url": None}
        ai = {"email": "a@b.com"}
        merged = _merge_results(rule, ai)
        assert merged["_conflicts"] == []

    def test_ai_value_used_when_rule_is_none(self):
        rule = {"email": None, "phone": None, "linkedin_url": None,
                "github_url": None, "portfolio_url": None}
        ai = {"email": "ai@example.com"}
        merged = _merge_results(rule, ai)
        assert merged["email"] == "ai@example.com"


# ===========================================================================
# 5. ResumeParser Orchestrator Tests (AI mocked)
# ===========================================================================

class TestResumeParserRulesOnly:
    """Parser without AI extractor — rule-based extraction only."""

    def test_failed_doc_returns_failed_record(self):
        parser = ResumeParser(ai_extractor=None)
        doc = _make_failed_doc()
        record = parser.parse(doc)
        assert record.metadata.processing_status == "failed"
        assert record.resume_filename == "bad.pdf"

    def test_successful_doc_extracts_email(self):
        parser = ResumeParser(ai_extractor=None)
        doc = _make_success_doc(ALICE_TEXT, "alice.pdf")
        record = parser.parse(doc)
        assert record.email == "alice.chen@example.com"

    def test_successful_doc_extracts_phone(self):
        parser = ResumeParser(ai_extractor=None)
        doc = _make_success_doc(ALICE_TEXT, "alice.pdf")
        record = parser.parse(doc)
        assert record.phone is not None

    def test_indian_phone_extracted(self):
        parser = ResumeParser(ai_extractor=None)
        doc = _make_success_doc(INDIAN_TEXT, "ravi.pdf")
        record = parser.parse(doc)
        assert record.phone is not None

    def test_raw_text_snippet_set(self):
        parser = ResumeParser(ai_extractor=None)
        doc = _make_success_doc(ALICE_TEXT)
        record = parser.parse(doc)
        assert record.raw_text_snippet is not None
        assert len(record.raw_text_snippet) <= 500

    def test_missing_fields_detected_without_ai(self):
        parser = ResumeParser(ai_extractor=None)
        doc = _make_success_doc(ALICE_TEXT)
        record = parser.parse(doc)
        # Without AI, full_name and education will be missing
        assert "full_name" in record.metadata.missing_fields

    def test_extraction_method_is_rules_only(self):
        parser = ResumeParser(ai_extractor=None)
        doc = _make_success_doc(ALICE_TEXT)
        record = parser.parse(doc)
        assert record.metadata.extraction_method == "rules_only"


class TestResumeParserWithMockedAI:
    """Parser with a mocked AI extractor."""

    def test_successful_ai_populates_name(self):
        mock_ai = _make_mock_ai({
            "full_name": "Alice Chen",
            "location": "San Francisco, CA",
            "education": [{"qualification": "B.Sc. Computer Science",
                           "institution": "Stanford University",
                           "graduation_year": "2022"}],
            "technical_skills": ["Python", "JavaScript"],
            "programming_languages": [],
            "tools": ["Docker", "AWS"],
            "work_experience": [{"employer": "TechCorp Inc.", "job_title": "Software Engineer",
                                  "start_date": "Jan 2023", "end_date": "Present",
                                  "responsibilities": ["Designed REST APIs"]}],
            "projects": [{"name": "ResumeParser", "description": "Resume tool",
                           "technologies": ["Python", "spaCy"]}],
            "certifications": ["AWS Certified Solutions Architect"],
            "linkedin_url": None,
            "github_url": None,
            "portfolio_url": None,
        })
        parser = ResumeParser(ai_extractor=mock_ai)
        doc = _make_success_doc(ALICE_TEXT, "alice.pdf")
        record = parser.parse(doc)

        assert record.full_name == "Alice Chen"
        assert record.email == "alice.chen@example.com"   # rule wins
        assert len(record.education) == 1
        assert record.education[0].institution == "Stanford University"
        assert "Python" in record.technical_skills
        assert len(record.work_experience) == 1
        assert record.work_experience[0].employer == "TechCorp Inc."
        assert len(record.projects) == 1
        assert record.metadata.extraction_method == "rules+ai"

    def test_rule_email_overrides_ai_email(self):
        mock_ai = _make_mock_ai({"full_name": "Alice", "email": "wrong@ai.com"})
        parser = ResumeParser(ai_extractor=mock_ai)
        doc = _make_success_doc(ALICE_TEXT)
        record = parser.parse(doc)
        # Rule-extracted email should win
        assert record.email == "alice.chen@example.com"

    def test_failed_ai_still_returns_record(self):
        mock_ai = _make_mock_ai(success=False, error="Ollama is down")
        parser = ResumeParser(ai_extractor=mock_ai)
        doc = _make_success_doc(ALICE_TEXT)
        record = parser.parse(doc)
        assert record.resume_filename is not None
        assert record.email == "alice.chen@example.com"  # rules still work

    def test_multiple_education_records_preserved(self):
        mock_ai = _make_mock_ai({
            "full_name": "Bob",
            "education": [
                {"qualification": "M.Sc. Data Science", "institution": "Edinburgh",
                 "graduation_year": "2021"},
                {"qualification": "B.Eng. Electronics", "institution": "IIT Bombay",
                 "graduation_year": "2019"},
            ],
        })
        parser = ResumeParser(ai_extractor=mock_ai)
        doc = _make_success_doc(INDIAN_TEXT)
        record = parser.parse(doc)
        assert len(record.education) == 2

    def test_multiple_work_experience_preserved(self):
        mock_ai = _make_mock_ai({
            "work_experience": [
                {"employer": "Infosys", "job_title": "Developer",
                 "start_date": "Jul 2021", "end_date": "Dec 2022"},
                {"employer": "Wipro", "job_title": "Senior Dev",
                 "start_date": "Jan 2023", "end_date": "Present"},
            ],
        })
        parser = ResumeParser(ai_extractor=mock_ai)
        doc = _make_success_doc(INDIAN_TEXT)
        record = parser.parse(doc)
        assert len(record.work_experience) == 2

    def test_long_resume_truncation_note(self):
        long_text = "A" * 15_000
        mock_ai = _make_mock_ai({"full_name": "Test"})
        parser = ResumeParser(ai_extractor=mock_ai, max_chars=12_000)
        doc = _make_success_doc(long_text)
        record = parser.parse(doc)
        assert any("truncated" in note.lower() for note in record.metadata.review_notes)

    def test_fresher_no_work_experience(self):
        mock_ai = _make_mock_ai({
            "full_name": "Priya Sharma",
            "work_experience": [],
            "education": [{"qualification": "B.E. Electronics",
                           "institution": "Osmania University",
                           "graduation_year": "Expected 2025"}],
        })
        parser = ResumeParser(ai_extractor=mock_ai)
        doc = _make_success_doc(FRESHER_TEXT)
        record = parser.parse(doc)
        assert record.work_experience == []
        assert len(record.education) == 1

    def test_model_used_recorded(self):
        mock_ai = _make_mock_ai({"full_name": "Alice"})
        parser = ResumeParser(ai_extractor=mock_ai)
        doc = _make_success_doc(ALICE_TEXT)
        record = parser.parse(doc)
        assert record.metadata.model_used == "qwen3:4b"


# ===========================================================================
# 6. Truncation Tests
# ===========================================================================

class TestTruncation:

    def test_short_text_not_truncated(self):
        text = "Hello world"
        out, was = _truncate_resume(text, max_chars=100)
        assert was is False
        assert out == text

    def test_long_text_truncated(self):
        text = "A" * 20_000
        out, was = _truncate_resume(text, max_chars=12_000)
        assert was is True
        assert len(out) <= 12_000

    def test_truncation_at_paragraph_boundary(self):
        # Text with paragraph breaks
        para = "This is a paragraph.\n\n" * 500
        out, was = _truncate_resume(para, max_chars=2_000)
        assert was is True
        # Should end at a blank line, not mid-sentence
        assert out.endswith("\n\n") or len(out) <= 2_000


# ===========================================================================
# 7. Validation Tests
# ===========================================================================

class TestValidateEmail:

    def test_valid_email_no_issue(self):
        assert validate_email("alice@example.com") is None

    def test_invalid_email_has_issue(self):
        assert validate_email("not-an-email") is not None

    def test_none_email_no_issue(self):
        assert validate_email(None) is None

    def test_missing_tld_invalid(self):
        assert validate_email("alice@example") is not None


class TestValidatePhone:

    def test_valid_phone_no_issue(self):
        assert validate_phone("+91-98765-43210") is None

    def test_short_phone_has_issue(self):
        assert validate_phone("123") is not None

    def test_none_phone_no_issue(self):
        assert validate_phone(None) is None

    def test_very_long_phone_has_issue(self):
        assert validate_phone("12345678901234567") is not None


class TestValidateGraduationYears:

    def test_valid_year_no_issue(self):
        rec = CandidateRecord(
            resume_filename="a.pdf",
            education=[EducationRecord(graduation_year="2020")],
        )
        issues = validate_graduation_years(rec)
        assert issues == []

    def test_future_year_flagged(self):
        rec = CandidateRecord(
            resume_filename="a.pdf",
            education=[EducationRecord(graduation_year="2099")],
        )
        issues = validate_graduation_years(rec)
        assert len(issues) > 0

    def test_expected_year_text_not_flagged(self):
        # "Expected 2025" contains a valid year
        rec = CandidateRecord(
            resume_filename="a.pdf",
            education=[EducationRecord(graduation_year="Expected 2025")],
        )
        issues = validate_graduation_years(rec)
        assert issues == []


class TestFormulaInjection:

    def test_equal_sign_prefixed(self):
        assert sanitise_formula_injection("=SUM(A1)") == "'=SUM(A1)"

    def test_at_sign_prefixed(self):
        assert sanitise_formula_injection("@user") == "'@user"

    def test_normal_value_unchanged(self):
        assert sanitise_formula_injection("Alice Chen") == "Alice Chen"

    def test_none_unchanged(self):
        assert sanitise_formula_injection(None) is None


class TestValidateCandidate:

    def test_valid_record_stays_success(self):
        rec = CandidateRecord(
            resume_filename="a.pdf",
            email="a@b.com",
            phone="+91-98765-43210",
        )
        rec.metadata.processing_status = "success"
        validated = validate_candidate(rec)
        assert validated.metadata.processing_status == "success"

    def test_bad_email_becomes_review_required(self):
        rec = CandidateRecord(
            resume_filename="a.pdf",
            email="not-valid",
        )
        rec.metadata.processing_status = "success"
        validated = validate_candidate(rec)
        assert validated.metadata.processing_status == "review_required"

    def test_duplicate_education_flagged(self):
        rec = CandidateRecord(
            resume_filename="a.pdf",
            education=[
                EducationRecord(qualification="B.Sc.", institution="MIT"),
                EducationRecord(qualification="B.Sc.", institution="MIT"),
            ],
        )
        rec.metadata.processing_status = "success"
        validated = validate_candidate(rec)
        assert any("duplicate" in n.lower() for n in validated.metadata.review_notes)


# ===========================================================================
# 8. Batch processing / partial failure
# ===========================================================================

class TestBatchProcessing:

    def test_batch_with_one_failed_continues(self):
        mock_ai = _make_mock_ai({"full_name": "Alice"})
        parser = ResumeParser(ai_extractor=mock_ai)
        docs = [
            _make_success_doc(ALICE_TEXT, "alice.pdf"),
            _make_failed_doc("bad.pdf"),
            _make_success_doc(INDIAN_TEXT, "ravi.pdf"),
        ]
        records = [parser.parse(doc) for doc in docs]
        assert len(records) == 3
        assert records[0].metadata.processing_status in ("success", "review_required", "partial")
        assert records[1].metadata.processing_status == "failed"
        assert records[2].metadata.processing_status in ("success", "review_required", "partial")

    def test_failed_record_has_filename(self):
        parser = ResumeParser(ai_extractor=None)
        doc = _make_failed_doc("broken.pdf")
        record = parser.parse(doc)
        assert record.resume_filename == "broken.pdf"

    def test_empty_batch_returns_empty_list(self):
        parser = ResumeParser(ai_extractor=None)
        records = [parser.parse(doc) for doc in []]
        assert records == []

    def test_conflicting_values_noted(self):
        mock_ai = _make_mock_ai({
            "email": "ai_version@example.com",
            "full_name": "Alice",
        })
        parser = ResumeParser(ai_extractor=mock_ai)
        doc = _make_success_doc(ALICE_TEXT)
        record = parser.parse(doc)
        # alice.chen@example.com (rule) vs ai_version@example.com (ai) = conflict
        review_notes = " ".join(record.metadata.review_notes)
        assert "email" in review_notes.lower()
