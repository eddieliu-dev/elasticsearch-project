"""Explicit document mapping and ranked multi-field full-text search."""

from es.es_client import get_client

MAPPINGS = {
    "properties": {
        "title": {"type": "text"},
        "keywords": {"type": "text"},
        "content": {"type": "text"},
        "source": {"type": "keyword"},
        "ingested_at": {"type": "date"},
    }
}


def create_or_get_index(index_name: str):
    client = get_client()
    if not client.indices.exists(index=index_name):
        client.indices.create(index=index_name, mappings=MAPPINGS)


def require_index(index_name: str):
    if not get_client().indices.exists(index=index_name):
        raise ValueError(f"Index '{index_name}' does not exist. Run ingest first.")


def add_document(index_name: str, doc_id: str, document: dict):
    # Indexing with a stable ID replaces that document and preserves other records.
    get_client().index(index=index_name, id=doc_id, document=document)


def refresh_index(index_name: str):
    get_client().indices.refresh(index=index_name)


def count_documents(index_name: str) -> int:
    require_index(index_name)
    return get_client().count(index=index_name)["count"]


def query_document(index_name: str, query: str, limit: int = 3) -> list[dict]:
    if limit < 1:
        raise ValueError("The result limit must be positive.")
    require_index(index_name)
    response = get_client().search(
        index=index_name,
        query={"multi_match": {"query": query, "fields": ["title^3", "keywords^2", "content"]}},
        size=limit,
    )
    return [
        {"id": hit["_id"], "score": hit["_score"], **hit["_source"]}
        for hit in response["hits"]["hits"]
    ]
