import asyncio
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from src.pdf_parser import pdf_to_markdown
from src.text_processor import clean_markdown
from src.llm_extractor import extract_to_json
from config import LLM_MAX_CONCURRENT

app = FastAPI(title="Resume Parser API", version="1.0.0")

# Semaphore to limit concurrent LLM calls (prevents rate-limit hammering)
_llm_semaphore = asyncio.Semaphore(LLM_MAX_CONCURRENT)


@app.post("/resume/upload")
async def upload_resume(file: UploadFile = File(...)):
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pdf", ".txt"):
        raise HTTPException(status_code=400, detail="Only .pdf and .txt files are supported")

    # Save upload to a temp file so pymupdf4llm can read from disk
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.close()

        # Stage 1: Parse to Markdown
        if suffix == ".pdf":
            md_text = pdf_to_markdown(tmp.name)
        else:
            md_text = Path(tmp.name).read_text(encoding="utf-8")

        # Stage 2: Clean
        clean_md = clean_markdown(md_text)

        # Stage 3: LLM extraction (rate-limited via semaphore)
        async with _llm_semaphore:
            result = extract_to_json(clean_md)

        # If extraction returned an error dict, surface it
        if isinstance(result, dict) and "error" in result:
            raise HTTPException(status_code=422, detail=result["error"])

        return JSONResponse(content=result)

    finally:
        # Always delete the temp file
        Path(tmp.name).unlink(missing_ok=True)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/queue/status")
async def queue_status():
    """Returns current queue depth (number of requests waiting for the LLM)."""
    waiting = max(0, LLM_MAX_CONCURRENT - _llm_semaphore._value)
    return {
        "max_concurrent": LLM_MAX_CONCURRENT,
        "active": waiting,
        "waiting": max(0, waiting - 1) if waiting > 0 else 0,
    }
