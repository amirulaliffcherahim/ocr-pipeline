import json
import time
import requests
from pathlib import Path
from src.models import ResumeData
from src.normalizer import normalize_resume
from config import (
    LLM_BASE_URL, LLM_MODEL, LLM_API_KEY, LLM_TIMEOUT,
    LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_MAX_INPUT_CHARS,
    LLM_MAX_RETRIES, LLM_RETRY_BACKOFF, LLM_REASONING_ENABLED,
)


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "resume_extraction.md"


def extract_to_json(md_text: str) -> dict:
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    prompt = f"""
Extract the resume information.

Resume Text:
{md_text[:LLM_MAX_INPUT_CHARS]}   # truncate if too long
"""

    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY:
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": LLM_TEMPERATURE,
        "max_tokens": LLM_MAX_TOKENS,
        "reasoning": {"enabled": LLM_REASONING_ENABLED},
    }

    last_error = None
    for attempt in range(LLM_MAX_RETRIES + 1):
        response = requests.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=LLM_TIMEOUT
        )

        # Success — break out
        if response.status_code == 200:
            break

        # Retryable errors: 429 (rate limit) and 5xx (server errors)
        if response.status_code in (429, 500, 502, 503, 504) and attempt < LLM_MAX_RETRIES:
            delay = LLM_RETRY_BACKOFF ** attempt
            print(f"[RETRY] HTTP {response.status_code} — attempt {attempt + 1}/{LLM_MAX_RETRIES}, waiting {delay:.0f}s")
            time.sleep(delay)
            last_error = response
            continue

        # Non-retryable — raise immediately
        response.raise_for_status()

    # If all retries exhausted, raise the last error
    if last_error is not None and response.status_code != 200:
        last_error.raise_for_status()

    try:
        resp_json = response.json()
        raw_content = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not raw_content or not raw_content.strip():
            print(f"[ERROR] LLM returned empty content. Full response keys: {list(resp_json.keys())}")
            if "error" in resp_json:
                print(f"[ERROR] API error: {resp_json['error']}")
            return {"error": "LLM returned empty content"}

        print(f"[DEBUG] Raw LLM response ({len(raw_content)} chars):\n{raw_content[:3000]}\n")

        # Clean possible markdown code blocks
        json_str = raw_content
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1] if "```" in json_str else json_str

        json_str = json_str.strip()
        if not json_str:
            print(f"[ERROR] Content became empty after cleaning. Raw was:\n{raw_content[:2000]}")
            return {"error": "LLM content empty after markdown-fence cleaning"}

        data = json.loads(json_str)
        print(f"[DEBUG] Parsed JSON keys: {list(data.keys())}")

        # Validate with Pydantic
        ResumeData.model_validate(data)

        # Normalize dates and clean structure for consistent output
        data = normalize_resume(data)

        return data
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON decode failed: {e}")
        print(f"[ERROR] Content that failed to parse:\n{json_str[:1000]}")
        return {"error": f"JSON decode failed: {e}"}
    except Exception as e:
        print(f"[ERROR] Validation/parsing failed: {type(e).__name__}: {e}")
        return {"error": f"{type(e).__name__}: {e}"}
