import re
from pathlib import Path

# Unicode bullet characters commonly found in PDFs
_BULLET_CHARS = "\u2022\u25e6\u25aa\u25cb\u25cf\u2756\u2043\u2023\u25b8\u25c6\u25a0\u2794\u27a2\u2714\u2713"
_BULLET_RE = re.compile(f"^[{_BULLET_CHARS}]\\s*")

# Patterns for Markdown restructuring
_SKILLS_TABLE_RE = re.compile(
    r"\|\s*\*\*SPECIFIC KNOWLEDGE[^|]*\|.*?\n"  # header row
    r"\|[\s-]+\|.*?\n"                                 # separator row
    r"(?:\|[^|]*\|[^|]*\|[^|]*\|\n)+",               # data rows (3 columns)
    re.IGNORECASE,
)
_DISCLAIMER_RE = re.compile(
    r"#{1,3}\s*\*\*Disclaimer Statement\*\*.*?(?=\n#{1,3}\s|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_DUPE_HEADING_RE = re.compile(r"(#{1,3}\s*\*\*[^*]+\*\*)\s*\n")


def read_text_file(txt_path: str | Path) -> str:
    with open(txt_path, "r", encoding="utf-8") as f:
        return f.read()


def clean_markdown(md_text: str) -> str:
    """
    Clean, normalize, and restructure Markdown from PDF conversion:
      - Restructure messy page-break output (extract skills table, deduplicate)
      - Normalize unicode bullets to "-"
      - Merge lines broken mid-sentence
      - Collapse excessive blank lines
    """
    # ── Phase 0: restructure the document ──
    md_text = _restructure_markdown(md_text)

    # ── Phase 1: normalize ──
    lines = md_text.splitlines()
    cleaned = []

    for line in lines:
        line = line.strip()
        if not line:
            cleaned.append("")
            continue
        line = _BULLET_RE.sub("- ", line)
        cleaned.append(line)

    # ── Phase 2: merge continuation lines ──
    merged = []
    prev_blank = False
    for line in cleaned:
        if line == "":
            if not prev_blank:
                merged.append(line)
            prev_blank = True
        else:
            prev_blank = False
            if merged and not _is_new_block(line) and not _is_new_block(merged[-1]) and merged[-1] != "":
                merged[-1] += " " + line
            else:
                merged.append(line)

    return "\n".join(merged).strip()


def _restructure_markdown(md_text: str) -> str:
    """
    Fix critical pymupdf4llm artifacts: extract misplaced skills table,
    remove disclaimer noise, clean page-break garbage.
    """
    # 1. Extract skills table and remove it from wherever it appears
    skills_block = ""
    skills_match = _SKILLS_TABLE_RE.search(md_text)
    if skills_match:
        skills_block = skills_match.group(0).strip()
        md_text = _SKILLS_TABLE_RE.sub("", md_text)

    # 2. Remove disclaimer blocks entirely
    md_text = _DISCLAIMER_RE.sub("", md_text)

    # 3. Remove "OpenThis Document..." noise (orphaned disclaimer body text)
    md_text = re.sub(r"OpenThis\s+Document[^.]*\.[^#]*", "", md_text, flags=re.DOTALL)

    # 4. Remove orphaned bold **RESOURCE PROFILE** / **Disclaimer Statement** without ## prefix
    md_text = re.sub(
        r"^\*\*(?:RESOURCE\s+PROFILE|Disclaimer\s+Statement)\*\*\s*$",
        "",
        md_text,
        flags=re.MULTILINE | re.IGNORECASE,
    )

    # 5. Insert skills section before the first PROFESSIONAL HISTORY
    if skills_block:
        marker = "PROFESSIONAL HISTORY"
        idx = md_text.find(marker)
        if idx != -1:
            line_start = md_text.rfind("\n", 0, idx) + 1
            skills_section = f"\n\n## SKILLS\n\n{skills_block}\n"
            md_text = md_text[:line_start] + skills_section + md_text[line_start:]
        else:
            md_text += f"\n\n## SKILLS\n\n{skills_block}\n"

    return md_text


def _is_new_block(line: str) -> bool:
    """Return True if a line starts a new semantic block (heading, bullet, etc.)."""
    return bool(
        line.startswith("#")
        or line.startswith("- ")
        or line.startswith("* ")
        or re.match(r"^\d+[\.\)]", line)  # numbered list
        or line.isupper()                    # ALL-CAPS section header
    )
