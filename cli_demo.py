"""
cli_demo.py
===========
Phase 1 CLI demonstration — preserved from the original app.py.

Processes PDF and DOCX resumes from a directory and prints a
formatted per-file status report.  Useful for quick smoke-testing
without starting the Streamlit server.

Usage (from the project root with the virtual environment active):

    python cli_demo.py
    python cli_demo.py --dir path/to/folder
    python cli_demo.py file1.pdf file2.docx
    python cli_demo.py --verbose
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.document_reader import DocumentReader, ProcessingStatus

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

_COLOURS_ENABLED = sys.stdout.isatty()


def _colour(code: str, text: str) -> str:
    if not _COLOURS_ENABLED:
        return text
    return f"\033[{code}m{text}\033[0m"


GREEN  = lambda t: _colour("32", t)   # noqa: E731
YELLOW = lambda t: _colour("33", t)   # noqa: E731
RED    = lambda t: _colour("31", t)   # noqa: E731
CYAN   = lambda t: _colour("36", t)   # noqa: E731
BOLD   = lambda t: _colour("1",  t)   # noqa: E731

_STATUS_ICONS = {
    ProcessingStatus.SUCCESS:           "✅",
    ProcessingStatus.EMPTY:             "⚠️ ",
    ProcessingStatus.EMPTY_FILE:        "⚠️ ",
    ProcessingStatus.UNSUPPORTED_FORMAT:"❌",
    ProcessingStatus.FILE_TOO_LARGE:    "❌",
    ProcessingStatus.DUPLICATE:         "🔁",
    ProcessingStatus.CORRUPT:           "💥",
    ProcessingStatus.PASSWORD_PROTECTED:"🔒",
    ProcessingStatus.ERROR:             "❌",
}


def collect_files(sources: list[str]) -> list[Path]:
    collected: list[Path] = []
    for src in sources:
        p = Path(src)
        if p.is_dir():
            for ext in ("*.pdf", "*.PDF", "*.docx", "*.DOCX"):
                collected.extend(sorted(p.glob(ext)))
        elif p.is_file():
            collected.append(p)
        else:
            print(YELLOW(f"  Warning: '{src}' does not exist — skipped."))
    return collected


def print_result(result) -> None:
    icon   = _STATUS_ICONS.get(result.status, "?")
    status = result.status.value.upper().replace("_", " ")
    colour = GREEN if result.status == ProcessingStatus.SUCCESS else (
        YELLOW if result.status in (ProcessingStatus.DUPLICATE, ProcessingStatus.EMPTY, ProcessingStatus.EMPTY_FILE)
        else RED
    )
    print(f"\n  {icon}  {BOLD(result.filename)}")
    print(f"      Status   : {colour(status)}")
    print(f"      Chars    : {result.char_count:,}")
    if result.file_hash:
        print(f"      SHA-256  : {result.file_hash[:16]}…")
    if result.error:
        print(f"      Error    : {result.error}")
    if result.text:
        preview = result.text[:300].replace("\n", "↵ ")
        if len(result.text) > 300:
            preview += " …"
        print(f"      Preview  : {CYAN(preview)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 1 CLI: Extract text from PDF/DOCX resumes.")
    parser.add_argument("sources", nargs="*", help="Files or directories to process.")
    parser.add_argument("--dir", metavar="DIR", help="Process all PDF/DOCX in this directory.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable DEBUG logging.")
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    sources = list(args.sources)
    if args.dir:
        sources.append(args.dir)
    if not sources:
        sources = ["sample_resumes"]

    files = collect_files(sources)

    print(BOLD("\n" + "=" * 60))
    print(BOLD("  Resume-to-Excel  ·  Phase 1 CLI Demo"))
    print(BOLD("=" * 60))

    if not files:
        print(YELLOW("\n  No PDF or DOCX files found."))
        print("  Generate synthetic test files with:\n    python tests/create_test_files.py\n")
        return 0

    print(f"\n  Files found : {len(files)}\n  Processing  …")

    reader  = DocumentReader()
    results = reader.process_files(files)

    print(BOLD("\n" + "-" * 60 + "\n  Per-file Results\n" + "-" * 60))
    for r in results:
        print_result(r)

    success = sum(1 for r in results if r.status == ProcessingStatus.SUCCESS)
    failed  = len(results) - success
    print(BOLD("\n" + "=" * 60 + "\n  Batch Summary\n" + "=" * 60))
    print(f"  Total files : {len(results)}")
    print(f"  {GREEN('Succeeded')}  : {success}")
    print(f"  {RED('Failed')}     : {failed}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
