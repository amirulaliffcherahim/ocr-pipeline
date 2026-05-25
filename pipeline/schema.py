"""ATS-optimized resume JSON schema — standard + ATS fields.

Used both as Pydantic models for validation and as the target schema
sent to the LLM for structured extraction.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ── Sub-models ──────────────────────────────────────────────────────────────

class WorkExperience(BaseModel):
    title: str = Field(description="Job title, e.g. 'Senior Software Engineer'")
    company: str = Field(description="Company or organization name")
    location: Optional[str] = Field(default=None, description="City and state/country, e.g. 'San Francisco, CA'")
    start_date: Optional[str] = Field(default=None, description="Start date as 'YYYY-MM' or 'YYYY'")
    end_date: Optional[str] = Field(default=None, description="End date as 'YYYY-MM', 'YYYY', or 'Present'")
    is_current: bool = Field(default=False, description="True if this is the current job")
    bullets: list[str] = Field(default_factory=list, description="Achievement-oriented bullet points, 1-5 entries")


class Education(BaseModel):
    degree: str = Field(description="Degree earned, e.g. 'Bachelor of Science in Computer Science'")
    school: str = Field(description="Institution name")
    field_of_study: Optional[str] = Field(default=None, description="Major or concentration")
    start_date: Optional[str] = Field(default=None, description="Start year as 'YYYY'")
    end_date: Optional[str] = Field(default=None, description="End year as 'YYYY'")
    gpa: Optional[str] = Field(default=None, description="GPA if listed, e.g. '3.8/4.0'")


class SkillsBlock(BaseModel):
    technical: list[str] = Field(default_factory=list, description="Technical skills: languages, frameworks, tools, platforms")
    soft: list[str] = Field(default_factory=list, description="Soft skills: leadership, communication, etc.")
    languages: list[str] = Field(default_factory=list, description="Human languages spoken, e.g. 'English (Native)', 'Spanish (Fluent)'")
    certifications: list[str] = Field(default_factory=list, description="Certifications earned, e.g. 'AWS Solutions Architect'")


class Project(BaseModel):
    name: str = Field(description="Project name or title")
    description: Optional[str] = Field(default=None, description="Short 1-2 sentence summary of the project")
    url: Optional[str] = Field(default=None, description="Link to repo, demo, or live site")
    technologies: list[str] = Field(default_factory=list, description="Tech stack used in the project")


# ── Top-level resume ────────────────────────────────────────────────────────

class Resume(BaseModel):
    # Contact
    name: Optional[str] = Field(default=None, description="Full name of the candidate")
    email: Optional[str] = Field(default=None, description="Email address")
    phone: Optional[str] = Field(default=None, description="Phone number")
    location: Optional[str] = Field(default=None, description="City, state, country — e.g. 'Kuala Lumpur, Malaysia'")
    linkedin: Optional[str] = Field(default=None, description="LinkedIn profile URL")
    github: Optional[str] = Field(default=None, description="GitHub profile URL")
    website: Optional[str] = Field(default=None, description="Personal website or portfolio URL")

    # ATS summary
    headline: Optional[str] = Field(default=None, description="One-line professional headline, e.g. 'Full-Stack Developer | Cloud & AI'")
    summary: Optional[str] = Field(default=None, description="2-4 sentence professional summary paragraph")
    years_of_experience: Optional[float] = Field(default=None, description="Total years of professional experience as a float, e.g. 5.5")
    seniority_level: Optional[str] = Field(default=None, description="One of: 'Junior', 'Mid-level', 'Senior', 'Lead', 'Manager', 'Executive'")
    top_skills: list[str] = Field(default_factory=list, description="Top 5-10 most prominent skills across the resume")
    keywords: list[str] = Field(default_factory=list, description="ATS keywords: technologies, methodologies, domains mentioned")

    # Structured sections
    work_experience: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: SkillsBlock = Field(default_factory=SkillsBlock)
    projects: list[Project] = Field(default_factory=list)


# ── JSON schema for the LLM prompt ──────────────────────────────────────────

def get_json_schema_text() -> str:
    """Return a compact JSON schema description to embed in the LLM system prompt."""
    return r"""{
  "name": "string or null",
  "email": "string or null",
  "phone": "string or null",
  "location": "string or null",
  "linkedin": "string or null",
  "github": "string or null",
  "website": "string or null",
  "headline": "string or null",
  "summary": "string or null",
  "years_of_experience": "float or null",
  "seniority_level": "'Junior' | 'Mid-level' | 'Senior' | 'Lead' | 'Manager' | 'Executive' | null",
  "top_skills": ["string", "..."],
  "keywords": ["string", "..."],
  "work_experience": [
    {
      "title": "string",
      "company": "string",
      "location": "string or null",
      "start_date": "YYYY-MM or YYYY or null",
      "end_date": "YYYY-MM or YYYY or 'Present' or null",
      "is_current": "boolean",
      "bullets": ["string", "..."]
    }
  ],
  "education": [
    {
      "degree": "string",
      "school": "string",
      "field_of_study": "string or null",
      "start_date": "YYYY or null",
      "end_date": "YYYY or null",
      "gpa": "string or null"
    }
  ],
  "skills": {
    "technical": ["string", "..."],
    "soft": ["string", "..."],
    "languages": ["string", "..."],
    "certifications": ["string", "..."]
  },
  "projects": [
    {
      "name": "string",
      "description": "string or null",
      "url": "string or null",
      "technologies": ["string", "..."]
    }
  ]
}"""


def build_system_prompt() -> str:
    """Build the full system prompt for the LLM extraction stage."""
    schema = get_json_schema_text()

    return f"""You are a resume parser that extracts structured data from markdown. Your task is to read the markdown representation of a resume and output a single JSON object following the exact schema below.

RULES:
1. Extract ALL information present. Never invent or guess. If a field is not found, use null (for strings/floats) or empty array [] (for lists).
2. For years_of_experience: estimate total professional work years from the date ranges. Use null if unclear.
3. For seniority_level: infer from titles, years, and scope described. Use null if ambiguous.
4. For top_skills: pick the 5-10 most prominent technical skills mentioned.
5. For keywords: collect technologies, tools, methodologies, domains, and certifications mentioned.
6. For work_experience bullets: extract the actual bullet-point achievements. Aim for 1-5 per role.
7. Output ONLY valid JSON — no markdown fences, no preamble, no explanation.

SCHEMA:
{schema}"""
