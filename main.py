"""Enrich local documents and search them with Elasticsearch full-text queries."""

import argparse
import asyncio
import json
import sys

import aiohttp
from elasticsearch import ApiError, TransportError

from config import ELASTICSEARCH_INDEX, OLLAMA_TIMEOUT, ROOT
from es import es_function
from helpers import doc_helper
from llm import llm_client


def positive_int(value: str) -> int:
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="Enrich and upsert one document per line")
    ingest.add_argument("--file", default=str(ROOT / "data/sample.txt"))
    query = commands.add_parser("query", help="Search title, keywords and content")
    query.add_argument("text", help="Full-text search query")
    query.add_argument("--limit", type=positive_int, default=3)
    count = commands.add_parser("count", help="Count indexed documents")
    for command in (ingest, query, count):
        command.add_argument("--index", default=ELASTICSEARCH_INDEX)
    return parser


async def ingest_documents(file_name: str, index_name: str) -> int:
    documents = doc_helper.file_reader(file_name)
    if not documents:
        raise ValueError("The input file contains no documents.")
    es_function.create_or_get_index(index_name)
    timeout = aiohttp.ClientTimeout(total=OLLAMA_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for number, document in enumerate(documents, start=1):
            metadata = await llm_client.extract_metadata(document, session)
            es_function.add_document(
                index_name, doc_helper.document_id(document),
                doc_helper.generate_doc(document, **metadata, source=str(file_name)),
            )
            print(f"[{number}/{len(documents)}] {metadata['title']}", file=sys.stderr)
    es_function.refresh_index(index_name)
    return es_function.count_documents(index_name)


def run(args: argparse.Namespace):
    if args.command == "ingest":
        return {"index": args.index, "count": asyncio.run(ingest_documents(args.file, args.index))}
    if args.command == "count":
        return {"index": args.index, "count": es_function.count_documents(args.index)}
    if not args.text.strip():
        raise ValueError("The search query must not be blank.")
    return es_function.query_document(args.index, args.text, args.limit)


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run(args)
    except (OSError, ValueError, RuntimeError, ApiError, TransportError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
