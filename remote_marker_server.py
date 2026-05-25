"""Remote Marker extraction server — deploy on ai.amirulaliff.com.

Receives PDFs via HTTP, runs Marker extraction, returns markdown.
Designed to offload GPU/CPU-heavy Marker from the laptop to a server
with better hardware and pre-cached models.

Usage:
    pip install marker-pdf fastapi uvicorn python-multipart
    uvicorn remote_marker_server:app --host 0.0.0.0 --port 8001

Endpoints:
    POST /extract-markdown  —  PDF bytes → markdown + timing
    GET  /health            —  liveness + marker init status
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, HTTPException, UploadFile

# ── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("remote-marker")

# ── Lifespan (pre-warm Marker models) ───────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    global converter, init_time_ms
    logger.info("Pre-warming Marker models...")
    t0 = time.perf_counter()
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict

    converter = PdfConverter(
        artifact_dict=create_model_dict(device="cpu", dtype="float16"),
    )
    init_time_ms = (time.perf_counter() - t0) * 1000
    logger.info("Marker ready in %.0f ms", init_time_ms)
    yield
    logger.info("Shutting down")


# ── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Remote Marker Server",
    description="Offload Marker PDF → Markdown extraction to a server with cached models.",
    version="0.1.0",
    lifespan=lifespan,
)

# Set by lifespan
converter = None
init_time_ms: float = 0.0

ALLOWED_MIME = {"application/pdf"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


# ── Routes ──────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "marker_ready": converter is not None,
        "marker_init_ms": init_time_ms,
    }


@app.post("/extract-markdown")
async def extract_markdown(file: UploadFile = File(...)):
    """Receive a PDF, return markdown + page/timing info.

    Request: multipart/form-data with a single 'file' field (PDF).
    Response: JSON with markdown, page_count, timing_ms.
    """
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}. Only PDF accepted.",
        )

    if converter is None:
        raise HTTPException(
            status_code=503,
            detail="Marker models not yet loaded. Try again in a moment.",
        )

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(contents)} bytes. Max is {MAX_FILE_SIZE}.",
        )

    if not contents:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    filename = file.filename or "upload.pdf"
    logger.info("Extracting: %s (%d bytes)", filename, len(contents))

    # Write to temp file (Marker prefers file paths)
    with NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        from marker.output import text_from_rendered

        t0 = time.perf_counter()
        rendered = converter(tmp_path)
        conversion_ms = (time.perf_counter() - t0) * 1000

        page_count = len(rendered.pages) if hasattr(rendered, "pages") else 0
        markdown, _, _ = text_from_rendered(rendered)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    markdown_chars = len(markdown)
    logger.info(
        "Extracted %d chars from %d pages in %.0f ms (%.0f ms/page)",
        markdown_chars, page_count, conversion_ms,
        conversion_ms / page_count if page_count else 0,
    )

    return {
        "filename": filename,
        "markdown": markdown,
        "page_count": page_count,
        "markdown_chars": markdown_chars,
        "timing_ms": {
            "conversion_ms": round(conversion_ms, 1),
            "ms_per_page": round(conversion_ms / page_count, 1) if page_count else 0,
        },
    }
