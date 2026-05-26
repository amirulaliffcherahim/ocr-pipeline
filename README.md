# Resume Parser

Lightweight resume parser — **PDF → Markdown → Structured JSON** via LLM extraction. Extracts applicant photos, QR codes, and structured data. Works with OpenRouter (cloud), Ollama (local), or LM Studio (local).

## Features

- **PDF parsing** via `pymupdf4llm` with auto-fallback to OCR for scanned/image-based PDFs
- **Hybrid mode** — native + OCR merge for maximum text coverage on complex layouts
- **Photo extraction** — automatically detects and extracts applicant headshots from page 1
- **QR code decoding** — extracts LinkedIn, GitHub, portfolio links from QR codes
- **LLM extraction** using any OpenAI-compatible API — one-line switch between backends
- **Structured output** validated by Pydantic, normalized for consistency across runs
- **Date normalization** — `"2024"`, `"Jan 2024"`, `"2024-01"` all become `"2024-01"`
- **Rate limiting** with retry + exponential backoff + concurrency control

## Quick Start

### 1. Install

```bash
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Pick a backend — set `LLM_BACKEND` and configure that section:

| Backend | Set `LLM_BACKEND` to | What to configure |
|---------|---------------------|-------------------|
| **OpenRouter** (cloud) | `openrouter` | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` |
| **Ollama** (local) | `ollama` | `OLLAMA_MODEL` (run `ollama pull qwen3:1.7b` first) |
| **LM Studio** (local) | `lmstudio` | `LM_STUDIO_MODEL` (load model in LM Studio UI) |

Recommended model for production: `qwen/qwen3.5-flash` (fast, cheap, reliable).

### 3. Run (CLI)

```bash
python main.py                # processes data/input/ → data/output/
python test_runner.py         # batch test with accuracy scoring
```

### 4. Run (API)

```bash
uvicorn api:app --host 0.0.0.0 --port 8001
# → http://localhost:8001/docs
```

## API Guide

Three endpoints for different needs:

| Endpoint | Returns | LLM? | Photo? | Speed |
|----------|---------|------|--------|-------|
| `POST /resume` | Resume JSON | Yes | No | ~10-30s |
| `POST /photo` | `{"photo_path": "..."}` | No | Yes | ~1s |
| `POST /full` | Resume JSON + photo | Yes | Yes | ~10-30s |

### `POST /resume` — Extract resume data only

```bash
curl -X POST http://localhost:8001/resume \
  -F "file=@resume.pdf"

# With layout override for 2-column resumes:
curl -X POST "http://localhost:8001/resume?layout=single" \
  -F "file=@resume.pdf"
```

**Response (200):**
```json
{
  "personal_info": {
    "full_name": "Jane Doe",
    "email": "jane@example.com",
    "phone": "+60 12-345 6789",
    "location": "Kuala Lumpur, Malaysia",
    "linkedin": null,
    "website": null
  },
  "summary": "Experienced software engineer...",
  "skills": ["Python", "JavaScript", "React"],
  "experience": [...],
  "projects": [...],
  "education": [...],
  "certifications": []
}
```

### `POST /photo` — Extract photo only

```bash
curl -X POST http://localhost:8001/photo \
  -F "file=@resume.pdf"
```

**Response (200):**
```json
{"photo_path": "photos/resume_photo.jpg"}
```

Fetch the image:
```bash
curl http://localhost:8001/photos/resume_photo.jpg --output photo.jpg
```

### `POST /full` — Resume + photo

```bash
curl -X POST http://localhost:8001/full \
  -F "file=@resume.pdf"
```

Same JSON as `/resume` but with `personal_info.photo_path` populated.

### `GET /health`

```bash
curl http://localhost:8001/health
# → {"status":"ok"}
```

### `GET /queue/status`

```bash
curl http://localhost:8001/queue/status
# → {"max_concurrent":1,"active":0,"waiting":0}
```

### Error Codes

| Status | Cause |
|--------|-------|
| 400 | Missing file, wrong format, or invalid `?layout=` value |
| 404 | No photo found in PDF (`/photo` only) |
| 422 | LLM extraction or JSON parsing failure |
| 500 | Internal server error |

## Switching Backends

All backends speak the OpenAI `/chat/completions` protocol — change one line:

```env
LLM_BACKEND=openrouter   # cloud: qwen3, claude, gpt-4o-mini
LLM_BACKEND=ollama       # local: qwen3:1.7b, llama3.2:3b
LLM_BACKEND=lmstudio     # local: any model in LM Studio
```

## PDF Parse Modes

| Mode | Behavior | Speed | Use case |
|------|----------|-------|----------|
| `auto` (default) | Native + 2-column detection, OCR fallback if sparse | Fast | 90% of resumes |
| `native` | pymupdf4llm only | Fastest | Text-based PDFs |
| `ocr` | Always OCR first | Slow | Scanned/image PDFs |
| `hybrid` | Native + OCR merge (best quality) | Slowest | Complex layouts |

Set via `PDF_PARSE_MODE` in `.env`. Layout override via `?layout=auto|single` query param.

## Photo Extraction

Automatically detects the largest portrait-ish image on page 1 (>20KB, aspect 0.5–1.5) and saves it as the applicant photo. Photos are served via `/photos/{filename}`.

```env
PHOTO_ENABLED=true        # toggle on/off
PHOTO_DIR=data/photos     # storage (gitignored)
```

Photo size per CV: ~20-100 KB.

## QR Code Handling

QR codes (LinkedIn, GitHub, portfolio, vCard) are automatically decoded via `pyzbar` and fed into the LLM extraction.

```env
QR_SCAN_ENABLED=true
QR_SAVE_ARTIFACTS=false    # set true to save QR images
```

## Output Normalization

All extracted JSON passes through `src/normalizer.py`:

- **Dates** → `YYYY-MM` (`"2024"` → `"2024-01"`, `"Jan 2024"` → `"2024-01"`)
- **`end_date`** preserves `"Present"` for ongoing roles
- **`graduation_year`** → `YYYY` only
- **Strings** trimmed; empty strings → `null`
- **Skills & certifications** deduplicated and sorted

## Output Schema

```json
{
  "personal_info": {
    "full_name": "string | null",
    "email": "string | null",
    "phone": "string | null",
    "location": "string | null",
    "linkedin": "string | null",
    "website": "string | null",
    "photo_path": "string | null"
  },
  "summary": "string | null",
  "skills": ["string"],
  "experience": [
    {
      "company": "string",
      "title": "string",
      "start_date": "YYYY-MM | null",
      "end_date": "YYYY-MM or Present | null",
      "location": "string | null",
      "description": ["string"]
    }
  ],
  "projects": [
    {
      "name": "string",
      "role": "string | null",
      "start_date": "YYYY-MM | null",
      "end_date": "YYYY-MM | null",
      "description": ["string"]
    }
  ],
  "education": [
    {
      "institution": "string",
      "degree": "string",
      "field": "string | null",
      "graduation_year": "string | null"
    }
  ],
  "certifications": ["string"]
}
```

## Storage Estimates

For planning database capacity with 20,000 CVs:

| What | Per CV | × 20,000 |
|------|--------|----------|
| JSON only | ~6 KB | ~120 MB |
| JSON + photo | ~50 KB | ~1 GB |
| JSON + photo + PDF | ~250 KB | ~5 GB |

JSON compresses well — gzipped, ~2-3 KB per CV.

## Batch Testing

```bash
# Extract all PDFs in a directory:
python test_runner.py --dir data/input

# With ground truth comparison:
python test_runner.py --dir data/test_pdfs --ground-truth data/ground_truth
```

Results saved to `data/test_results/` as JSON + CSV with per-section accuracy scores.

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_BACKEND` | `openrouter` | `openrouter`, `ollama`, or `lmstudio` |
| **OpenRouter** | | |
| `OPENROUTER_API_KEY` | — | API key from openrouter.ai |
| `OPENROUTER_MODEL` | `qwen/qwen3-1.7b` | Model slug |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | API endpoint |
| `OPENROUTER_TIMEOUT` | `120` | Request timeout (seconds) |
| `OPENROUTER_TEMPERATURE` | `0.0` | LLM temperature |
| `OPENROUTER_MAX_TOKENS` | `8192` | Max output tokens |
| **Ollama** | | |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama endpoint |
| `OLLAMA_MODEL` | `qwen3:1.7b` | Model name |
| `OLLAMA_TIMEOUT` | `120` | Request timeout |
| `OLLAMA_TEMPERATURE` | `0.0` | LLM temperature |
| `OLLAMA_MAX_TOKENS` | `8192` | Max output tokens |
| **LM Studio** | | |
| `LM_STUDIO_BASE_URL` | `http://localhost:1234/v1` | LM Studio endpoint |
| `LM_STUDIO_MODEL` | `gemma-3-4b-it` | Model name |
| `LM_STUDIO_TIMEOUT` | `120` | Request timeout |
| `LM_STUDIO_TEMPERATURE` | `0.0` | LLM temperature |
| `LM_STUDIO_MAX_TOKENS` | `8192` | Max output tokens |
| **General** | | |
| `LLM_REASONING_ENABLED` | `false` | Enable thinking phase |
| `LLM_MAX_INPUT_CHARS` | `200000` | Max resume chars to LLM |
| `LLM_MAX_RETRIES` | `3` | Retries on 429/5xx |
| `LLM_RETRY_BACKOFF` | `2.0` | Backoff multiplier |
| `LLM_MAX_CONCURRENT` | `1` | Max concurrent LLM calls |
| **PDF** | | |
| `PDF_PARSE_MODE` | `auto` | `auto`, `native`, `ocr`, `hybrid` |
| `PDF_PAGE_LAYOUT` | `auto` | `auto` or `single` |
| `OCR_LANGUAGE` | `eng` | Tesseract language code |
| `OCR_MIN_CHARS` | `300` | Fallback threshold |
| **QR** | | |
| `QR_SCAN_ENABLED` | `true` | Scan PDF for QR codes |
| `QR_SAVE_ARTIFACTS` | `false` | Save QR images to disk |
| **Photo** | | |
| `PHOTO_ENABLED` | `true` | Extract applicant photo |
| `PHOTO_DIR` | `data/photos` | Photo storage path |

## Project Structure

```
ocr-pipeline/
├── main.py                    # CLI batch processor
├── api.py                     # FastAPI: /resume, /photo, /full
├── test_runner.py             # Batch test + accuracy scoring
├── config.py                  # Env loading, backend resolution
├── requirements.txt
├── .env.example
├── data/
│   ├── input/                 # Drop resumes here
│   ├── output/                # JSON results
│   ├── photos/                # Extracted applicant photos
│   └── test_results/          # Batch test reports
├── src/
│   ├── models.py              # Pydantic schemas
│   ├── pdf_parser.py          # PDF → Markdown (auto/native/ocr/hybrid)
│   ├── text_processor.py      # Markdown restructuring + cleaning
│   ├── llm_extractor.py       # LLM API + retry logic
│   ├── qr_decoder.py          # QR code detection
│   ├── photo_extractor.py     # Applicant photo extraction
│   └── normalizer.py          # Date & output normalization
├── prompts/
│   └── resume_extraction.md   # LLM system prompt
└── docs/
    ├── architecture.md
    ├── flow.md
    ├── rules.md
    ├── standard.md
    └── api-guide.md
```

## Debugging

Debug output (`[DEBUG]`, `[ERROR]`, `[RETRY]`, `[QR]`, `[PHOTO]`, `[AUTO]`, `[HYBRID]`, `[OCR]`) prints to stdout. Remove `print()` calls for production.
