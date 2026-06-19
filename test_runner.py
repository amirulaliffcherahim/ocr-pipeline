"""
Batch test runner for the resume OCR pipeline.

Processes all PDFs in a directory and optionally compares results
against ground truth JSON files for per-section accuracy scoring.

Usage:
    python test_runner.py --dir data/input
    python test_runner.py --dir data/test_pdfs --ground-truth data/ground_truth
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path
from datetime import datetime

from src.pdf_parser import pdf_to_markdown
from src.text_processor import read_text_file, clean_markdown
from src.llm_extractor import extract_to_json
from config import OUTPUT_DIR

logger = logging.getLogger(__name__)

DEFAULT_RESULTS_DIR = Path("data/test_results")


# ── Scoring ──────────────────────────────────────────────────

def _jaccard(set_a: set, set_b: set) -> float:
    """Jaccard similarity between two sets. 1.0 = perfect match."""
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _fuzzy_match(a: str | None, b: str | None) -> bool:
    """Case-insensitive, whitespace-trimmed string match."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return a.strip().lower() == b.strip().lower()


def score_personal_info(extracted: dict, ground: dict) -> dict:
    """Score personal_info fields: name, email, phone, location, linkedin, website."""
    pi_ext = extracted.get("personal_info", {}) or {}
    pi_gnd = ground.get("personal_info", {}) or {}
    fields = ["full_name", "email", "phone", "location", "linkedin", "website"]
    correct = 0
    details = {}
    for f in fields:
        match = _fuzzy_match(pi_ext.get(f), pi_gnd.get(f))
        if match:
            correct += 1
        details[f"pi_{f}"] = 1 if match else 0
    details["pi_score"] = correct / len(fields) if fields else 0.0
    return details


def score_skills(extracted: dict, ground: dict) -> dict:
    """Score skills via Jaccard similarity on lowercased skill names."""
    ext = set(s.lower() for s in (extracted.get("skills") or []))
    gnd = set(s.lower() for s in (ground.get("skills") or []))
    return {"skills_score": round(_jaccard(ext, gnd), 4)}


def score_experience(extracted: dict, ground: dict) -> dict:
    """Score experience: count match + company/title overlap."""
    ext_exp = extracted.get("experience") or []
    gnd_exp = ground.get("experience") or []

    count_match = 1 if len(ext_exp) == len(gnd_exp) else 0

    ext_companies = {e.get("company", "").lower() for e in ext_exp}
    gnd_companies = {e.get("company", "").lower() for e in gnd_exp}
    company_overlap = _jaccard(ext_companies, gnd_companies)

    return {
        "exp_count_match": count_match,
        "exp_count_extracted": len(ext_exp),
        "exp_count_ground": len(gnd_exp),
        "exp_company_jaccard": round(company_overlap, 4),
    }


def score_education(extracted: dict, ground: dict) -> dict:
    """Score education: count match + institution overlap."""
    ext_edu = extracted.get("education") or []
    gnd_edu = ground.get("education") or []

    count_match = 1 if len(ext_edu) == len(gnd_edu) else 0

    ext_institutions = {e.get("institution", "").lower() for e in ext_edu}
    gnd_institutions = {e.get("institution", "").lower() for e in gnd_edu}
    inst_overlap = _jaccard(ext_institutions, gnd_institutions)

    return {
        "edu_count_match": count_match,
        "edu_count_extracted": len(ext_edu),
        "edu_count_ground": len(gnd_edu),
        "edu_institution_jaccard": round(inst_overlap, 4),
    }


def score_certifications(extracted: dict, ground: dict) -> dict:
    """Score certifications via Jaccard similarity."""
    ext = set(c.lower() for c in (extracted.get("certifications") or []))
    gnd = set(c.lower() for c in (ground.get("certifications") or []))
    return {"certs_score": round(_jaccard(ext, gnd), 4)}


def score_summary(extracted: dict, ground: dict) -> dict:
    """Score summary presence (not exact match — LLM paraphrasing is expected)."""
    ext_has = bool((extracted.get("summary") or "").strip())
    gnd_has = bool((ground.get("summary") or "").strip())
    return {
        "summary_extracted": 1 if ext_has else 0,
        "summary_ground": 1 if gnd_has else 0,
    }


def compute_scores(extracted: dict, ground: dict) -> dict:
    """Compute all per-section scores between extracted and ground truth JSON."""
    scores = {}
    scores.update(score_personal_info(extracted, ground))
    scores.update(score_skills(extracted, ground))
    scores.update(score_experience(extracted, ground))
    scores.update(score_education(extracted, ground))
    scores.update(score_certifications(extracted, ground))
    scores.update(score_summary(extracted, ground))

    # Composite score: average of all percentage-based sub-scores
    percentage_keys = [
        "pi_score", "skills_score",
        "exp_company_jaccard",
        "edu_institution_jaccard",
        "certs_score",
    ]
    values = [scores[k] for k in percentage_keys if k in scores]
    scores["composite_score"] = round(sum(values) / len(values), 4) if values else 0.0

    return scores


# ── Main runner ──────────────────────────────────────────────

def process_directory(input_dir: Path, ground_truth_dir: Path | None = None,
                      results_dir: Path = DEFAULT_RESULTS_DIR) -> None:
    """Process all PDFs in a directory and score against ground truth if provided."""
    results_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(input_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning("No PDF files found in %s", input_dir)
        return

    logger.info("Found %d PDF(s) in %s", len(pdf_files), input_dir)

    all_scores: list[dict] = []

    for pdf_path in pdf_files:
        stem = pdf_path.stem
        logger.info("Processing: %s", pdf_path.name)

        try:
            # ── Parse & extract ──
            if pdf_path.suffix.lower() == ".pdf":
                md_text, photo_path = pdf_to_markdown(pdf_path)
            elif pdf_path.suffix.lower() == ".txt":
                md_text = read_text_file(pdf_path)
            else:
                logger.warning("Skipping unsupported file: %s", pdf_path.name)
                continue

            clean_md = clean_markdown(md_text)
            result = extract_to_json(clean_md)

            if photo_path:
                result.setdefault("personal_info", {})["photo_path"] = photo_path

            # ── Save extracted JSON ──
            output_path = results_dir / f"{stem}.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            # ── Score against ground truth ──
            row: dict = {"file": pdf_path.name}

            if ground_truth_dir:
                gt_path = ground_truth_dir / f"{stem}.json"
                if gt_path.exists():
                    with open(gt_path, "r", encoding="utf-8") as f:
                        ground = json.load(f)
                    scores = compute_scores(result, ground)
                    row.update(scores)
                    logger.info("  Composite score: %.2f", scores["composite_score"])
                else:
                    logger.warning("  No ground truth found for %s (expected: %s)", stem, gt_path)

            row["error"] = "error" in result
            all_scores.append(row)

            logger.info("  Saved to %s", output_path.name)

        except Exception as e:
            logger.error("Failed to process %s: %s", pdf_path.name, e)
            all_scores.append({"file": pdf_path.name, "error": True, "exception": str(e)})

    # ── Write summary CSV ──
    if all_scores:
        _write_csv(results_dir, all_scores)

    logger.info("Done. Results saved to %s", results_dir)


def _write_csv(results_dir: Path, rows: list[dict]) -> None:
    """Write scoring results to a CSV file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = results_dir / f"scores_{timestamp}.csv"

    # Collect all column names from all rows
    fieldnames: list[str] = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Scores CSV written to %s", csv_path)


# ── CLI ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Batch test the resume OCR pipeline with optional ground-truth scoring.",
    )
    parser.add_argument(
        "--dir", required=True, type=Path,
        help="Directory containing PDF/TXT resume files to process.",
    )
    parser.add_argument(
        "--ground-truth", type=Path, default=None,
        help="Directory containing ground truth JSON files (same basename as PDFs).",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_RESULTS_DIR,
        help="Directory for extracted JSON and scoring CSV. Default: data/test_results/",
    )
    args = parser.parse_args()

    if not args.dir.is_dir():
        logger.error("Input directory not found: %s", args.dir)
        return

    process_directory(args.dir, args.ground_truth, args.output_dir)


if __name__ == "__main__":
    main()
