"""Tests for the OpenAI LLM provider wrapper (semantica.llms.OpenAI)."""

from unittest.mock import MagicMock

import pytest

from semantica.llms import OpenAI
from semantica.utils.exceptions import ProcessingError


def test_construction_stores_model_and_api_key():
    llm = OpenAI(model="gpt-4", api_key="fake-key")
    assert llm.model == "gpt-4"
    assert llm.api_key == "fake-key"


def test_is_available_false_with_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    llm = OpenAI(api_key=None)
    assert llm.is_available() is False


def test_generate_raises_clear_error_when_unavailable(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    llm = OpenAI(api_key=None)
    with pytest.raises(ProcessingError, match="OpenAI provider not available"):
        llm.generate("hello")


def test_generate_forwards_to_the_real_provider_when_available():
    llm = OpenAI(api_key="fake-key")
    llm.provider = MagicMock()
    llm.provider.is_available.return_value = True
    llm.provider.generate.return_value = "a fake response"

    result = llm.generate("hello", temperature=0.5)

    assert result == "a fake response"
    llm.provider.generate.assert_called_once_with("hello", temperature=0.5)


def test_generate_structured_forwards_to_the_real_provider():
    llm = OpenAI(api_key="fake-key")
    llm.provider = MagicMock()
    llm.provider.is_available.return_value = True
    llm.provider.generate_structured.return_value = {"key": "value"}

    result = llm.generate_structured("hello")

    assert result == {"key": "value"}
    llm.provider.generate_structured.assert_called_once_with("hello")


def test_generate_typed_forwards_schema_and_max_retries():
    llm = OpenAI(api_key="fake-key")
    llm.provider = MagicMock()
    llm.provider.is_available.return_value = True
    fake_schema = object()
    llm.provider.generate_typed.return_value = "typed result"

    result = llm.generate_typed("hello", fake_schema, max_retries=5)

    assert result == "typed result"
    llm.provider.generate_typed.assert_called_once_with(
        "hello", fake_schema, max_retries=5
    )


def test_generate_structured_raises_clear_error_when_unavailable(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    llm = OpenAI(api_key=None)
    with pytest.raises(ProcessingError, match="OpenAI provider not available"):
        llm.generate_structured("hello")


def test_generate_typed_raises_clear_error_when_unavailable(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    llm = OpenAI(api_key=None)
    with pytest.raises(ProcessingError, match="OpenAI provider not available"):
        llm.generate_typed("hello", object())


def test_generate_structured_passes_through_list_return():
    """generate_structured() must propagate a top-level JSON array unchanged."""
    llm = OpenAI(api_key="fake-key")
    llm.provider = MagicMock()
    llm.provider.is_available.return_value = True
    llm.provider.generate_structured.return_value = [{"id": 1}, {"id": 2}]

    result = llm.generate_structured("return a list")

    assert result == [{"id": 1}, {"id": 2}]
    assert isinstance(result, list)


# OpenAI shut these down in 2026 (https://developers.openai.com/api/docs/deprecations).
SHUT_DOWN_OPENAI_MODELS = {"gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"}


def test_default_openai_model_is_not_shut_down():
    from semantica.semantic_extract.providers import DEFAULT_OPENAI_MODEL

    assert DEFAULT_OPENAI_MODEL not in SHUT_DOWN_OPENAI_MODELS


def test_openai_wrapper_uses_shared_default_model():
    from semantica.semantic_extract.providers import DEFAULT_OPENAI_MODEL

    llm = OpenAI(api_key="fake-key")

    assert llm.model == DEFAULT_OPENAI_MODEL
    assert llm.provider.model == DEFAULT_OPENAI_MODEL


def test_openai_provider_uses_shared_default_model():
    from semantica.semantic_extract.providers import (
        DEFAULT_OPENAI_MODEL,
        OpenAIProvider,
    )

    assert OpenAIProvider(api_key="fake-key").model == DEFAULT_OPENAI_MODEL


def _record_split_llm_provider_kwargs(monkeypatch, **split_kwargs):
    from semantica.split import methods

    calls = []

    def fake_create_provider(provider, **kwargs):
        calls.append((provider, kwargs))
        raise RuntimeError("stop after recording the provider arguments")

    monkeypatch.setattr(methods, "SEMANTIC_EXTRACT_AVAILABLE", True)
    monkeypatch.setattr(methods, "create_provider", fake_create_provider, raising=False)
    methods.split_llm("Some text to split.", chunk_size=100, **split_kwargs)

    assert len(calls) == 1
    return calls[0]


def test_split_llm_without_model_leaves_default_to_provider(monkeypatch):
    provider, kwargs = _record_split_llm_provider_kwargs(monkeypatch)

    assert provider == "openai"
    assert "model" not in kwargs


def test_split_llm_does_not_send_openai_model_to_other_providers(monkeypatch):
    provider, kwargs = _record_split_llm_provider_kwargs(monkeypatch, provider="groq")

    assert provider == "groq"
    assert "model" not in kwargs


def test_split_llm_passes_explicit_model(monkeypatch):
    _, kwargs = _record_split_llm_provider_kwargs(
        monkeypatch, provider="openai", model="gpt-4o"
    )

    assert kwargs["model"] == "gpt-4o"
