# Coding Standards

## Python Style

- **Formatting**: PEP 8 — 4-space indentation, 88-char line limit
- **Imports**: stdlib → third-party → local, each group blank-line separated
- **Type hints**: All function signatures include type hints (`str | Path`, `dict`, `bool`)
- **Docstrings**: Module-level and public functions only; inline for trivial helpers

## File Naming

| Type | Convention | Example |
|------|-----------|---------|
| Modules | `snake_case.py` | `pdf_parser.py`, `qr_decoder.py` |
| Config | `config.py` | `config.py` |
| Prompt files | `snake_case.md` | `resume_extraction.md` |
| Docs | `lowercase.md` | `architecture.md` |

## Module Boundaries

Each module in `src/` has exactly one responsibility:

| Module | Responsibility | Key dependencies |
|--------|---------------|-----------------|
| `models.py` | Pydantic schemas, field validators | `pydantic` |
| `pdf_parser.py` | PDF → Markdown, parse mode dispatch | `pymupdf4llm`, `ocrmypdf`, `qr_decoder` |
| `qr_decoder.py` | QR code image extraction + decoding | `pymupdf`, `pyzbar`, `pillow` |
| `text_processor.py` | TXT reading, layout-aware markdown cleaning | stdlib, `re` |
| `llm_extractor.py` | LLM API call, retry, JSON parsing | `requests`, `models`, `normalizer` |
| `normalizer.py` | Post-extraction date/string normalization | stdlib, `re` |

Cross-module imports are one-directional. No circular dependencies.

## Configuration

- `.env` → `config.py` → flat module-level variables
- `config.py` is the single source of truth
- No hardcoded URLs, keys, or paths in source
- Three-backend resolution: `if/elif/else` in `config.py` maps to unified `LLM_*` vars

## Adding a New Backend

Any service with an OpenAI-compatible `/chat/completions` endpoint works with no code changes in `llm_extractor.py`:

1. Add env vars section to `.env` and `.env.example`
2. Add defaults in `config.py`
3. Add branch in the backend resolver

Example for a new provider "FooAI":

```python
# config.py
FOOAI_BASE_URL = os.getenv("FOOAI_BASE_URL", "https://api.fooai.com/v1")
FOOAI_MODEL = os.getenv("FOOAI_MODEL", "foo-model")

if LLM_BACKEND == "fooai":
    LLM_BASE_URL = FOOAI_BASE_URL
    LLM_MODEL = FOOAI_MODEL
    LLM_API_KEY = os.getenv("FOOAI_API_KEY", "")
    ...
```

No other files change.

## Error Handling

- LLM extraction errors produce `{"error": "..."}` dicts, not exceptions
- File I/O errors propagate naturally (no broad try/except)
- API errors surface via `response.raise_for_status()` after retries exhausted
- Normalizer is defensive — handles missing keys, null values, unexpected types

## Dependencies

Minimal footprint — core stack:

| Package | Purpose |
|---------|---------|
| `pymupdf4llm` | PDF → Markdown |
| `pymupdf` | PDF image extraction (QR codes) |
| `pyzbar` | QR code decoding |
| `ocrmypdf` | OCR for scanned PDFs (optional) |
| `requests` | HTTP to LLM API |
| `pydantic` | Schema validation + coercion |
| `fastapi` + `uvicorn` | API server |
| `python-dotenv` | .env loading |
| `tqdm` | CLI progress bars |
| `pillow` | Image handling (QR) |

## Git Hygiene

- `.env` is gitignored (secrets)
- `data/output/` is gitignored (generated)
- `venv/`, `__pycache__/` are gitignored
- Commit messages: imperative mood, short subject
