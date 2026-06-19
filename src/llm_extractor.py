import json
import logging
import re
import time
import requests
from pathlib import Path
from src.models import ResumeData
from src.normalizer import normalize_resume
from config import (
    LLM_BASE_URL, LLM_MODEL, LLM_API_KEY, LLM_TIMEOUT,
    LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_MAX_INPUT_CHARS,
    LLM_MAX_RETRIES, LLM_RETRY_BACKOFF, LLM_REASONING_ENABLED,
    LLM_JSON_MODE,
)

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "resume_extraction.md"


def _extract_json_block(text: str) -> str:
    """
    Extract JSON object from text that may contain markdown fences,
    explanatory text, or trailing garbage.
    """
    text = text.strip()

    # Try fenced code blocks first
    if "```json" in text:
        parts = text.split("```json", 1)
        if len(parts) == 2:
            inner = parts[1].split("```", 1)[0]
            return inner.strip()
    if "```" in text:
        parts = text.split("```", 1)
        if len(parts) == 2:
            inner = parts[1].split("```", 1)[0]
            return inner.strip()

    # Find outermost JSON object via brace matching
    start = text.find("{")
    if start == -1:
        return text

    depth = 0
    end = -1
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break

    if end != -1:
        return text[start:end + 1]

    return text[start:]


def _repair_json(text: str) -> str:
    """Quick fixes for common small-model JSON mistakes."""
    # Remove trailing commas before ] or }
    text = re.sub(r",\s*(\]|\})", r"\1", text)
    # Fix unquoted keys (e.g. {skills: ["a"]} → {"skills": ["a"]})
    text = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
    return text


def extract_to_json(md_text: str) -> dict:
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    prompt = f"""Extract the resume information from the text below.\n\nResume Text:\n{md_text[:LLM_MAX_INPUT_CHARS]}\n"""

    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"

    payload: dict = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": LLM_TEMPERATURE,
        "max_tokens": LLM_MAX_TOKENS,
    }

    # Request structured JSON output if the endpoint supports it
    if LLM_JSON_MODE:
        payload["response_format"] = {"type": "json_object"}

    # Reasoning control for supported models (Qwen3, DeepSeek-R1, etc.)
    if LLM_REASONING_ENABLED:
        payload["reasoning"] = {"enabled": True}

    last_error = None
    for attempt in range(LLM_MAX_RETRIES + 1):
        try:
            response = requests.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=LLM_TIMEOUT
            )
        except requests.exceptions.Timeout:
            logger.warning("Request timeout — attempt %d/%d", attempt + 1, LLM_MAX_RETRIES + 1)
            if attempt < LLM_MAX_RETRIES:
                delay = LLM_RETRY_BACKOFF ** attempt
                time.sleep(delay)
                continue
            return {"error": "LLM request timed out after all retries"}

        if response.status_code == 200:
            break

        if response.status_code in (429, 500, 502, 503, 504) and attempt < LLM_MAX_RETRIES:
            delay = LLM_RETRY_BACKOFF ** attempt
            logger.warning("HTTP %d — attempt %d/%d, waiting %.0fs", response.status_code, attempt + 1, LLM_MAX_RETRIES, delay)
            time.sleep(delay)
            last_error = response
            continue

        response.raise_for_status()

    if last_error is not None and response.status_code != 200:
        last_error.raise_for_status()

    try:
        resp_json = response.json()
        raw_content = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not raw_content or not raw_content.strip():
            logger.error("LLM returned empty content. Full response keys: %s", list(resp_json.keys()))
            if "error" in resp_json:
                logger.error("API error: %s", resp_json['error'])
            return {"error": "LLM returned empty content"}

        logger.debug("Raw LLM response (%d chars):\n%s", len(raw_content), raw_content[:3000])

        # Extract and clean JSON
        json_str = _extract_json_block(raw_content)
        json_str = _repair_json(json_str)

        if not json_str:
            logger.error("Content became empty after cleaning. Raw was:\n%s", raw_content[:2000])
            return {"error": "LLM content empty after markdown-fence cleaning"}

        data = json.loads(json_str)
        logger.debug("Parsed JSON keys: %s", list(data.keys()))

        # Validate with Pydantic
        ResumeData.model_validate(data)

        # Normalize dates and clean structure for consistent output
        data = normalize_resume(data)

        return data
    except json.JSONDecodeError as e:
        logger.error("JSON decode failed: %s", e)
        logger.error("Content that failed to parse:\n%s", json_str[:1000])
        return {"error": f"JSON decode failed: {e}"}
    except Exception as e:
        logger.error("Validation/parsing failed: %s: %s", type(e).__name__, e)
        return {"error": f"{type(e).__name__}: {e}"}
