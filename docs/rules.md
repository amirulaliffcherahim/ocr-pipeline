# Extraction Rules

These rules define how the LLM should extract resume data. They live in `prompts/resume_extraction.md` as the system prompt.

## Core Principles

### 1. Never Alter Proper Nouns
Copy names, company names, project names, and institutions **exactly** as written — character for character, letter for letter. Do not drop middle names, do not "fix" perceived typos, do not substitute similar-looking letters (e.g., "u" for "e"). Every character must match the source.

### 2. Do Not Leak Bullets Between Entries
Each experience entry and project entry must contain ONLY the description bullets that belong to that specific role. Do not copy bullets from other roles, projects, or sections into an entry's description. The first job should not absorb every bullet in the CV.

### 3. Extract All Description Bullets
Every bullet point under a role or project must appear in the `description` array. Do not skip, merge, or summarize any bullet. The normalizer removes empty strings, so the prompt must not pre-filter.

### 3. Extract Full Summary Verbatim
Do not truncate, paraphrase, or omit any sentences from the summary section.

### 4. Distinguish Employment vs Projects
- `experience` = paid employment at a company (has employer, job title, dates)
- `projects` = self-contained work (freelance, academic, side projects, final-year projects)
- If a section is labeled "Projects," put all entries in `projects[]`, not `experience[]`.

### 5. Location is Geographic Only
`location` is ALWAYS a city, state, or country. Never put a job title, role name, or project name in `location`.

### 6. Do Not Hallucinate Education
If there is no dedicated "Education" section with a real degree name, leave `education: []`. A final-year project description is NOT an education entry.

### 7. Skills — Only From Explicit Skills Section
Extract skills ONLY from a dedicated "Skills" section. Do NOT infer or fabricate skills from job descriptions, project details, or bullet points. If there is no explicit Skills section, return `skills: []`. Preserve parenthetical context like `"REST API (design, integration, deployment)"` when present.

### 8. Dates — Null If Missing
Output dates if explicitly stated (any format — normalizer converts to `YYYY-MM`). If a date is not present on the resume, use `null`. Never guess or fabricate a date. A missing date is better than a wrong date.

### 9. Output Only Valid JSON
No markdown fences, no extra commentary. Just the JSON object.

## Schema

```json
{
  "personal_info": {
    "full_name": "...",
    "email": "...",
    "phone": "...",
    "location": "...",
    "linkedin": "...",
    "website": "..."
  },
  "summary": "full verbatim summary text",
  "skills": ["skill1", "skill2"],
  "experience": [
    {
      "company": "employer name",
      "title": "job title",
      "start_date": "YYYY-MM",
      "end_date": "YYYY-MM or Present",
      "location": "city, country",
      "description": ["bullet1", "bullet2"]
    }
  ],
  "projects": [
    {
      "name": "project name",
      "role": "your role on the project",
      "start_date": "YYYY-MM",
      "end_date": "YYYY-MM",
      "description": ["bullet1", "bullet2"]
    }
  ],
  "education": [
    {
      "institution": "...",
      "degree": "...",
      "field": "...",
      "graduation_year": "YYYY"
    }
  ],
  "certifications": ["cert1", "cert2"]
}
```

## Post-Processing

After the LLM returns JSON, `src/normalizer.py` applies:

| Step | Effect |
|------|--------|
| Date normalization | `"2024"` → `"2024-01"`, `"Jan 2024"` → `"2024-01"` |
| `graduation_year` stripping | `"2023-01"` → `"2023"` |
| String trimming | `"  text  "` → `"text"` |
| Empty → null | `""` → `null` |
| Deduplication | Duplicate skills/certs removed |
| Sorting | Skills and certifications alphabetized |

## Edge Cases

| Scenario | Handling |
|----------|----------|
| Multi-page PDF | All pages processed; truncation at 200K chars |
| Scanned/image PDF | `auto` mode detects sparse text → OCR fallback |
| QR code in PDF | Decoded by `pyzbar` before LLM extraction |
| No work experience | `experience: []` (never null) |
| No education section | `education: []` |
| Non-English resume | Extract as-is; set `OCR_LANGUAGE` for OCR |
| Tables in PDF | Converted to Markdown by pymupdf4llm |
| Duplicate roles | Extract both — may represent real experience |
| Year-only dates | `"2024"` → normalized to `"2024-01"` |
| Missing fields | `null` for optional, `""` for required strings, `[]` for arrays |

## Prompt Iteration

If extraction quality degrades for specific resume formats:

1. Add few-shot examples to the system prompt
2. Adjust `LLM_MAX_INPUT_CHARS` for very long resumes
3. Try a different model — stronger models handle complex layouts better
4. Force OCR mode for image-heavy PDFs: `PDF_PARSE_MODE=ocr`
