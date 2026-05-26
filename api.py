import asyncio
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.pdf_parser import pdf_to_markdown
from src.text_processor import clean_markdown, read_text_file
from src.llm_extractor import extract_to_json
from src.photo_extractor import extract_photo
from config import LLM_MAX_CONCURRENT, PHOTO_DIR, PHOTO_ENABLED

app = FastAPI(title="Resume Parser API", version="1.0.0")

PHOTO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/photos", StaticFiles(directory=str(PHOTO_DIR)), name="photos")

_llm_semaphore = asyncio.Semaphore(LLM_MAX_CONCURRENT)


# ── Shared helpers ───────────────────────────────────────────

async def _save_temp(file: UploadFile, suffix: str) -> Path:
    """Save uploaded file to a temp location and return its path."""
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    content = await file.read()
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


def _validate_pdf(file: UploadFile) -> str:
    """Validate file is a PDF. Returns the filename stem."""
    if not file.filename:
        raise HTTPException(400, "No file provided")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "PDF file required")
    return Path(file.filename).stem


def _parse_and_extract(tmp_path: Path, layout: str | None = None) -> dict:
    """Parse PDF to Markdown, clean, LLM extract. Returns dict."""
    md_text, _ = pdf_to_markdown(tmp_path, layout_override=layout)
    clean_md = clean_markdown(md_text)
    return extract_to_json(clean_md)


# ── Endpoints ────────────────────────────────────────────────

@app.post("/resume")
async def resume_only(file: UploadFile = File(...), layout: str | None = None):
    """Extract resume JSON only. No photo extraction. Fast."""
    if layout and layout not in ("auto", "single"):
        raise HTTPException(400, "layout must be 'auto' or 'single'")

    _validate_pdf(file)
    tmp_path = await _save_temp(file, ".pdf")
    try:
        async with _llm_semaphore:
            result = _parse_and_extract(tmp_path, layout)
        if isinstance(result, dict) and "error" in result:
            raise HTTPException(422, result["error"])
        return JSONResponse(content=result)
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/photo")
async def photo_only(file: UploadFile = File(...)):
    """Extract applicant photo only. No LLM — fast."""
    if not PHOTO_ENABLED:
        raise HTTPException(400, "Photo extraction disabled (PHOTO_ENABLED=false)")

    _validate_pdf(file)
    tmp_path = await _save_temp(file, ".pdf")
    try:
        photo_path = extract_photo(tmp_path, PHOTO_DIR)
        if not photo_path:
            raise HTTPException(404, "No photo found in this PDF")
        return JSONResponse({"photo_path": photo_path})
    finally:
        tmp_path.unlink(missing_ok=True)


@app.post("/full")
async def full_extract(file: UploadFile = File(...), layout: str | None = None):
    """Extract resume JSON + applicant photo. Full pipeline."""
    if layout and layout not in ("auto", "single"):
        raise HTTPException(400, "layout must be 'auto' or 'single'")

    _validate_pdf(file)
    tmp_path = await _save_temp(file, ".pdf")
    try:
        async with _llm_semaphore:
            result = _parse_and_extract(tmp_path, layout)

        if isinstance(result, dict) and "error" in result:
            raise HTTPException(422, result["error"])

        if PHOTO_ENABLED:
            photo_path = extract_photo(tmp_path, PHOTO_DIR)
            if photo_path:
                result.setdefault("personal_info", {})["photo_path"] = photo_path

        return JSONResponse(content=result)
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/queue/status")
async def queue_status():
    waiting = max(0, LLM_MAX_CONCURRENT - _llm_semaphore._value)
    return {
        "max_concurrent": LLM_MAX_CONCURRENT,
        "active": waiting,
        "waiting": max(0, waiting - 1) if waiting > 0 else 0,
    }
