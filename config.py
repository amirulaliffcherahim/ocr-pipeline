import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "data/input"
OUTPUT_DIR = BASE_DIR / "data/output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── LLM Backend ──────────────────────────────────────────────
# Options: openrouter | lmstudio | ollama
LLM_BACKEND = os.getenv("LLM_BACKEND", "openrouter")

# ── OpenRouter (cloud) ──────────────────────────────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "qwen/qwen3-1.7b")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_TIMEOUT = int(os.getenv("OPENROUTER_TIMEOUT", "120"))
OPENROUTER_TEMPERATURE = float(os.getenv("OPENROUTER_TEMPERATURE", "0.0"))
OPENROUTER_MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "8192"))

# ── LM Studio (local) ───────────────────────────────────────
LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "gemma-3-4b-it")
LM_STUDIO_TIMEOUT = int(os.getenv("LM_STUDIO_TIMEOUT", "120"))
LM_STUDIO_TEMPERATURE = float(os.getenv("LM_STUDIO_TEMPERATURE", "0.0"))
LM_STUDIO_MAX_TOKENS = int(os.getenv("LM_STUDIO_MAX_TOKENS", "8192"))

# ── Ollama (local) ──────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.0"))
OLLAMA_MAX_TOKENS = int(os.getenv("OLLAMA_MAX_TOKENS", "8192"))

# ── Reasoning (for Qwen 3, DeepSeek-R1, etc.) ───────────────
LLM_REASONING_ENABLED = os.getenv("LLM_REASONING_ENABLED", "false").lower() == "true"

# Resolve active backend
if LLM_BACKEND == "ollama":
    LLM_BASE_URL = OLLAMA_BASE_URL
    LLM_MODEL = OLLAMA_MODEL
    LLM_API_KEY = ""
    LLM_TIMEOUT = OLLAMA_TIMEOUT
    LLM_TEMPERATURE = OLLAMA_TEMPERATURE
    LLM_MAX_TOKENS = OLLAMA_MAX_TOKENS
elif LLM_BACKEND == "lmstudio":
    LLM_BASE_URL = LM_STUDIO_BASE_URL
    LLM_MODEL = LM_STUDIO_MODEL
    LLM_API_KEY = ""
    LLM_TIMEOUT = LM_STUDIO_TIMEOUT
    LLM_TEMPERATURE = LM_STUDIO_TEMPERATURE
    LLM_MAX_TOKENS = LM_STUDIO_MAX_TOKENS
else:  # openrouter
    LLM_BASE_URL = OPENROUTER_BASE_URL
    LLM_MODEL = OPENROUTER_MODEL
    LLM_API_KEY = OPENROUTER_API_KEY
    LLM_TIMEOUT = OPENROUTER_TIMEOUT
    LLM_TEMPERATURE = OPENROUTER_TEMPERATURE
    LLM_MAX_TOKENS = OPENROUTER_MAX_TOKENS

# ── Input Truncation ────────────────────────────────────────
# Max characters of resume text sent to the LLM (safety limit)
LLM_MAX_INPUT_CHARS = int(os.getenv("LLM_MAX_INPUT_CHARS", "200000"))

# ── PDF Parsing ─────────────────────────────────────────────
# auto  = try native first, fall back to OCR if output looks empty/scanned
# native = pymupdf4llm only (fast, good for text-based PDFs)
# ocr    = always OCR first (slow, best for scanned/image-heavy PDFs)
PDF_PARSE_MODE = os.getenv("PDF_PARSE_MODE", "auto")
OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "eng")     # tesseract lang code
OCR_MIN_CHARS = int(os.getenv("OCR_MIN_CHARS", "300"))  # fallback threshold

# ── PDF Layout ──────────────────────────────────────────────
# Controls text extraction order for multi-column resumes.
# auto   = let pymupdf decide (default — may interleave columns)
# single = force single-column ordering (better for 2-column resumes)
PDF_PAGE_LAYOUT = os.getenv("PDF_PAGE_LAYOUT", "auto")

# ── QR Code Scanning ────────────────────────────────────────
QR_SCAN_ENABLED = os.getenv("QR_SCAN_ENABLED", "true").lower() == "true"
QR_SAVE_ARTIFACTS = os.getenv("QR_SAVE_ARTIFACTS", "false").lower() == "true"

# ── Rate Limiting & Retry ───────────────────────────────────
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_RETRY_BACKOFF = float(os.getenv("LLM_RETRY_BACKOFF", "2.0"))   # multiplier
LLM_MAX_CONCURRENT = int(os.getenv("LLM_MAX_CONCURRENT", "1"))
