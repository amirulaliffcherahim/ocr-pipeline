from src.pdf_parser import pdf_to_markdown
from src.text_processor import read_text_file, clean_markdown
from src.llm_extractor import extract_to_json
from config import INPUT_DIR, OUTPUT_DIR
import json
from pathlib import Path
from tqdm import tqdm


def process_file(file_path: Path):
    print(f"Processing: {file_path.name}")

    if file_path.suffix.lower() == ".pdf":
        md_text = pdf_to_markdown(file_path)
    elif file_path.suffix.lower() == ".txt":
        md_text = read_text_file(file_path)
    else:
        print("Unsupported format")
        return

    clean_md = clean_markdown(md_text)
    result = extract_to_json(clean_md)

    output_path = OUTPUT_DIR / f"{file_path.stem}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Saved to {output_path.name}\n")


if __name__ == "__main__":
    files = list(INPUT_DIR.glob("*.pdf")) + list(INPUT_DIR.glob("*.txt"))

    for file in tqdm(files):
        process_file(file)
