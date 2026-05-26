# Architecture

## Overview

The pipeline follows a four-stage linear architecture: Parse → Clean → Extract → Normalize.

```
┌──────────┐     ┌───────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│ PDF/TXT  │ ──▶ │  Parse to MD  │ ──▶ │  Clean MD     │ ──▶ │  LLM → JSON  │ ──▶ │ Normalize│
│  Input   │     │  + QR scan    │     │               │     │  + Retry      │     │  Output  │
└──────────┘     └───────────────┘     └──────────────┘     └──────────────┘     └──────────┘
                       │                      │                   │                   │
                 pdf_parser.py         text_processor.py    llm_extractor.py    normalizer.py
                 qr_decoder.py          (layout-aware)      (OpenAI API)        (dates, strings)
```

## Component Map

### `config.py` — Configuration Hub
- Loads `.env` via `python-dotenv`
- Supports three backends: OpenRouter, Ollama, LM Studio
- Resolves active backend into unified `LLM_*` variables
- All runtime settings flow from here — no hardcoded values

### `src/pdf_parser.py` — PDF Ingestion
- **`auto` mode**: Try `pymupdf4llm` → if output < 300 chars or < 50 words → fallback to `ocrmypdf`
- **`native` mode**: `pymupdf4llm` only (fast, text-layer extraction)
- **`ocr` mode**: Always `ocrmypdf` first (handles scanned/image PDFs)
- After parsing, scans for QR codes via `src/qr_decoder.py` and appends decoded data

### `src/qr_decoder.py` — QR Code Extraction
- Uses `pymupdf` (fitz) to extract embedded images from PDF pages
- `pyzbar` decodes QR codes from those images
- Classifies decoded data: URL, EMAIL, VCARD, PHONE, TEXT
- Optional artifact saving to disk for debugging

### `src/text_processor.py` — Text Handling
- `read_text_file()` — reads `.txt` files (UTF-8)
- `clean_markdown()` — layout-aware cleaning:
  - Normalizes unicode bullet characters (• ◦ ▪ ● ✔ → `- `)
  - Merges broken mid-sentence lines (common in multi-column PDFs)
  - Preserves section headers (ALL-CAPS, `#` prefixes)
  - Collapses excessive blank lines

### `src/llm_extractor.py` — LLM Extraction
- Loads system prompt from `prompts/resume_extraction.md`
- Sends system + user messages to `{LLM_BASE_URL}/chat/completions`
- **Retry logic**: 3 retries with exponential backoff on 429/5xx
- **Reasoning control**: Disables thinking phase by default for speed
- **Auth handling**: Bearer token for OpenRouter, no auth for Ollama/LM Studio
- Parses JSON from response, stripping markdown code fences
- Validates against Pydantic `ResumeData`, then passes to normalizer

### `src/normalizer.py` — Output Normalization
- **Dates**: `"2024"` → `"2024-01"`, `"Jan 2024"` → `"2024-01"`, `"Present"` preserved
- **graduation_year**: kept as `YYYY` only
- **Strings**: trimmed, empty → `null`
- **Skills & certifications**: deduplicated, sorted alphabetically
- Runs automatically after Pydantic validation

### `src/models.py` — Data Contracts
- `PersonalInfo` — name, email, phone, location, links
- `Experience` — company, title, dates, location, description bullets
- `Project` — name, role, dates, description (separate from employment)
- `Education` — institution, degree, field, graduation year
- `ResumeData` — top-level container
- `field_validator(mode='before')` coercers for int→str on date/year fields

### `api.py` — FastAPI Server
- `POST /resume/upload` — accepts PDF/TXT, returns JSON
- `GET /health` — liveness check
- `GET /queue/status` — concurrency semaphore state
- Temp files deleted in `finally` block

### `main.py` — CLI Batch Processor
- Scans `data/input/` for `.pdf`/`.txt`
- Sequential processing with `tqdm` progress bars

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| OpenAI-compatible protocol | One codebase, three backends (OpenRouter, Ollama, LM Studio) |
| Pydantic `mode='before'` coercers | LLMs emit `graduation_year: 2023` (int) — coerce silently |
| Separate `projects` from `experience` | Resumes commonly have distinct Project sections |
| Normalizer as post-processing step | Consistent output regardless of LLM variance in date/string formatting |
| QR scanning in parse stage | Decoded data feeds into LLM extraction naturally |
| `auto` parse mode with OCR fallback | Handles text + scanned PDFs transparently |
| System prompt as external `.md` file | Iterate on prompts without touching code |
| Synchronous `requests` | Resume count is low; simplicity > throughput |
| In-process semaphore (not Redis) | Single-server deployments; no external dependency |
