"""Extract validated metadata using Ollama's structured JSON output."""

import json

import aiohttp

from config import OLLAMA_BASE_URL, OLLAMA_MODEL
from helpers.prompt import METADATA_PROMPT, METADATA_SCHEMA


def parse_metadata(response: str) -> dict:
    try:
        metadata = json.loads(response)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Ollama returned invalid metadata JSON.") from exc
    if not isinstance(metadata, dict):
        raise ValueError("Ollama metadata must be a JSON object.")
    title = metadata.get("title")
    keywords = metadata.get("keywords")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Ollama metadata must contain a nonempty title.")
    if (
        not isinstance(keywords, list) or not 3 <= len(keywords) <= 5
        or any(not isinstance(word, str) or not word.strip() for word in keywords)
    ):
        raise ValueError("Ollama metadata must contain 3 to 5 nonempty keywords.")
    return {"title": title.strip(), "keywords": [word.strip() for word in keywords]}


async def extract_metadata(text: str, session: aiohttp.ClientSession) -> dict:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": METADATA_PROMPT.replace("{{DOCUMENT}}", text),
        "format": METADATA_SCHEMA,
        "stream": False,
        "options": {"temperature": 0},
    }
    try:
        async with session.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload) as response:
            response.raise_for_status()
            body = await response.json()
    except (aiohttp.ClientError, TimeoutError) as exc:
        raise RuntimeError(
            f"Ollama request failed at {OLLAMA_BASE_URL}. "
            "Check the server, OLLAMA_MODEL and OLLAMA_TIMEOUT."
        ) from exc
    if not isinstance(body, dict) or not isinstance(body.get("response"), str):
        raise ValueError("Ollama response is missing the generated metadata.")
    return parse_metadata(body["response"])
