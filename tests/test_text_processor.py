"""Tests for src/text_processor.py — markdown cleaning and normalization."""
import pytest
from pathlib import Path
import tempfile
from src.text_processor import clean_markdown, read_text_file, _is_new_block


class TestReadTextFile:
    def test_reads_utf8(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("Hello\nWorld")
            tmp_path = f.name
        try:
            result = read_text_file(tmp_path)
            assert result == "Hello\nWorld"
        finally:
            Path(tmp_path).unlink()


class TestIsNewBlock:
    def test_heading(self):
        assert _is_new_block("# Summary") is True
        assert _is_new_block("## Experience") is True

    def test_bullet(self):
        assert _is_new_block("- Built API") is True
        assert _is_new_block("* Led team") is True

    def test_numbered_list(self):
        assert _is_new_block("1. First item") is True
        assert _is_new_block("10) Another item") is True

    def test_all_caps_header(self):
        assert _is_new_block("PROFESSIONAL EXPERIENCE") is True
        assert _is_new_block("EDUCATION") is True

    def test_normal_line(self):
        assert _is_new_block("Regular text line") is False
        assert _is_new_block("  indented text") is False


class TestCleanMarkdown:
    def test_bullet_normalization(self):
        # Unicode bullet → "- "
        md = "\u2022 First item\n\u25e6 Second item\n\u25aa Third"
        result = clean_markdown(md)
        assert "- First item" in result
        assert "- Second item" in result
        assert "- Third" in result

    def test_preserves_headings(self):
        md = "# Summary\nSome text\n## Skills\nPython"
        result = clean_markdown(md)
        assert "# Summary" in result
        assert "## Skills" in result

    def test_collapses_multiple_blank_lines(self):
        md = "Line 1\n\n\n\nLine 2"
        result = clean_markdown(md)
        assert result.count("\n\n") == 1
        # Should have one blank line between, not three
        assert "\n\n\n" not in result

    def test_merges_continuation_lines(self):
        # Lines that aren't new blocks should merge
        md = "This is a line\nthat continues here."
        result = clean_markdown(md)
        assert "This is a line that continues here." in result

    def test_does_not_merge_block_starts(self):
        md = "Some text\n- A bullet point"
        result = clean_markdown(md)
        assert "Some text" in result
        assert "- A bullet point" in result

    def test_empty_string(self):
        result = clean_markdown("")
        assert result == ""

    def test_whitespace_only(self):
        result = clean_markdown("   \n  \n  ")
        assert result == ""
