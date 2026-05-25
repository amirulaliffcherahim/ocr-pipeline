"""Standalone Marker profiling — times model load + PDF extraction end-to-end.

Usage: python profile_marker.py [path/to/resume.pdf]
"""
import sys
import time
from pathlib import Path

# ── 1. Model init timing ───────────────────────────────────────────────────
print("=" * 60)
print("PHASE 1: Model initialization (cold start)")
print("=" * 60)

t0 = time.perf_counter()

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

t_import = time.perf_counter() - t0
print(f"  Import marker modules: {t_import * 1000:.0f} ms")

t1 = time.perf_counter()
converter = PdfConverter(
    artifact_dict=create_model_dict(device="cpu", dtype="float16"),
)
t_init = time.perf_counter() - t1
print(f"  PdfConverter init (5 models): {t_init * 1000:.0f} ms")
print(f"  Total cold start: {(t_import + t_init) * 1000:.0f} ms")

# ── 2. PDF extraction timing ───────────────────────────────────────────────
pdf_path = sys.argv[1] if len(sys.argv) > 1 else "resume/CV - Muhammad Amirul Aliff.pdf"
file_size = Path(pdf_path).stat().st_size if Path(pdf_path).exists() else 0

print()
print("=" * 60)
print(f"PHASE 2: PDF extraction")
print(f"  File: {pdf_path}")
print(f"  Size: {file_size:,} bytes ({file_size / 1024:.0f} KB)")
print("=" * 60)

t2 = time.perf_counter()
rendered = converter(pdf_path)
t_convert = time.perf_counter() - t2

page_count = len(rendered.pages) if hasattr(rendered, "pages") else 0
markdown, _, _ = text_from_rendered(rendered)
markdown_chars = len(markdown)

print(f"  Pages: {page_count}")
print(f"  Conversion time: {t_convert * 1000:.0f} ms")
print(f"  Time per page: {t_convert * 1000 / page_count:.0f} ms" if page_count else "  N/A")
print(f"  Markdown output: {markdown_chars:,} chars")
print(f"  Chars per page: {markdown_chars / page_count:.0f}" if page_count else "  N/A")

# ── 3. Summary ─────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"  Model init : {t_init * 1000:>8.0f} ms  (one-time, cached after pre-warm)")
print(f"  Conversion : {t_convert * 1000:>8.0f} ms  (per-resume)")
print(f"  Total      : {(t_import + t_init + t_convert) * 1000:>8.0f} ms  (first request)")
print(f"  Subsequent : {t_convert * 1000:>8.0f} ms  (after pre-warm)")
print()

# Save markdown for inspection
out_path = Path(pdf_path).with_suffix(".md")
out_path.write_text(markdown, encoding="utf-8")
print(f"  Markdown saved to: {out_path}")
print(f"  First 500 chars preview:")
print("  ---")
for line in markdown[:500].split("\n")[:15]:
    print(f"  | {line[:100]}")
print("  ---")
