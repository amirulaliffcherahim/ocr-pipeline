# Data Flow & UX — DynaConSurv OCR → HR Pipeline

## Overview

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  1. UPLOAD   │───▶│  2. EXTRACT  │───▶│  3. APPLICANT │───▶│ 4. SHORTLIST  │───▶│  5. INTERN   │
│  Resume PDF  │    │  LLM → JSON │    │  row created │    │  Interview    │    │  row created │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                                                                       │
                                                                                       ▼
                         ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
                         │  7. ARCHIVE  │◀───│  6. STAFF    │◀───│  5b. HIRE    │
                         │ past_applicant│   │  row created │    │   decision   │
                         └──────────────┘    └──────────────┘    └──────────────┘
```

## Stage 1: Upload & Extract

**UX**: HR uploads a resume PDF via `/resume` or `/full` API endpoint.

**System**:
1. PDF → Markdown (pymupdf4llm or OCR)
2. Markdown → LLM extraction → JSON
3. JSON validated against `ResumeData` Pydantic model
4. API returns structured JSON to caller

**Output shape** (`ResumeData`):
```json
{
  "personal_info": { "full_name", "email", "phone", "location", "linkedin", "website" },
  "summary": "Professional summary text",
  "skills": ["Python", "SQL", "React"],
  "tags": ["Software Engineer", "Backend", "Python Dev"],
  "experience": [{ "company", "title", "start_date", "end_date", "location", "description": [] }],
  "projects": [{ "name", "role", "start_date", "end_date", "description": [] }],
  "education": [{ "institution", "degree", "graduation_year", "result" }],
  "certifications": [{ "name", "institute", "validity_start", "validity_end", "level" }]
}
```

No `resumes` table — the JSON lives transiently until saved into an entity.

---

## Stage 2: Applicant Creation

**UX**: HR reviews extracted JSON, confirms or edits, clicks "Create Applicant."

**System** creates rows in:

| Table | What's written |
|-------|---------------|
| `applicant` | personal_info, summary, source='ocr_upload', status='new', raw_json |
| `entity_skills` | entity_type='applicant', entity_id, skill_id (resolved from lookup) |
| `entity_tags` | entity_type='applicant', entity_id, tag_id (resolved from lookup) |
| `entity_degrees` | entity_type='applicant', entity_id, degree_id, graduation_year, result |
| `entity_certifications` | entity_type='applicant', entity_id, certification_id |
| `entity_experiences` | entity_type='applicant', entity_id, company, title, dates, description |
| `entity_projects` | entity_type='applicant', entity_id, name, role, dates, description |

**Lookup resolution**: `skills`, `tags`, `degrees`, and `certifications` are shared lookup tables. On insert:
- If the skill "Python" already exists → use existing `skill_id`
- If not → INSERT new row, use new `skill_id`
- Same for tags, degrees, certifications

This means every unique skill/degree/cert is stored once. Entities reference them via polymorphic junction tables.

---

## Stage 3: Shortlisting & Interview

**UX**: HR moves applicant through hiring stages. Schedules interviews via calendar.

**System**:
- `applicant.status` updates: `new` → `screening` → `interviewing` → `shortlisted` → `offered`
- Every status change logged in `hiring_status` (who, when, from→to, notes)
- Interviews scheduled in `interview_schedule` (date, interviewer, stage, location)
- HR can rate applicant 1-5 in `applicant.rating`

**Status flow**:
```
new → screening → interviewing → shortlisted → offered → hired
  ↘                ↘               ↘
  rejected        rejected        rejected → archived to past_applicant
  withdrawn       withdrawn       withdrawn
```

---

## Stage 4: Hire as Intern

**UX**: HR clicks "Hire as Intern" on an applicant. Sets start date, stipend, supervisor.

**System**:
1. **Copy junction rows to `past_applicant`**: Create duplicate junction rows with `entity_type='past_applicant'`, `entity_id=past_applicant.id`. This is the full snapshot archive.
2. **Copy personal info to `past_applicant`**: full_name, email, phone, location, summary, source, final_status, reason, raw_json, applied_at → `past_applicant`.
3. **Reassign original junction rows to `intern`**: UPDATE all junction rows from `entity_type='applicant'` → `entity_type='intern'`, `entity_id=intern.id`.
4. **Create `intern` row**: Personal info, start_date, end_date, stipend, supervisor_id.
5. **Log transition**: `entity_transitions` from `applicant` → `intern`.
6. **Delete `applicant` row** (or soft-delete via `deleted_at`).

**Result**: Past applicant has full snapshot. Intern owns all the normalized data (skills, education, certs, experience, projects, tags).

---

## Stage 5: Promote to Staff

**UX**: Intern completes term → HR promotes to staff. Sets salary, employment type.

**System**: Same pattern as Stage 4, but from `intern` → `staff`.
1. Intern data → `past_applicant` archive (or a dedicated archive flow)
2. Junction rows reassigned from `intern` to `staff`
3. `staff` row created with salary, employment_type
4. Transition logged: `intern` → `staff`
5. Intern row soft-deleted

---

## Stage 6: Manpower (Contract Workers)

**UX**: HR adds contract/agency workers directly (not from pipeline), or from applicant.

**System**:
- `manpower` table: personal info, agency, project_id, contract_value, start/end dates
- Same junction tables for skills/education/certs/tags if available
- Links to `hr_projects` for project assignment
- Not part of the applicant→intern→staff pipeline — separate pool

---

## Junction Table Pattern

All 6 polymorphic junction tables share the same structure:

```
(entity_type, entity_id, [lookup_id]) → PRIMARY KEY
```

| Junction | Lookup FK | Extra columns |
|----------|-----------|---------------|
| `entity_skills` | `skill_id` → `skills.id` | — |
| `entity_tags` | `tag_id` → `tags.id` | — |
| `entity_degrees` | `degree_id` → `degrees.id` | `graduation_year`, `result`, `sort_order` |
| `entity_certifications` | `certification_id` → `certifications.id` | — |
| `entity_experiences` | (none — inline) | `company`, `title`, `start/end_date`, `location`, `description`, `sort_order` |
| `entity_projects` | (none — inline) | `name`, `role`, `start/end_date`, `description`, `sort_order` |

`entity_type` values: `'applicant'`, `'past_applicant'`, `'intern'`, `'staff'`, `'manpower'`

---

## Lookup Tables

### `skills`
| id | name |
|----|------|
| 1 | Docker |
| 2 | JavaScript |
| 3 | Python |

One "Python" row serves every entity who has Python.

### `degrees`
| id | institution | degree |
|----|-------------|--------|
| 1 | Universiti Teknologi MARA | Bachelor of IT (Hons.) |
| 2 | Universiti Teknologi MARA | Diploma in Computer Science |

Combination of (institution, degree) is UNIQUE. `entity_degrees` stores the person-specific year/result.

### `certifications`
| id | name | institute | validity_start | validity_end | level |
|----|------|-----------|----------------|--------------|-------|
| 1 | AWS Solutions Architect | Amazon | 2023-06-01 | 2026-06-01 | Professional |

Combination of (name, institute) is UNIQUE.

### `tags`
| id | name |
|----|------|
| 1 | Backend |
| 2 | Software Engineer |

Same as skills — shared lookup.

---

## Interview & Calendar

Two separate systems:

| Table | Purpose |
|-------|---------|
| `interview_schedule` | Hiring pipeline interviews. Links applicant, position, hiring stage, interviewer. Tracks scheduled/completed/cancelled. |
| `calendar_events` | General HR calendar — meetings, onboarding sessions, follow-ups, deadlines. Not tied to hiring pipeline. |

---

## Entity Transition Log

Every pipeline move is audited:

```
applicant[id=abc] ──▶ intern[id=def]
applicant[id=abc] ──▶ staff[id=ghi]
intern[id=def]    ──▶ staff[id=ghi]
```

`entity_transitions` captures: from_type, from_id, to_type, to_id, when, who, notes.

---

## UX Summary

| Screen | Action |
|--------|--------|
| Upload Resume | Drag-drop PDF → auto-extract → preview JSON |
| Review & Confirm | Edit extracted fields → "Create Applicant" button |
| Applicant Pipeline | Kanban board: New / Screening / Interviewing / Shortlisted / Offered |
| Schedule Interview | Pick applicant → pick stage → pick interviewer → set date/time → calendar |
| Rate & Note | Star rating + text notes per applicant |
| Hire as Intern | "Hire" button → set start date, stipend, supervisor → archive to past_applicant |
| Promote to Staff | From intern detail → "Promote" → set salary, employment type |
| Manpower | Add contract worker → assign project → set contract period |
| Past Applicants | Archived list with reason, final status, full data snapshot |

---

## API Surface (future — not yet built)

| Endpoint | Action |
|----------|--------|
| `POST /resume` | Upload PDF → extract JSON |
| `POST /applicants` | Create applicant from extracted JSON |
| `GET /applicants` | List applicants (filter by status, position, rating) |
| `PATCH /applicants/:id` | Update status, rating, notes |
| `POST /applicants/:id/transition` | Move to intern/staff |
| `GET /past_applicants` | Archived applicants |
| `POST /interview` | Schedule interview |
| `GET /interviews` | List interviews (by applicant, interviewer, date range) |
| `GET /staff` | Active employees |
| `GET /interns` | Active interns |
| `GET /manpower` | Contract workers |
| `POST /manpower` | Add contract worker |
