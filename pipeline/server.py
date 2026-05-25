"""FastAPI server — simple sync resume extraction.

POST /extract?mode=full    — PDF → Markdown (Marker) → Structured JSON (LLM)
POST /extract?mode=partial — PDF → Markdown (Marker) only
GET  /health               — liveness check + init timing
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from enum import StrEnum
from typing import Annotated

from fastapi import FastAPI, File, UploadFile, HTTPException, Query

from pipeline.config import config
from pipeline.extractor import extract_pdf_bytes, warm_up, get_init_time_ms
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


# ── Lifespan (pre-warm on startup) ──────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm Marker models on startup so the first request is fast."""
    logger.info("Pre-warming Marker models...")
    init_ms = warm_up()
    logger.info("Marker pre-warmed in %.0f ms — ready for requests", init_ms)
    yield
    logger.info("Shutting down")


# ── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Resume OCR Pipeline",
    description="Two-stage pipeline: PDF → Markdown (Marker) → Structured JSON (LLM)",
    version="0.4.0",
    lifespan=lifespan,
)


# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mode": "sync",
        "marker_init_ms": get_init_time_ms(),
        "marker_ready": get_init_time_ms() > 0,
    }


@app.post("/extract")
async def extract_resume(
    file: Annotated[UploadFile, File()],
    mode: Annotated[
        ExtractMode | None,
        Query(description="Extraction mode: 'full' (Marker + LLM) or 'partial' (Marker only)"),
    ] = ExtractMode.FULL,
):
    """Upload a PDF resume. Returns JSON with extracted data.

    Modes:
    - **full** (default): PDF → Marker → Markdown → LLM → Structured Resume JSON
    - **partial**: PDF → Marker → Markdown only (no LLM call)
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

    # Stage 1: PDF → Markdown (Marker)
    stage1_start = time.perf_counter()
    try:
        markdown, stage1_timing = extract_pdf_bytes(contents, filename)
    except Exception as exc:
        logger.exception("Marker extraction failed")
        raise HTTPException(
            status_code=422,
            detail=f"Document extraction failed: {type(exc).__name__}: {exc}",
        )
    stage1_ms = int((time.perf_counter() - stage1_start) * 1000)
    logger.info("Stage 1 (Marker): %d ms total", stage1_ms)

    response: dict = {
        "filename": filename,
        "mode": mode.value,
        "timing_ms": {
            "stage1_extraction": stage1_ms,
            "stage1_detail": stage1_timing,
        },
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
