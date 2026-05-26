"""
Post-processing: normalizes dates and cleans the extracted resume JSON
so every output is structurally identical regardless of LLM variance.
"""
from __future__ import annotations

import re
from typing import Any

# ── Date normalization ───────────────────────────────────────

_MONTH_MAP = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",
    "aug": "08", "august": "08",
    "sep": "09", "september": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12",
}

_DATE_RANGE_RE = re.compile(r"(\d{4})\s*[-–—to]+\s*(\d{4}|Present)", re.IGNORECASE)
_NAMED_MONTH_RE = re.compile(
    r"(" + "|".join(_MONTH_MAP.keys()) + r")\.?\s*,?\s*(\d{4})", re.IGNORECASE
)
_YEAR_ONLY_RE = re.compile(r"^(\d{4})$")
_YM_RE = re.compile(r"^(\d{4})-(\d{2})$")


def normalize_date(value: Any) -> str | None:
    """Normalize a date string to 'YYYY-MM', or 'Present', or None."""
    if value is None:
        return None

    s = str(value).strip()
    if not s:
        return None

    # Already canonical: 2024-01
    m = _YM_RE.match(s)
    if m:
        return s

    # "Present" (case-insensitive)
    if s.lower() == "present":
        return "Present"

    # Year only: 2024 → 2024-01
    m = _YEAR_ONLY_RE.match(s)
    if m:
        return f"{s}-01"

    # Named month: "Jan 2024", "January 2024" → 2024-01
    m = _NAMED_MONTH_RE.match(s)
    if m:
        month = _MONTH_MAP[m.group(1).lower()]
        year = m.group(2)
        return f"{year}-{month}"

    # Date range like "2024 - 2025" → take start (we handle ranges elsewhere)
    m = _DATE_RANGE_RE.match(s)
    if m:
        return f"{m.group(1)}-01"

    # Fallback: return as-is if it roughly looks like a date
    if re.search(r"\d{4}", s):
        return s

    return None


def _clean_str(value: Any) -> str | None:
    """Trim whitespace; return None for empty strings."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def normalize_resume(data: dict) -> dict:
    """Normalize an entire resume dict: dates, strings, and structure."""

    # ── Personal info ──
    pi = data.get("personal_info", {}) or {}
    for key in ("full_name", "email", "phone", "location", "linkedin", "website"):
        if key in pi:
            pi[key] = _clean_str(pi[key])

    # ── Summary ──
    if "summary" in data:
        data["summary"] = _clean_str(data["summary"])

    # ── Skills ──
    skills = data.get("skills") or []
    data["skills"] = sorted(set(_clean_str(s) for s in skills if _clean_str(s)))

    # ── Experience ──
    for exp in data.get("experience") or []:
        exp["company"] = _clean_str(exp.get("company", "")) or ""
        exp["title"] = _clean_str(exp.get("title", "")) or ""
        exp["start_date"] = normalize_date(exp.get("start_date"))
        exp["end_date"] = normalize_date(exp.get("end_date"))
        exp["location"] = _clean_str(exp.get("location"))
        exp["description"] = [
            d for d in (_clean_str(d) for d in (exp.get("description") or [])) if d
        ]

    # ── Projects ──
    for proj in data.get("projects") or []:
        proj["name"] = _clean_str(proj.get("name", "")) or ""
        proj["role"] = _clean_str(proj.get("role"))
        proj["start_date"] = normalize_date(proj.get("start_date"))
        proj["end_date"] = normalize_date(proj.get("end_date"))
        proj["description"] = [
            d for d in (_clean_str(d) for d in (proj.get("description") or [])) if d
        ]

    # ── Education ──
    for edu in data.get("education") or []:
        edu["institution"] = _clean_str(edu.get("institution", "")) or ""
        edu["degree"] = _clean_str(edu.get("degree", "")) or ""
        edu["field"] = _clean_str(edu.get("field"))
        edu["graduation_year"] = normalize_date(edu.get("graduation_year"))
        # For graduation_year, strip the "-01" suffix (just keep "YYYY")
        if edu["graduation_year"] and edu["graduation_year"] != "Present":
            edu["graduation_year"] = edu["graduation_year"][:4]

    # ── Certifications ──
    certs = data.get("certifications") or []
    data["certifications"] = sorted(set(_clean_str(c) for c in certs if _clean_str(c)))

    return data
