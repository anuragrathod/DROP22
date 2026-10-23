"""
pages/e.py
==========
Extracted Text Viewer
Accessible at: http://localhost:8501/e

A dedicated, minimalist page to upload a resume and inspect the exact text
extracted by DocumentReader (PyMuPDF / MarkItDown).
"""

from __future__ import annotations

import html
from pathlib import Path
# pyrefly: ignore[missing-import]
import streamlit as st

st.set_page_config(
    page_title="Extracted text · ResumeDrop",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from src.document_reader import DocumentReader, DocumentResult, ProcessingStatus

# ---------------------------------------------------------------------------
# Design system (same tokens as app.py)
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
[data-testid="stSidebar"] { background: var(--sidebar); border-right: 1px solid var(--line); }
.block-container {
    max-width: 1080px;
    padding: 2.5rem clamp(1rem, 4vw, 2.5rem) 4rem !important;
}

/* Header */
.rd-back { color: var(--accent); text-decoration: none; font-size: 0.9rem; font-weight: 500; }
.rd-back:hover { text-decoration: underline; }
.rd-title {
    font-size: clamp(2rem, 4.5vw, 2.75rem);
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1.1;
    margin: 1rem 0 0.5rem 0;
    color: var(--text);
}
.rd-lede { font-size: 1.05rem; line-height: 1.5; color: var(--muted); margin: 0 0 1.75rem 0; max-width: 38rem; }

/* Result summary */
.rd-meta { margin: 1.25rem 0 0.75rem 0; font-size: 0.95rem; color: var(--text); overflow-wrap: anywhere; }
.rd-meta strong { font-weight: 600; }
.rd-meta span { color: var(--muted); font-size: 0.85rem; margin-left: 8px; }

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

/* Buttons */
.stButton > button,
.stDownloadButton > button {
    min-height: 2.6rem;
    border-radius: 980px;
    font-weight: 500;
    font-size: 0.92rem;
    border: 1px solid var(--line-strong) !important;
    background: var(--surface) !important;
    color: var(--text) !important;
    box-shadow: none !important;
    transition: background-color 0.15s ease, border-color 0.15s ease;
}
.stButton > button:hover,
.stDownloadButton > button:hover { background: #f5f5f7 !important; border-color: rgba(0, 0, 0, 0.35) !important; }
.stDownloadButton > button[kind="primary"],
button[data-testid="stBaseButton-primary"] {
    background: var(--accent) !important;
    border-color: var(--accent) !important;
    color: #ffffff !important;
}
.stDownloadButton > button[kind="primary"]:hover,
button[data-testid="stBaseButton-primary"]:hover {
    background: var(--accent-hover) !important;
    border-color: var(--accent-hover) !important;
}
.stDownloadButton > button[kind="primary"] p,
button[data-testid="stBaseButton-primary"] p { color: #ffffff !important; }
button:focus-visible, summary:focus-visible { outline: 3px solid rgba(0, 113, 227, 0.3) !important; outline-offset: 2px; }

/* Extracted text: one bordered surface, no nested boxes */
[data-testid="stCodeBlock"] {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    box-shadow: none;
}
[data-testid="stCodeBlock"] pre { background: transparent !important; padding: 1rem 1.25rem !important; }
[data-testid="stCodeBlock"] code {
    font-family: "SF Mono", "Fira Code", Menlo, Monaco, Consolas, monospace !important;
    font-size: 0.88rem !important;
    line-height: 1.6 !important;
    color: #1f2328 !important;
}

/* Alerts */
[data-testid="stAlert"] { border-radius: var(--radius); box-shadow: none; }
[data-testid="stAlert"] p { font-size: 0.88rem; }

@media (max-width: 640px) {
    .block-container { padding-top: 1.5rem !important; }
    .stDownloadButton > button { width: 100%; }
}
@media (prefers-reduced-motion: reduce) {
    * { transition: none !important; }
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<a class="rd-back" href="/" target="_self">← ResumeDrop</a>
<h1 class="rd-title">Extracted text</h1>
<p class="rd-lede">Upload a resume to see the exact text extracted from it.</p>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Upload Section
# ---------------------------------------------------------------------------
uploaded_file = st.file_uploader(
    "Upload a resume (PDF or DOCX)",
    type=["pdf", "docx"],
    accept_multiple_files=False,
    key="raw_text_uploader",
    help="Upload a single PDF or DOCX file to extract and inspect its text.",
    label_visibility="collapsed",
)

# ---------------------------------------------------------------------------
# Text Extraction & Display
# ---------------------------------------------------------------------------
if uploaded_file:
    reader = DocumentReader()
    raw_bytes = uploaded_file.getvalue()
    doc_result: DocumentResult = reader.process_bytes(raw_bytes, uploaded_file.name)

    if doc_result.status == ProcessingStatus.SUCCESS:
        text = doc_result.text
        char_count = len(text)
        word_count = len(text.split())
        line_count = len(text.splitlines())

        col_info, col_dl = st.columns([3, 1], vertical_alignment="center")
        with col_info:
            st.markdown(
                f'<div class="rd-meta"><strong>{html.escape(uploaded_file.name)}</strong>'
                f"<span>{char_count:,} characters · {word_count:,} words · {line_count:,} lines</span></div>",
                unsafe_allow_html=True,
            )

        with col_dl:
            base_name = Path(uploaded_file.name).stem
            st.download_button(
                label="Download .txt",
                data=text,
                file_name=f"{base_name}_extracted.txt",
                mime="text/plain",
                type="primary",
                use_container_width=True,
                key="download_raw_txt",
            )

        st.code(text, language="text", wrap_lines=True)

    else:
        st.error(f"Failed to extract text from {uploaded_file.name}: {doc_result.error}")
else:
    st.info("Upload a resume above to see its extracted text.")