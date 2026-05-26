from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any


def _coerce_to_str(v: Any) -> str | None:
    """Convert int/float to str, pass through None and str as-is."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return str(v)
    return v


class PersonalInfo(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    website: Optional[str] = None

    _coerce_phone = field_validator("phone", mode="before")(_coerce_to_str)


class Experience(BaseModel):
    company: str
    title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None
    description: List[str] = Field(default_factory=list)

    _coerce_start = field_validator("start_date", mode="before")(_coerce_to_str)
    _coerce_end = field_validator("end_date", mode="before")(_coerce_to_str)


class Project(BaseModel):
    name: str
    role: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: List[str] = Field(default_factory=list)

    _coerce_start = field_validator("start_date", mode="before")(_coerce_to_str)
    _coerce_end = field_validator("end_date", mode="before")(_coerce_to_str)


class Education(BaseModel):
    institution: str
    degree: str
    field: Optional[str] = None
    graduation_year: Optional[str] = None

    _coerce_year = field_validator("graduation_year", mode="before")(_coerce_to_str)


class ResumeData(BaseModel):
    personal_info: PersonalInfo
    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
