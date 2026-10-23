"""
src/resume_parser.py
====================
Phase 2: Rule-based extraction and extraction orchestrator.

Rule-based extraction handles fields that can be found reliably with
regular expressions — primarily email, phone and profile URLs.

The orchestrator (ResumeParser) coordinates:
  1. Rule-based extraction on the cleaned text.
  2. AI-based extraction via src.ai_extractor.
  3. Merging results with explicit precedence rules.
  4. Missing-field detection and validation-issue recording.
  5. Returning a validated CandidateRecord.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from src.document_reader import DocumentResult, ProcessingStatus
from schemas.candidate import (
    CandidateRecord,
    EducationRecord,
    ExtractionMetadata,
    Project,
    WorkExperience,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled regular expressions
# ---------------------------------------------------------------------------

# Email — strict RFC-5321 local part, common TLDs
_EMAIL_RE = re.compile(
    r"(?<![^\s])([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
    re.IGNORECASE,
)

# Phone numbers — supports:
#   +91-XXXXX-XXXXX  /  +91 XXXXX XXXXX
#   0XXXXXXXXXX  (10-digit with leading 0)
#   XXXXXXXXXX   (10-digit bare)
#   +1 (XXX) XXX-XXXX  (North America)
#   +44 XXXX XXXXXX    (UK)
#   Generic: +CC XXXXXXXXXX
_PHONE_RE = re.compile(
    r"""
    (?<!\d)                         # not preceded by digit
    (?:
        # International with country code
        \+\d{1,3}[\s\-\.]?          # +91, +1, +44 …
        (?:\(?\d{1,4}\)?[\s\-\.]?)? # optional area code
        \d{3,5}[\s\-\.]?\d{3,5}    # subscriber number
        |
        # Indian with leading 0
        0\d{10}
        |
        # 10-digit bare Indian / generic
        [6-9]\d{9}                  # Indian mobile (starts 6-9)
    )
    (?!\d)                          # not followed by digit
    """,
    re.VERBOSE,
)

# LinkedIn profile URL — matches with or without https?://
_LINKEDIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-%.]+/?",
    re.IGNORECASE,
)

# GitHub profile URL — matches with or without https?://
_GITHUB_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/[\w\-]+/?",
    re.IGNORECASE,
)

# Portfolio / personal site — catches common patterns but is intentionally
# conservative to avoid matching arbitrary URLs.
_PORTFOLIO_RE = re.compile(
    r"https?://(?:www\.)?(?!linkedin\.com|github\.com|mail\.google|gmail)"
    r"[\w\-]+\.(?:io|dev|me|site|tech|app|co|com|net|org)/[\w\-./]*",
    re.IGNORECASE,
)

# Minimum phone candidate length (digits only)
_MIN_PHONE_DIGITS = 8

# Maximum plausible phone candidates to return
_MAX_PHONE_CANDIDATES = 3


# ---------------------------------------------------------------------------
# Rule-based extraction functions
# ---------------------------------------------------------------------------


def extract_email(text: str) -> Optional[str]:
    """Return the first well-formed email address found in *text*, or None.

    Returns the first match only.  If multiple emails appear we take the
    first one encountered (top-to-bottom in the resume) which is most
    likely the candidate's primary contact.
    """
    match = _EMAIL_RE.search(text)
    return match.group(1).lower() if match else None


def extract_phone(text: str) -> Optional[str]:
    """Return the most plausible phone number from *text*, or None.

    Strategy:
    - Find all pattern matches.
    - Filter out strings that are clearly not phone numbers (e.g. years,
      ID numbers, ZIP codes) by checking digit count.
    - Prefer longer matches (more digits) as they are more specific.
    - Return the first surviving candidate as a string, preserving original
      formatting (spaces, hyphens).
    """
    candidates: list[str] = []
    for match in _PHONE_RE.finditer(text):
        raw = match.group(0).strip()
        digit_count = sum(c.isdigit() for c in raw)
        if _MIN_PHONE_DIGITS <= digit_count <= 15:
            candidates.append(raw)
        if len(candidates) >= _MAX_PHONE_CANDIDATES:
            break

    if not candidates:
        return None

    # Prefer the longest (most digit-rich) match
    chosen = max(candidates, key=lambda s: sum(c.isdigit() for c in s))
    # Strip any leading non-numeric labels that may have been prefixed
    cleaned = re.sub(r"^(?:phone[-_ ]*(?:alt)?|tel|mobile|cell)\s*[:\-]?\s*", "", chosen, flags=re.IGNORECASE).strip()
    return cleaned or chosen


def extract_linkedin_url(text: str) -> Optional[str]:
    """Return the first LinkedIn profile URL found in *text*, or None."""
    match = _LINKEDIN_RE.search(text)
    if not match:
        return None
    url = match.group(0).strip().rstrip("/")
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    return url


def extract_github_url(text: str) -> Optional[str]:
    """Return the first GitHub profile URL found in *text*, or None."""
    match = _GITHUB_RE.search(text)
    if not match:
        return None
    url = match.group(0).strip().rstrip("/")
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    return url


def extract_portfolio_url(text: str) -> Optional[str]:
    """Return the first portfolio URL found in *text*, or None."""
    match = _PORTFOLIO_RE.search(text)
    return match.group(0) if match else None


_LOCATION_RE = re.compile(
    r"""
    (?:(?:map[-_ ]*marker(?:[-_ ]*alt)?|location|address|residence|city)\s*[:\-]?\s*)?
    ([A-Z][a-zA-Z\s]{1,30},\s*[A-Z][a-zA-Z\s]{1,30}(?:\s*,\s*[A-Z][a-zA-Z\s]{1,30})?)
    """,
    re.VERBOSE,
)


def extract_name(text: str) -> Optional[str]:
    """Extract candidate name from top header lines as a fallback heuristic."""
    if not text:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:8]:
        if "@" in line or "http" in line or "www." in line or ".com" in line or ".org" in line or ".in" in line:
            continue
        digits = sum(c.isdigit() for c in line)
        if digits >= 3:
            continue
        if line.startswith(("-", "*", "•", "#", ">", "|")):
            continue
        lower = line.lower()
        if any(h in lower for h in ("curriculum vitae", "resume", "cv", "profile", "contact",
                                    "experience", "education", "skills", "projects", "summary",
                                    "objective", "phone", "email", "address")):
            continue
        candidate = re.sub(r"^(?:name|candidate|user)\s*[:\-]\s*", "", line, flags=re.IGNORECASE).strip()
        if " | " in candidate:
            candidate = candidate.split(" | ")[0].strip()
        elif " - " in candidate:
            candidate = candidate.split(" - ")[0].strip()

        words = candidate.split()
        if 2 <= len(words) <= 4:
            if all(re.match(r"^[A-Za-z.\-']+$", w) for w in words):
                if candidate.isupper():
                    candidate = candidate.title()
                return candidate
    return None


def extract_location(text: str) -> Optional[str]:
    """Extract location (City, State / Country) from top resume lines."""
    if not text:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()][:15]
    for line in lines:
        match = _LOCATION_RE.search(line)
        if match:
            loc = match.group(1).strip().strip("|,;:-•")
            if not any(w in loc.lower() for w in ("university", "college", "school", "technologies", "institute", "developer", "engineer")):
                return loc
    return None


def run_rule_based_extraction(text: str) -> dict:
    """Run all rule-based extractors and return a dict of found values.

    Only fields that are reliably extractable by rules are included.
    Missing values are represented as None so the orchestrator can
    distinguish "not found" from "found an empty string".

    Args:
        text: Cleaned resume text from Phase 1.

    Returns:
        Dict with keys: email, phone, linkedin_url, github_url, portfolio_url.
    """
    return {
        "email": extract_email(text),
        "phone": extract_phone(text),
        "linkedin_url": extract_linkedin_url(text),
        "github_url": extract_github_url(text),
        "portfolio_url": extract_portfolio_url(text),
    }


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------

# Fields where rule-based extraction takes precedence over AI output.
_RULE_PRIORITY_FIELDS = {"email", "phone", "linkedin_url", "github_url", "portfolio_url"}


def _merge_results(rule_data: dict, ai_data: dict) -> dict:
    """Merge rule-based and AI extraction results with explicit precedence.

    Rules:
    - For fields in _RULE_PRIORITY_FIELDS: prefer non-None rule value.
    - If AI found a phone with country code (+) and matching rule digits, keep AI's phone.
    - For all other fields: prefer AI value when present, else keep rule value.
    - Never overwrite a known value (non-None) with None.
    - If both sources have conflicting non-None values for a priority field,
      keep the rule value and log a note.

    Args:
        rule_data: Output of run_rule_based_extraction().
        ai_data:   Parsed AI output dict (may be partial or empty).

    Returns:
        Merged dict suitable for constructing a CandidateRecord.
    """
    merged: dict = {}
    conflicts: list[str] = []

    # Start with AI data as the base (richer, covers more fields)
    merged.update(ai_data)

    # Apply rule-based fields with priority
    for field in _RULE_PRIORITY_FIELDS:
        rule_val = rule_data.get(field)
        ai_val = ai_data.get(field)

        if rule_val is not None:
            if field == "phone" and ai_val is not None:
                rule_digits = "".join(c for c in str(rule_val) if c.isdigit())
                ai_digits = "".join(c for c in str(ai_val) if c.isdigit())
                if str(ai_val).strip().startswith("+") and ai_digits.endswith(rule_digits):
                    merged[field] = ai_val
                    continue
            if ai_val is not None and ai_val != rule_val:
                conflicts.append(
                    f"{field}: rule='{rule_val}' vs ai='{ai_val}' — kept rule value"
                )
            merged[field] = rule_val
        elif ai_val is not None:
            merged[field] = ai_val
        # else: both None — leave as None

    merged["_conflicts"] = conflicts
    return merged


# ---------------------------------------------------------------------------
# Text chunking for long resumes
# ---------------------------------------------------------------------------

# Configurable limit: characters sent to the model in one call.
# Groq Llama 3.3 70B supports 128k context; 25k chars easily fits while preventing truncation.
DEFAULT_MAX_CHARS = 25_000


def _truncate_resume(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> tuple[str, bool]:
    """Return (truncated_text, was_truncated).

    Tries to truncate at a paragraph boundary to avoid cutting mid-sentence.
    """
    if len(text) <= max_chars:
        return text, False

    # Try to break at a blank line near the limit
    cutoff = text.rfind("\n\n", 0, max_chars)
    if cutoff == -1 or cutoff < max_chars // 2:
        cutoff = max_chars

    return text[:cutoff], True


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


class ResumeParser:
    """Coordinates rule-based and AI extraction for a single resume.

    Typical usage::

        parser = ResumeParser()
        candidate = parser.parse(document_result)

    Args:
        ai_extractor: An :class:`~src.ai_extractor.AIExtractor` instance.
                      Pass ``None`` to run rule-based extraction only (useful
                      for testing without Ollama).
        max_chars:    Maximum characters to send to the model per call.
    """

    def __init__(
        self,
        ai_extractor=None,  # AIExtractor | None
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> None:
        self._ai = ai_extractor
        self._max_chars = max_chars

    def parse(self, doc: DocumentResult) -> CandidateRecord:
        """Convert a DocumentResult into a CandidateRecord.

        If the document failed text extraction, a CandidateRecord is still
        returned but its metadata marks it as failed so Phase 3 can report it.

        Args:
            doc: A :class:`~src.document_reader.DocumentResult`.

        Returns:
            A populated (or minimally populated) :class:`~schemas.candidate.CandidateRecord`.
        """
        # ----- Baseline record -----------------------------------------
        record = CandidateRecord(
            resume_filename=doc.filename,
            metadata=ExtractionMetadata(
                processing_status="pending",
                extraction_method="none",
            ),
        )

        # ----- Skip failed documents -----------------------------------
        if doc.status != ProcessingStatus.SUCCESS:
            record.metadata.processing_status = "failed"
            record.metadata.validation_issues.append(
                f"Document reading failed: {doc.status.value} — {doc.error}"
            )
            return record

        text = doc.text
        record.raw_text_snippet = text[:500] if text else None

        # ----- Step 1: Rule-based extraction ---------------------------
        rule_data = run_rule_based_extraction(text)
        logger.debug(
            "[%s] Rule extraction: email=%s phone=%s",
            doc.filename,
            rule_data.get("email"),
            rule_data.get("phone"),
        )

        # ----- Step 2: AI extraction -----------------------------------
        ai_data: dict = {}
        ai_method = "rules_only"
        model_used: Optional[str] = None

        if self._ai is not None:
            truncated, was_truncated = _truncate_resume(text, self._max_chars)
            if was_truncated:
                record.add_review_note(
                    f"Resume was truncated to {self._max_chars} chars before AI extraction."
                )

            ai_result = self._ai.extract(truncated, doc.filename)
            if ai_result.success:
                ai_data = ai_result.data
                ai_method = "rules+ai"
                model_used = ai_result.model_used
            else:
                record.add_issue(f"AI extraction failed: {ai_result.error}")
                record.metadata.processing_status = "partial"
                ai_method = "rules_only"
                logger.warning("[%s] AI extraction failed: %s", doc.filename, ai_result.error)
        else:
            logger.debug("[%s] No AI extractor — using rules only.", doc.filename)

        # ----- Step 3: Merge -------------------------------------------
        merged = _merge_results(rule_data, ai_data)

        for conflict in merged.pop("_conflicts", []):
            record.add_review_note(conflict)

        # AI-mode fallbacks: if AI ran but missed name or location, use heuristics
        if self._ai is not None:
            if not merged.get("full_name"):
                name_fb = extract_name(text)
                if name_fb:
                    merged["full_name"] = name_fb
            if not merged.get("location"):
                loc_fb = extract_location(text)
                if loc_fb:
                    merged["location"] = loc_fb

        # ----- Step 4: Populate record ---------------------------------
        _populate_record(record, merged)

        # ----- Step 5: Detect missing fields ---------------------------
        _check_missing_fields(record)

        # ----- Step 6: Finalise metadata -------------------------------
        if record.metadata.processing_status == "pending":
            record.metadata.processing_status = "success"
        record.metadata.extraction_method = ai_method
        record.metadata.model_used = model_used

        return record


# ---------------------------------------------------------------------------
# Record population & normalization helpers
# ---------------------------------------------------------------------------


def _clean_name(name: Optional[str]) -> Optional[str]:
    """Clean candidate name from icons, prefixes, roles, and casing artifacts."""
    if not name or not name.strip():
        return None
    cleaned = name.strip()
    # Strip common label prefixes
    cleaned = re.sub(
        r"^(?:name\s*[:\-]|candidate\s*[:\-]|resume\s*[:\-]|cv\s*[:\-])\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    # If the model extracted name with a pipe or separator (e.g. "Anurag Rathod | Python Developer")
    if " | " in cleaned:
        parts = cleaned.split(" | ")
        cleaned = parts[0].strip()
    elif " - " in cleaned and len(cleaned.split(" - ")) == 2:
        parts = cleaned.split(" - ")
        if any(role_word in parts[1].lower() for role_word in ("developer", "engineer", "designer", "intern", "manager", "tester", "student")):
            cleaned = parts[0].strip()
    # If name is in ALL CAPS (e.g., "SARTHAK PADWAL"), convert to title case
    if cleaned.isupper() and len(cleaned) > 2:
        cleaned = cleaned.title()
    return cleaned or None


def _clean_phone(phone: Optional[str]) -> Optional[str]:
    """Clean phone string from icon labels or prefix words."""
    if not phone or not phone.strip():
        return None
    cleaned = phone.strip()
    cleaned = re.sub(r"^(?:phone[-_ ]*(?:alt)?|tel|mobile|cell)\s*[:\-]?\s*", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned or None


def _clean_location(loc: Optional[str]) -> Optional[str]:
    """Clean location string from icons, labels, or trailing separators."""
    if not loc or not str(loc).strip():
        return None
    cleaned = str(loc).strip()
    cleaned = re.sub(
        r"^(?:map[-_ ]*marker(?:[-_ ]*alt)?|location|address|city|residence|pin)\s*[:\-]?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = cleaned.strip("|,;:-•")
    return cleaned or None


def _clean_url(url: Optional[str]) -> Optional[str]:
    """Ensure URL has https:// prefix if present."""
    if not url or not url.strip():
        return None
    cleaned = url.strip().rstrip("/")
    if not cleaned.lower().startswith(("http://", "https://")):
        cleaned = "https://" + cleaned
    return cleaned


def _clean_education(edu: EducationRecord) -> EducationRecord:
    """Normalize education record (split qualification/specialization if combined)."""
    # If qualification contains " in " and specialization is missing
    # e.g. "B.Tech in Computer Engineering" -> qual: "B.Tech", spec: "Computer Engineering"
    if edu.qualification and " in " in edu.qualification and not edu.specialization:
        parts = edu.qualification.split(" in ", 1)
        edu.qualification = parts[0].strip()
        edu.specialization = parts[1].strip()
    elif edu.qualification and " - " in edu.qualification and not edu.specialization:
        parts = edu.qualification.split(" - ", 1)
        edu.qualification = parts[0].strip()
        edu.specialization = parts[1].strip()
    elif edu.qualification and ", " in edu.qualification and not edu.specialization:
        parts = edu.qualification.split(", ", 1)
        edu.qualification = parts[0].strip()
        edu.specialization = parts[1].strip()

    # If graduation_year is a range like "2023 - 2026", split start and grad year
    if edu.graduation_year and (" - " in edu.graduation_year or "–" in edu.graduation_year or " to " in edu.graduation_year):
        sep = " - " if " - " in edu.graduation_year else ("–" if "–" in edu.graduation_year else " to ")
        parts = [p.strip() for p in edu.graduation_year.split(sep, 1)]
        if len(parts) == 2:
            m_start = re.search(r"\b(19\d\d|20\d\d)\b", parts[0])
            if m_start and not edu.start_year:
                edu.start_year = m_start.group(1)
            elif not edu.start_year and parts[0]:
                edu.start_year = parts[0]

            m_end = re.search(r"\b(19\d\d|20\d\d)\b", parts[1])
            if m_end:
                edu.graduation_year = m_end.group(1)
            else:
                edu.graduation_year = parts[1]

    if edu.start_year:
        m_yr = re.search(r"\b(19\d\d|20\d\d)\b", edu.start_year)
        if m_yr:
            edu.start_year = m_yr.group(1)

    return edu


def _clean_work_experience(exp: WorkExperience) -> WorkExperience:
    """Normalize work experience record: clean bullets, split date ranges."""
    # Split combined date range in start_date if end_date is missing
    if exp.start_date and not exp.end_date:
        s_date = exp.start_date.strip()
        if " - " in s_date or "–" in s_date or " to " in s_date:
            sep = " - " if " - " in s_date else ("–" if "–" in s_date else " to ")
            parts = [p.strip() for p in s_date.split(sep, 1)]
            if len(parts) == 2:
                exp.start_date = parts[0]
                exp.end_date = parts[1]

    # Clean bullet points in responsibilities
    cleaned_resp: list[str] = []
    for r in exp.responsibilities:
        if not r or not isinstance(r, str):
            continue
        cleaned_bullet = re.sub(r"^[\s•*–\-\u2022\u25cf\u25cb\u25aa\d.]+\s*", "", r).strip()
        if cleaned_bullet:
            cleaned_resp.append(cleaned_bullet)
    exp.responsibilities = cleaned_resp

    # If responsibilities list is empty, but description has bullet lines, split it
    if not exp.responsibilities and exp.description:
        desc_lines = [line.strip() for line in exp.description.splitlines() if line.strip()]
        if len(desc_lines) > 1 or (desc_lines and re.match(r"^[\s•*–\-\u2022\u25cf]", desc_lines[0])):
            bullets = [re.sub(r"^[\s•*–\-\u2022\u25cf\u25cb\u25aa\d.]+\s*", "", line).strip() for line in desc_lines]
            exp.responsibilities = [b for b in bullets if b]
            exp.description = None

    return exp


def _clean_project(proj: Project) -> Project:
    """Normalize project name and technology tags."""
    if proj.name:
        name = proj.name.strip()
        if "|" in name:
            parts = [p.strip() for p in name.split("|", 1)]
            proj.name = parts[0].strip()
            if len(parts) > 1 and not proj.technologies:
                techs = [t.strip() for t in parts[1].split(",") if t.strip()]
                proj.technologies = techs
        elif "(" in name and name.endswith(")"):
            m = re.match(r"^(.*?)\s*\((.*?)\)$", name)
            if m:
                proj.name = m.group(1).strip()
                if not proj.technologies:
                    techs = [t.strip() for t in m.group(2).split(",") if t.strip()]
                    proj.technologies = techs
        elif " - " in name and not proj.technologies:
            parts = name.split(" - ", 1)
            sub_parts = [t.strip() for t in parts[1].split(",") if t.strip()]
            if len(sub_parts) >= 2 or any(p.lower() in ("python", "flutter", "react", "java", "api", "json") for p in sub_parts):
                proj.name = parts[0].strip()
                proj.technologies = sub_parts

    if proj.description:
        proj.description = re.sub(r"^[\s•*–\-\u2022\u25cf]+\s*", "", proj.description.strip())

    return proj


_KNOWN_LANGUAGES = {
    "python", "java", "c", "c++", "cpp", "c#", "csharp", "javascript", "typescript",
    "dart", "go", "golang", "rust", "ruby", "php", "swift", "kotlin", "scala",
    "r", "sql", "html", "css", "bash", "shell", "perl", "matlab",
}

_KNOWN_TOOLS = {
    "flutter", "firebase", "react", "angular", "vue", "next.js", "node.js", "nodejs",
    "django", "flask", "fastapi", "spring", "spring boot", "express",
    "mysql", "postgresql", "postgres", "mongodb", "sqlite", "redis", "oracle",
    "git", "github", "gitlab", "docker", "kubernetes", "postman", "android studio",
    "vs code", "vscode", "linux", "ubuntu", "aws", "azure", "gcp", "jira", "figma",
}


def _clean_skills_list(skills: list[str]) -> list[str]:
    """Clean, split comma-separated items, and deduplicate skills case-insensitively."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for s in skills:
        if not s or not isinstance(s, str):
            continue
        sub_items = [item.strip() for item in s.split(",") if item.strip()]
        for sub in sub_items:
            item = sub.strip("'\"`.,;:-•*[]()")
            if item and item.lower() not in seen:
                seen.add(item.lower())
                cleaned.append(item)
    return cleaned


def _populate_record(record: CandidateRecord, data: dict) -> None:
    """Write merged extraction data into *record* in place.

    Only writes non-None / non-empty values. Existing values are never
    overwritten with None.
    """
    raw_name = data.get("full_name")
    if raw_name:
        cleaned_name = _clean_name(raw_name)
        if cleaned_name:
            record.full_name = cleaned_name

    raw_phone = data.get("phone")
    if raw_phone:
        cleaned_phone = _clean_phone(raw_phone)
        if cleaned_phone:
            record.phone = cleaned_phone

    raw_email = data.get("email")
    if raw_email and str(raw_email).strip():
        record.email = str(raw_email).strip()

    raw_loc = data.get("location")
    if raw_loc:
        cleaned_loc = _clean_location(raw_loc)
        if cleaned_loc:
            record.location = cleaned_loc

    raw_li = data.get("linkedin_url")
    if raw_li:
        cleaned_li = _clean_url(raw_li)
        if cleaned_li:
            record.linkedin_url = cleaned_li

    raw_gh = data.get("github_url")
    if raw_gh:
        cleaned_gh = _clean_url(raw_gh)
        if cleaned_gh:
            record.github_url = cleaned_gh

    raw_pf = data.get("portfolio_url")
    if raw_pf:
        cleaned_pf = _clean_url(raw_pf)
        if cleaned_pf:
            record.portfolio_url = cleaned_pf

    # Skills lists
    tech_skills = _clean_skills_list(data.get("technical_skills") or [])
    if tech_skills:
        record.technical_skills = tech_skills

    prog_langs = _clean_skills_list(data.get("programming_languages") or [])
    if prog_langs:
        record.programming_languages = prog_langs

    tool_items = _clean_skills_list(data.get("tools") or [])
    if tool_items:
        record.tools = tool_items

    certs = _clean_skills_list(data.get("certifications") or [])
    if certs:
        record.certifications = certs

    # Education
    raw_edu = data.get("education") or []
    if raw_edu:
        education = []
        for item in raw_edu:
            if isinstance(item, dict):
                try:
                    education.append(_clean_education(EducationRecord(**item)))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Could not parse education record %s: %s", item, exc)
            elif isinstance(item, EducationRecord):
                education.append(_clean_education(item))
        if education:
            record.education = education

    # Work experience
    raw_exp = data.get("work_experience") or []
    if raw_exp:
        experiences = []
        for item in raw_exp:
            if isinstance(item, dict):
                try:
                    experiences.append(_clean_work_experience(WorkExperience(**item)))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Could not parse experience record %s: %s", item, exc)
            elif isinstance(item, WorkExperience):
                experiences.append(_clean_work_experience(item))
        if experiences:
            record.work_experience = experiences

    # Projects
    raw_proj = data.get("projects") or []
    if raw_proj:
        projects = []
        for item in raw_proj:
            if isinstance(item, dict):
                try:
                    projects.append(_clean_project(Project(**item)))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Could not parse project record %s: %s", item, exc)
            elif isinstance(item, Project):
                projects.append(_clean_project(item))
        if projects:
            record.projects = projects


# ---------------------------------------------------------------------------
# Missing-field checker
# ---------------------------------------------------------------------------

_IMPORTANT_FIELDS = [
    ("full_name", lambda r: r.full_name),
    ("email", lambda r: r.email),
    ("phone", lambda r: r.phone),
    ("education", lambda r: r.education),
    ("technical_skills", lambda r: r.technical_skills or r.programming_languages or r.tools),
]


def _check_missing_fields(record: CandidateRecord) -> None:
    """Populate record.metadata.missing_fields for fields that are absent."""
    for field_name, getter in _IMPORTANT_FIELDS:
        try:
            value = getter(record)
        except Exception:  # noqa: BLE001
            value = None

        if not value:
            record.mark_missing(field_name)
