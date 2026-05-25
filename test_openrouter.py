"""Test OpenRouter API directly with a sample resume markdown."""
import os, json, time, asyncio
from dotenv import load_dotenv
import httpx

load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("OPENROUTER_MODEL", "liquid/lfm-2-24b-a2b")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

print(f"Backend: OpenRouter")
print(f"Model:   {MODEL}")
print(f"API Key: {API_KEY[:20]}..." if API_KEY else "API Key: MISSING")

# Sample resume markdown (simulating Docling output)
sample_md = """
# Muhammad Amirul Aliff

**Email:** amirul@example.com | **Phone:** +60 12-345 6789 | **Location:** Kuala Lumpur, Malaysia
**LinkedIn:** linkedin.com/in/amirulaliff | **GitHub:** github.com/amirulaliff

## Professional Summary

Full-stack software engineer with 5 years of experience building scalable web applications and AI-powered systems. Proficient in Python, TypeScript, React, and cloud infrastructure.

## Work Experience

### Senior Software Engineer — TechCorp Malaysia
*Jan 2022 – Present*
- Led migration of monolithic backend to microservices, reducing deployment time by 60%
- Built real-time analytics dashboard serving 10K+ daily users
- Mentored 4 junior engineers on best practices and code review

### Software Engineer — StartupXYZ
*Jun 2019 – Dec 2021*
- Developed REST APIs handling 1M+ requests/day with 99.9% uptime
- Implemented CI/CD pipelines using GitHub Actions and Docker
- Built OCR pipeline for automated document processing

## Education

### Bachelor of Computer Science — University of Malaya
*2015 – 2019*
- CGPA: 3.75/4.0
- Final Year Project: AI-powered Resume Parser

## Skills

**Technical:** Python, TypeScript, React, Node.js, PostgreSQL, Docker, AWS, FastAPI
**Soft:** Leadership, Communication, Problem-solving
**Languages:** English (Fluent), Malay (Native)
**Certifications:** AWS Solutions Architect Associate, Google Cloud Professional Developer

## Projects

### OCR Pipeline
An async two-stage document processing pipeline using Docling and LLMs for structured data extraction.
**Tech:** Python, FastAPI, PostgreSQL, Docling, OpenRouter
"""

system_prompt = """You are a resume parser that extracts structured data from markdown. Output ONLY valid JSON following this exact schema. No markdown fences, no preamble.

{
  "name": "string or null",
  "email": "string or null",
  "phone": "string or null",
  "location": "string or null",
  "linkedin": "string or null",
  "github": "string or null",
  "headline": "string or null",
  "summary": "string or null",
  "years_of_experience": "float or null",
  "seniority_level": "'Junior' | 'Mid-level' | 'Senior' | 'Lead' | 'Manager' | 'Executive' | null",
  "top_skills": ["string"],
  "keywords": ["string"],
  "work_experience": [{"title": "string", "company": "string", "location": "string or null", "start_date": "string or null", "end_date": "string or null", "is_current": "boolean", "bullets": ["string"]}],
  "education": [{"degree": "string", "school": "string", "field_of_study": "string or null", "start_date": "string or null", "end_date": "string or null", "gpa": "string or null"}],
  "skills": {"technical": ["string"], "soft": ["string"], "languages": ["string"], "certifications": ["string"]},
  "projects": [{"name": "string", "description": "string or null", "url": "string or null", "technologies": ["string"]}]
}"""

async def test():
    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "OCR Pipeline Test",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract the resume data from this markdown:\n\n{sample_md}"},
        ],
        "temperature": 0.0,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }

    print(f"\nSending request to {url}...")
    t1 = time.perf_counter()

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=payload, headers=headers)

    elapsed = (time.perf_counter() - t1) * 1000
    print(f"Response in {elapsed:.0f}ms — status {resp.status_code}")

    if resp.status_code != 200:
        print(f"ERROR: {resp.text[:500]}")
        return

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    print(f"\nTokens: {data.get('usage', {}).get('completion_tokens', '?')}")

    # Parse
    parsed = json.loads(content)
    print("\n--- Extracted Resume ---")
    print(json.dumps(parsed, indent=2, ensure_ascii=False))

asyncio.run(test())
