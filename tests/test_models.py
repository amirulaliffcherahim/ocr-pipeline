"""Tests for src/models.py — Pydantic schemas and type coercion."""
import pytest
from pydantic import ValidationError
from src.models import (
    PersonalInfo,
    Experience,
    Project,
    Education,
    Certification,
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
        assert edu.graduation_year is None

    def test_graduation_year_int_coercion(self):
        edu = Education(institution="MIT", degree="BSc", graduation_year=2023)
        assert edu.graduation_year == "2023"

    def test_result_field(self):
        edu = Education(institution="MIT", degree="BSc", result="CGPA: 3.8")
        assert edu.result == "CGPA: 3.8"

    def test_result_int_coercion(self):
        edu = Education(institution="MIT", degree="BSc", result=3.8)
        assert edu.result == "3.8"

    def test_result_none_by_default(self):
        edu = Education(institution="MIT", degree="BSc")
        assert edu.result is None


class TestCertification:
    def test_minimal(self):
        cert = Certification(name="AWS Solutions Architect")
        assert cert.name == "AWS Solutions Architect"
        assert cert.institute is None
        assert cert.level is None

    def test_full(self):
        cert = Certification(
            name="AWS Solutions Architect",
            institute="Amazon",
            validity_start="2023-06",
            validity_end="2026-06",
            level="Professional",
        )
        assert cert.institute == "Amazon"
        assert cert.level == "Professional"
        assert cert.validity_start == "2023-06"

    def test_date_int_coercion(self):
        cert = Certification(
            name="AWS SA",
            validity_start=2023,
            validity_end=2026,
        )
        assert cert.validity_start == "2023"
        assert cert.validity_end == "2026"


class TestResumeData:
    def test_minimal(self):
        rd = ResumeData(personal_info=PersonalInfo())
        assert rd.personal_info.full_name is None
        assert rd.skills == []
        assert rd.tags == []
        assert rd.experience == []

    def test_full_document(self):
        rd = ResumeData(
            personal_info=PersonalInfo(full_name="Jane Doe", email="jane@test.com"),
            summary="Experienced dev",
            skills=["Python", "JavaScript"],
            tags=["Software Engineer", "Python Dev", "Full Stack"],
            experience=[
                Experience(company="Acme", title="Dev", start_date="2022-01", end_date="Present"),
            ],
            projects=[
                Project(name="Side Project", role="Solo", description=["Built it"]),
            ],
            education=[
                Education(institution="MIT", degree="BSc", graduation_year="2020", result="CGPA: 3.8"),
            ],
            certifications=[Certification(name="AWS Certified")],
        )
        assert rd.personal_info.full_name == "Jane Doe"
        assert len(rd.skills) == 2
        assert len(rd.tags) == 3
        assert len(rd.experience) == 1
        assert len(rd.projects) == 1
        assert len(rd.education) == 1
        assert rd.education[0].result == "CGPA: 3.8"
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
            tags=["Software Engineer"],
        )
        d = rd.model_dump()
        assert d["personal_info"]["full_name"] == "Jane"
        assert d["skills"] == ["Python"]
        assert d["tags"] == ["Software Engineer"]
        assert d["experience"] == []
