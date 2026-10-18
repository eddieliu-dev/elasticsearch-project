"""Regression tests that do not require Ollama or downloaded models."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import aiohttp

from helpers import doc_helper as helper
from llm.llm_client import extract_metadata, parse_metadata


class DocumentTests(unittest.TestCase):
    def test_utf8_input_ignores_empty_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.txt"
            source.write_text("  first document  \n\n 中文文本 \n", encoding="utf-8")
            self.assertEqual(helper.file_reader(source), ["first document", "中文文本"])

    def test_content_ids_are_stable_and_distinct(self):
        self.assertEqual(helper.document_id("solar"), helper.document_id("solar"))
        self.assertNotEqual(helper.document_id("solar"), helper.document_id("rail"))

    def test_valid_metadata_is_normalized(self):
        metadata = parse_metadata(json.dumps({"title": " Solar ", "keywords": [" sun ", "power", "roof"]}))
        self.assertEqual(metadata, {"title": "Solar", "keywords": ["sun", "power", "roof"]})

    def test_bad_model_output_is_rejected(self):
        for value in ("not JSON", "[]", "null", "{}", '{"title":"", "keywords":["a","b","c"]}',
                      '{"title":"Solar", "keywords":"sun"}',
                      '{"title":"Solar", "keywords":["a", "b"]}',
                      '{"title":"Solar", "keywords":["a", "b", 3]}'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_metadata(value)


class OllamaTests(unittest.IsolatedAsyncioTestCase):
    def make_session(self, body):
        response = MagicMock()
        response.json = AsyncMock(return_value=body)
        session = MagicMock()
        session.post.return_value.__aenter__ = AsyncMock(return_value=response)
        session.post.return_value.__aexit__ = AsyncMock(return_value=False)
        return session, response

    async def test_structured_output_and_http_status(self):
        session, response = self.make_session({"response": json.dumps({
            "title": "Solar", "keywords": ["sun", "power", "roof"]
        })})
        result = await extract_metadata("A rooftop generates power.", session)
        self.assertEqual(result["title"], "Solar")
        response.raise_for_status.assert_called_once()
        payload = session.post.call_args.kwargs["json"]
        self.assertEqual(payload["format"]["type"], "object")
        self.assertIn("A rooftop generates power.", payload["prompt"])

    async def test_failed_request_has_actionable_error(self):
        session, response = self.make_session({})
        response.raise_for_status.side_effect = aiohttp.ClientConnectionError("offline")
        with self.assertRaisesRegex(RuntimeError, "Ollama request failed"):
            await extract_metadata("document", session)

    async def test_missing_response_is_rejected(self):
        session, _ = self.make_session({"error": "missing model"})
        with self.assertRaisesRegex(ValueError, "missing"):
            await extract_metadata("document", session)
