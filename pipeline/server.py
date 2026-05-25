"""FastAPI server — simple sync resume extraction.

POST /extract?mode=full    — PDF → Markdown (Docling) → Structured JSON (LLM)
POST /extract?mode=partial — PDF → Markdown (Docling) only
GET  /health               — liveness check
"""

from __future__ import annotations

import logging
import time
from enum import StrEnum
from typing import Annotated

from fastapi import FastAPI, File, UploadFile, HTTPException, Query

from pipeline.config import config
from pipeline.extractor import extract_pdf_bytes
from pipeline.llm_parser import get_backend

# ── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("server")

ALLOWED_MIME = {"application/pdf"}


class ExtractMode(StrEnum):
    FULL = "full"
    PARTIAL = "partial"


# ── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Resume OCR Pipeline",
    description="Simple two-stage pipeline: PDF → Markdown (Docling) → Structured JSON (LLM)",
    version="0.3.0",
)


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "mode": "sync"}


@app.post("/extract")
async def extract_resume(
    file: Annotated[UploadFile, File()],
    mode: Annotated[
        ExtractMode | None,
        Query(description="Extraction mode: 'full' (Docling + LLM) or 'partial' (Docling only)"),
    ] = ExtractMode.FULL,
):
    """Upload a PDF resume. Returns JSON with extracted data.

    Modes:
    - **full** (default): PDF → Docling → Markdown → LLM → Structured Resume JSON
    - **partial**: PDF → Docling → Markdown only (no LLM call)
    """
    # Validate content type
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}. Only PDF is accepted.",
        )

    # Read with size limit
    contents = await file.read()

    if len(contents) > config.file_size_limit:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(contents)} bytes. Maximum is {config.file_size_limit} bytes (10 MB).",
        )

    if not contents:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    filename = file.filename or "upload.pdf"
    logger.info("Processing: %s (%d bytes), mode=%s", filename, len(contents), mode.value)

    # Stage 1: PDF → Markdown (Docling)
    stage1_start = time.perf_counter()
    try:
        markdown = extract_pdf_bytes(contents, filename)
    except Exception as exc:
        logger.exception("Docling extraction failed")
        raise HTTPException(
            status_code=422,
            detail=f"Document extraction failed: {type(exc).__name__}: {exc}",
        )
    stage1_ms = int((time.perf_counter() - stage1_start) * 1000)
    logger.info("Stage 1 (Docling): %d ms, %d chars", stage1_ms, len(markdown))

    response: dict = {
        "filename": filename,
        "mode": mode.value,
        "timing_ms": {"stage1_extraction": stage1_ms},
    }

    if mode == ExtractMode.PARTIAL:
        response["markdown"] = markdown
        return response

    # Stage 2: Markdown → Structured JSON (LLM)
    stage2_start = time.perf_counter()
    try:
        backend = get_backend()
        result_dict = await backend.parse_markdown(markdown)
    except Exception as exc:
        logger.exception("LLM parsing failed")
        raise HTTPException(
            status_code=422,
            detail=f"LLM parsing failed: {type(exc).__name__}: {exc}",
        )
    stage2_ms = int((time.perf_counter() - stage2_start) * 1000)
    logger.info("Stage 2 (%s): %d ms", backend.name, stage2_ms)

    response["backend_used"] = backend.name
    response["timing_ms"]["stage2_llm"] = stage2_ms
    response["timing_ms"]["total"] = stage1_ms + stage2_ms
    response["result"] = result_dict
    return response
