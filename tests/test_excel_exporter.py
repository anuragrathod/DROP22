"""
tests/test_excel_exporter.py
=============================
Phase 3: Tests for src/excel_exporter.py.

All tests open the generated workbook with openpyxl to verify content.
No Ollama is required.
"""

from __future__ import annotations

import io

import openpyxl
# pyrefly: ignore[missing-import]
import pytest

from schemas.candidate import (
    CandidateRecord,
    EducationRecord,
    ExtractionMetadata,
    Project,
    WorkExperience,
)
from src.excel_exporter import export_to_bytes, export_to_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    filename: str = "test.pdf",
    name: str = "Alice Chen",
    email: str = "alice@example.com",
    phone: str = "+1 555-0101",
    location: str = "SF, CA",
    status: str = "success",
) -> CandidateRecord:
    rec = CandidateRecord(
        resume_filename=filename,
        full_name=name,
        email=email,
        phone=phone,
        location=location,
        education=[
            EducationRecord(
                qualification="B.Sc. Computer Science",
                institution="Stanford",
                graduation_year="2022",
            )
        ],
        technical_skills=["Python", "Docker"],
        programming_languages=["Go"],
        tools=["AWS"],
        work_experience=[
            WorkExperience(
                employer="TechCorp",
                job_title="SWE",
                start_date="Jan 2023",
                end_date="Present",
                responsibilities=["Built APIs", "Led team"],
            )
        ],
        projects=[
            Project(name="ResumeBot", description="OSS tool", technologies=["Python"])
        ],
        certifications=["AWS SAA"],
        linkedin_url="https://linkedin.com/in/alice",
        github_url="https://github.com/alice",
        metadata=ExtractionMetadata(
            processing_status=status,
            extraction_method="rules+ai",
            missing_fields=[],
            validation_issues=[],
        ),
        raw_text_snippet="Alice Chen resume text...",
    )
    return rec


def _open_workbook(data: bytes) -> openpyxl.Workbook:
    return openpyxl.load_workbook(io.BytesIO(data))


def _sheet_headers(ws) -> list[str]:
    return [cell.value for cell in ws[1]]


def _sheet_rows(ws) -> list[list]:
    """Return all data rows (excluding header)."""
    return [[cell.value for cell in row] for row in ws.iter_rows(min_row=2)]


# ---------------------------------------------------------------------------
# Basic structure tests
# ---------------------------------------------------------------------------

class TestWorkbookStructure:

    def test_returns_bytes(self):
        data = export_to_bytes([])
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_empty_records_produces_valid_workbook(self):
        data = export_to_bytes([])
        wb = _open_workbook(data)
        assert wb is not None

    def test_correct_sheet_names(self):
        data = export_to_bytes([_make_record()])
        wb = _open_workbook(data)
        assert wb.sheetnames == [
            "Candidates", "Education", "Work Experience", "Projects", "Processing Log"
        ]

    def test_candidates_sheet_has_headers(self):
        data = export_to_bytes([_make_record()])
        wb = _open_workbook(data)
        headers = _sheet_headers(wb["Candidates"])
        assert "Candidate ID" in headers
        assert "Full Name" in headers
        assert "Email" in headers
        assert "Phone" in headers
        assert "Processing Status" in headers

    def test_education_sheet_has_headers(self):
        data = export_to_bytes([_make_record()])
        wb = _open_workbook(data)
        headers = _sheet_headers(wb["Education"])
        assert "Qualification" in headers
        assert "Institution" in headers
        assert "Graduation Year" in headers

    def test_experience_sheet_has_headers(self):
        data = export_to_bytes([_make_record()])
        wb = _open_workbook(data)
        headers = _sheet_headers(wb["Work Experience"])
        assert "Employer" in headers
        assert "Job Title" in headers
        assert "Responsibilities" in headers

    def test_projects_sheet_has_headers(self):
        data = export_to_bytes([_make_record()])
        wb = _open_workbook(data)
        headers = _sheet_headers(wb["Projects"])
        assert "Project Name" in headers
        assert "Technologies" in headers

    def test_log_sheet_has_headers(self):
        data = export_to_bytes([_make_record()])
        wb = _open_workbook(data)
        headers = _sheet_headers(wb["Processing Log"])
        assert "Resume Filename" in headers
        assert "Extraction Status" in headers


# ---------------------------------------------------------------------------
# Single candidate tests
# ---------------------------------------------------------------------------

class TestSingleCandidate:

    def test_name_in_candidates_sheet(self):
        rec = _make_record(name="Alice Chen")
        wb = _open_workbook(export_to_bytes([rec]))
        rows = _sheet_rows(wb["Candidates"])
        assert any("Alice Chen" in str(cell) for cell in rows[0])

    def test_email_in_candidates_sheet(self):
        rec = _make_record(email="alice@example.com")
        wb = _open_workbook(export_to_bytes([rec]))
        rows = _sheet_rows(wb["Candidates"])
        assert any("alice@example.com" in str(cell) for cell in rows[0])

    def test_phone_preserved_as_string(self):
        rec = _make_record(phone="+1 555-0101")
        wb = _open_workbook(export_to_bytes([rec]))
        ws = wb["Candidates"]
        # Find the phone column index
        headers = _sheet_headers(ws)
        phone_col = headers.index("Phone") + 1
        phone_val = ws.cell(row=2, column=phone_col).value
        # Must be a string, not a number
        assert isinstance(phone_val, str)
        assert "555" in phone_val

    def test_education_row_created(self):
        rec = _make_record()
        wb = _open_workbook(export_to_bytes([rec]))
        rows = _sheet_rows(wb["Education"])
        assert len(rows) == 1
        assert any("Stanford" in str(cell) for cell in rows[0])

    def test_experience_row_created(self):
        rec = _make_record()
        wb = _open_workbook(export_to_bytes([rec]))
        rows = _sheet_rows(wb["Work Experience"])
        assert len(rows) == 1
        assert any("TechCorp" in str(cell) for cell in rows[0])

    def test_project_row_created(self):
        rec = _make_record()
        wb = _open_workbook(export_to_bytes([rec]))
        rows = _sheet_rows(wb["Projects"])
        assert len(rows) == 1
        assert any("ResumeBot" in str(cell) for cell in rows[0])

    def test_log_row_created(self):
        rec = _make_record()
        wb = _open_workbook(export_to_bytes([rec]))
        rows = _sheet_rows(wb["Processing Log"])
        assert len(rows) == 1
        assert any("test.pdf" in str(cell) for cell in rows[0])

    def test_candidate_id_present(self):
        rec = _make_record()
        wb = _open_workbook(export_to_bytes([rec]))
        rows = _sheet_rows(wb["Candidates"])
        assert any(rec.candidate_id in str(cell) for cell in rows[0])


# ---------------------------------------------------------------------------
# Multiple candidates
# ---------------------------------------------------------------------------

class TestMultipleCandidates:

    def test_two_candidates_two_rows(self):
        recs = [_make_record("a.pdf", "Alice"), _make_record("b.pdf", "Bob")]
        wb = _open_workbook(export_to_bytes(recs))
        rows = _sheet_rows(wb["Candidates"])
        assert len(rows) == 2

    def test_education_rows_per_candidate(self):
        r1 = _make_record("a.pdf")
        r2 = _make_record("b.pdf")
        r2.education.append(
            EducationRecord(qualification="M.Sc.", institution="MIT", graduation_year="2024")
        )
        wb = _open_workbook(export_to_bytes([r1, r2]))
        rows = _sheet_rows(wb["Education"])
        # r1 has 1 edu, r2 has 2 = 3 total
        assert len(rows) == 3

    def test_experience_rows_per_candidate(self):
        r1 = _make_record("a.pdf")
        r1.work_experience.append(
            WorkExperience(employer="OtherCo", job_title="Dev")
        )
        r2 = _make_record("b.pdf")
        wb = _open_workbook(export_to_bytes([r1, r2]))
        rows = _sheet_rows(wb["Work Experience"])
        assert len(rows) == 3  # 2 from r1, 1 from r2


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_candidate_with_no_education(self):
        rec = _make_record()
        rec.education = []
        data = export_to_bytes([rec])
        wb = _open_workbook(data)
        rows = _sheet_rows(wb["Education"])
        assert len(rows) == 0

    def test_candidate_with_no_experience(self):
        rec = _make_record()
        rec.work_experience = []
        data = export_to_bytes([rec])
        wb = _open_workbook(data)
        rows = _sheet_rows(wb["Work Experience"])
        assert len(rows) == 0

    def test_candidate_with_no_projects(self):
        rec = _make_record()
        rec.projects = []
        data = export_to_bytes([rec])
        wb = _open_workbook(data)
        rows = _sheet_rows(wb["Projects"])
        assert len(rows) == 0

    def test_missing_name_becomes_blank(self):
        rec = _make_record()
        rec.full_name = None
        wb = _open_workbook(export_to_bytes([rec]))
        ws = wb["Candidates"]
        headers = _sheet_headers(ws)
        name_col = headers.index("Full Name") + 1
        val = ws.cell(row=2, column=name_col).value
        # openpyxl returns None for blank cells
        assert val in (None, "")

    def test_multiple_education_records_in_education_sheet(self):
        rec = _make_record()
        rec.education = [
            EducationRecord(qualification="B.Sc.", institution="MIT", graduation_year="2020"),
            EducationRecord(qualification="M.Sc.", institution="Stanford", graduation_year="2022"),
        ]
        wb = _open_workbook(export_to_bytes([rec]))
        rows = _sheet_rows(wb["Education"])
        assert len(rows) == 2

    def test_empty_records_list(self):
        data = export_to_bytes([])
        wb = _open_workbook(data)
        rows = _sheet_rows(wb["Candidates"])
        assert len(rows) == 0


# ---------------------------------------------------------------------------
# Formula injection protection
# ---------------------------------------------------------------------------

class TestFormulaInjection:

    def test_equals_sign_in_name_is_sanitised(self):
        rec = _make_record(name="=SUM(A1:A10)")
        wb = _open_workbook(export_to_bytes([rec]))
        ws = wb["Candidates"]
        headers = _sheet_headers(ws)
        col = headers.index("Full Name") + 1
        val = ws.cell(row=2, column=col).value
        assert val is not None
        assert not str(val).startswith("=")

    def test_at_sign_in_email_is_sanitised(self):
        # Note: valid emails start with word chars not @, but we test the guard
        rec = _make_record()
        rec.email = None  # bypass pydantic email validation
        rec2 = CandidateRecord(
            resume_filename="x.pdf",
            full_name="@Injector",
        )
        wb = _open_workbook(export_to_bytes([rec2]))
        ws = wb["Candidates"]
        headers = _sheet_headers(ws)
        col = headers.index("Full Name") + 1
        val = ws.cell(row=2, column=col).value
        assert not str(val).startswith("@")


# ---------------------------------------------------------------------------
# Failed documents in log
# ---------------------------------------------------------------------------

class TestFailedDocuments:

    def test_failed_doc_appears_in_log(self):
        failed = [{"filename": "broken.pdf", "doc_status": "corrupt", "error": "Parse error"}]
        data = export_to_bytes([], failed_docs=failed)
        wb = _open_workbook(data)
        rows = _sheet_rows(wb["Processing Log"])
        assert len(rows) == 1
        assert any("broken.pdf" in str(c) for c in rows[0])

    def test_failed_doc_does_not_appear_in_candidates(self):
        failed = [{"filename": "broken.pdf", "doc_status": "corrupt", "error": "Parse error"}]
        data = export_to_bytes([], failed_docs=failed)
        wb = _open_workbook(data)
        rows = _sheet_rows(wb["Candidates"])
        assert len(rows) == 0

    def test_mix_of_success_and_failure(self):
        rec = _make_record("good.pdf")
        failed = [{"filename": "bad.pdf", "doc_status": "corrupt", "error": "Broken"}]
        wb = _open_workbook(export_to_bytes([rec], failed_docs=failed))
        assert len(_sheet_rows(wb["Candidates"])) == 1
        assert len(_sheet_rows(wb["Processing Log"])) == 2  # 1 success + 1 fail


# ---------------------------------------------------------------------------
# export_to_file
# ---------------------------------------------------------------------------

class TestExportToFile:

    def test_file_is_written(self, tmp_path):
        path = tmp_path / "out.xlsx"
        result = export_to_file([_make_record()], path)
        assert result == path
        assert path.exists()
        assert path.stat().st_size > 0

    def test_file_is_valid_workbook(self, tmp_path):
        path = tmp_path / "out.xlsx"
        export_to_file([_make_record()], path)
        wb = openpyxl.load_workbook(path)
        assert "Candidates" in wb.sheetnames

    def test_corrected_record_reflected_in_file(self, tmp_path):
        rec = _make_record(name="Old Name")
        rec.full_name = "Corrected Name"
        path = tmp_path / "out.xlsx"
        export_to_file([rec], path)
        wb = openpyxl.load_workbook(path)
        ws = wb["Candidates"]
        headers = _sheet_headers(ws)
        col = headers.index("Full Name") + 1
        assert ws.cell(row=2, column=col).value == "Corrected Name"
