import pymupdf4llm
import re
from pathlib import Path


def pdf_to_markdown(pdf_path: str | Path, layout_override: str | None = None) -> str:
    """
    Convert a PDF to Markdown using the configured parse mode.
    Also scans for QR codes and appends decoded data.

    Modes (set via PDF_PARSE_MODE in .env / config):
      - auto:   Try both layouts; fall back to OCR if sparse.
      - native: pymupdf4llm only (fast).
      - ocr:    Always OCR first (thorough).
      - hybrid: Run native + OCR, merge best of both.

    Args:
        pdf_path: Path to the PDF file.
        layout_override: Force page layout ("auto" or "single").
    """
    from config import PDF_PARSE_MODE, OCR_LANGUAGE, OCR_MIN_CHARS, QR_SCAN_ENABLED, QR_SAVE_ARTIFACTS, PHOTO_ENABLED, PHOTO_DIR

    pdf_path = Path(pdf_path)

    if PDF_PARSE_MODE == "ocr":
        md = _ocr_then_parse(pdf_path, OCR_LANGUAGE, PDF_PAGE_LAYOUT)
    elif PDF_PARSE_MODE == "native":
        layout = layout_override or PDF_PAGE_LAYOUT
        md = _native_parse(pdf_path, layout)
    elif PDF_PARSE_MODE == "hybrid":
        md = _hybrid_parse(pdf_path, OCR_LANGUAGE, OCR_MIN_CHARS)
    else:  # auto
        md = _auto_parse(pdf_path, OCR_LANGUAGE, OCR_MIN_CHARS, layout_override)

    # ── QR code scanning ─────────────────────────────────────
    if QR_SCAN_ENABLED:
        from src.qr_decoder import extract_qr_from_pdf, qr_results_to_markdown
        qr_results = extract_qr_from_pdf(pdf_path, save_artifacts=QR_SAVE_ARTIFACTS)
        if qr_results:
            print(f"[QR] Found {len(qr_results)} QR code(s)")
            md += "\n" + qr_results_to_markdown(qr_results)

    # ── Photo extraction ────────────────────────────────────
    photo_path = None
    if PHOTO_ENABLED:
        from src.photo_extractor import extract_photo
        photo_path = extract_photo(pdf_path, PHOTO_DIR)

    return md, photo_path


# ── Parse strategies ─────────────────────────────────────────

def _auto_parse(pdf_path: Path, ocr_lang: str, min_chars: int, layout_override: str | None) -> str:
    """Try both layouts; fall back to OCR if sparse."""
    if layout_override:
        md = _native_parse(pdf_path, layout_override)
        print(f"[AUTO] Layout override → {layout_override}")
    else:
        md_auto = _native_parse(pdf_path, "auto")
        md_single = _native_parse(pdf_path, "single")
        h_auto = _count_section_headers(md_auto)
        h_single = _count_section_headers(md_single)
        wc_auto = len(md_auto.split())
        wc_single = len(md_single.split())

        if h_single > h_auto and wc_single > wc_auto * 1.30:
            md = md_single
            print(f"[AUTO] Multi-column detected (single={wc_single} vs auto={wc_auto} words) → single")
        else:
            md = md_auto
            print(f"[AUTO] Using auto layout ({wc_auto} words)")

    if len(md.strip()) < min_chars or len(md.split()) < 50:
        print(f"[AUTO] Parse too sparse ({len(md)} chars) — falling back to OCR")
        md = _ocr_then_parse(pdf_path, ocr_lang, PDF_PAGE_LAYOUT)

    return md


def _hybrid_parse(pdf_path: Path, ocr_lang: str, min_chars: int) -> str:
    """Run native + OCR, merge best of both. Always produces richer output than either alone."""
    # Run both parsers
    md_native = _native_parse(pdf_path, "auto")
    md_single = _native_parse(pdf_path, "single")
    h_auto = _count_section_headers(md_native)
    h_single = _count_section_headers(md_single)
    if h_single > h_auto and len(md_single.split()) > len(md_native.split()) * 1.30:
        md_native = md_single
        print(f"[HYBRID] Multi-column detected — using single layout")

    md_ocr = _ocr_then_parse(pdf_path, ocr_lang, "auto")
    wc_native = len(md_native.split())
    wc_ocr = len(md_ocr.split())

    if wc_ocr > wc_native * 1.30:
        # OCR found significantly more content — use it as base, preserving native tables
        print(f"[HYBRID] OCR richer ({wc_ocr} vs {wc_native} words) — merging native tables into OCR")
        md = _merge_native_tables(md_ocr, md_native)
    else:
        print(f"[HYBRID] Native sufficient ({wc_native} words)")
        md = md_native

    if len(md.strip()) < min_chars or len(md.split()) < 50:
        print(f"[HYBRID] Output still sparse — using raw OCR")
        md = md_ocr

    return md


def _merge_native_tables(ocr_text: str, native_text: str) -> str:
    """
    Use OCR text as the base, but extract Markdown tables from native
    and insert them into corresponding positions in the OCR text.
    Tables in native preserve column structure that OCR loses.
    """
    # Extract all Markdown tables from native text
    table_pattern = re.compile(r"(\|.+\|\n\|[-|\s]+\|\n(?:\|.+\|\n)+)", re.MULTILINE)
    native_tables = table_pattern.findall(native_text)
    if not native_tables:
        return ocr_text

    # For each table, try to find its approximate position in OCR text
    # by looking for shared keywords near the table in native
    result = ocr_text
    for table in native_tables:
        # Find the table's context in native (2 lines before)
        table_pos = native_text.find(table)
        if table_pos < 0:
            continue
        context_start = max(0, table_pos - 200)
        context = native_text[context_start:table_pos]
        # Extract the last meaningful line as anchor
        context_lines = [l for l in context.splitlines() if l.strip() and not l.startswith("|")]
        if not context_lines:
            continue
        anchor = context_lines[-1].strip()[:60]

        # Find anchor in OCR text and insert table after it
        anchor_pos = result.find(anchor)
        if anchor_pos >= 0:
            insert_pos = anchor_pos + len(anchor)
            # Only insert if table isn't already there
            if table not in result[max(0, anchor_pos - 100):insert_pos + 200]:
                result = result[:insert_pos] + "\n\n" + table + result[insert_pos:]

    return result


# ── Low-level parsers ────────────────────────────────────────

def _native_parse(pdf_path: Path, page_layout: str = "auto") -> str:
    """Convert PDF to Markdown using pymupdf4llm (text layer extraction)."""
    return pymupdf4llm.to_markdown(str(pdf_path), page_layout=page_layout)


def _ocr_then_parse(pdf_path: Path, language: str = "eng", page_layout: str = "auto") -> str:
    """Run OCR on the PDF, then convert the searchable result to Markdown."""
    try:
        import ocrmypdf
    except ImportError:
        print("[OCR] ocrmypdf not installed — falling back to native")
        return _native_parse(pdf_path, page_layout)

    ocr_path = pdf_path.with_name(f"{pdf_path.stem}_ocr{pdf_path.suffix}")
    try:
        print(f"[OCR] Running ocrmypdf (lang={language}) …")
        ocrmypdf.ocr(str(pdf_path), str(ocr_path), language=language, deskew=True)
        md = _native_parse(ocr_path, page_layout)
        return md
    except Exception as e:
        print(f"[OCR] Failed: {e} — falling back to native")
        return _native_parse(pdf_path, page_layout)
    finally:
        ocr_path.unlink(missing_ok=True)


# ── Helpers ──────────────────────────────────────────────────

_SECTION_HEADERS_RE = re.compile(
    r"^#{1,3}\s*(?:SUMMARY|PROFILE|EXPERIENCE|WORK\s*EXPERIENCE|"
    r"PROFESSIONAL\s*HISTORY|EMPLOYMENT|PROJECTS?|EDUCATION|"
    r"SKILLS?|TECHNICAL\s*SKILLS?|CERTIFICATIONS?|ACHIEVEMENTS?|"
    r"LANGUAGES?|REFERENCES?|PERSONAL\s*INFO)",
    re.IGNORECASE | re.MULTILINE,
)


def _count_section_headers(md_text: str) -> int:
    """Count recognizable resume section headers in the Markdown."""
    return len(_SECTION_HEADERS_RE.findall(md_text))
