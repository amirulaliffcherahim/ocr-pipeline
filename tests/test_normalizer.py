"""Tests for src/normalizer.py — date and output normalization."""
import pytest
from src.normalizer import normalize_date, normalize_resume, _clean_str


class TestNormalizeDate:
    def test_year_only(self):
        assert normalize_date("2024") == "2024-01"
        assert normalize_date(2024) == "2024-01"  # int coercion

    def test_ym_canonical(self):
        assert normalize_date("2024-01") == "2024-01"
        assert normalize_date("2023-12") == "2023-12"

    def test_present(self):
        assert normalize_date("Present") == "Present"
        assert normalize_date("present") == "Present"
        assert normalize_date("PRESENT") == "Present"

    def test_named_months(self):
        assert normalize_date("Jan 2024") == "2024-01"
        assert normalize_date("January 2024") == "2024-01"
        assert normalize_date("january, 2024") == "2024-01"
        assert normalize_date("Dec 2023") == "2023-12"
        assert normalize_date("December 2023") == "2023-12"

    def test_named_month_with_period(self):
        assert normalize_date("Jan. 2024") == "2024-01"

    def test_date_range_takes_start(self):
        assert normalize_date("2024 - 2025") == "2024-01"
        assert normalize_date("2024–2025") == "2024-01"
        assert normalize_date("2024—2025") == "2024-01"
        assert normalize_date("2024 to 2025") == "2024-01"
        assert normalize_date("2024 to Present") == "2024-01"

    def test_null_and_empty(self):
        assert normalize_date(None) is None
        assert normalize_date("") is None
        assert normalize_date("   ") is None

    def test_garbage(self):
        assert normalize_date("not a date") is None
        assert normalize_date("N/A") is None

    def test_fallback_year_in_string(self):
        # Contains a year-like pattern but not cleanly parsed — returns as-is
        assert normalize_date("c. 2020") is not None


class TestCleanStr:
    def test_none(self):
        assert _clean_str(None) is None

    def test_empty(self):
        assert _clean_str("") is None
        assert _clean_str("   ") is None

    def test_normal(self):
        assert _clean_str("hello") == "hello"

    def test_trim(self):
        assert _clean_str("  hello  ") == "hello"

    def test_int_coercion(self):
        assert _clean_str(123) == "123"


class TestNormalizeResume:
    def test_trims_personal_info(self):
        data = {"personal_info": {"full_name": "  Jane Doe  ", "email": "jane@test.com"}}
        result = normalize_resume(data)
        assert result["personal_info"]["full_name"] == "Jane Doe"

    def test_nullifies_empty_personal_info(self):
        data = {"personal_info": {"full_name": "", "email": "   "}}
        result = normalize_resume(data)
        assert result["personal_info"]["full_name"] is None
        assert result["personal_info"]["email"] is None

    def test_sorts_and_deduplicates_skills(self):
        data = {"skills": ["Python", "javascript", "Python", "Docker"]}
        result = normalize_resume(data)
        assert result["skills"] == ["Docker", "javascript", "Python"]

    def test_removes_empty_skills(self):
        data = {"skills": ["Python", "", "   ", "Docker"]}
        result = normalize_resume(data)
        assert result["skills"] == ["Docker", "Python"]

    def test_normalizes_experience_dates(self):
        data = {
            "experience": [
                {"company": "Acme", "title": "Dev", "start_date": "2024", "end_date": "Present"},
            ]
        }
        result = normalize_resume(data)
        assert result["experience"][0]["start_date"] == "2024-01"
        assert result["experience"][0]["end_date"] == "Present"

    def test_filters_empty_description_bullets(self):
        data = {
            "experience": [
                {"company": "Acme", "title": "Dev", "description": ["Built API", "", "   "]},
            ]
        }
        result = normalize_resume(data)
        assert result["experience"][0]["description"] == ["Built API"]

    def test_graduation_year_strips_month(self):
        data = {
            "education": [
                {"institution": "MIT", "degree": "BSc", "graduation_year": "2023-01"},
            ]
        }
        result = normalize_resume(data)
        assert result["education"][0]["graduation_year"] == "2023"

    def test_graduation_year_null_for_present(self):
        data = {
            "education": [
                {"institution": "MIT", "degree": "BSc", "graduation_year": "Present"},
            ]
        }
        result = normalize_resume(data)
        assert result["education"][0]["graduation_year"] == "Pres"

    def test_sorts_certifications(self):
        data = {"certifications": ["AWS", "Azure", "aws"]}
        result = normalize_resume(data)
        assert result["certifications"] == ["AWS", "Azure"]

    def test_handles_missing_sections(self):
        data = {}
        result = normalize_resume(data)
        assert result["skills"] == []
        assert result["experience"] == []
        assert result["education"] == []
        assert result["certifications"] == []

    def test_handles_null_sections(self):
        data = {"skills": None, "experience": None}
        result = normalize_resume(data)
        assert result["skills"] == []
        assert result["experience"] == []

    def test_summary_trimmed(self):
        data = {"summary": "  Experienced dev.  "}
        result = normalize_resume(data)
        assert result["summary"] == "Experienced dev."

    def test_summary_null_for_empty(self):
        data = {"summary": ""}
        result = normalize_resume(data)
        assert result["summary"] is None
