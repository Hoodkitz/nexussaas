"""Small LLM adapter: Gemini (if a key is configured), else Ollama, else None.

LLM output is treated as untrusted data: callers parse JSON and validate it
strictly (e.g. normalize_blueprint) before it influences anything.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import httpx

log = logging.getLogger("nexus.llm")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")


def _gemini_key() -> str | None:
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key.strip()
    path = Path(os.getenv("GEMINI_API_KEY_FILE", str(Path.home() / ".secrets" / "gemini_api_key")))
    try:
        return path.read_text().strip() or None
    except OSError:
        return None


def provider() -> str:
    return "gemini" if _gemini_key() else "ollama"


async def complete_json(prompt: str, timeout: float = 60.0) -> dict | None:
    """Ask the model for a JSON object. Returns None if no model answers or output is not JSON."""
    text = None
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            key = _gemini_key()
            if key:
                r = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
                    headers={"x-goog-api-key": key},
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3}})
                r.raise_for_status()
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            else:
                r = await client.post(f"{OLLAMA_URL}/api/generate",
                                      json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                                            "format": "json"})
                r.raise_for_status()
                text = r.json().get("response", "")
    except Exception as e:
        log.warning("llm unavailable", extra={"fields": {"provider": provider(), "error": type(e).__name__}})
        return None
    return _parse(text)


def _parse(text: str | None) -> dict | None:
    if not text:
        return None
    t = text.strip()
    if "```" in t:
        parts = t.split("```")
        t = parts[1] if len(parts) > 1 else t
        t = t[4:] if t.startswith("json") else t
    start, end = t.find("{"), t.rfind("}") + 1
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(t[start:end])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
