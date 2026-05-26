# API Guide

Base URL: `http://localhost:8001` (default)

Interactive docs: [http://localhost:8001/docs](http://localhost:8001/docs)

---

## Endpoints

### `POST /resume` — Extract resume data

Parses a PDF resume and returns structured JSON. No photo extraction.

```bash
curl -X POST http://localhost:8001/resume \
  -H "Content-Type: multipart/form-data" \
  -F "file=@resume.pdf"
```

**Query params:**

| Param | Values | Default | Description |
|-------|--------|---------|-------------|
| `layout` | `auto`, `single` | (auto-detect) | Force page layout for 2-column resumes |

**Response (200):**

```json
{
  "personal_info": {
    "full_name": "Jane Doe",
    "email": "jane@example.com",
    "phone": "+60 12-345 6789",
    "location": "Kuala Lumpur",
    "linkedin": null,
    "website": null
  },
  "summary": "Experienced software engineer with 5 years...",
  "skills": ["Python", "JavaScript", "Node.js", "React"],
  "experience": [
    {
      "company": "Acme Corp",
      "title": "Senior Developer",
      "start_date": "2022-01",
      "end_date": "Present",
      "location": "Kuala Lumpur",
      "description": [
        "Led backend migration from monolith to microservices",
        "Mentored junior developers on code quality"
      ]
    }
  ],
  "projects": [
    {
      "name": "Inventory Management System",
      "role": "Full Stack Developer",
      "start_date": "2023-06",
      "end_date": "2024-01",
      "description": [
        "Built real-time dashboard with WebSocket integration",
        "Reduced query latency by 40%"
      ]
    }
  ],
  "education": [
    {
      "institution": "University of Technology",
      "degree": "Bachelor of Computer Science",
      "field": "Software Engineering",
      "graduation_year": "2020"
    }
  ],
  "certifications": ["AWS Solutions Architect"]
}
```

**Errors:**

| Status | Body | Cause |
|--------|------|-------|
| 400 | `{"detail":"PDF file required"}` | No file or wrong format |
| 400 | `{"detail":"layout must be 'auto' or 'single'"}` | Invalid layout param |
| 422 | `{"detail":"JSON decode failed: ..."}` | LLM extraction failure |
| 500 | `{"detail":"Internal Server Error"}` | Unexpected error |

---

### `POST /photo` — Extract photo only

Extracts the applicant's headshot from page 1. No LLM call — fast (~1s).

```bash
curl -X POST http://localhost:8001/photo \
  -F "file=@resume.pdf"
```

**Response (200):**

```json
{
  "photo_path": "photos/resume_photo.jpg"
}
```

**Response (404):**

```json
{
  "detail": "No photo found in this PDF"
}
```

**Fetching the image:**

```bash
curl http://localhost:8001/photos/resume_photo.jpg --output photo.jpg
```

Or open directly: `http://localhost:8001/photos/resume_photo.jpg`

---

### `POST /full` — Resume + photo

Full pipeline: extracts both structured JSON and applicant photo.

```bash
curl -X POST http://localhost:8001/full \
  -F "file=@resume.pdf"
```

Same response as `/resume` but with `personal_info.photo_path` populated:

```json
{
  "personal_info": {
    "full_name": "Jane Doe",
    "photo_path": "photos/resume_photo.jpg",
    ...
  },
  ...
}
```

---

### `GET /health` — Health check

```bash
curl http://localhost:8001/health
```

```json
{"status": "ok"}
```

---

### `GET /queue/status` — Concurrency status

```bash
curl http://localhost:8001/queue/status
```

```json
{
  "max_concurrent": 1,
  "active": 0,
  "waiting": 0
}
```

---

## Client Examples

### Python

```python
import requests

# Resume only
with open("resume.pdf", "rb") as f:
    resp = requests.post(
        "http://localhost:8001/resume",
        files={"file": f},
        params={"layout": "auto"}
    )
data = resp.json()
print(data["personal_info"]["full_name"])
print(data["skills"])

# Photo only
with open("resume.pdf", "rb") as f:
    resp = requests.post(
        "http://localhost:8001/photo",
        files={"file": f}
    )
photo = resp.json()
print(photo["photo_path"])
```

### JavaScript (fetch)

```javascript
const form = new FormData();
form.append("file", fileInput.files[0]);

const resp = await fetch("http://localhost:8001/resume", {
    method: "POST",
    body: form,
});
const data = await resp.json();
console.log(data.personal_info.full_name);
```

### cURL (with 2-column layout override)

```bash
curl -X POST "http://localhost:8001/resume?layout=single" \
  -F "file=@resume.pdf" | jq .
```

---

## Rate Limiting

The API processes one LLM request at a time via an in-process semaphore. Additional requests wait in queue. Configure via `.env`:

```env
LLM_MAX_CONCURRENT=1       # max simultaneous LLM calls
LLM_MAX_RETRIES=3          # retry on provider 429/5xx
LLM_RETRY_BACKOFF=2.0      # delay = 2^attempt seconds
```

Check queue depth: `GET /queue/status`.

---

## Performance

| Endpoint | Typical latency | Bottleneck |
|----------|----------------|------------|
| `/resume` | 10-30s | LLM API call |
| `/photo` | 1-2s | PDF image extraction |
| `/full` | 10-30s | LLM + photo |

Latency depends on resume length and model speed. `qwen/qwen3.5-flash` averages ~12s per resume.
