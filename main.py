from src.pdf_parser import pdf_to_markdown
from src.text_processor import read_text_file, clean_markdown
from src.llm_extractor import extract_to_json
from config import INPUT_DIR, OUTPUT_DIR
import json
import logging
from pathlib import Path
from tqdm import tqdm

logger = logging.getLogger(__name__)


def process_file(file_path: Path):
    logger.info("Processing: %s", file_path.name)
    photo_path = None

    if file_path.suffix.lower() == ".pdf":
        md_text, photo_path = pdf_to_markdown(file_path)
    elif file_path.suffix.lower() == ".txt":
        md_text = read_text_file(file_path)
    else:
        logger.warning("Unsupported format: %s", file_path.suffix)
        return

    clean_md = clean_markdown(md_text)
    result = extract_to_json(clean_md)

    output_path = OUTPUT_DIR / f"{file_path.stem}.json"
    if photo_path:
        result.setdefault("personal_info", {})["photo_path"] = photo_path
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    logger.info("Saved to %s", output_path.name)


if __name__ == "__main__":
    files = list(INPUT_DIR.glob("*.pdf")) + list(INPUT_DIR.glob("*.txt"))

    for file in tqdm(files):
        process_file(file)
