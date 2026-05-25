"""
Tests for issue #554: NERExtractor LLM method returning pattern-based output.

Three bugs fixed:
  1. ner_extractor.py – exc_info=True missing on method-failure warning
  2. providers.py OpenAIProvider.generate_structured – forced response_format=json_object
     even for custom gateway base_url endpoints that don't support it
  3. providers.py BaseProvider.generate_typed manual repair loop – no fallback from
     generate_structured to plain generate() when the structured call itself fails

These tests work without pydantic / instructor / openai installed: mock clients are
injected directly and a minimal stub schema class replaces pydantic.BaseModel where
needed.
"""

import json
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from semantica.semantic_extract.ner_extractor import NERExtractor
from semantica.semantic_extract.providers import OpenAIProvider
from semantica.utils.exceptions import ProcessingError
from semantica.utils.logging import get_logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entity_response(entities):
    """Return a mock that looks like an EntitiesResponse Pydantic model."""
    mock_resp = MagicMock()
    mock_resp.entities = [
        MagicMock(
            text=e["text"],
            label=e["label"],
            confidence=e.get("confidence", 0.9),
            start=e.get("start", 0),
            end=e.get("end", len(e["text"])),
        )
        for e in entities
    ]
    return mock_resp


def _bare_openai_provider(base_url=None):
    """
    Build an OpenAIProvider without invoking _init_client (no openai package needed).
    """
    provider = object.__new__(OpenAIProvider)
    provider.config = {}
    provider.logger = get_logger("test_provider")
    provider.api_key = "test-key"
    provider.model = "test-model"
    provider.base_url = base_url
    provider.client = MagicMock()
    return provider


class _StubEntityOut:
    def __init__(self, text, label, confidence):
        self.text = text
        self.label = label
        self.confidence = confidence


class _StubEntitiesResponse:
    """
    Minimal pydantic-like schema stub usable without pydantic installed.

    The class-level `entities = None` is required so that
    `hasattr(schema, "entities")` returns True inside generate_typed's
    auto-wrap logic.
    """

    model_fields = {"entities": None}
    entities = None  # class-level placeholder — mirrors pydantic field descriptor

    def __init__(self, entities):
        self.entities = entities

    @classmethod
    def model_validate(cls, data):
        if not isinstance(data, dict) or "entities" not in data:
            raise ValueError(f"Expected dict with 'entities' key, got: {data!r}")
        return cls([_StubEntityOut(**e) for e in data["entities"]])


# ---------------------------------------------------------------------------
# Bug 1 – exc_info=True on method failure in NERExtractor
# ---------------------------------------------------------------------------

class TestBug1ExcInfoOnMethodFailure(unittest.TestCase):
    """
    NERExtractor.extract_entities must log the full traceback when a method
    raises, not just the single-line message.  Without exc_info=True the user
    sees 'Method llm failed: <msg>' but no root cause.
    """

    @patch("semantica.semantic_extract.methods.create_provider")
    def test_traceback_logged_on_llm_failure(self, mock_create):
        """Full traceback must appear in the log when the LLM method fails."""
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.generate_typed.side_effect = RuntimeError("gateway timeout")
        mock_create.return_value = mock_llm

        extractor = NERExtractor(method="llm", provider="openai", llm_model="test-model")

        with self.assertLogs("semantica.ner_extractor", level="WARNING") as log_ctx:
            extractor.extract_entities("Hello World.")

        has_traceback = any(r.exc_info is not None for r in log_ctx.records)
        self.assertTrue(
            has_traceback,
            "Expected a WARNING record with exc_info set, but none found. "
            "Ensure exc_info=True is in the method-failure warning call.",
        )

    @patch("semantica.semantic_extract.methods.create_provider")
    def test_failure_message_contains_method_name(self, mock_create):
        """Warning message must identify which method failed."""
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.generate_typed.side_effect = ProcessingError("schema mismatch")
        mock_create.return_value = mock_llm

        extractor = NERExtractor(method="llm", provider="openai", llm_model="test-model")

        with self.assertLogs("semantica.ner_extractor", level="WARNING") as log_ctx:
            extractor.extract_entities("Hello World.")

        messages = " ".join(r.getMessage() for r in log_ctx.records)
        self.assertIn("llm", messages.lower())

    @patch("semantica.semantic_extract.methods.create_provider")
    def test_fallback_to_pattern_on_llm_failure(self, mock_create):
        """After LLM failure the extractor must still return results, not raise."""
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.generate_typed.side_effect = ProcessingError("instructor failed")
        mock_create.return_value = mock_llm

        extractor = NERExtractor(method="llm", provider="openai", llm_model="test-model")

        with self.assertLogs("semantica.ner_extractor", level="WARNING"):
            result = extractor.extract_entities(
                "John Smith visited Microsoft in New York."
            )

        self.assertIsInstance(result, list)
        methods = {e.metadata.get("extraction_method") for e in result}
        self.assertTrue(
            methods <= {"pattern", "last_resort_pattern"},
            f"Unexpected extraction_method values after fallback: {methods}",
        )

    @patch("semantica.semantic_extract.methods.EntitiesResponse",
           _StubEntitiesResponse, create=True)
    @patch("semantica.semantic_extract.methods.SCHEMAS_AVAILABLE", True)
    @patch("semantica.semantic_extract.methods.create_provider")
    def test_llm_success_returns_llm_typed_metadata(self, mock_create):
        """When LLM succeeds, entities must carry extraction_method='llm_typed'."""
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.generate_typed.return_value = _make_entity_response([
            {"text": "John Smith", "label": "PERSON", "confidence": 0.95},
            {"text": "Microsoft",  "label": "ORG",    "confidence": 0.90},
        ])
        mock_create.return_value = mock_llm

        extractor = NERExtractor(method="llm", provider="openai", llm_model="test-model")
        result = extractor.extract_entities("John Smith visited Microsoft.")

        self.assertGreaterEqual(len(result), 1)
        for e in result:
            self.assertEqual(
                e.metadata.get("extraction_method"), "llm_typed",
                f"Expected llm_typed, got {e.metadata}",
            )


# ---------------------------------------------------------------------------
# Bug 2 – OpenAIProvider.generate_structured must not send response_format
#          when base_url (custom gateway) is set
# ---------------------------------------------------------------------------

class TestBug2GenerateStructuredCustomGateway(unittest.TestCase):
    """
    generate_structured always added response_format=json_object even for
    custom gateways that don't support it.  After the fix, it is omitted when
    base_url is set.
    """

    def _capture_create_kwargs(self, provider, prompt="Extract entities."):
        """Run generate_structured and return kwargs sent to the API."""
        captured = {}
        payload = json.dumps({
            "entities": [{"text": "Alice", "label": "PERSON", "confidence": 0.9}]
        })
        resp = MagicMock()
        resp.choices[0].message.content = payload

        def fake_create(**kwargs):
            captured.update(kwargs)
            return resp

        provider.client.chat.completions.create.side_effect = fake_create
        provider.generate_structured(prompt)
        return captured

    def test_standard_endpoint_sends_response_format(self):
        """Standard OpenAI (no base_url) must still send response_format=json_object."""
        provider = _bare_openai_provider(base_url=None)
        kwargs = self._capture_create_kwargs(provider)
        self.assertIn(
            "response_format", kwargs,
            "Standard endpoint must send response_format=json_object",
        )
        self.assertEqual(kwargs["response_format"], {"type": "json_object"})

    def test_custom_gateway_omits_response_format(self):
        """Custom gateway (base_url set) must NOT send response_format."""
        provider = _bare_openai_provider(
            base_url="https://qa-llmgateway.local/api/v1beta/llm/messages"
        )
        kwargs = self._capture_create_kwargs(provider)
        self.assertNotIn(
            "response_format", kwargs,
            "Custom gateway must not receive response_format=json_object — "
            "many gateways reject this parameter, causing silent fallback.",
        )

    def test_custom_localhost_gateway_omits_response_format(self):
        """Any non-None base_url must suppress response_format."""
        provider = _bare_openai_provider(base_url="http://localhost:8080/v1")
        kwargs = self._capture_create_kwargs(provider)
        self.assertNotIn("response_format", kwargs)

    def test_generate_structured_parses_json_without_response_format(self):
        """Result must still be parsed correctly even without response_format."""
        provider = _bare_openai_provider(
            base_url="https://qa-llmgateway.local/api/v1beta"
        )
        payload = {"entities": [{"text": "Bob", "label": "PERSON", "confidence": 0.8}]}
        resp = MagicMock()
        resp.choices[0].message.content = json.dumps(payload)
        provider.client.chat.completions.create.return_value = resp

        result = provider.generate_structured("Find entities.")
        self.assertEqual(result, payload)

    def test_standard_endpoint_result_unchanged(self):
        """Standard-endpoint path must still return correct data."""
        provider = _bare_openai_provider(base_url=None)
        payload = {"entities": [{"text": "Eve", "label": "PERSON", "confidence": 0.7}]}
        resp = MagicMock()
        resp.choices[0].message.content = json.dumps(payload)
        provider.client.chat.completions.create.return_value = resp

        result = provider.generate_structured("Find entities.")
        self.assertEqual(result, payload)

    def test_invalid_base_url_scheme_raises(self):
        """Non-HTTP(S) base_url must be rejected at init time to prevent SSRF."""
        for bad_url in ("file:///etc/passwd", "ftp://internal.host/v1", "javascript:void"):
            with self.assertRaises(ValueError, msg=f"Expected ValueError for {bad_url!r}"):
                provider = object.__new__(OpenAIProvider)
                provider.config = {}
                provider.logger = get_logger("test_provider")
                provider.api_key = "test-key"
                provider.model = "test-model"
                provider.base_url = bad_url
                provider.client = None
                provider._init_client()

    def test_valid_http_base_url_accepted(self):
        """http:// and https:// base_url values must pass validation."""
        for good_url in ("https://gateway.corp/api/v1", "http://localhost:8080/v1"):
            provider = object.__new__(OpenAIProvider)
            provider.config = {}
            provider.logger = get_logger("test_provider")
            provider.api_key = "test-key"
            provider.model = "test-model"
            provider.base_url = good_url
            provider.client = None
            # _init_client will fail to import openai (not installed) but must
            # not raise ValueError before reaching the import
            try:
                provider._init_client()
            except ValueError:
                self.fail(f"_init_client raised ValueError for valid URL {good_url!r}")
            except Exception:
                pass  # ImportError / OSError from missing openai package is expected


# ---------------------------------------------------------------------------
# Bug 3 – generate_typed manual repair loop must fall back to plain generate()
#          when generate_structured itself raises
# ---------------------------------------------------------------------------

class TestBug3GenerateTypedFallbackToPlainGenerate(unittest.TestCase):
    """
    The manual repair loop inside generate_typed called generate_structured,
    which for custom gateways also fails (same response_format rejection).
    After the fix, if generate_structured raises, the loop immediately retries
    via plain generate() + _parse_json.
    """

    def _valid_json(self):
        return json.dumps({
            "entities": [
                {"text": "Alice",     "label": "PERSON", "confidence": 0.95},
                {"text": "Acme Corp", "label": "ORG",    "confidence": 0.88},
            ]
        })

    def test_fallback_to_plain_generate_when_structured_fails(self):
        """
        If generate_structured raises, generate_typed must call plain generate()
        and successfully parse the JSON it returns.
        """
        provider = _bare_openai_provider(base_url="https://gateway.local/api/v1")

        provider.generate_structured = MagicMock(
            side_effect=ProcessingError("response_format not supported")
        )
        provider.generate = MagicMock(return_value=self._valid_json())

        result = provider.generate_typed(
            "Extract entities from: Alice works at Acme Corp.",
            schema=_StubEntitiesResponse,
            max_retries=2,
        )

        self.assertEqual(len(result.entities), 2)
        self.assertEqual(result.entities[0].text, "Alice")
        self.assertEqual(result.entities[1].text, "Acme Corp")
        provider.generate.assert_called()

    def test_generate_structured_is_attempted_first(self):
        """Plain generate() is the fallback, not the primary path."""
        provider = _bare_openai_provider()

        call_order = []

        def fake_structured(_prompt, **_kw):
            call_order.append("structured")
            return {"entities": [{"text": "Bob", "label": "PERSON", "confidence": 0.9}]}

        def fake_generate(_prompt, **_kw):
            call_order.append("generate")
            return json.dumps({"entities": [{"text": "Bob", "label": "PERSON", "confidence": 0.9}]})

        provider.generate_structured = fake_structured
        provider.generate = fake_generate

        provider.generate_typed(
            "Find entities.", schema=_StubEntitiesResponse, max_retries=1
        )

        self.assertEqual(call_order[0], "structured",
                         "generate_structured must be tried first")
        self.assertNotIn("generate", call_order,
                         "plain generate() must NOT be called when generate_structured succeeds")

    def test_error_raised_when_both_paths_fail(self):
        """
        If both generate_structured AND plain generate() fail, generate_typed
        must raise — not silently return empty/wrong data.
        """
        provider = _bare_openai_provider(base_url="https://gateway.local/api/v1")

        provider.generate_structured = MagicMock(
            side_effect=ProcessingError("json_object not supported")
        )
        provider.generate = MagicMock(
            side_effect=ConnectionError("gateway unreachable")
        )

        with self.assertRaises(Exception):
            provider.generate_typed(
                "Extract entities.", schema=_StubEntitiesResponse, max_retries=2
            )

    def test_generate_structured_fallback_warning_has_exc_info(self):
        """
        The warning logged when generate_structured fails must carry exc_info so
        the full traceback is visible in production logs (consistent with other
        warnings added in this PR).
        """
        provider = _bare_openai_provider(base_url="https://gateway.local/api/v1")

        provider.generate_structured = MagicMock(
            side_effect=ProcessingError("response_format rejected")
        )
        provider.generate = MagicMock(return_value=self._valid_json())

        with self.assertLogs("semantica.test_provider", level="WARNING") as log_ctx:
            provider.generate_typed(
                "Extract entities.", schema=_StubEntitiesResponse, max_retries=1
            )

        has_traceback = any(r.exc_info is not None for r in log_ctx.records)
        self.assertTrue(
            has_traceback,
            "generate_structured fallback warning must include exc_info=True "
            "so the gateway rejection traceback is visible in logs.",
        )

    def test_fallback_preserves_error_on_bad_json(self):
        """
        If plain generate() returns malformed JSON the error must propagate,
        not silently swallow the result.
        """
        provider = _bare_openai_provider(base_url="https://gateway.local/api/v1")

        provider.generate_structured = MagicMock(
            side_effect=ProcessingError("json_object not supported")
        )
        provider.generate = MagicMock(return_value="<html>not json</html>")

        with self.assertRaises(Exception):
            provider.generate_typed(
                "Extract entities.", schema=_StubEntitiesResponse, max_retries=1
            )

    def test_schema_validation_wraps_plain_list(self):
        """
        If plain generate() returns a bare list (not wrapped in {"entities": [...]}),
        generate_typed must auto-wrap it before calling model_validate.
        """
        provider = _bare_openai_provider(base_url="https://gateway.local/api/v1")

        provider.generate_structured = MagicMock(
            side_effect=ProcessingError("response_format not supported")
        )
        provider.generate = MagicMock(return_value=json.dumps([
            {"text": "Carol", "label": "PERSON", "confidence": 0.85},
        ]))

        result = provider.generate_typed(
            "Extract entities.", schema=_StubEntitiesResponse, max_retries=2
        )

        self.assertEqual(len(result.entities), 1)
        self.assertEqual(result.entities[0].text, "Carol")


# ---------------------------------------------------------------------------
# Integration – all three fixes working together
# ---------------------------------------------------------------------------

class TestIssue554EndToEnd(unittest.TestCase):
    """
    Simulate harshalizode's exact scenario:
      - NERExtractor(method="llm", provider="openai", base_url="custom-gateway")
      - instructor fails / generate_typed is mocked to succeed
      - Returned entities must carry extraction_method="llm_typed", not "pattern"
    """

    @patch("semantica.semantic_extract.methods.EntitiesResponse",
           _StubEntitiesResponse, create=True)
    @patch("semantica.semantic_extract.methods.SCHEMAS_AVAILABLE", True)
    @patch("semantica.semantic_extract.methods.create_provider")
    def test_custom_gateway_returns_llm_entities_not_pattern(self, mock_create):
        """
        End-to-end: custom gateway produces LLM entities, NOT pattern-fallback.
        """
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.generate_typed.return_value = _make_entity_response([
            {"text": "Miss Theodora Clare", "label": "PERSON",   "confidence": 0.95},
            {"text": "Cedar Lodge",          "label": "LOCATION", "confidence": 0.95},
            {"text": "India",                "label": "GPE",      "confidence": 0.95},
        ])
        mock_create.return_value = mock_llm

        extractor = NERExtractor(
            method="llm",
            provider="openai",
            llm_model="Llama-4-Scout",
            base_url="https://qa-llmgateway.local/api/v1beta/llm/messages",
            entity_types=["PERSON", "LOCATION", "GPE"],
        )

        result = extractor.extract_entities(
            "Miss Theodora Clare arrived at Cedar Lodge. She had spent five years in India."
        )

        # At least some LLM entities must come through
        self.assertGreater(len(result), 0)

        # None should carry pattern metadata
        for e in result:
            self.assertNotEqual(
                e.metadata.get("extraction_method"), "pattern",
                f"Entity {e.text!r} must not have extraction_method='pattern'; "
                f"got metadata={e.metadata}",
            )

        # Must include at least the PERSON entity
        labels = {e.label for e in result}
        self.assertIn("PERSON", labels)

    @patch("semantica.semantic_extract.methods.create_provider")
    def test_instructor_failure_logged_with_traceback(self, mock_create):
        """
        When instructor / generate_typed fails, the warning must carry exc_info
        so the user can diagnose the root cause from logs alone.
        """
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.generate_typed.side_effect = ProcessingError(
            "instructor: response_format not supported by gateway"
        )
        mock_create.return_value = mock_llm

        extractor = NERExtractor(
            method="llm",
            provider="openai",
            llm_model="Llama-4-Scout",
            base_url="https://qa-llmgateway.local/api/v1beta/llm/messages",
        )

        with self.assertLogs("semantica.ner_extractor", level="WARNING") as log_ctx:
            result = extractor.extract_entities(
                "John Smith visited Microsoft in Seattle."
            )

        has_traceback = any(r.exc_info is not None for r in log_ctx.records)
        self.assertTrue(
            has_traceback,
            "Warning log must carry exc_info so the gateway error is diagnosable.",
        )
        self.assertIsInstance(result, list)

    @patch("semantica.semantic_extract.methods.EntitiesResponse",
           _StubEntitiesResponse, create=True)
    @patch("semantica.semantic_extract.methods.SCHEMAS_AVAILABLE", True)
    @patch("semantica.semantic_extract.methods.create_provider")
    def test_fallback_chain_llm_then_pattern(self, mock_create):
        """
        With method=["llm", "pattern"], LLM failure falls through to pattern —
        not raise — and pattern entities are returned.
        """
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.generate_typed.side_effect = ProcessingError("timeout")
        mock_create.return_value = mock_llm

        extractor = NERExtractor(
            method=["llm", "pattern"],
            provider="openai",
            llm_model="test-model",
        )

        with self.assertLogs("semantica.ner_extractor", level="WARNING"):
            result = extractor.extract_entities(
                "Barack Obama visited the United States Capitol."
            )

        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0, "Pattern method should extract something")


if __name__ == "__main__":
    unittest.main(verbosity=2)
