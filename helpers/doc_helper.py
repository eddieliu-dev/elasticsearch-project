"""Read UTF-8 documents and attach content-based IDs and ingestion metadata."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path


def file_reader(file_name: str | Path) -> list[str]:
    with open(file_name, encoding="utf-8") as source:
        return [line.strip() for line in source if line.strip()]


def document_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def generate_doc(content: str, title: str, keywords: list[str], source: str) -> dict:
    return {
        "title": title,
        "keywords": keywords,
        "content": content,
        "source": source,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }
