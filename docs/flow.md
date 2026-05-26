# Data Flow

## End-to-End Pipeline

```
                   ┌──────────────────────────────────────────────────┐
                   │                    main.py / api.py               │
                   │  for each file: parse → clean → extract → norm   │
                   └──┬───────────────────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          │                       │
     .pdf file               .txt file
          │                       │
          ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│  pdf_parser.py    │    │ text_processor.py │
│                   │    │  read_text_file() │
│  auto/native/ocr  │    │  → raw string     │
│  → raw Markdown   │    └────────┬──────────┘
│                   │             │
│  qr_decoder.py    │             │
│  → QR data as MD  │             │
└────────┬──────────┘             │
         │                        │
         ▼                        ▼
         └───────────┬────────────┘
                     │ raw Markdown string
                     ▼
          ┌──────────────────┐
          │ text_processor.py │
          │  clean_markdown() │
          │  → bullet norm    │
          │  → line merge     │
          │  → blank collapse │
          └────────┬──────────┘
                   │ cleaned Markdown
                   ▼
          ┌──────────────────┐
          │ llm_extractor.py  │
          │                   │
          │  1. Load prompt   │
          │  2. POST /chat/   │
          │     completions   │
          │  3. Retry 429/5xx │
          │  4. Parse JSON    │
          │  5. Pydantic val  │
          └────────┬──────────┘
                   │ raw dict
                   ▼
          ┌──────────────────┐
          │  normalizer.py    │
          │  → dates to YYYY-MM│
          │  → strings trimmed│
          │  → skills sorted  │
          │  → empties → null │
          └────────┬──────────┘
                   │ clean dict
                   ▼
          ┌──────────────────┐
          │  json.dump()      │
          │  → data/output/   │
          │    {name}.json    │
          └──────────────────┘
```

## Backend Switching

All three backends speak the same `/chat/completions` protocol. Changing backends requires only `.env`:

```
LLM_BACKEND=openrouter   → https://openrouter.ai/api/v1    (needs API key)
LLM_BACKEND=ollama       → http://localhost:11434/v1        (no auth)
LLM_BACKEND=lmstudio     → http://localhost:1234/v1         (no auth)
```

The `config.py` resolver maps each backend's settings to unified `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, etc.

## Parse Mode Flow (auto)

```
PDF input
    │
    ▼
_native_parse()  ← pymupdf4llm
    │
    ├── chars ≥ 300 AND words ≥ 50? ──▶ Use native output
    │
    └── too sparse? ──▶ _ocr_then_parse()  ← ocrmypdf → pymupdf4llm
                            │
                            └── Clean up temp OCR'd PDF
    │
    ▼
QR scan (if enabled)
    │
    ▼
Return Markdown
```

## Error Handling

```
API Error (4xx non-retryable)
  → requests raises HTTPError immediately

API Error (429 / 5xx)
  → Retry up to LLM_MAX_RETRIES with exponential backoff
  → [RETRY] HTTP 429 — attempt 1/3, waiting 1s
  → [RETRY] HTTP 429 — attempt 2/3, waiting 2s
  → [RETRY] HTTP 429 — attempt 3/3, waiting 4s
  → If all exhausted, raise HTTPError

JSON Parse Failure
  → [ERROR] JSON decode failed: ...
  → Output: {"error": "JSON decode failed: ..."}

Pydantic Validation Failure
  → [ERROR] Validation/parsing failed: ValidationError: ...
  → Output: {"error": "ValidationError: ..."}

Empty LLM Response
  → [ERROR] LLM returned empty content
  → Output: {"error": "LLM returned empty content"}

Type Coercion
  → field_validator(mode='before') silently converts int → str

Normalization
  → All date formats → "YYYY-MM"
  → Empty strings → null
  → Duplicate skills → deduplicated + sorted
```

## Concurrency Model

- API: `asyncio.Semaphore(LLM_MAX_CONCURRENT)` limits concurrent LLM calls (default 1)
- Additional requests wait on the semaphore (not rejected)
- `GET /queue/status` shows active/waiting counts
- CLI (`main.py`): sequential, single-threaded
