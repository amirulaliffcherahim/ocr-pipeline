# Resume Parser

Lightweight resume parser — **PDF/TXT → Markdown → Structured JSON** via LLM extraction. Works with OpenRouter (cloud), Ollama (local), or LM Studio (local).

## Features

- **PDF parsing** via `pymupdf4llm` with auto-fallback to OCR for scanned/image-based PDFs
- **Multi-strategy**: `auto` (native → OCR fallback), `native`, or `ocr` modes for any resume layout
- **QR code decoding** — extracts LinkedIn, GitHub, portfolio links from QR codes embedded in PDFs
- **LLM extraction** using any OpenAI-compatible API — one-line switch between backends
- **Structured output** validated by Pydantic, normalized for consistency across runs
- **Date normalization** — `"2024"`, `"Jan 2024"`, `"2024-01"` all become `"2024-01"`
- **Rate limiting** with retry + exponential backoff + in-process concurrency control

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

### 3. Run (CLI)

```bash
# Drop .pdf / .txt files in data/input/, then:
python main.py
# → JSON in data/output/
```

### 4. Run (API)

```bash
uvicorn api:app --host 0.0.0.0 --port 8001
# → http://localhost:8001/docs
```

```bash
curl -X POST http://localhost:8001/resume/upload -F "file=@resume.pdf"
```

## Switching Backends

All backends speak the OpenAI `/chat/completions` protocol — just change one line:

```env
# .env — pick one:
LLM_BACKEND=openrouter   # cloud: qwen3, claude, gpt-4o-mini, etc.
LLM_BACKEND=ollama       # local: qwen3:1.7b, llama3.2:3b, etc.
LLM_BACKEND=lmstudio     # local: any model loaded in LM Studio
```

Ollama exposes its API at `http://localhost:11434/v1` — no extra config needed. LM Studio at `http://localhost:1234/v1`.

## API Endpoints

### `POST /resume/upload`

Upload a PDF or TXT resume. File is deleted immediately after processing.

```bash
curl -X POST http://localhost:8001/resume/upload -F "file=@resume.pdf"
```

**Response** (200): Full `ResumeData` JSON.

| Status | Cause |
|--------|-------|
| 400 | Missing file or unsupported format |
| 422 | LLM extraction / JSON parsing failure |
| 500 | Internal error |

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

## PDF Parse Modes

| Mode | Behavior | Use case |
|------|----------|----------|
| `auto` (default) | Native extraction, fall back to OCR if output sparse | **Recommended** — handles text + image PDFs |
| `native` | pymupdf4llm text-layer only | Fast; digitally-created PDFs |
| `ocr` | Always OCR via ocrmypdf | Scanned, image-heavy, multi-column |

Set via `PDF_PARSE_MODE` in `.env`.

## QR Code Handling

QR codes in PDFs (LinkedIn, GitHub, portfolio, vCard) are automatically decoded via `pyzbar` and appended to the Markdown before LLM extraction. Enable artifact saving to keep QR images:

```env
QR_SAVE_ARTIFACTS=true   # saves to data/qr_artifacts/
```

## Output Normalization

All extracted JSON passes through `src/normalizer.py` for consistent output:

- **Dates** → `YYYY-MM` (`"2024"` → `"2024-01"`, `"Jan 2024"` → `"2024-01"`)
- **`end_date`** preserves `"Present"` for ongoing roles
- **`graduation_year`** → `YYYY` only (no month suffix)
- **Strings** trimmed; empty strings → `null`
- **Skills & certifications** deduplicated and sorted alphabetically

## Output Schema

```json
{
  "personal_info": {
    "full_name": "string | null",
    "email": "string | null",
    "phone": "string | null",
    "location": "string | null",
    "linkedin": "string | null",
    "website": "string | null"
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
| `OLLAMA_MODEL` | `qwen3:1.7b` | Model name (`ollama list`) |
| `OLLAMA_TIMEOUT` | `120` | Request timeout |
| `OLLAMA_TEMPERATURE` | `0.0` | LLM temperature |
| `OLLAMA_MAX_TOKENS` | `8192` | Max output tokens |
| **LM Studio** | | |
| `LM_STUDIO_BASE_URL` | `http://localhost:1234/v1` | LM Studio endpoint |
| `LM_STUDIO_MODEL` | `gemma-3-4b-it` | Model loaded in LM Studio |
| `LM_STUDIO_TIMEOUT` | `120` | Request timeout |
| `LM_STUDIO_TEMPERATURE` | `0.0` | LLM temperature |
| `LM_STUDIO_MAX_TOKENS` | `8192` | Max output tokens |
| **General** | | |
| `LLM_REASONING_ENABLED` | `false` | Enable thinking phase (Qwen 3, R1) |
| `LLM_MAX_INPUT_CHARS` | `200000` | Max resume chars sent to LLM |
| `LLM_MAX_RETRIES` | `3` | Retries on 429/5xx errors |
| `LLM_RETRY_BACKOFF` | `2.0` | Delay multiplier per retry |
| `LLM_MAX_CONCURRENT` | `1` | Max concurrent LLM calls |
| **PDF** | | |
| `PDF_PARSE_MODE` | `auto` | `auto`, `native`, or `ocr` |
| `OCR_LANGUAGE` | `eng` | Tesseract language code |
| `OCR_MIN_CHARS` | `300` | Fallback threshold for `auto` |
| **QR** | | |
| `QR_SCAN_ENABLED` | `true` | Scan PDF for QR codes |
| `QR_SAVE_ARTIFACTS` | `false` | Save QR images to disk |

## OCR for Scanned PDFs

For image-based PDFs, force OCR mode:

```env
PDF_PARSE_MODE=ocr
OCR_LANGUAGE=msa+eng          # Malay + English
```

Requires `ocrmypdf` + system install of [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki).

## Project Structure

```
ocr-pipeline/
├── main.py                    # CLI batch processor
├── api.py                     # FastAPI server (POST /resume/upload)
├── config.py                  # Env loading, backend resolution
├── requirements.txt
├── .env.example
├── data/
│   ├── input/                 # Drop resumes here
│   └── output/                # JSON results
├── src/
│   ├── models.py              # Pydantic schemas
│   ├── pdf_parser.py          # PDF → Markdown (multi-strategy)
│   ├── text_processor.py      # TXT + layout-aware cleaning
│   ├── llm_extractor.py       # LLM API call + retry logic
│   ├── qr_decoder.py          # QR code detection + decoding
│   └── normalizer.py          # Date & output normalization
├── prompts/
│   └── resume_extraction.md   # System prompt
└── docs/
    ├── architecture.md
    ├── flow.md
    ├── rules.md
    └── standard.md
```

## Debugging

Debug output (`[DEBUG]`, `[ERROR]`, `[RETRY]`, `[QR]`, `[AUTO]`, `[OCR]`) prints to stdout. Remove `print()` calls in `src/llm_extractor.py` for production.
