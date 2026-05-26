import pymupdf4llm
from pathlib import Path


def pdf_to_markdown(pdf_path: str | Path) -> str:
    """
    Convert a PDF to Markdown using the configured parse mode.
    Also scans for QR codes and appends decoded data.

    Modes (set via PDF_PARSE_MODE in .env / config):
      - auto:   Try native first; fall back to OCR if output appears empty/scanned.
      - native: pymupdf4llm only (fast, works for text-based PDFs).
      - ocr:    Always OCR first via ocrmypdf (handles scanned/image-heavy PDFs).
    """
    from config import PDF_PARSE_MODE, OCR_LANGUAGE, OCR_MIN_CHARS, QR_SCAN_ENABLED, QR_SAVE_ARTIFACTS

    pdf_path = Path(pdf_path)

    if PDF_PARSE_MODE == "ocr":
        md = _ocr_then_parse(pdf_path, OCR_LANGUAGE)
    elif PDF_PARSE_MODE == "native":
        md = _native_parse(pdf_path, PDF_PAGE_LAYOUT)
    else:
        # auto mode: try both layouts, pick best word count, fall back to OCR if sparse
        md_auto = _native_parse(pdf_path, "auto")
        md_single = _native_parse(pdf_path, "single")

        wc_auto = len(md_auto.split())
        wc_single = len(md_single.split())

        if wc_single > wc_auto * 1.15:
            # single layout produced 15%+ more words — likely a 2-column resume
            md = md_single
            print(f"[AUTO] Detected multi-column layout (single={wc_single} vs auto={wc_auto} words) → using single")
        else:
            md = md_auto
            print(f"[AUTO] Single-column layout (auto={wc_auto} words)")

        if len(md.strip()) < OCR_MIN_CHARS or len(md.split()) < 50:
            print(f"[AUTO] Parse too sparse ({len(md)} chars) — falling back to OCR")
            md = _ocr_then_parse(pdf_path, OCR_LANGUAGE)

    # ── QR code scanning ─────────────────────────────────────
    if QR_SCAN_ENABLED:
        from src.qr_decoder import extract_qr_from_pdf, qr_results_to_markdown

        qr_results = extract_qr_from_pdf(
            pdf_path,
            save_artifacts=QR_SAVE_ARTIFACTS,
        )
        if qr_results:
            print(f"[QR] Found {len(qr_results)} QR code(s)")
            md += "\n" + qr_results_to_markdown(qr_results)

    return md


def _native_parse(pdf_path: Path, page_layout: str = "auto") -> str:
    """Convert PDF to Markdown using pymupdf4llm (text layer extraction)."""
    return pymupdf4llm.to_markdown(str(pdf_path), page_layout=page_layout)


def _ocr_then_parse(pdf_path: Path, language: str = "eng") -> str:
    """Run OCR on the PDF, then convert the searchable result to Markdown."""
    import ocrmypdf

    ocr_path = pdf_path.with_name(f"{pdf_path.stem}_ocr{pdf_path.suffix}")
    print(f"[OCR] Running ocrmypdf (lang={language}) …")
    ocrmypdf.ocr(
        str(pdf_path),
        str(ocr_path),
        language=language,
        deskew=True,
    )
    md = _native_parse(ocr_path, PDF_PAGE_LAYOUT)
    # Clean up the temporary OCR'd PDF
    ocr_path.unlink(missing_ok=True)
    return md
