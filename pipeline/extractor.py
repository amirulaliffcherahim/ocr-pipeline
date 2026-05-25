"""Stage 1 — Document extraction: PDF → Markdown via Marker.

Marker converts PDFs to markdown quickly and accurately, preserving
tables, forms, equations, links, references, and code blocks.

Optimization notes:
- Singleton converter with lazy init + explicit pre-warm via warm_up().
- Pass device="cpu" and dtype=torch.float16 to reduce memory and speed up CPU inference.
- Profiling via log level: INFO shows stage timings, DEBUG shows per-page breakdown.
"""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path

import httpx
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

from pipeline.config import config

logger = logging.getLogger(__name__)

# Singleton converter — Marker models are heavy to reload
_converter: PdfConverter | None = None
_converter_init_time_ms: float = 0.0


def _get_converter(device: str = "cpu", dtype: str = "float16") -> PdfConverter:
    """Return the singleton PdfConverter, initializing on first call.

    Args:
        device: Torch device ("cpu", "cuda", "mps"). Defaults to "cpu".
        dtype: Torch dtype for models ("float16", "float32", "bfloat16").
               float16 halves memory usage, often faster on CPU too.
    """
    global _converter, _converter_init_time_ms
    if _converter is None:
        logger.info("Initializing Marker PdfConverter (device=%s, dtype=%s)...", device, dtype)
        t0 = time.perf_counter()
        _converter = PdfConverter(
            artifact_dict=create_model_dict(device=device, dtype=dtype),
        )
        _converter_init_time_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "Marker PdfConverter initialized in %.0f ms (device=%s, dtype=%s)",
            _converter_init_time_ms, device, dtype,
        )
    return _converter


def warm_up(device: str = "cpu", dtype: str = "float16") -> float:
    """Pre-warm Marker by loading models into memory.

    Call this on app startup so the first request is fast.

    Returns:
        Initialization time in milliseconds.
    """
    _get_converter(device=device, dtype=dtype)
    return _converter_init_time_ms


def get_init_time_ms() -> float:
    """Return the converter init time, or 0 if not yet initialized."""
    return _converter_init_time_ms


def _extract_impl(file_path: str | Path) -> tuple[str, dict]:
    """Core extraction: convert PDF to markdown with timing profiling.

    Returns:
        Tuple of (markdown_text, timing_dict) where timing_dict contains:
        - page_count: Number of pages
        - conversion_ms: Time spent in Marker's __call__
        - markdown_chars: Length of output markdown
    """
    converter = _get_converter()
    path_str = str(file_path)

    logger.info("Converting: %s", path_str)
    t0 = time.perf_counter()
    rendered = converter(path_str)
    conversion_ms = (time.perf_counter() - t0) * 1000

    page_count = len(rendered.pages) if hasattr(rendered, "pages") else 0
    markdown, _, _ = text_from_rendered(rendered)
    markdown_chars = len(markdown)

    timing = {
        "page_count": page_count,
        "conversion_ms": round(conversion_ms, 1),
        "ms_per_page": round(conversion_ms / page_count, 1) if page_count else 0,
        "markdown_chars": markdown_chars,
        "chars_per_page": round(markdown_chars / page_count, 1) if page_count else 0,
    }

    logger.info(
        "Extracted %d chars from %d pages in %.0f ms (%.0f ms/page)",
        markdown_chars, page_count, conversion_ms,
        conversion_ms / page_count if page_count else 0,
    )

    return markdown, timing


def extract_pdf(file_path: str | Path) -> str:
    """Extract a PDF to markdown using Marker.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Markdown string preserving layout and reading order.
    """
    markdown, _ = _extract_impl(file_path)
    return markdown


def extract_pdf_bytes(
    pdf_bytes: bytes,
    filename: str = "upload.pdf",
) -> tuple[str, dict]:
    """Extract a PDF from raw bytes to markdown.

    Routes to remote Marker server if REMOTE_MARKER_URL is configured,
    otherwise uses local Marker.

    Returns:
        Tuple of (markdown_string, timing_dict).
    """
    if config.remote_marker_url:
        return _extract_remote(pdf_bytes, filename)
    return _extract_local(pdf_bytes, filename)


def _extract_local(pdf_bytes: bytes, filename: str = "upload.pdf") -> tuple[str, dict]:
    """Extract a PDF locally using Marker."""
    logger.info("Converting from bytes (%d bytes)", len(pdf_bytes))

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        markdown, timing = _extract_impl(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return markdown, timing


def _extract_remote(pdf_bytes: bytes, filename: str = "upload.pdf") -> tuple[str, dict]:
    """Extract a PDF by calling the remote Marker server."""
    url = f"{config.remote_marker_url}/extract-markdown"
    logger.info(
        "Remote extraction: %s (%d bytes) -> %s",
        filename, len(pdf_bytes), url,
    )

    t0 = time.perf_counter()
    try:
        response = httpx.post(
            url,
            files={"file": (filename, pdf_bytes, "application/pdf")},
            timeout=config.remote_marker_timeout,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.exception("Remote Marker request failed")
        raise RuntimeError(
            f"Remote Marker extraction failed: {type(exc).__name__}: {exc}"
        ) from exc

    elapsed_ms = (time.perf_counter() - t0) * 1000
    data = response.json()

    remote_timing = data.get("timing_ms", {})
    timing = {
        "page_count": data.get("page_count", 0),
        "conversion_ms": remote_timing.get("conversion_ms", 0),
        "ms_per_page": remote_timing.get("ms_per_page", 0),
        "markdown_chars": data.get("markdown_chars", 0),
        "roundtrip_ms": round(elapsed_ms, 1),
        "remote": True,
    }

    logger.info(
        "Remote extraction: %d pages, %.0f ms roundtrip (%.0f ms server)",
        timing["page_count"], elapsed_ms, timing["conversion_ms"],
    )

    return data["markdown"], timing
