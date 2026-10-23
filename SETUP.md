# 🚀 ResumeDrop — Setup Guide

> **AI-powered Resume to Excel automation system**
> Works on **Windows 10/11** and **Linux (Ubuntu/Debian/Fedora)**

---

## 📋 Prerequisites

| Requirement       | Version         | Download Link                                      |
| ----------------- | --------------- | -------------------------------------------------- |
| **Python**        | 3.11 or 3.12    | [python.org/downloads](https://www.python.org/downloads/) |
| **Git**           | Any recent      | [git-scm.com](https://git-scm.com/downloads)       |
| **Groq API Key**  | Free tier works | [console.groq.com](https://console.groq.com/keys)  |
| **Ollama** *(optional)* | Latest    | [ollama.com/download](https://ollama.com/download)  |

---

## ⚡ Quick Setup (TL;DR)

```bash
git clone https://github.com/anuragrathod/ResumeDrop.git
cd ResumeDrop
pip install -r requirements.txt
cp .env.example .env        # Then add your GROQ_API_KEY
streamlit run app.py
```

---

## 🪟 Windows Setup (Step-by-Step)

### Step 1 — Install Python

1. Download Python **3.11 or 3.12** from [python.org](https://www.python.org/downloads/)
2. Run the installer
3. ✅ **Check** "Add Python to PATH" at the bottom of the installer
4. Click **Install Now**
5. Verify installation — open **Command Prompt** or **PowerShell**:
   ```cmd
   python --version
   pip --version
   ```

### Step 2 — Install Git

1. Download Git from [git-scm.com](https://git-scm.com/downloads/win)
2. Run the installer with default settings
3. Verify:
   ```cmd
   git --version
   ```

### Step 3 — Clone the Repository

```cmd
git clone https://github.com/anuragrathod/ResumeDrop.git
cd ResumeDrop
```

### Step 4 — Create a Virtual Environment (Recommended)

```cmd
python -m venv .venv
.venv\Scripts\activate
```

> 💡 You should see `(.venv)` at the beginning of your prompt.

### Step 5 — Install Dependencies

```cmd
pip install -r requirements.txt
```

> ⏳ This may take a few minutes. Docling and PyMuPDF are large packages.

### Step 6 — Configure Environment Variables

```cmd
copy .env.example .env
```

Open `.env` in Notepad and replace the placeholder with your actual API key:

```env
GROQ_API_KEY=gsk_your_actual_groq_api_key_here
```

**To get a Groq API Key:**
1. Go to [console.groq.com](https://console.groq.com/)
2. Sign up / Log in
3. Navigate to **API Keys** → **Create API Key**
4. Copy the key (starts with `gsk_`)

### Step 7 — Run the App

```cmd
streamlit run app.py
```

The app will open automatically in your browser at `http://localhost:8501` 🎉

---

## 🐧 Linux Setup (Step-by-Step)

### Step 1 — Install Python

**Ubuntu / Debian:**
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip git -y
```

**Fedora:**
```bash
sudo dnf install python3.12 python3-pip git -y
```

**Arch Linux:**
```bash
sudo pacman -S python python-pip git
```

Verify installation:
```bash
python3 --version
pip3 --version
git --version
```

### Step 2 — Clone the Repository

```bash
git clone https://github.com/anuragrathod/ResumeDrop.git
cd ResumeDrop
```

### Step 3 — Create a Virtual Environment (Recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate
```

> 💡 You should see `(.venv)` at the beginning of your prompt.

### Step 4 — Install Dependencies

```bash
pip install -r requirements.txt
```

> ⏳ This may take a few minutes.

> **Note (Ubuntu/Debian):** If you encounter issues with `python-magic`, install the system library:
> ```bash
> sudo apt install libmagic1
> ```

### Step 5 — Configure Environment Variables

```bash
cp .env.example .env
nano .env   # or use any text editor: vim, code, gedit
```

Set your Groq API key:
```env
GROQ_API_KEY=gsk_your_actual_groq_api_key_here
```

### Step 6 — Run the App

```bash
streamlit run app.py
```

The app will be available at `http://localhost:8501` 🎉

---

## 🤖 Optional: Ollama Setup (Offline AI)

ResumeDrop supports **Ollama** as a local/offline AI backend (no API key needed).

### Install Ollama

- **Windows:** Download from [ollama.com/download](https://ollama.com/download)
- **Linux:**
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ```

### Pull a Model

```bash
ollama pull qwen3:4b
```

### Usage

In the ResumeDrop app, select **"Ollama (Local)"** as the AI provider in the sidebar. No API key required.

---

## 📁 Project Structure

```
ResumeDrop/
├── app.py                  # Main Streamlit dashboard
├── pages/
│   └── e.py                # Text Extraction Inspector page
├── src/
│   ├── ai_extractor.py     # Groq/Ollama AI extraction logic
│   ├── document_reader.py  # PDF/DOCX text extraction (Docling + fallbacks)
│   ├── excel_exporter.py   # Excel file generation
│   ├── resume_parser.py    # Resume field parsing
│   ├── validator.py        # Data validation
│   └── utils.py            # Shared utilities
├── tests/                  # Unit & integration tests
├── .streamlit/
│   └── config.toml         # Streamlit theme configuration
├── .env.example            # Environment variable template
├── .env                    # Your local config (git-ignored)
├── requirements.txt        # Python dependencies
└── SETUP.md                # This file
```

---

## 🧪 Running Tests

```bash
# Run all tests
pytest tests/ --ignore=tests/test_integration_real_model.py

# Run with coverage
pytest tests/ --ignore=tests/test_integration_real_model.py --cov=src
```

---

## ❓ Troubleshooting

### `ModuleNotFoundError: No module named 'streamlit'`
You forgot to activate the virtual environment or install dependencies:
```bash
# Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

# Then
pip install -r requirements.txt
```

### `GROQ_API_KEY not found` or `AI extraction failed`
Make sure your `.env` file exists and contains a valid key:
```bash
cat .env   # Linux
type .env  # Windows
```

### `python-magic` error on Linux
Install the system library:
```bash
sudo apt install libmagic1   # Ubuntu/Debian
sudo dnf install file-libs   # Fedora
```

### `python-magic` error on Windows
Install the binary:
```cmd
pip install python-magic-bin
```

### Port 8501 already in use
Kill the existing process or use a different port:
```bash
streamlit run app.py --server.port 8502
```

### Docling installation fails
Try installing without the optional format extras first:
```bash
pip install docling-slim
```

---

## 📝 Notes

- The `.env` file is **git-ignored** — your API key will never be committed
- The app supports **PDF**, **DOCX**, and **DOC** resume formats
- Extracted data can be downloaded as **Excel (.xlsx)** files
- You can process **multiple resumes** in batch mode

---

**Made with ❤️ by [Anurag Rathod](https://github.com/anuragrathod)**
