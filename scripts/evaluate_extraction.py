"""
scripts/evaluate_extraction.py
================================
Phase 4: Field-level accuracy evaluation against the synthetic dataset.

Usage:
    # AI-enabled (requires Ollama + qwen3:4b running):
    python scripts/evaluate_extraction.py

    # Rules-only mode:
    python scripts/evaluate_extraction.py --rules-only

    # Save JSON + CSV results:
    python scripts/evaluate_extraction.py --output-dir eval_results/

    # Limit to first N resumes (for quick smoke tests):
    python scripts/evaluate_extraction.py --limit 5

    # Verbose: show per-resume details:
    python scripts/evaluate_extraction.py --verbose
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

# Ensure project root is on sys.path when run directly
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from eval_data.dataset import DATASET
from schemas.candidate import CandidateRecord
from src.ai_extractor import AIConfig, AIExtractor, check_ollama_running, check_model_available
from src.document_reader import DocumentResult, ProcessingStatus
from src.resume_parser import ResumeParser
from src.validator import validate_candidate

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FieldResult:
    field: str
    expected: object
    got: object
    correct: bool
    note: str = ""


@dataclass
class ResumeResult:
    resume_id: str
    notes: str
    processing_status: str
    extraction_method: str
    duration_s: float
    fields: list[FieldResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def correct_count(self) -> int:
        return sum(1 for f in self.fields if f.correct)

    @property
    def total_count(self) -> int:
        return len(self.fields)

    @property
    def accuracy(self) -> float:
        return self.correct_count / self.total_count if self.total_count else 0.0


@dataclass
class EvalReport:
    model: str
    rules_only: bool
    evaluated_at: str
    resume_count: int
    total_fields: int
    correct_fields: int
    resume_results: list[ResumeResult] = field(default_factory=list)

    @property
    def overall_accuracy(self) -> float:
        return self.correct_fields / self.total_fields if self.total_fields else 0.0

    @property
    def per_field_accuracy(self) -> dict[str, dict]:
        acc: dict[str, list[bool]] = {}
        for rr in self.resume_results:
            for fr in rr.fields:
                acc.setdefault(fr.field, []).append(fr.correct)
        return {
            f: {"correct": sum(v), "total": len(v),
                "accuracy": sum(v) / len(v) if v else 0.0}
            for f, v in acc.items()
        }


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _norm_str(s: object) -> str:
    """Lowercase, strip, collapse whitespace."""
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _digits_only(s: object) -> str:
    if s is None:
        return ""
    return re.sub(r"\D", "", str(s))


def _extract_year(s: object) -> str:
    if s is None:
        return ""
    m = re.search(r"\b(19|20)\d{2}\b", str(s))
    return m.group() if m else ""


def _norm_list(lst: list[str]) -> set[str]:
    return {_norm_str(x) for x in lst if x}


# ---------------------------------------------------------------------------
# Per-field checkers
# ---------------------------------------------------------------------------

def _check_name(rec: CandidateRecord, exp: dict) -> FieldResult:
    exp_name = exp.get("full_name")
    got = rec.full_name
    if exp_name is None:
        # No expected name — skip
        return FieldResult("full_name", None, got, True, "no expectation")
    correct = exp_name is not None and _norm_str(exp_name) in _norm_str(got)
    return FieldResult("full_name", exp_name, got, correct)


def _check_email(rec: CandidateRecord, exp: dict) -> FieldResult:
    exp_email = exp.get("email", "SKIP")
    if exp_email == "SKIP":
        return FieldResult("email", "SKIP", rec.email, True, "not tested")
    got = rec.email
    if exp_email is None:
        correct = got is None or got == ""
        return FieldResult("email", None, got, correct,
                           "email must be absent" if not correct else "")
    correct = _norm_str(exp_email) == _norm_str(got)
    return FieldResult("email", exp_email, got, correct)


def _check_phone(rec: CandidateRecord, exp: dict) -> FieldResult:
    exp_phone = exp.get("phone", "SKIP")
    if exp_phone == "SKIP":
        # Check min digits if specified
        min_digits = exp.get("phone_digits_min")
        if min_digits is not None:
            got = rec.phone
            digits = len(_digits_only(got))
            correct = got is not None and digits >= min_digits
            return FieldResult("phone", f"≥{min_digits} digits", got, correct)
        return FieldResult("phone", "SKIP", rec.phone, True, "not tested")
    got = rec.phone
    if exp_phone is None:
        correct = got is None or got == ""
        return FieldResult("phone", None, got, correct)
    correct = _digits_only(exp_phone) == _digits_only(got)
    return FieldResult("phone", exp_phone, got, correct)


def _check_location(rec: CandidateRecord, exp: dict) -> FieldResult:
    exp_loc = exp.get("location", "SKIP")
    if exp_loc == "SKIP":
        return FieldResult("location", "SKIP", rec.location, True, "not tested")
    got = rec.location
    if exp_loc is None:
        correct = got is None or got == ""
        return FieldResult("location", None, got, correct)
    correct = _norm_str(exp_loc) in _norm_str(got)
    return FieldResult("location", exp_loc, got, correct)


def _check_education_count(rec: CandidateRecord, exp: dict) -> list[FieldResult]:
    results = []
    exp_count = exp.get("education_count")
    exp_count_min = exp.get("education_count_min")
    got = len(rec.education)

    if exp_count is not None:
        correct = got == exp_count
        results.append(FieldResult("education_count", exp_count, got, correct))
    elif exp_count_min is not None:
        correct = got >= exp_count_min
        results.append(FieldResult("education_count", f"≥{exp_count_min}", got, correct))

    # Check graduation years
    exp_years = exp.get("graduation_years", [])
    if exp_years:
        got_years = {_extract_year(e.graduation_year) for e in rec.education}
        for yr in exp_years:
            correct = yr in got_years
            results.append(FieldResult("graduation_year", yr, list(got_years), correct))

    return results


def _check_skills(rec: CandidateRecord, exp: dict) -> list[FieldResult]:
    results = []
    has_skills = exp.get("has_technical_skills")
    if has_skills is not None:
        all_skills = rec.technical_skills + rec.programming_languages + rec.tools
        got_bool = len(all_skills) > 0
        results.append(FieldResult("has_technical_skills", has_skills, got_bool, got_bool == has_skills))

    min_count = exp.get("skills_count_min")
    if min_count is not None:
        all_skills = rec.technical_skills + rec.programming_languages + rec.tools
        got = len(all_skills)
        results.append(FieldResult("skills_count_min", f"≥{min_count}", got, got >= min_count))

    return results


def _check_experience(rec: CandidateRecord, exp: dict) -> list[FieldResult]:
    results = []
    exp_count = exp.get("work_experience_count")
    if exp_count is not None:
        got = len(rec.work_experience)
        correct = got == exp_count
        results.append(FieldResult("work_experience_count", exp_count, got, correct))
    return results


def _check_projects(rec: CandidateRecord, exp: dict) -> list[FieldResult]:
    results = []
    exp_count = exp.get("project_count")
    if exp_count is not None:
        got = len(rec.projects)
        correct = got == exp_count
        results.append(FieldResult("project_count", exp_count, got, correct))
    return results


def _check_certifications(rec: CandidateRecord, exp: dict) -> list[FieldResult]:
    results = []
    exp_count = exp.get("certification_count")
    if exp_count is not None:
        got = len(rec.certifications)
        correct = got == exp_count
        results.append(FieldResult("certification_count", exp_count, got, correct))
    return results


def _check_urls(rec: CandidateRecord, exp: dict) -> list[FieldResult]:
    results = []
    if "linkedin_url_present" in exp:
        expected = exp["linkedin_url_present"]
        got = rec.linkedin_url is not None and rec.linkedin_url != ""
        results.append(FieldResult("linkedin_url_present", expected, got, got == expected))

    if "github_url_present" in exp:
        expected = exp["github_url_present"]
        got = rec.github_url is not None and rec.github_url != ""
        results.append(FieldResult("github_url_present", expected, got, got == expected))

    if "portfolio_url_present" in exp:
        expected = exp["portfolio_url_present"]
        got = rec.portfolio_url is not None and rec.portfolio_url != ""
        results.append(FieldResult("portfolio_url_present", expected, got, got == expected))

    return results


def evaluate_record(rec: CandidateRecord, exp: dict) -> list[FieldResult]:
    """Return all FieldResult objects for one resume."""
    fields: list[FieldResult] = []
    fields.append(_check_name(rec, exp))
    fields.append(_check_email(rec, exp))
    fields.append(_check_phone(rec, exp))
    fields.append(_check_location(rec, exp))
    fields.extend(_check_education_count(rec, exp))
    fields.extend(_check_skills(rec, exp))
    fields.extend(_check_experience(rec, exp))
    fields.extend(_check_projects(rec, exp))
    fields.extend(_check_certifications(rec, exp))
    fields.extend(_check_urls(rec, exp))
    # Remove "not tested" entries from counting
    return [f for f in fields if f.note != "not tested"]


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------

def run_evaluation(
    rules_only: bool = False,
    model: str = "qwen3:4b",
    host: str = "http://localhost:11434",
    limit: int | None = None,
    verbose: bool = False,
) -> EvalReport:

    dataset = DATASET[:limit] if limit else DATASET
    print(f"\n{'='*60}")
    print(f"  Resume Extraction Accuracy Evaluation")
    print(f"  Mode:  {'Rules only' if rules_only else f'AI ({model})'}")
    print(f"  Items: {len(dataset)}")
    print(f"{'='*60}\n")

    # Build extractor
    extractor = None
    if not rules_only:
        running, msg = check_ollama_running(host)
        if not running:
            print(f"⚠️  Ollama not reachable ({msg}). Falling back to rules-only mode.")
            rules_only = True
        else:
            ok, msg2 = check_model_available(model, host)
            if not ok:
                print(f"⚠️  Model not available ({msg2}). Falling back to rules-only.")
                rules_only = True
            else:
                extractor = AIExtractor(AIConfig(model=model, host=host, temperature=0.0, think=False))

    parser = ResumeParser(ai_extractor=extractor)

    resume_results: list[ResumeResult] = []

    for entry in dataset:
        rid   = entry["id"]
        text  = entry["text"]
        exp   = entry["expected"]
        notes = entry.get("notes", "")

        print(f"  Processing {rid} …", end="", flush=True)
        t0 = time.monotonic()

        doc = DocumentResult(
            filename=f"{rid}.txt",
            status=ProcessingStatus.SUCCESS,
            text=text,
            file_hash=rid,
        )

        try:
            rec = parser.parse(doc)
            rec = validate_candidate(rec)
        except Exception as exc:  # noqa: BLE001
            dur = time.monotonic() - t0
            print(f" ❌ ERROR: {exc}")
            resume_results.append(ResumeResult(
                resume_id=rid, notes=notes,
                processing_status="error",
                extraction_method="none",
                duration_s=dur,
                errors=[str(exc)],
            ))
            continue

        dur = time.monotonic() - t0
        fields = evaluate_record(rec, exp)
        correct = sum(1 for f in fields if f.correct)
        total   = len(fields)
        pct     = correct / total * 100 if total else 0

        status_icon = "✅" if pct >= 80 else ("⚠️" if pct >= 50 else "❌")
        print(f" {status_icon} {correct}/{total} ({pct:.0f}%)  [{dur:.1f}s]")

        if verbose:
            for fr in fields:
                icon = "✓" if fr.correct else "✗"
                print(f"      {icon} {fr.field:30s} expected={str(fr.expected)[:40]:40s} got={str(fr.got)[:40]}")

        rr = ResumeResult(
            resume_id=rid, notes=notes,
            processing_status=rec.metadata.processing_status,
            extraction_method=rec.metadata.extraction_method,
            duration_s=round(dur, 2),
            fields=fields,
        )
        if rec.metadata.validation_issues:
            rr.errors = rec.metadata.validation_issues

        resume_results.append(rr)

    # Build report
    total_fields   = sum(rr.total_count for rr in resume_results)
    correct_fields = sum(rr.correct_count for rr in resume_results)

    report = EvalReport(
        model=model if not rules_only else "rules_only",
        rules_only=rules_only,
        evaluated_at=datetime.now().isoformat(),
        resume_count=len(resume_results),
        total_fields=total_fields,
        correct_fields=correct_fields,
        resume_results=resume_results,
    )

    return report


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------

def print_report(report: EvalReport) -> None:
    print(f"\n{'='*60}")
    print("  EVALUATION RESULTS")
    print(f"{'='*60}")
    print(f"  Model:          {report.model}")
    print(f"  Resumes:        {report.resume_count}")
    print(f"  Fields checked: {report.total_fields}")
    print(f"  Correct:        {report.correct_fields}")
    print(f"  Overall acc.:   {report.overall_accuracy*100:.1f}%")
    print(f"\n  Per-field accuracy:")
    for fname, data in sorted(report.per_field_accuracy.items()):
        bar = "█" * int(data["accuracy"] * 20)
        print(f"    {fname:30s} {data['correct']:3d}/{data['total']:3d}  {data['accuracy']*100:5.1f}%  {bar}")

    failed = [rr for rr in report.resume_results if rr.accuracy < 0.5]
    if failed:
        print(f"\n  ⚠️  Low-accuracy resumes ({len(failed)}):")
        for rr in failed:
            print(f"    {rr.resume_id:30s}  {rr.accuracy*100:.0f}%  [{rr.notes}]")

    print(f"\n  Avg. time/resume: {sum(r.duration_s for r in report.resume_results)/max(1,len(report.resume_results)):.1f}s")
    print(f"  Total wall time:  {sum(r.duration_s for r in report.resume_results):.1f}s")


def save_report(report: EvalReport, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON
    json_path = output_dir / f"eval_{ts}.json"
    payload = {
        "summary": {
            "model": report.model,
            "rules_only": report.rules_only,
            "evaluated_at": report.evaluated_at,
            "resume_count": report.resume_count,
            "total_fields": report.total_fields,
            "correct_fields": report.correct_fields,
            "overall_accuracy": round(report.overall_accuracy, 4),
        },
        "per_field": report.per_field_accuracy,
        "resumes": [
            {
                "id": rr.resume_id,
                "notes": rr.notes,
                "processing_status": rr.processing_status,
                "extraction_method": rr.extraction_method,
                "duration_s": rr.duration_s,
                "accuracy": round(rr.accuracy, 4),
                "correct": rr.correct_count,
                "total": rr.total_count,
                "fields": [
                    {"field": f.field, "expected": str(f.expected),
                     "got": str(f.got), "correct": f.correct, "note": f.note}
                    for f in rr.fields
                ],
                "errors": rr.errors,
            }
            for rr in report.resume_results
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  💾 JSON saved: {json_path}")

    # CSV
    import csv
    csv_path = output_dir / f"eval_{ts}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["resume_id", "notes", "field", "expected", "got", "correct"])
        for rr in report.resume_results:
            for fr in rr.fields:
                writer.writerow([rr.resume_id, rr.notes, fr.field,
                                  str(fr.expected), str(fr.got), fr.correct])
    print(f"  💾 CSV saved:  {csv_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate extraction accuracy against the synthetic dataset."
    )
    parser.add_argument("--rules-only", action="store_true",
                        help="Skip AI, use rule-based extraction only.")
    parser.add_argument("--model", default="qwen3:4b",
                        help="Ollama model tag (default: qwen3:4b).")
    parser.add_argument("--host", default="http://localhost:11434",
                        help="Ollama server URL.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only evaluate the first N resumes.")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print per-field results for each resume.")
    parser.add_argument("--output-dir", default="eval_results/",
                        help="Directory to save JSON and CSV reports.")
    args = parser.parse_args()

    report = run_evaluation(
        rules_only=args.rules_only,
        model=args.model,
        host=args.host,
        limit=args.limit,
        verbose=args.verbose,
    )
    print_report(report)
    save_report(report, Path(args.output_dir))

    # Exit 1 if overall accuracy is below 50%
    return 0 if report.overall_accuracy >= 0.50 else 1


if __name__ == "__main__":
    sys.exit(main())
