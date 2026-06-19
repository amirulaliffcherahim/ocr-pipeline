"""Tests for src/models.py — Pydantic schemas and type coercion."""
import pytest
from pydantic import ValidationError
from src.models import (
    PersonalInfo,
    Experience,
    Project,
    Education,
    ResumeData,
)


class TestPersonalInfo:
    def test_all_fields_optional(self):
        pi = PersonalInfo()
        assert pi.full_name is None
        assert pi.email is None

    def test_partial_fields(self):
        pi = PersonalInfo(full_name="Jane Doe", email="jane@test.com")
        assert pi.full_name == "Jane Doe"
        assert pi.phone is None

    def test_phone_int_coercion(self):
        pi = PersonalInfo(phone=60123456789)
        assert pi.phone == "60123456789"

    def test_phone_float_coercion(self):
        pi = PersonalInfo(phone=60123456789.0)
        assert pi.phone == "60123456789.0"

    def test_phone_none_stays_none(self):
        pi = PersonalInfo(phone=None)
        assert pi.phone is None

    def test_extra_fields_ignored(self):
        pi = PersonalInfo(full_name="Jane", extra_field="ignored")
        assert pi.full_name == "Jane"


class TestExperience:
    def test_minimal(self):
        exp = Experience(company="Acme", title="Dev")
        assert exp.company == "Acme"
        assert exp.title == "Dev"
        assert exp.start_date is None
        assert exp.description == []

    def test_date_int_coercion(self):
        exp = Experience(company="Acme", title="Dev", start_date=2024, end_date=2025)
        assert exp.start_date == "2024"
        assert exp.end_date == "2025"

    def test_description_default(self):
        exp = Experience(company="Acme", title="Dev")
        assert exp.description == []

    def test_with_description(self):
        exp = Experience(company="Acme", title="Dev", description=["Built API", "Led team"])
        assert len(exp.description) == 2


class TestProject:
    def test_minimal(self):
        proj = Project(name="My Project")
        assert proj.name == "My Project"
        assert proj.role is None

    def test_all_fields(self):
        proj = Project(
            name="My Project",
            role="Lead",
            start_date="2024-01",
            end_date="2024-06",
            description=["Did stuff"],
        )
        assert proj.role == "Lead"
        assert proj.start_date == "2024-01"


class TestEducation:
    def test_minimal(self):
        edu = Education(institution="MIT", degree="BSc")
        assert edu.institution == "MIT"
        assert edu.field is None

    def test_graduation_year_int_coercion(self):
        edu = Education(institution="MIT", degree="BSc", graduation_year=2023)
        assert edu.graduation_year == "2023"


class TestResumeData:
    def test_minimal(self):
        rd = ResumeData(personal_info=PersonalInfo())
        assert rd.personal_info.full_name is None
        assert rd.skills == []
        assert rd.experience == []

    def test_full_document(self):
        rd = ResumeData(
            personal_info=PersonalInfo(full_name="Jane Doe", email="jane@test.com"),
            summary="Experienced dev",
            skills=["Python", "JavaScript"],
            experience=[
                Experience(company="Acme", title="Dev", start_date="2022-01", end_date="Present"),
            ],
            projects=[
                Project(name="Side Project", role="Solo", description=["Built it"]),
            ],
            education=[
                Education(institution="MIT", degree="BSc", field="CS", graduation_year="2020"),
            ],
            certifications=["AWS Certified"],
        )
        assert rd.personal_info.full_name == "Jane Doe"
        assert len(rd.skills) == 2
        assert len(rd.experience) == 1
        assert len(rd.projects) == 1
        assert len(rd.education) == 1
        assert len(rd.certifications) == 1

    def test_invalid_missing_required_fields(self):
        # company and title are required on Experience
        with pytest.raises(ValidationError):
            ResumeData(
                personal_info=PersonalInfo(),
                experience=[{"description": ["missing company and title"]}],
            )

    def test_serialization(self):
        rd = ResumeData(
            personal_info=PersonalInfo(full_name="Jane"),
            skills=["Python"],
        )
        d = rd.model_dump()
        assert d["personal_info"]["full_name"] == "Jane"
        assert d["skills"] == ["Python"]
        assert d["experience"] == []
