"""
schemas/candidate.py
====================
Canonical Pydantic data model for a single candidate record.

Every successfully processed resume produces exactly one CandidateRecord.
Missing scalar values are represented as None; missing collections as [].
Nothing is ever invented to fill required fields.

Phase 2 populates this schema.
Phase 3 will serialise it to Excel.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class EducationRecord(BaseModel):
    """A single qualification / degree."""

    qualification: Optional[str] = None
    """E.g. 'B.Sc. Computer Science', 'M.Tech', 'Ph.D.'"""

    specialization: Optional[str] = None
    """E.g. 'Machine Learning', 'Information Systems'"""

    institution: Optional[str] = None
    """College or university name."""

    graduation_year: Optional[str] = None
    """4-digit year string, or original text when ambiguous (e.g. 'Expected 2025')."""

    start_year: Optional[str] = None
    """Start year if available."""

    @field_validator("graduation_year", "start_year", mode="before")
    @classmethod
    def coerce_year_to_str(cls, v: object) -> Optional[str]:
        """Accept int years from model output and convert to string."""
        if v is None:
            return None
        return str(v).strip() or None


class WorkExperience(BaseModel):
    """A single work experience entry."""

    employer: Optional[str] = None
    job_title: Optional[str] = None
    start_date: Optional[str] = None
    """Free-form date string, e.g. 'Jan 2021', '2020-06', 'Present'."""
    end_date: Optional[str] = None
    summary: Optional[str] = None
    """AI-written one-line summary of role and impact."""
    responsibilities: list[str] = Field(default_factory=list)
    """Bullet-point responsibilities as a list of strings."""
    description: Optional[str] = None
    """Free-form description when a bullet list is not available."""


class Project(BaseModel):
    """A single project entry."""

    name: Optional[str] = None
    summary: Optional[str] = None
    """AI-written one-line summary of project purpose and outcome."""
    description: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)


class ExtractionMetadata(BaseModel):
    """Records what happened during extraction — never modifies candidate data."""

    processing_status: str = "pending"
    """One of: pending | success | partial | failed | review_required"""

    missing_fields: list[str] = Field(default_factory=list)
    """Names of fields that could not be extracted."""

    validation_issues: list[str] = Field(default_factory=list)
    """Human-readable descriptions of validation problems."""

    review_notes: list[str] = Field(default_factory=list)
    """Flags raised for manual review (conflicting data, low confidence, etc.)."""

    extraction_method: str = "none"
    """How the record was built: 'rules_only' | 'ai' | 'rules+ai' | 'none'"""

    model_used: Optional[str] = None
    """The Ollama model tag that was used, e.g. 'qwen3:4b'."""

    extracted_at: Optional[str] = None
    """ISO-8601 timestamp of extraction."""


# ---------------------------------------------------------------------------
# Top-level candidate record
# ---------------------------------------------------------------------------


class CandidateRecord(BaseModel):
    """The canonical output record for a single resume.

    Every resume that Phase 1 successfully reads should produce exactly one
    CandidateRecord.  Missing values remain None / [] — they are never
    invented.
    """

    # ---- Identification --------------------------------------------------
    candidate_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resume_filename: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None

    # ---- Education -------------------------------------------------------
    education: list[EducationRecord] = Field(default_factory=list)

    # ---- Skills ----------------------------------------------------------
    technical_skills: list[str] = Field(default_factory=list)
    programming_languages: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)

    # ---- Work experience -------------------------------------------------
    work_experience: list[WorkExperience] = Field(default_factory=list)

    # ---- Projects --------------------------------------------------------
    projects: list[Project] = Field(default_factory=list)

    # ---- Additional ------------------------------------------------------
    certifications: list[str] = Field(default_factory=list)
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None

    # ---- Metadata (never exported to Excel candidate columns) ------------
    metadata: ExtractionMetadata = Field(default_factory=ExtractionMetadata)

    # ---- Source text (for debugging, not exported) -----------------------
    raw_text_snippet: Optional[str] = None
    """First 500 chars of the extracted text — useful for debugging."""

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, v: object) -> Optional[str]:
        if v is None or v == "":
            return None
        return str(v).strip().lower()

    @field_validator("phone", mode="before")
    @classmethod
    def coerce_phone(cls, v: object) -> Optional[str]:
        """Keep phone as a string; strip surrounding whitespace."""
        if v is None or v == "":
            return None
        return str(v).strip()

    @field_validator(
        "technical_skills", "programming_languages", "tools", "certifications",
        mode="before",
    )
    @classmethod
    def ensure_list(cls, v: object) -> list:
        """Tolerate None and single strings from model output."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        return list(v)

    @model_validator(mode="after")
    def stamp_extraction_time(self) -> "CandidateRecord":
        if self.metadata.extracted_at is None:
            self.metadata.extracted_at = datetime.now(timezone.utc).isoformat()
        return self

    # ---- Convenience helpers ---------------------------------------------

    def mark_missing(self, field_name: str) -> None:
        """Record that a field could not be extracted."""
        if field_name not in self.metadata.missing_fields:
            self.metadata.missing_fields.append(field_name)

    def add_issue(self, issue: str) -> None:
        """Record a validation issue."""
        self.metadata.validation_issues.append(issue)

    def add_review_note(self, note: str) -> None:
        """Flag something for manual review."""
        self.metadata.review_notes.append(note)

    @property
    def is_complete(self) -> bool:
        """True when no missing fields and no validation issues."""
        return (
            not self.metadata.missing_fields
            and not self.metadata.validation_issues
        )

    def to_flat_dict(self) -> dict:
        """Return a flat dictionary suitable for a single Excel row.

        Collections (education, experience, projects) are joined as
        semicolon-separated strings.  Used by Phase 3 Excel export.
        """
        edu_str = "; ".join(
            " ".join(filter(None, [e.qualification, e.specialization, e.institution, e.graduation_year]))
            for e in self.education
        )
        exp_str = "; ".join(
            " ".join(filter(None, [e.job_title, e.employer, e.start_date, e.end_date]))
            for e in self.work_experience
        )
        proj_str = "; ".join(p.name or "" for p in self.projects if p.name)
        skills_str = ", ".join(self.technical_skills + self.programming_languages + self.tools)

        return {
            "candidate_id": self.candidate_id,
            "resume_filename": self.resume_filename,
            "full_name": self.full_name or "",
            "email": self.email or "",
            "phone": self.phone or "",
            "location": self.location or "",
            "education": edu_str,
            "skills": skills_str,
            "work_experience": exp_str,
            "projects": proj_str,
            "certifications": "; ".join(self.certifications),
            "linkedin_url": self.linkedin_url or "",
            "github_url": self.github_url or "",
            "portfolio_url": self.portfolio_url or "",
            "processing_status": self.metadata.processing_status,
            "missing_fields": ", ".join(self.metadata.missing_fields),
            "review_notes": "; ".join(self.metadata.review_notes),
        }
