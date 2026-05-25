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

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

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


def extract_pdf_bytes(pdf_bytes: bytes, filename: str = "upload.pdf") -> tuple[str, dict]:
    """Extract a PDF from raw bytes (e.g., FastAPI upload) to markdown.

    Args:
        pdf_bytes: Raw PDF file content.
        filename: Virtual filename for format detection.

    Returns:
        Tuple of (markdown_string, timing_dict).
    """
    logger.info("Converting from bytes (%d bytes)", len(pdf_bytes))

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        markdown, timing = _extract_impl(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return markdown, timing
