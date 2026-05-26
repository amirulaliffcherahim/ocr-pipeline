import re
from pathlib import Path

# Unicode bullet characters commonly found in PDFs
_BULLET_CHARS = "\u2022\u25e6\u25aa\u25cb\u25cf\u2756\u2043\u2023\u25b8\u25c6\u25a0\u2794\u27a2\u2714\u2713"
_BULLET_RE = re.compile(f"^[{_BULLET_CHARS}]\\s*")


def read_text_file(txt_path: str | Path) -> str:
    with open(txt_path, "r", encoding="utf-8") as f:
        return f.read()


def clean_markdown(md_text: str) -> str:
    """
    Clean and normalize Markdown from PDF conversion:
      - Normalize unicode bullets to "-"
      - Merge lines broken mid-sentence (single newline within paragraphs)
      - Collapse excessive blank lines
      - Strip trailing whitespace
    """
    lines = md_text.splitlines()
    cleaned = []

    for line in lines:
        line = line.strip()
        if not line:
            cleaned.append("")
            continue

        # Normalize unicode bullet characters to "- "
        line = _BULLET_RE.sub("- ", line)
        cleaned.append(line)

    # Collapse consecutive blank lines into a single blank line
    merged = []
    prev_blank = False
    for line in cleaned:
        if line == "":
            if not prev_blank:
                merged.append(line)
            prev_blank = True
        else:
            prev_blank = False
            # Merge short continuation lines with previous line
            # (lines that don't start with a heading, bullet, or look like a section break)
            if merged and not _is_new_block(line) and not _is_new_block(merged[-1]) and merged[-1] != "":
                merged[-1] += " " + line
            else:
                merged.append(line)

    return "\n".join(merged).strip()


def _is_new_block(line: str) -> bool:
    """Return True if a line starts a new semantic block (heading, bullet, etc.)."""
    return bool(
        line.startswith("#")
        or line.startswith("- ")
        or line.startswith("* ")
        or re.match(r"^\d+[\.\)]", line)  # numbered list
        or line.isupper()                    # ALL-CAPS section header
    )
