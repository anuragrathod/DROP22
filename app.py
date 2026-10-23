from __future__ import annotations

import html
import io
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

# pyrefly: ignore[missing-import]
import streamlit as st

# ---------------------------------------------------------------------------
# Page configuration (must be the first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="ResumeDrop",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    import dotenv

    _env_path = Path(__file__).resolve().parent / ".env"
    if _env_path.exists():
        dotenv.load_dotenv(dotenv_path=_env_path, override=True)
    else:
        dotenv.load_dotenv(override=True)
except ImportError:
    pass


def _save_groq_key_to_env(key: str) -> bool:
    """Save GROQ_API_KEY into the local .env file so the user only enters it once."""
    env_file = Path(__file__).resolve().parent / ".env"
    clean_key = key.strip()
    if not clean_key:
        return False

    lines = []
    found = False
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("GROQ_API_KEY="):
                lines.append(f"GROQ_API_KEY={clean_key}")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"GROQ_API_KEY={clean_key}")

    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ["GROQ_API_KEY"] = clean_key
    return True


# ---------------------------------------------------------------------------
# Domain Imports
# ---------------------------------------------------------------------------
from schemas.candidate import (
    CandidateRecord,
    EducationRecord,
    ExtractionMetadata,
    Project,
    WorkExperience,
)
from src.ai_extractor import (
    DEFAULT_GROQ_MODEL,
    AIConfig,
    AIExtractor,
    check_groq_available,
    list_groq_models,
)
from src.document_reader import DocumentReader, DocumentResult, ProcessingStatus
from src.excel_exporter import export_to_bytes
from src.resume_parser import ResumeParser
from src.validator import validate_candidate

logging.basicConfig(level=logging.WARNING)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_FILE_SIZE_MB = 10
_AVAILABLE_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
]

_STATUS_CONFIG = {
    "success": {"label": "Verified", "dot": "green", "badge_class": "badge-success"},
    "partial": {"label": "Partial", "dot": "orange", "badge_class": "badge-warning"},
    "review_required": {"label": "Needs Review", "dot": "orange", "badge_class": "badge-warning"},
    "failed": {"label": "Failed", "dot": "red", "badge_class": "badge-danger"},
    "pending": {"label": "Pending", "dot": "grey", "badge_class": "badge-neutral"},
}

# ---------------------------------------------------------------------------
# Design system: one light neutral theme, one accent, one radius scale
# ---------------------------------------------------------------------------
st.markdown("""
<style>
:root {
    --bg: #fbfbfd;
    --surface: #ffffff;
    --sidebar: #f5f5f7;
    --text: #1d1d1f;
    --muted: #6e6e73;
    --line: rgba(0, 0, 0, 0.10);
    --line-strong: rgba(0, 0, 0, 0.22);
    --accent: #0071e3;
    --accent-hover: #0077ed;
    --ok: #248a3d;
    --warn: #b25000;
    --bad: #d70015;
    --radius: 12px;
    --font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display",
            "Helvetica Neue", Helvetica, Arial, sans-serif;
}

/* Typography (scoped so icon fonts keep working) */
.stApp,
.stApp :where(p, li, label, input, textarea, button, summary, h1, h2, h3, h4, td, th) {
    font-family: var(--font);
    -webkit-font-smoothing: antialiased;
}
[data-testid="stIconMaterial"] {
    font-family: "Material Symbols Rounded", "Material Symbols Outlined" !important;
}

/* Canvas */
.stApp { background: var(--bg); color: var(--text); }
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }
.block-container {
    max-width: 1080px;
    padding: 2.5rem clamp(1rem, 4vw, 2.5rem) 4rem !important;
}

/* Headings */
h1, h2, h3 { color: var(--text) !important; letter-spacing: -0.025em !important; }
h3 { font-size: 1.3rem !important; font-weight: 600 !important; padding-top: 2.25rem !important; }
[data-testid="stHeaderActionElements"] { display: none; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: var(--muted); }

.rd-title {
    font-size: clamp(2rem, 4.5vw, 2.75rem);
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1.1;
    margin: 0 0 0.5rem 0;
    color: var(--text);
}
.rd-lede {
    font-size: 1.05rem;
    line-height: 1.5;
    color: var(--muted);
    margin: 0 0 1.75rem 0;
    max-width: 38rem;
}
.rd-brand { font-size: 1.15rem; font-weight: 600; letter-spacing: -0.02em; margin: 0 0 1.5rem 0; }
.rd-status { display: flex; align-items: center; gap: 8px; font-size: 0.85rem; color: var(--text); margin: 0.25rem 0 0.25rem 0; }
.rd-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex: none; }
.rd-dot.ok { background: var(--ok); }
.rd-dot.warn { background: var(--warn); }
.rd-note { font-size: 0.8rem; color: var(--muted); line-height: 1.5; margin: 0 0 1rem 0; }
.rd-link { color: var(--accent); text-decoration: none; font-size: 0.9rem; font-weight: 500; }
.rd-link:hover { text-decoration: underline; }
.rd-progress-line { font-size: 0.85rem; margin: 4px 0; }
.rd-progress-line.ok { color: var(--ok); }
.rd-progress-line.bad { color: var(--bad); }

/* Sidebar */
[data-testid="stSidebar"] { background: var(--sidebar); border-right: 1px solid var(--line); }
[data-testid="stSidebar"] > div:first-child { padding: 1rem 0.5rem; }
[data-testid="stSidebar"] hr { margin: 1.25rem 0; border-color: var(--line); }

/* Metrics: plain figures, no boxes */
[data-testid="stMetric"] {
    background: transparent;
    border: none;
    border-top: 1px solid var(--line);
    border-radius: 0;
    padding: 0.9rem 0 0 0;
    box-shadow: none;
}
[data-testid="stMetricLabel"] p { font-size: 0.85rem; font-weight: 500; color: var(--muted); }
[data-testid="stMetricValue"] div {
    font-size: clamp(1.6rem, 3vw, 2.2rem);
    font-weight: 600;
    letter-spacing: -0.03em;
    color: var(--text);
}

/* Buttons */
.stButton > button,
.stFormSubmitButton > button,
.stDownloadButton > button {
    min-height: 2.6rem;
    border-radius: 980px;
    font-weight: 500;
    font-size: 0.92rem;
    padding: 0.4rem 1.4rem;
    border: 1px solid var(--line-strong) !important;
    background: var(--surface) !important;
    color: var(--text) !important;
    box-shadow: none !important;
    transition: background-color 0.15s ease, border-color 0.15s ease;
}
.stButton > button:hover,
.stFormSubmitButton > button:hover,
.stDownloadButton > button:hover {
    background: #f5f5f7 !important;
    border-color: rgba(0, 0, 0, 0.35) !important;
}
.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"],
button[data-testid="stBaseButton-primary"] {
    background: var(--accent) !important;
    border-color: var(--accent) !important;
    color: #ffffff !important;
}
.stButton > button[kind="primary"]:hover,
.stDownloadButton > button[kind="primary"]:hover,
.stFormSubmitButton > button[kind="primary"]:hover,
button[data-testid="stBaseButton-primary"]:hover {
    background: var(--accent-hover) !important;
    border-color: var(--accent-hover) !important;
}
.stButton > button[kind="primary"] p,
.stDownloadButton > button[kind="primary"] p,
button[data-testid="stBaseButton-primary"] p { color: #ffffff !important; }
.stButton > button:disabled,
.stDownloadButton > button:disabled {
    background: #f2f2f7 !important;
    border-color: var(--line) !important;
    color: #8e8e93 !important;
    cursor: not-allowed;
}
button:focus-visible,
input:focus-visible,
textarea:focus-visible,
summary:focus-visible {
    outline: 3px solid rgba(0, 113, 227, 0.3) !important;
    outline-offset: 2px;
}

/* File uploader */
[data-testid="stFileUploader"] section {
    background: var(--surface);
    border: 1.5px dashed var(--line-strong);
    border-radius: 16px;
    padding: 1.5rem 1.25rem;
    transition: border-color 0.15s ease;
}
[data-testid="stFileUploader"] section:hover { border-color: var(--accent); }
[data-testid="stFileUploader"] small { color: var(--muted); }

/* File list */
.rd-files { display: flex; flex-wrap: wrap; gap: 8px; margin: 0.75rem 0 1rem 0; }
.rd-file {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 980px;
    padding: 4px 12px;
    font-size: 0.82rem;
    color: var(--text);
}
.rd-file span { color: var(--muted); margin-left: 6px; font-size: 0.75rem; }
.rd-file.dup { border-color: rgba(178, 80, 0, 0.45); }
.rd-file.dup span { color: var(--warn); }

/* Expanders */
[data-testid="stExpander"] { border: none !important; background: transparent; margin-bottom: 0.6rem; }
[data-testid="stExpander"] details {
    background: var(--surface);
    border: 1px solid var(--line) !important;
    border-radius: var(--radius) !important;
    box-shadow: none;
}
[data-testid="stExpander"] summary { padding: 0.85rem 1rem; font-weight: 500; color: var(--text); }
[data-testid="stExpander"] summary:hover { background: #fafafc; border-radius: var(--radius); }
[data-testid="stExpanderDetails"] { padding: 0.5rem 1rem 1.25rem 1rem; }

/* Forms and inputs */
div[data-testid="stForm"] { border: none; padding: 0; background: transparent; }
div[data-baseweb="input"],
div[data-baseweb="textarea"],
div[data-baseweb="select"] > div {
    background: var(--surface) !important;
    border-color: var(--line) !important;
    border-radius: 10px !important;
}
div[data-baseweb="input"]:focus-within,
div[data-baseweb="textarea"]:focus-within,
div[data-baseweb="select"] > div:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.15);
}
input, textarea { color: var(--text) !important; background: transparent !important; }
label[data-testid="stWidgetLabel"] p { color: var(--text); font-size: 0.85rem; font-weight: 500; }
div[data-baseweb="popover"] ul[role="listbox"] {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--radius);
}
li[role="option"]:hover, li[role="option"][aria-selected="true"] { background: var(--sidebar) !important; }

/* Alerts, progress, tables */
[data-testid="stAlert"] { border-radius: var(--radius); box-shadow: none; }
[data-testid="stAlert"] p { font-size: 0.88rem; }
[data-testid="stProgress"] > div { background: rgba(0, 0, 0, 0.06); border-radius: 980px; height: 6px; }
[data-testid="stProgress"] > div > div { background: var(--accent); border-radius: 980px; }
[data-testid="stDataFrame"] {
    border: 1px solid var(--line);
    border-radius: var(--radius);
    overflow: hidden;
}

/* Small screens */
@media (max-width: 640px) {
    .block-container { padding-top: 1.5rem !important; }
    .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button { width: 100%; }
    h3 { padding-top: 1.5rem !important; }
}
@media (prefers-reduced-motion: reduce) {
    * { transition: none !important; }
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------
def _init_state() -> None:
    defaults = {
        "candidates":   [],       # list[CandidateRecord]
        "failed_docs":  [],       # list[dict]
        "processed":    False,
        "upload_key":   0,        # increment to reset uploader
        "edited":       {},       # filename → edited CandidateRecord
        "selected_model": DEFAULT_GROQ_MODEL,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


def _reset_workspace() -> None:
    st.session_state.candidates  = []
    st.session_state.failed_docs = []
    st.session_state.processed   = False
    st.session_state.edited      = {}
    st.session_state.upload_key += 1
    st.rerun()  


# ---------------------------------------------------------------------------
# AI Resource Loader (Groq Only, API key read silently from environment)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _get_groq_extractor(model: str) -> tuple[Optional[AIExtractor], bool, str]:
    """Instantiate Groq AIExtractor using GROQ_API_KEY from environment."""
    api_key = os.environ.get("GROQ_API_KEY")
    config = AIConfig(
        provider="groq",
        model=model,
        api_key=api_key or None,
    )
    extractor = AIExtractor(config=config)
    ok, msg = extractor.check_availability()
    return extractor, ok, msg


# ---------------------------------------------------------------------------
# Sidebar: model, connection status, tools
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="rd-brand">ResumeDrop</div>', unsafe_allow_html=True)

    groq_api_key = os.environ.get("GROQ_API_KEY")
    available_groq_models = list_groq_models(groq_api_key) or _AVAILABLE_MODELS
    selected_model = st.selectbox(
        "Model",
        options=available_groq_models,
        index=0,
        key="groq_model_selector",
        help="Groq Cloud. GPT-OSS 120B gives the most accurate resume extraction.",
    )
    st.session_state.selected_model = selected_model

    extractor, is_ready, status_msg = _get_groq_extractor(selected_model)

    if is_ready:
        st.markdown(
            '<div class="rd-status"><span class="rd-dot ok"></span>Groq connected</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="rd-status"><span class="rd-dot warn"></span>Groq not connected</div>'
            '<div class="rd-note">Add <code>GROQ_API_KEY</code> to the <code>.env</code> file '
            "in the project folder to turn on AI extraction.</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    st.write("")
    if st.button("Reset workspace", key="sidebar_reset_btn", use_container_width=True):
        _reset_workspace()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<h1 class="rd-title">Resume to Excel</h1>
<p class="rd-lede">Drop PDF or DOCX resumes below. Candidate details are extracted into a formatted Excel workbook you can review and edit first.</p>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Upload Section
# ---------------------------------------------------------------------------
uploaded_files = st.file_uploader(
    "Upload resumes",
    type=["pdf", "docx"],
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.upload_key}",
    help=f"PDF or DOCX, up to {MAX_FILE_SIZE_MB} MB per file.",
    label_visibility="collapsed",
)

if uploaded_files:
    filenames = [f.name for f in uploaded_files]

    # Detect duplicate filenames in current batch
    seen_names: set[str] = set()
    duplicate_names: set[str] = set()
    for name in filenames:
        if name in seen_names:
            duplicate_names.add(name)
        seen_names.add(name)

    chips_html = '<div class="rd-files">'
    for uf in uploaded_files:
        size_kb = len(uf.getvalue()) / 1024
        is_dup = uf.name in duplicate_names
        chips_html += (
            f'<div class="rd-file{" dup" if is_dup else ""}">'
            f"{html.escape(uf.name)}<span>{size_kb:.1f} KB{' · duplicate' if is_dup else ''}</span>"
            "</div>"
        )
    chips_html += "</div>"
    st.markdown(chips_html, unsafe_allow_html=True)

    if duplicate_names:
        st.warning(f"Duplicate files detected: {', '.join(duplicate_names)}. Only the first instance will be extracted.")

    # Reset results if batch has changed
    if st.session_state.processed:
        prev = set(st.session_state.get("_last_filenames", []))
        curr = set(filenames)
        if prev != curr:
            st.session_state.candidates  = []
            st.session_state.failed_docs = []
            st.session_state.processed   = False
            st.session_state.edited      = {}
    st.session_state["_last_filenames"] = filenames

# ---------------------------------------------------------------------------
# Action Bar
# ---------------------------------------------------------------------------
col_btn1, col_btn2, _ = st.columns([1.5, 1, 3])
with col_btn1:
    process_clicked = st.button(
        "Process resumes",
        disabled=not uploaded_files,
        key="process_btn",
        type="primary",
        use_container_width=True,
    )
with col_btn2:
    if st.button("Clear all", key="clear_btn", use_container_width=True):
        _reset_workspace()

# ---------------------------------------------------------------------------
# Processing Workflow
# ---------------------------------------------------------------------------
if process_clicked and uploaded_files and not st.session_state.processed:
    extractor, is_ready, status_msg = _get_groq_extractor(st.session_state.selected_model)

    # Groq is the sole AI engine
    parser = ResumeParser(ai_extractor=extractor if is_ready else None)
    reader = DocumentReader()

    candidates: list[CandidateRecord] = []
    failed_docs: list[dict] = []

    progress_bar = st.progress(0, text="Starting…")
    status_area = st.empty()

    # Deduplicate uploads by name
    seen_fn: set[str] = set()
    unique_files = []
    for uf in uploaded_files:
        if uf.name not in seen_fn:
            seen_fn.add(uf.name)
            unique_files.append(uf)

    total_files = len(unique_files)

    for i, uf in enumerate(unique_files):
        pct = int((i / total_files) * 100)
        progress_bar.progress(pct, text=f"Processing {uf.name} ({i+1}/{total_files})…")
        try:
            raw_bytes = uf.getvalue()
            doc: DocumentResult = reader.process_bytes(raw_bytes, uf.name)

            if doc.status == ProcessingStatus.SUCCESS:
                candidate = parser.parse(doc)
                candidate = validate_candidate(candidate)
                candidates.append(candidate)
                status_area.markdown(
                    f'<div class="rd-progress-line ok">✓ {html.escape(uf.name)} → {html.escape(str(candidate.metadata.processing_status))}</div>',
                    unsafe_allow_html=True,
                )
            else:
                failed_docs.append({
                    "filename":   uf.name,
                    "doc_status": doc.status.value,
                    "error":      doc.error,
                    "char_count": doc.char_count,
                })
                status_area.markdown(
                    f'<div class="rd-progress-line bad">✗ {html.escape(uf.name)} → {html.escape(str(doc.error))}</div>',
                    unsafe_allow_html=True,
                )
        except Exception as exc:  # noqa: BLE001
            failed_docs.append({
                "filename":   uf.name,
                "doc_status": "error",
                "error":      str(exc),
                "char_count": 0,
            })
            status_area.markdown(
                f'<div class="rd-progress-line bad">✗ {html.escape(uf.name)} → Unexpected error: {html.escape(str(exc))}</div>',
                unsafe_allow_html=True,
            )

    progress_bar.progress(100, text="Extraction complete")
    st.session_state.candidates  = candidates
    st.session_state.failed_docs = failed_docs
    st.session_state.processed   = True
    st.session_state.edited      = {}
    status_area.empty()
    st.rerun()

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
if st.session_state.processed:
    candidates  = st.session_state.candidates
    failed_docs = st.session_state.failed_docs

    st.subheader("Results")

    total      = len(candidates) + len(failed_docs)
    succeeded  = sum(1 for c in candidates if c.metadata.processing_status == "success")
    review     = sum(1 for c in candidates if c.metadata.processing_status in ("review_required", "partial"))
    failed     = len(failed_docs)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total resumes", total)
    c2.metric("Verified", succeeded)
    c3.metric("Needs review", review)
    c4.metric("Failed", failed)

    # Candidate overview table
    if candidates:
        st.write("")
        table_rows = []
        for rec in candidates:
            effective_rec = st.session_state.edited.get(rec.resume_filename, rec)
            edu_str = "; ".join(
                " · ".join(filter(None, [e.qualification, e.institution, e.graduation_year]))
                for e in effective_rec.education
            )
            status = effective_rec.metadata.processing_status
            cfg = _STATUS_CONFIG.get(status, {"label": status})
            table_rows.append({
                "Filename":  effective_rec.resume_filename,
                "Candidate Name": effective_rec.full_name or "—",
                "Email":     effective_rec.email or "—",
                "Phone":     effective_rec.phone or "—",
                "Education": edu_str or "—",
                "Top Skills": ", ".join(effective_rec.technical_skills[:5]) or "—",
                "Status":    cfg["label"],
            })
        st.dataframe(table_rows, use_container_width=True, hide_index=True)

    # Failed documents list
    if failed_docs:
        with st.expander(f"Failed documents ({len(failed_docs)})", expanded=False):
            for fd in failed_docs:
                st.markdown(f"- **{fd['filename']}** — `{fd['doc_status']}`: {fd.get('error', 'Unspecified error')}")

    # Inline editor for review
    if candidates:
        st.subheader("Review and edit")
        st.caption("Changes you save here are included in the exported workbook.")

        for orig_rec in candidates:
            filename = orig_rec.resume_filename
            rec = st.session_state.edited.get(filename, orig_rec)
            status = rec.metadata.processing_status
            cfg = _STATUS_CONFIG.get(status, {"label": status, "dot": "grey"})

            with st.expander(f"{rec.full_name or filename}  ·  {cfg['label']}", expanded=(status == "review_required")):
                if rec.metadata.validation_issues:
                    st.warning("**Validation Notes:**\n" + "\n".join(f"- {issue}" for issue in rec.metadata.validation_issues))
                if rec.metadata.missing_fields:
                    st.info("**Missing Recommended Fields:** " + ", ".join(rec.metadata.missing_fields))

                with st.form(key=f"edit_form_{filename}"):
                    col1, col2 = st.columns(2)
                    new_name  = col1.text_input("Full Name", value=rec.full_name or "", key=f"fn_{filename}")
                    new_email = col2.text_input("Email", value=rec.email or "", key=f"em_{filename}")

                    col3, col4 = st.columns(2)
                    new_phone = col3.text_input("Phone Number", value=rec.phone or "", key=f"ph_{filename}")
                    new_loc   = col4.text_input("Location", value=rec.location or "", key=f"lc_{filename}")

                    edu_text = st.text_area(
                        "Education (Qualification | Specialization | Institution | Graduation Year)",
                        value="\n".join(
                            " | ".join(filter(None, [e.qualification, e.specialization, e.institution, e.graduation_year]))
                            for e in rec.education
                        ),
                        height=80,
                        key=f"edu_{filename}",
                    )

                    col5, col6, col7 = st.columns(3)
                    new_skills = col5.text_area("Technical Skills", value=", ".join(rec.technical_skills), height=70, key=f"sk_{filename}")
                    new_langs  = col6.text_area("Languages", value=", ".join(rec.programming_languages), height=70, key=f"lg_{filename}")
                    new_tools  = col7.text_area("Tools & Libraries", value=", ".join(rec.tools), height=70, key=f"tl_{filename}")

                    exp_text = st.text_area(
                        "Work Experience (Employer | Job Title | Start Date | End Date)",
                        value="\n".join(
                            " | ".join(filter(None, [e.employer, e.job_title, e.start_date, e.end_date]))
                            for e in rec.work_experience
                        ),
                        height=90,
                        key=f"exp_{filename}",
                    )

                    proj_text = st.text_area(
                        "Projects (Project Name | Description | Technologies)",
                        value="\n".join(
                            " | ".join(filter(None, [p.name, p.description, ", ".join(p.technologies)]))
                            for p in rec.projects
                        ),
                        height=80,
                        key=f"prj_{filename}",
                    )

                    col8, col9, col10 = st.columns(3)
                    new_li = col8.text_input("LinkedIn", value=rec.linkedin_url or "", key=f"li_{filename}")
                    new_gh = col9.text_input("GitHub", value=rec.github_url or "", key=f"gh_{filename}")
                    new_pf = col10.text_input("Portfolio", value=rec.portfolio_url or "", key=f"pf_{filename}")

                    new_certs = st.text_input("Certifications (comma-separated)", value=", ".join(rec.certifications), key=f"crt_{filename}")

                    save_submitted = st.form_submit_button("Save changes", use_container_width=True)

                if save_submitted:
                    # Parse education entries
                    new_edu: list[EducationRecord] = []
                    for line in edu_text.strip().splitlines():
                        parts = [p.strip() for p in line.split("|")]
                        if any(parts):
                            new_edu.append(EducationRecord(
                                qualification=parts[0] if len(parts) > 0 and parts[0] else None,
                                specialization=parts[1] if len(parts) > 1 and parts[1] else None,
                                institution=parts[2] if len(parts) > 2 and parts[2] else None,
                                graduation_year=parts[3] if len(parts) > 3 and parts[3] else None,
                            ))

                    # Parse work experience entries
                    new_exp: list[WorkExperience] = []
                    for line in exp_text.strip().splitlines():
                        parts = [p.strip() for p in line.split("|")]
                        if any(parts):
                            new_exp.append(WorkExperience(
                                employer=parts[0] if len(parts) > 0 and parts[0] else None,
                                job_title=parts[1] if len(parts) > 1 and parts[1] else None,
                                start_date=parts[2] if len(parts) > 2 and parts[2] else None,
                                end_date=parts[3] if len(parts) > 3 and parts[3] else None,
                            ))

                    # Parse project entries
                    new_proj: list[Project] = []
                    for line in proj_text.strip().splitlines():
                        parts = [p.strip() for p in line.split("|")]
                        if any(parts):
                            techs = [t.strip() for t in parts[2].split(",")] if len(parts) > 2 and parts[2] else []
                            new_proj.append(Project(
                                name=parts[0] if len(parts) > 0 and parts[0] else None,
                                description=parts[1] if len(parts) > 1 and parts[1] else None,
                                technologies=techs,
                            ))

                    def _split_csv(s: str) -> list[str]:
                        return [x.strip() for x in s.split(",") if x.strip()]

                    updated_record = CandidateRecord(
                        candidate_id=rec.candidate_id,
                        resume_filename=rec.resume_filename,
                        full_name=new_name.strip() or None,
                        email=new_email.strip() or None,
                        phone=new_phone.strip() or None,
                        location=new_loc.strip() or None,
                        education=new_edu,
                        technical_skills=_split_csv(new_skills),
                        programming_languages=_split_csv(new_langs),
                        tools=_split_csv(new_tools),
                        work_experience=new_exp,
                        projects=new_proj,
                        certifications=_split_csv(new_certs),
                        linkedin_url=new_li.strip() or None,
                        github_url=new_gh.strip() or None,
                        portfolio_url=new_pf.strip() or None,
                        metadata=ExtractionMetadata(
                            processing_status=rec.metadata.processing_status,
                            extraction_method=rec.metadata.extraction_method,
                            model_used=rec.metadata.model_used,
                            extracted_at=rec.metadata.extracted_at,
                        ),
                        raw_text_snippet=rec.raw_text_snippet,
                    )
                    updated_record = validate_candidate(updated_record)
                    st.session_state.edited[filename] = updated_record
                    st.success(f"Updated record for {filename}")
                    st.rerun()

    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------
    final_records = [
        st.session_state.edited.get(rec.resume_filename, rec)
        for rec in st.session_state.candidates
    ]

    if final_records or st.session_state.failed_docs:
        st.subheader("Export")
        try:
            excel_bytes = export_to_bytes(final_records, failed_docs=st.session_state.failed_docs)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dl_filename = f"candidates_{timestamp}.xlsx"

            st.download_button(
                label=f"Download Excel workbook ({len(final_records)} candidates)",
                data=excel_bytes,
                file_name=dl_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_btn",
                type="primary",
                use_container_width=True,
            )
        except Exception as exc:
            st.error(f"Error creating Excel workbook: {exc}")