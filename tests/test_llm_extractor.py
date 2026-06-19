"""Tests for src/llm_extractor.py — JSON extraction and repair helpers."""
import pytest

# Import the pure helper functions directly
from src.llm_extractor import _extract_json_block, _repair_json


class TestExtractJsonBlock:
    def test_plain_json(self):
        text = '{"name": "Jane", "age": 30}'
        result = _extract_json_block(text)
        assert result == '{"name": "Jane", "age": 30}'

    def test_json_with_whitespace(self):
        text = '\n\n  {"name": "Jane"}\n'
        result = _extract_json_block(text)
        assert result == '{"name": "Jane"}'

    def test_json_in_markdown_fence(self):
        text = '```json\n{"name": "Jane"}\n```'
        result = _extract_json_block(text)
        assert result == '{"name": "Jane"}'

    def test_json_in_generic_fence(self):
        text = '```\n{"name": "Jane"}\n```'
        result = _extract_json_block(text)
        assert result == '{"name": "Jane"}'

    def test_json_with_leading_explanation(self):
        text = 'Here is the extracted resume:\n\n{"name": "Jane"}'
        result = _extract_json_block(text)
        assert result == '{"name": "Jane"}'

    def test_json_with_trailing_garbage(self):
        text = '{"name": "Jane"}\n\nHope this helps!'
        result = _extract_json_block(text)
        assert result == '{"name": "Jane"}'

    def test_nested_braces(self):
        text = '{"person": {"name": "Jane", "skills": ["a", "b"]}}'
        result = _extract_json_block(text)
        assert result == '{"person": {"name": "Jane", "skills": ["a", "b"]}}'

    def test_nested_array(self):
        text = '{"items": [1, 2, {"nested": true}]}'
        result = _extract_json_block(text)
        assert result == '{"items": [1, 2, {"nested": true}]}'

    def test_no_braces_returns_original(self):
        text = "No JSON here"
        result = _extract_json_block(text)
        assert result == "No JSON here"

    def test_empty_string(self):
        result = _extract_json_block("")
        assert result == ""

    def test_json_fence_with_whitespace_around(self):
        text = 'Here you go:\n```json\n{"name": "Jane"}\n```\nDone.'
        result = _extract_json_block(text)
        assert result == '{"name": "Jane"}'

    def test_multiple_json_objects_takes_first(self):
        # Should extract the first JSON object (outermost)
        text = '{"first": 1} some text {"second": 2}'
        result = _extract_json_block(text)
        assert '"first": 1' in result


class TestRepairJson:
    def test_trailing_comma_in_object(self):
        text = '{"name": "Jane", "age": 30,}'
        result = _repair_json(text)
        assert '",}' not in result
        # Should be valid JSON now
        import json
        json.loads(result)

    def test_trailing_comma_in_array(self):
        text = '{"skills": ["Python", "JavaScript",]}'
        result = _repair_json(text)
        import json
        json.loads(result)

    def test_unquoted_keys(self):
        text = '{name: "Jane", age: 30}'
        result = _repair_json(text)
        assert '"name":' in result
        assert '"age":' in result

    def test_unquoted_keys_with_spaces(self):
        text = '{full_name: "Jane", skills: ["a", "b"]}'
        result = _repair_json(text)
        assert '"full_name":' in result
        assert '"skills":' in result

    def test_already_valid_json_unchanged(self):
        text = '{"name": "Jane"}'
        result = _repair_json(text)
        assert result == text

    def test_nested_unquoted_keys(self):
        text = '{personal_info: {full_name: "Jane"}}'
        result = _repair_json(text)
        assert '"personal_info":' in result
        assert '"full_name":' in result

    def test_idempotent(self):
        text = '{name: "Jane", skills: ["a", "b",]}'
        first = _repair_json(text)
        second = _repair_json(first)
        assert first == second
