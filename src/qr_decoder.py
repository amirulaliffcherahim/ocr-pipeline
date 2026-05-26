"""
QR code detection and decoding from PDF pages.

Uses pymupdf (fitz) to extract embedded images from each page,
then pyzbar to detect and decode QR codes within those images.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import List

import fitz  # pymupdf
from PIL import Image
from pyzbar.pyzbar import decode as pyzbar_decode


class QRResult:
    """A decoded QR code with its data and optional saved image path."""

    def __init__(self, data: str, qr_type: str, page: int, artifact_path: str | None = None):
        self.data = data
        self.qr_type = qr_type  # e.g. "URL", "TEXT", "EMAIL", "VCARD"
        self.page = page
        self.artifact_path = artifact_path


def extract_qr_from_pdf(
    pdf_path: str | Path,
    save_artifacts: bool = False,
    artifact_dir: str | Path | None = None,
) -> List[QRResult]:
    """
    Scan all pages of a PDF for QR codes.

    Args:
        pdf_path: Path to the PDF file.
        save_artifacts: If True, save detected QR code images to disk.
        artifact_dir: Directory for artifact images (default: pdf_path.parent / "qr_artifacts").

    Returns:
        List of QRResult objects with decoded data.
    """
    pdf_path = Path(pdf_path)
    doc = fitz.open(str(pdf_path))
    results: List[QRResult] = []

    if save_artifacts:
        artifact_dir = Path(artifact_dir or pdf_path.parent / "qr_artifacts")
        artifact_dir.mkdir(parents=True, exist_ok=True)

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]

            # Extract images embedded in this page
            image_list = page.get_images(full=True)
            for img_index, img_info in enumerate(image_list):
                xref = img_info[0]
                base_image = doc.extract_image(xref)

                if base_image is None:
                    continue

                image_bytes = base_image["image"]
                ext = base_image["ext"]  # "png", "jpeg", etc.

                # Decode QR codes from this image
                try:
                    pil_image = Image.open(io.BytesIO(image_bytes))
                    decoded = pyzbar_decode(pil_image)

                    for code in decoded:
                        data = code.data.decode("utf-8", errors="replace")
                        qr_type = _classify_qr_data(data)

                        artifact_path = None
                        if save_artifacts and artifact_dir:
                            fname = f"page{page_num + 1}_img{img_index}.{ext}"
                            art_path = artifact_dir / fname
                            pil_image.save(str(art_path))
                            artifact_path = str(art_path)

                        results.append(QRResult(
                            data=data,
                            qr_type=qr_type,
                            page=page_num + 1,
                            artifact_path=artifact_path,
                        ))
                except Exception:
                    # Skip images that can't be decoded (not a valid image format)
                    continue

    finally:
        doc.close()

    return results


def qr_results_to_markdown(results: List[QRResult]) -> str:
    """
    Convert QR code results into Markdown text for the LLM to consume.

    Example output:
        [QR-URL page 1]: https://linkedin.com/in/username
        [QR-URL page 1]: https://github.com/username
    """
    if not results:
        return ""

    lines = ["## QR Codes Found"]
    for r in results:
        label = f"[QR-{r.qr_type} page {r.page}]"
        lines.append(f"{label}: {r.data}")
        if r.artifact_path:
            lines.append(f"  (artifact: {r.artifact_path})")
    return "\n".join(lines) + "\n"


def _classify_qr_data(data: str) -> str:
    """Classify decoded QR data into a human-readable type."""
    data_lower = data.strip().lower()
    if data_lower.startswith(("http://", "https://")):
        return "URL"
    if data_lower.startswith("mailto:") or "@" in data_lower:
        return "EMAIL"
    if data_lower.startswith("begin:vcard") or data_lower.startswith("begin:mecard"):
        return "VCARD"
    if data_lower.startswith("tel:"):
        return "PHONE"
    return "TEXT"
