"""
src/validator.py
================
Phase 2: Post-extraction validation and normalisation.

This module receives a CandidateRecord that has already been populated by
the parser and runs a second pass of checks:

- Email format validation.
- Phone number plausibility.
- Graduation-year plausibility.
- Duplicate education / experience detection.
- Spreadsheet formula injection sanitisation (Phase 3 safety).

It NEVER modifies the candidate's actual data — it only appends issues and
review notes to metadata.  Normalisation is limited to safe transformations
(lowercase email, strip whitespace) that do not change meaning.
"""

from __future__ import annotations

import re
from typing import Optional

from schemas.candidate import CandidateRecord

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# A reasonable range for graduation years
_MIN_GRAD_YEAR = 1950
_MAX_GRAD_YEAR = 2035

# Characters that turn a cell into a spreadsheet formula
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

# Strict email pattern for validation (different from extraction — this one
# rejects clearly malformed addresses that somehow slipped through).
_VALID_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


# ---------------------------------------------------------------------------
# Individual validators
# ---------------------------------------------------------------------------


def validate_email(email: Optional[str]) -> Optional[str]:
    """Return an issue string if *email* is malformed, else None."""
    if email is None:
        return None
    if not _VALID_EMAIL_RE.match(email):
        return f"Email '{email}' does not appear to be valid."
    return None


def validate_phone(phone: Optional[str]) -> Optional[str]:
    """Return an issue string if *phone* has an implausible digit count."""
    if phone is None:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7:
        return f"Phone '{phone}' has fewer than 7 digits — likely not a phone number."
    if len(digits) > 15:
        return f"Phone '{phone}' has more than 15 digits — likely not a phone number."
    return None


def validate_graduation_years(record: CandidateRecord) -> list[str]:
    """Return a list of issue strings for implausible graduation years."""
    issues = []
    for edu in record.education:
        for attr in ("graduation_year", "start_year"):
            raw = getattr(edu, attr)
            if raw is None:
                continue
            # Extract 4-digit year if present
            year_match = re.search(r"\b(19|20)\d{2}\b", str(raw))
            if year_match:
                year = int(year_match.group())
                if not (_MIN_GRAD_YEAR <= year <= _MAX_GRAD_YEAR):
                    issues.append(
                        f"Education {attr} '{raw}' is outside the plausible range "
                        f"({_MIN_GRAD_YEAR}–{_MAX_GRAD_YEAR})."
                    )
    return issues


def sanitise_formula_injection(value: Optional[str]) -> Optional[str]:
    """Prefix a cell value with a single quote if it starts with a formula char.

    This is a defensive measure for Phase 3 Excel export.  The original
    CandidateRecord is NOT modified — this function is called by the Excel
    exporter at write time.
    """
    if value is None:
        return None
    if any(value.startswith(prefix) for prefix in _FORMULA_PREFIXES):
        return "'" + value
    return value


def _find_duplicates(items: list, key_fn) -> list[str]:
    """Return a list of duplicate key strings found in *items*."""
    seen: set = set()
    dupes: list[str] = []
    for item in items:
        k = key_fn(item)
        if k and k in seen:
            dupes.append(str(k))
        elif k:
            seen.add(k)
    return dupes


# ---------------------------------------------------------------------------
# Main validation function
# ---------------------------------------------------------------------------


def validate_candidate(record: CandidateRecord) -> CandidateRecord:
    """Run all post-extraction validation passes on *record* in place.

    All findings are appended to ``record.metadata.validation_issues`` or
    ``record.metadata.review_notes``.  The candidate data fields themselves
    are not modified (except safe normalisations explicitly documented below).

    Safe normalisations applied:
    - Email is already lowercased by the Pydantic validator.
    - Leading/trailing whitespace on strings is stripped.

    Args:
        record: A :class:`~schemas.candidate.CandidateRecord` populated by
                the parser.

    Returns:
        The same *record* instance, with metadata updated.
    """
    # ---- Email -----------------------------------------------------------
    email_issue = validate_email(record.email)
    if email_issue:
        record.add_issue(email_issue)

    # ---- Phone -----------------------------------------------------------
    phone_issue = validate_phone(record.phone)
    if phone_issue:
        record.add_issue(phone_issue)

    # ---- Graduation years ------------------------------------------------
    for issue in validate_graduation_years(record):
        record.add_issue(issue)

    # ---- Duplicate education records ------------------------------------
    edu_dupes = _find_duplicates(
        record.education,
        lambda e: (e.institution or "") + (e.qualification or ""),
    )
    for dupe in edu_dupes:
        record.add_review_note(f"Duplicate education entry detected: '{dupe}'")

    # ---- Duplicate work experience records ------------------------------
    exp_dupes = _find_duplicates(
        record.work_experience,
        lambda e: (e.employer or "") + (e.job_title or ""),
    )
    for dupe in exp_dupes:
        record.add_review_note(f"Duplicate work experience entry detected: '{dupe}'")

    # ---- Set final processing status ------------------------------------
    if record.metadata.validation_issues and record.metadata.processing_status == "success":
        record.metadata.processing_status = "review_required"

    return record
