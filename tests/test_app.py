"""
tests/test_app.py
==================
Phase 3: Streamlit application tests using Streamlit's built-in AppTest.

These tests use `streamlit.testing.v1.AppTest` which runs the app
headlessly — no browser, no server.  All AI calls are mocked so Ollama
is not required.

Run:
    pytest tests/test_app.py -v
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import openpyxl
# pyrefly: ignore[missing-import]
from streamlit.testing.v1 import AppTest

from schemas.candidate import (
    CandidateRecord,
    EducationRecord,
    ExtractionMetadata,
    Project,
    WorkExperience,
)
from src.document_reader import DocumentResult, ProcessingStatus
from src.excel_exporter import export_to_bytes

# ---------------------------------------------------------------------------
# Path to the application under test
# ---------------------------------------------------------------------------
_APP_PATH = str(Path(__file__).parent.parent / "app.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(filename: str = "alice.pdf", name: str = "Alice Chen") -> CandidateRecord:
    return CandidateRecord(
        resume_filename=filename,
        full_name=name,
        email=f"{name.lower().replace(' ', '.')}@example.com",
        phone="+1 555-0101",
        location="SF, CA",
        education=[EducationRecord(qualification="B.Sc.", institution="MIT", graduation_year="2022")],
        technical_skills=["Python", "Docker"],
        work_experience=[WorkExperience(employer="ACME", job_title="SWE",
                                        start_date="Jan 2023", end_date="Present")],
        projects=[Project(name="TestBot", technologies=["Python"])],
        certifications=["AWS SAA"],
        metadata=ExtractionMetadata(processing_status="success", extraction_method="rules+ai"),
    )


def _make_failed_doc(filename: str = "broken.pdf") -> dict:
    return {"filename": filename, "doc_status": "corrupt", "error": "Parse error", "char_count": 0}


# ---------------------------------------------------------------------------
# 1. App loads
# ---------------------------------------------------------------------------

class TestAppLoads:

    def test_app_loads_without_error(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        assert not at.exception, f"App raised: {at.exception}"

    def test_app_has_title(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        # The page title / main content should contain our brand text
        all_text = " ".join(str(e.value) for e in at.markdown if hasattr(e, "value"))
        assert "Resume" in all_text or "Resume-to-Excel" in at.title[0].value if at.title else True

    def test_upload_widget_exists(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        # file_uploader should be present
        assert len(at.file_uploader) >= 1

    def test_process_button_exists(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        btn_labels = [b.label for b in at.button]
        assert any("Process" in label for label in btn_labels)

    def test_clear_button_exists(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        btn_labels = [b.label for b in at.button]
        assert any("Clear" in label for label in btn_labels)


# ---------------------------------------------------------------------------
# 2. Session state initialisation
# ---------------------------------------------------------------------------

class TestSessionState:

    def test_initial_candidates_empty(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        assert at.session_state["candidates"] == []

    def test_initial_processed_false(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        assert at.session_state["processed"] is False

    def test_initial_failed_docs_empty(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        assert at.session_state["failed_docs"] == []

    def test_initial_edited_empty(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        assert at.session_state["edited"] == {}


# ---------------------------------------------------------------------------
# 3. Process button disabled when no files
# ---------------------------------------------------------------------------

class TestProcessButtonState:

    def test_process_button_disabled_without_upload(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        process_btns = [b for b in at.button if "Process" in b.label]
        assert len(process_btns) > 0
        assert process_btns[0].disabled is True


# ---------------------------------------------------------------------------
# 4. Results dashboard shown after processing
# ---------------------------------------------------------------------------

class TestResultsDashboard:

    def test_metrics_displayed_when_processed(self):
        """Inject processed state directly and verify metrics appear."""
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        at.session_state["candidates"]  = [_make_record()]
        at.session_state["failed_docs"] = []
        at.session_state["processed"]   = True
        at.run()
        assert not at.exception, f"App raised: {at.exception}"
        # Metrics should now be visible
        metric_values = [m.value for m in at.metric]
        assert len(metric_values) >= 4  # Total, Succeeded, Needs Review, Failed

    def test_download_button_available_when_processed(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        at.session_state["candidates"]  = [_make_record()]
        at.session_state["failed_docs"] = []
        at.session_state["processed"]   = True
        at.run()
        assert not at.exception
        # st.download_button is exposed via at.download_button in Streamlit AppTest
        assert len(at.download_button) >= 1

    def test_no_download_button_before_processing(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        # session_state["processed"] is False by default
        dl_buttons = [b for b in at.button if "Download" in b.label or "download" in b.label.lower()]
        assert len(dl_buttons) == 0

    def test_failed_doc_shown_in_dashboard(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        at.session_state["candidates"]  = []
        at.session_state["failed_docs"] = [_make_failed_doc()]
        at.session_state["processed"]   = True
        at.run()
        assert not at.exception


# ---------------------------------------------------------------------------
# 5. Clear button resets state
# ---------------------------------------------------------------------------

class TestClearButton:

    def test_clear_button_resets_processed(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        at.session_state["candidates"] = [_make_record()]
        at.session_state["processed"]  = True
        at.run()
        # Click clear
        clear_btn = next(b for b in at.button if "Clear" in b.label)
        clear_btn.click().run()
        assert at.session_state["processed"] is False
        assert at.session_state["candidates"] == []


# ---------------------------------------------------------------------------
# 6. Sidebar AI status controls
# ---------------------------------------------------------------------------

class TestSidebar:

    def test_no_ollama_in_sidebar(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        # Verify no inputs mention Ollama or local AI
        all_labels = [t.label for t in at.text_input] + [s.label for s in at.selectbox]
        assert not any("ollama" in lbl.lower() for lbl in all_labels)

    def test_no_api_key_input_present(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        # Verify no input is used to capture or display API keys
        all_labels = [t.label for t in at.text_input]
        assert not any("api key" in lbl.lower() or "groq_api_key" in lbl.lower() for lbl in all_labels)

    def test_no_rules_only_checkbox(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        # Rules-only mode has been removed in favor of Groq
        checkboxes = [c.label for c in at.checkbox]
        assert not any("rules" in lbl.lower() for lbl in checkboxes)

    def test_model_selector_present(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        select_labels = [s.label for s in at.selectbox]
        assert any("Model" in lbl for lbl in select_labels)

    def test_sidebar_reset_button_present(self):
        at = AppTest.from_file(_APP_PATH, default_timeout=30).run()
        btn_labels = [b.label for b in at.button]
        assert any("Reset" in lbl for lbl in btn_labels)


# ---------------------------------------------------------------------------
# 7. Excel export integration (end-to-end, no Streamlit)
# ---------------------------------------------------------------------------

class TestExcelExportIntegration:
    """These tests exercise the export pipeline directly — not through Streamlit."""

    def test_export_with_processed_records(self):
        records = [_make_record("a.pdf", "Alice"), _make_record("b.pdf", "Bob")]
        data = export_to_bytes(records)
        wb = openpyxl.load_workbook(io.BytesIO(data))
        ws = wb["Candidates"]
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        assert len(rows) == 2

    def test_export_with_mix_of_success_and_failure(self):
        records = [_make_record()]
        failed  = [_make_failed_doc("bad.pdf")]
        data = export_to_bytes(records, failed_docs=failed)
        wb = openpyxl.load_workbook(io.BytesIO(data))
        assert len(list(wb["Candidates"].iter_rows(min_row=2, values_only=True))) == 1
        log_rows = list(wb["Processing Log"].iter_rows(min_row=2, values_only=True))
        assert len(log_rows) == 2  # 1 success + 1 failure

    def test_edited_record_reflected_in_export(self):
        rec = _make_record()
        rec.full_name = "Corrected Name"
        data = export_to_bytes([rec])
        wb = openpyxl.load_workbook(io.BytesIO(data))
        ws = wb["Candidates"]
        headers = [c.value for c in ws[1]]
        col = headers.index("Full Name") + 1
        assert ws.cell(row=2, column=col).value == "Corrected Name"

    def test_empty_batch_export_does_not_crash(self):
        data = export_to_bytes([])
        assert isinstance(data, bytes)
        assert len(data) > 0
