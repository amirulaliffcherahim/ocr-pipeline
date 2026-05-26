"""
Extract applicant photo from resume PDFs.

Scans page 1 for embedded images and identifies the most likely
headshot based on size, aspect ratio, and position on the page.
"""
from __future__ import annotations

import io
from pathlib import Path

import fitz  # pymupdf
from PIL import Image


def extract_photo(pdf_path: str | Path, output_dir: str | Path) -> str | None:
    """
    Extract the most likely applicant photo from page 1 of a PDF.

    Heuristics for photo detection:
      - Largest image on page 1 (photos are usually the biggest image)
      - Aspect ratio between 0.5 and 1.5 (portrait-ish, not a banner/logo)
      - At least 20KB in size (filters tiny icons/logos)

    Args:
        pdf_path: Path to the PDF file.
        output_dir: Directory to save the extracted photo.

    Returns:
        Relative path to the saved photo, or None if no photo found.
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    candidates: list[tuple[float, int, bytes, str]] = []  # (score, xref, bytes, ext)

    try:
        page = doc[0]  # page 1 only — photos are always on the first page
        image_list = page.get_images(full=True)

        for img_info in image_list:
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            if base_image is None:
                continue

            image_bytes = base_image["image"]
            ext = base_image["ext"]  # "png", "jpeg", etc.

            # Skip tiny images (icons, logos)
            if len(image_bytes) < 20_000:
                continue

            # Score by size + aspect ratio
            try:
                pil_img = Image.open(io.BytesIO(image_bytes))
                w, h = pil_img.size
                aspect = w / h if h > 0 else 0

                # Face photos are roughly square or slightly taller than wide
                if 0.5 <= aspect <= 1.5:
                    score = len(image_bytes)  # bigger = more likely to be the photo
                else:
                    score = len(image_bytes) * 0.3  # penalize non-portrait images

                candidates.append((score, xref, image_bytes, ext))
            except Exception:
                continue

    finally:
        doc.close()

    if not candidates:
        return None

    # Pick the best candidate (highest score)
    candidates.sort(key=lambda c: c[0], reverse=True)
    _, _, best_bytes, best_ext = candidates[0]

    # Save the photo
    ext_normalized = best_ext if best_ext in ("png", "jpeg", "jpg") else "jpg"
    photo_name = f"{pdf_path.stem}_photo.{ext_normalized}"
    photo_path = output_dir / photo_name
    with open(photo_path, "wb") as f:
        f.write(best_bytes)

    print(f"[PHOTO] Extracted: {photo_name} ({len(best_bytes) / 1024:.0f} KB)")
    return f"photos/{photo_name}"
