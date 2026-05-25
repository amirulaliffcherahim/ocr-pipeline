# OCR Pipeline — Async Two-Stage Resume Extraction

PDF → Markdown (Docling) → Structured JSON (LLM — LM Studio or OpenRouter)

## Architecture

```
POST /extract (PDF upload)
       │
       ▼ job queued immediately
┌─────────────────────────────────────────────────┐
│  Postgres Job Queue                              │
│  ┌──────┐  ┌──────┐  ┌──────┐                   │
│  │pending│→│processing│→│completed/failed│       │
│  └──────┘  └──────┘  └──────────────┘           │
│       ▲         │                                 │
│       │    sequential worker                      │
│       │    (one-at-a-time)                        │
│       │         │                                 │
│       │    ┌────▼─────────────────────────────┐  │
│       │    │ Stage 1: Docling (local)          │  │
│       │    │ Stage 2: LLM (LM Studio/OpenRouter)│  │
│       │    └──────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
       │
       ▼
GET /jobs/{id} → result JSON (when completed)
```

Key properties:
- **Non-blocking**: `POST /extract` returns instantly with a `job_id`
- **Sequential**: One job processed at a time — never overloads the LLM backend
- **Durable**: Postgres-backed, survives restarts, full audit trail
- **Multi-backend**: LM Studio (local/remote) or OpenRouter (cloud)

## Quick Start

### 1. Install

```bash
pip install -r requirements.txt
```

### 2. Configure Postgres

Ensure the Postgres database is reachable. Default connection:

```
postgresql+asyncpg://postgres:Total1234@100.68.10.40:5433/postgres
```

Override via env var: `DATABASE_URL`

Tables are auto-created on first startup.

### 3. Choose LLM Backend

**Option A — LM Studio** (default, local/remote):
```
LLM_BACKEND=lmstudio
LM_STUDIO_BASE_URL=http://ai.amirulaliff.com:1234/v1
LM_STUDIO_MODEL=gemma-3-4b-it
```
No API key needed.

**Option B — OpenRouter** (cloud):
```bash
export LLM_BACKEND=openrouter
export OPENROUTER_API_KEY=sk-or-v1-...
export OPENROUTER_MODEL=liquid/lfm-2-24b-a2b
```

### 4. Run

```bash
uvicorn pipeline.server:app --host 0.0.0.0 --port 8000
```

## API

### `POST /extract`
Upload a PDF resume. Returns immediately with a job_id.

```bash
curl -X POST http://localhost:8000/extract -F "file=@resume.pdf"
```

```json
{
  "job_id": 42,
  "status": "pending",
  "filename": "resume.pdf",
  "queue_depth": 1,
  "message": "Job queued. Poll GET /jobs/42 for results."
}
```

### `GET /jobs/{job_id}`
Poll for job status and results.

```json
{
  "job_id": 42,
  "status": "completed",
  "filename": "resume.pdf",
  "backend_used": "lmstudio/gemma-3-4b-it",
  "result": { "name": "Jane Doe", ... },
  "timing_ms": { "stage1_extraction": 1200, "stage2_llm": 3400, "total": 4600 }
}
```

### `GET /jobs`
List all jobs (newest first). Optional `?status=pending` filter.

### `DELETE /jobs/{job_id}`
Delete a job (only if not currently processing).

### `GET /health`
```json
{ "status": "ok", "worker_running": true, "queue_depth": 3 }
```

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Postgres connection |
| `LLM_BACKEND` | `lmstudio` | `lmstudio` or `openrouter` |
| `LM_STUDIO_BASE_URL` | `http://ai.amirulaliff.com:1234/v1` | LM Studio API |
| `LM_STUDIO_MODEL` | `gemma-3-4b-it` | Model name |
| `LM_STUDIO_TIMEOUT` | `120` | Request timeout (seconds) |
| `LM_STUDIO_TEMPERATURE` | `0.0` | Deterministic output |
| `OPENROUTER_API_KEY` | `""` | OpenRouter API key |
| `OPENROUTER_MODEL` | `liquid/lfm-2-24b-a2b` | Model slug |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | API base |
| `QUEUE_POLL_INTERVAL` | `1.0` | Idle poll delay (seconds) |
| `JOB_MAX_RETRIES` | `0` | Retries on failure |

## Extracted Fields

Full ATS-optimized JSON schema across contact, summary, work experience, education, skills, and projects. See `pipeline/schema.py` for the complete Pydantic model.

## How It Works

1. **Enqueue** — PDF is stored in Postgres as `pending`. Client gets `job_id` instantly.
2. **Worker claims** — `SELECT ... FOR UPDATE SKIP LOCKED` picks the oldest pending job atomically.
3. **Stage 1 (Docling)** — PDF → Markdown preserving layout, reading order, headings.
4. **Stage 2 (LLM)** — Markdown → JSON via LM Studio (OpenAI-compatible API) or OpenRouter. Strict `response_format: json_object` mode prevents conversational preamble.
5. **Result stored** — Job marked `completed` with full JSON, timing, and audit trail.
