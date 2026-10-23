# Resume-to-Excel Automation System

A local Python application that accepts multiple PDF and DOCX resumes, extracts candidate information using a locally hosted AI model (Qwen3 4B via Ollama), and exports a formatted Excel workbook — **all processing runs locally, no data leaves your machine**.

---

## Features

- **Drag-and-drop multi-file upload** (PDF and DOCX, up to 10 MB per file)
- **SHA-256 duplicate detection** — same file uploaded twice is processed once
- **Rule-based extraction** for email, phone, LinkedIn, GitHub and portfolio URLs
- **AI extraction** via Ollama + Qwen3 4B for name, location, education, skills, work experience, projects and certifications
- **Editable review interface** — correct any extraction error before export
- **5-worksheet Excel workbook** — Candidates, Education, Work Experience, Projects, Processing Log
- **Extraction accuracy evaluation** against a 25-resume synthetic dataset
- **Performance benchmark** covering reader, AI inference, full pipeline and batch processing
- **Fully local** — no cloud AI, no external APIs, no credentials required

---

## Technology Stack

| Component | Library / Tool |
|---|---|
| Document parsing | MarkItDown + PyMuPDF (PyMuPDF fallback for PDFs) |
| AI inference | Ollama (local) + Qwen3 4B model |
| Data schema | Pydantic v2 |
| Excel export | pandas + openpyxl |
| Web interface | Streamlit |
| Testing | pytest + Streamlit AppTest |

---

## System Requirements

- **Python** 3.11 or 3.12
- **RAM** ≥ 8 GB (16 GB recommended for smooth AI inference)
- **VRAM** ≥ 4 GB if using GPU acceleration (tested with NVIDIA RTX 5050 8 GB)
- **Disk** ≥ 5 GB free (Ollama model: ~2.5 GB)
- **OS** Linux, macOS, or Windows (Linux recommended)
- **Git** (optional, for cloning)

---

## Installation

### 1. Clone the Repository

```bash
git clone <repo-url>
cd resume-to-excel
```

### 2. Create and Activate a Virtual Environment

```bash
# Create
python3 -m venv .venv

# Activate — Linux / macOS
source .venv/bin/activate

# Activate — Windows
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## AI Inference Engine Setup

The application supports **Groq Cloud API** (recommended for ultra-fast, 1–2 second resume processing) as well as **local Ollama** (for 100% offline processing).

### Option A: Groq Cloud API (Recommended — Free & Fast)

Groq processes resumes in ~1–2 seconds using cloud LPUs with the **`openai/gpt-oss-120b`** or **`openai/gpt-oss-20b`** models (high intelligence, sub-second latency):

1. **Get a free API key:** Sign up at [https://console.groq.com/keys](https://console.groq.com/keys) (no credit card required).
2. **Set the environment variable** (or enter it directly into the app sidebar):
   ```bash
   export GROQ_API_KEY="gsk_your_actual_key_here"
   ```

### Option B: Local Ollama (100% Offline)

If you prefer processing offline without external network calls:

```bash
# Step 1 — Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Step 2 — Pull the Qwen3 4B model (~2.5 GB download, one-time)
ollama pull qwen3:4b

# Step 3 — Start the Ollama server (keep running in a terminal)
ollama serve

# Step 4 — Verify
curl http://localhost:11434/     # Should print: Ollama is running
ollama list                      # Should list: qwen3:4b
```

> **Rules-Only Mode:** If neither Groq nor Ollama is configured, check **Rules-only mode** in the app sidebar. Email, phone, LinkedIn, and GitHub are still extracted reliably via regex.

---

## Running the Application

```bash
# Activate venv first
source .venv/bin/activate

# Start Ollama server in a separate terminal
ollama serve

# Launch the Streamlit web interface
streamlit run app.py
# Opens at: http://localhost:8501
```

---

## How to Use the App

| Step | Action |
|---|---|
| **1. Sidebar** | Click **Check AI Status** — green ✅ means Ollama is ready. Tick **Rules-only mode** if not. |
| **2. Upload** | Drag PDF or DOCX files into the uploader. Duplicate filenames are warned. |
| **3. Process** | Click **▶️ Process Resumes**. Progress bar shows each file. Failures don't stop the batch. |
| **4. Review** | Expand any candidate row to view and edit extracted data inline. Click **💾 Save Changes**. |
| **5. Download** | Click **⬇️ Download Excel Workbook** to download a timestamped `.xlsx` file. |

---

## CLI Demo (Phase 1 — Text Extraction Only)

```bash
# Process all files in sample_resumes/
python cli_demo.py

# Process a specific directory
python cli_demo.py --dir /path/to/resumes

# Process individual files
python cli_demo.py resume1.pdf resume2.docx

# Verbose output (shows text preview)
python cli_demo.py --verbose
```

---

## Running Tests

```bash
# Activate venv
source .venv/bin/activate

# All unit tests (no Ollama required — 193 tests)
pytest tests/ -v

# With coverage report
pytest tests/ --cov=src --cov=schemas --cov-report=term-missing

# Individual test suites
pytest tests/test_document_reader.py -v    # Phase 1: 42 tests
pytest tests/test_phase2.py -v             # Phase 2: 96 tests (mocked)
pytest tests/test_excel_exporter.py -v    # Phase 3: 33 tests
pytest tests/test_app.py -v               # Phase 3: 22 Streamlit tests

# Real-model integration tests (requires Ollama running + qwen3:4b pulled)
pytest tests/test_integration_real_model.py -v
```

**Expected results (without Ollama):**

```
Phase 1  test_document_reader:  42 passed
Phase 2  test_phase2:           96 passed
Phase 3  test_excel_exporter:   33 passed
Phase 3  test_app:              22 passed
Integration:                    10 passed  ← (skipped without Ollama)
─────────────────────────────────────────
Total:  193 passed (+ 10 integration)
```

---

## Extraction Accuracy Evaluation

Evaluates field-level extraction accuracy against 25 synthetic resumes with known ground truth.

```bash
# Full AI evaluation (requires Ollama)
python scripts/evaluate_extraction.py

# Rules-only baseline
python scripts/evaluate_extraction.py --rules-only

# Quick smoke test (first 5 resumes)
python scripts/evaluate_extraction.py --limit 5

# Verbose per-field output
python scripts/evaluate_extraction.py --verbose

# Save JSON + CSV reports to a specific directory
python scripts/evaluate_extraction.py --output-dir eval_results/
```

**What is evaluated per resume:**

- Candidate name presence and partial match
- Email exact match (or correct null)
- Phone digit count (or correct null)
- Location presence
- Education record count and graduation years
- Skills presence and count
- Work experience count
- Project count
- Certification count
- LinkedIn, GitHub and portfolio URL presence

**Rules-only baseline** (regex only, no AI):

| Field | Accuracy |
|---|---|
| Email | 100% |
| Phone | 100% |
| LinkedIn URL | 91% |
| GitHub URL | 100% |
| Name | ~8% (regex cannot reliably detect names) |
| Education / Experience / Skills | ~0–8% (require AI) |

---

## Performance Benchmark

Measures extraction time on the development machine.

```bash
# Full benchmark (requires Ollama)
python scripts/benchmark.py

# Rules-only (no AI)
python scripts/benchmark.py --rules-only

# Repeat each run N times for stability
python scripts/benchmark.py --runs 3

# Save results
python scripts/benchmark.py --output-dir bench_results/
```

**Typical timings on RTX 5050 8 GB VRAM:**

| Resume length | AI inference time |
|---|---|
| Short (~500 chars) | ~8–15 s |
| Medium (~1500 chars) | ~15–30 s |
| Long (~4000+ chars) | ~30–60 s |

> First inference is slower due to model loading into VRAM. Subsequent calls are faster.

---

## Project Structure

```
resume-to-excel/
├── app.py                              # Streamlit web application (Phase 3)
├── cli_demo.py                         # CLI text-extraction demo (Phase 1)
├── requirements.txt
├── pytest.ini
├── README.md
├── .gitignore
│
├── src/
│   ├── document_reader.py              # PDF/DOCX reader, duplicate detection (Phase 1)
│   ├── utils.py                        # Hashing, file validation (Phase 1)
│   ├── resume_parser.py                # Rule-based + orchestrator (Phase 2)
│   ├── ai_extractor.py                 # Ollama integration, retry (Phase 2)
│   ├── validator.py                    # Post-extraction validation (Phase 2)
│   └── excel_exporter.py               # Excel workbook generation (Phase 3)
│
├── schemas/
│   └── candidate.py                    # Pydantic data model (Phase 2)
│
├── prompts/
│   └── extract_candidate.txt           # AI extraction prompt template (Phase 2)
│
├── eval_data/
│   └── dataset.py                      # 25-resume synthetic dataset (Phase 4)
│
├── scripts/
│   ├── evaluate_extraction.py          # Accuracy evaluation script (Phase 4)
│   └── benchmark.py                    # Performance benchmark (Phase 4)
│
├── tests/
│   ├── test_document_reader.py         # Phase 1: 42 tests
│   ├── test_phase2.py                  # Phase 2: 96 unit tests (mocked)
│   ├── test_excel_exporter.py          # Phase 3: 33 Excel tests
│   ├── test_app.py                     # Phase 3: 22 Streamlit tests
│   ├── test_integration_real_model.py  # Integration: 10 real-model tests
│   └── create_test_files.py            # Generates synthetic PDF/DOCX test files
│
├── sample_resumes/                     # Sample PDFs/DOCX (git-ignored)
├── output/                             # Excel workbook output (git-ignored)
├── eval_results/                       # Evaluation JSON/CSV reports (git-ignored)
└── bench_results/                      # Benchmark JSON reports (git-ignored)
```

---

## Excel Workbook Structure

| Worksheet | One row per… | Key columns |
|---|---|---|
| **Candidates** | Resume file | Name, email, phone, all education, skills, status, issues |
| **Education** | Degree | Qualification, institution, grad year |
| **Work Experience** | Job | Employer, title, dates, responsibilities |
| **Projects** | Project | Name, description, technologies |
| **Processing Log** | Uploaded file | Status, method, errors for failures |

All worksheets have frozen headers, autofilters, colour-coded status cells, text wrapping and formula-injection protection.

---

## Processing Status Values

| Status | Meaning |
|---|---|
| `success` | Fully extracted with no validation issues |
| `partial` | AI failed; email/phone extracted by rules |
| `review_required` | Extracted but has validation issues (bad email, unusual year, etc.) |
| `failed` | Document reading failed (corrupt, empty, password-protected) |

---

## Supported File Formats

| Format | Primary reader | Fallback |
|---|---|---|
| PDF | MarkItDown | PyMuPDF |
| DOCX | MarkItDown | — |
| PDF (scanned image) | ❌ No text extracted | Reported as empty |

---

## Known Limitations

- **Scanned PDFs** produce no text and are reported as empty. Use OCR pre-processing.
- **Multi-column PDF layouts** may extract poorly (columns merged or scrambled).
- **AI accuracy** varies by resume structure. Unusual headings can confuse the model. Use the edit interface to correct errors.
- **Long resumes** (>12 000 chars) are truncated before being sent to the model. A note is added to the candidate record.
- **Inference speed** depends on hardware. CPU-only inference is very slow (~2–5 min/resume).
- **Ollama must be manually installed** — the app cannot install it automatically.
- **First inference** after starting Ollama is slower due to model loading.

---

## Privacy and Data Handling

- All AI inference runs locally via Ollama — **no resume text leaves your machine**.
- Resume text is held **in memory only** for the current browser session.
- No API keys, credentials or cloud accounts are required.
- Spreadsheet formula injection is prevented at export time.
- The app **does not rank, score or filter applicants** — it only extracts and exports data.
- Real resumes are git-ignored and must not be committed to version control.

---

## Troubleshooting

### Ollama connection refused

```bash
# Check if the service is running
systemctl status ollama        # Linux (systemd)
ollama serve                   # Start manually if needed

# Verify port
curl http://localhost:11434/   # Should print: Ollama is running
```

### Model not found

```bash
# Pull the model
ollama pull qwen3:4b
ollama list   # Verify it appears
```

### Empty extraction (all fields missing)

- Check that the resume is not a scanned image (open it and try to copy text).
- Try a different PDF reader: `python cli_demo.py yourfile.pdf --verbose` to see the extracted text.
- Enable verbose logging: set `LOGLEVEL=DEBUG` before running.

### Streamlit "ScriptRunContext" warnings in tests

These are normal when running Streamlit in headless AppTest mode. They do not indicate test failures.

### Out-of-memory errors during inference

- Close other applications to free RAM/VRAM.
- Reduce the number of simultaneous uploads.
- Consider a smaller model (e.g. `qwen3:1.7b`): change the model name in the sidebar.

### Evaluation script exits with code 1

The script returns exit code 1 if overall accuracy drops below 50%. This is a quality gate, not a crash. Check the printed report and JSON output for details.

---

## Running with a Different Model

The model can be changed from the sidebar. Any Ollama-supported model that outputs JSON reliably can be used. The prompt template is in `prompts/extract_candidate.txt`.

```bash
# Pull an alternative model
ollama pull llama3.2:3b
ollama pull mistral:7b

# Then select it in the sidebar
```

---

## Regenerating Synthetic Test Resumes

```bash
python tests/create_test_files.py
# Creates alice_chen_resume.pdf and bob_patel_resume.docx in sample_resumes/
```
