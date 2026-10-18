"""Regression coverage for safe ingestion and returning every requested search hit."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import main
from es import es_client
from es import es_function as db


class ElasticsearchTests(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock()
        self.patcher = patch("es.es_function.get_client", return_value=self.client)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_existing_index_is_preserved(self):
        self.client.indices.exists.return_value = True
        db.create_or_get_index("documents")
        self.client.indices.delete.assert_not_called()
        self.client.indices.create.assert_not_called()

    def test_new_index_has_explicit_mapping(self):
        self.client.indices.exists.return_value = False
        db.create_or_get_index("documents")
        mapping = self.client.indices.create.call_args.kwargs["mappings"]
        self.assertEqual(mapping["properties"]["ingested_at"]["type"], "date")

    def test_search_returns_all_hits_and_honors_limit(self):
        self.client.search.return_value = {"hits": {"hits": [
            {"_id": "one", "_score": 2.0, "_source": {"title": "Solar"}},
            {"_id": "two", "_score": 1.0, "_source": {"title": "Battery"}},
        ]}}
        results = db.query_document("documents", "clean power", limit=2)
        self.assertEqual([result["id"] for result in results], ["one", "two"])
        request = self.client.search.call_args.kwargs
        self.assertEqual(request["size"], 2)
        self.assertEqual(request["query"]["multi_match"]["query"], "clean power")

    def test_empty_search_returns_empty_list(self):
        self.client.search.return_value = {"hits": {"hits": []}}
        self.assertEqual(db.query_document("documents", "nothing"), [])

    def test_count_returns_an_integer(self):
        self.client.count.return_value = {"count": 6}
        self.assertEqual(db.count_documents("documents"), 6)

    def test_missing_index_explains_ingestion(self):
        self.client.indices.exists.return_value = False
        with self.assertRaisesRegex(ValueError, "Run ingest first"):
            db.query_document("missing", "power")

    def test_ingestion_uses_stable_ids_and_refreshes_without_deleting_index(self):
        self.client.count.return_value = {"count": 1}
        metadata = {"title": "Solar", "keywords": ["sun", "roof", "power"]}
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.txt"
            source.write_text("Solar power\n", encoding="utf-8")
            with patch("main.llm_client.extract_metadata", new=AsyncMock(return_value=metadata)):
                for _ in range(2):
                    self.assertEqual(asyncio.run(main.ingest_documents(str(source), "documents")), 1)
        calls = self.client.index.call_args_list
        self.assertEqual(calls[0].kwargs["id"], calls[1].kwargs["id"])
        self.assertEqual(calls[0].kwargs["document"]["content"], "Solar power")
        self.assertEqual(self.client.indices.refresh.call_count, 2)
        self.client.indices.delete.assert_not_called()

    def test_authentication_is_optional_and_comes_from_configuration(self):
        es_client.get_client.cache_clear()
        self.addCleanup(es_client.get_client.cache_clear)
        with patch.object(es_client, "ELASTICSEARCH_API_KEY", ""), \
             patch.object(es_client, "ELASTICSEARCH_CA_CERTS", ""), \
             patch.object(es_client, "Elasticsearch") as constructor:
            es_client.get_client()
            self.assertNotIn("api_key", constructor.call_args.kwargs)
        es_client.get_client.cache_clear()
        with patch.object(es_client, "ELASTICSEARCH_API_KEY", "test-key"), \
             patch.object(es_client, "ELASTICSEARCH_CA_CERTS", ""), \
             patch.object(es_client, "Elasticsearch") as constructor:
            es_client.get_client()
            self.assertEqual(constructor.call_args.kwargs["api_key"], "test-key")
