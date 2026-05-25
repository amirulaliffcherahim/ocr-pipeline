"""Stage 1 — Document extraction: PDF → Markdown via Marker.

Marker converts PDFs to markdown quickly and accurately, preserving
tables, forms, equations, links, references, and code blocks.
"""

from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

logger = logging.getLogger(__name__)

# Singleton converter — Marker models are heavy to reload
_converter: PdfConverter | None = None


def _get_converter() -> PdfConverter:
    global _converter
    if _converter is None:
        logger.info("Initializing Marker PdfConverter (first call)...")
        _converter = PdfConverter(artifact_dict=create_model_dict())
    return _converter


def extract_pdf(file_path: str | Path) -> str:
    """Extract a PDF to markdown using Marker.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Markdown string preserving layout and reading order.
    """
    converter = _get_converter()
    logger.info(f"Converting: {file_path}")

    rendered = converter(str(file_path))
    markdown, _, _ = text_from_rendered(rendered)

    logger.info(f"Extracted {len(markdown):,} characters of markdown")
    return markdown


def extract_pdf_bytes(pdf_bytes: bytes, filename: str = "upload.pdf") -> str:
    """Extract a PDF from raw bytes (e.g., FastAPI upload) to markdown.

    Args:
        pdf_bytes: Raw PDF file content.
        filename: Virtual filename for format detection.

    Returns:
        Markdown string preserving layout and reading order.
    """
    converter = _get_converter()
    logger.info(f"Converting from bytes ({len(pdf_bytes):,} bytes)")

    # Marker converter works with file paths — write to temp file
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        rendered = converter(tmp_path)
        markdown, _, _ = text_from_rendered(rendered)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    logger.info(f"Extracted {len(markdown):,} characters of markdown")
    return markdown
