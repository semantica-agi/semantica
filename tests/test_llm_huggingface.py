"""Tests for the HuggingFace LLM provider wrapper (semantica.llms.HuggingFaceLLM).

The wrapper builds a real ``HuggingFaceLLMProvider`` in ``__init__``, which would
load a model from disk/network. These tests patch that class so we only exercise
the wrapper's delegation and error handling.
"""

from unittest.mock import patch

import pytest

from semantica.utils.exceptions import ProcessingError

PROVIDER_PATH = "semantica.llms.huggingface.HuggingFaceLLMProvider"


def _make_wrapper(available=True):
    from semantica.llms import HuggingFaceLLM

    with patch(PROVIDER_PATH) as provider_cls:
        provider_cls.return_value.is_available.return_value = available
        return HuggingFaceLLM(model_name="gpt2")


def test_construction_stores_model_name():
    hf = _make_wrapper()
    assert hf.model_name == "gpt2"
    assert hf.model == "gpt2"  # alias kept for cross-provider consistency


def test_generate_raises_clear_error_when_unavailable():
    hf = _make_wrapper(available=False)
    with pytest.raises(ProcessingError, match="HuggingFace LLM provider not available"):
        hf.generate("hello")


def test_generate_forwards_to_the_real_provider_when_available():
    hf = _make_wrapper()
    hf.provider.generate.return_value = "a fake response"

    result = hf.generate("hello", max_new_tokens=10)

    assert result == "a fake response"
    hf.provider.generate.assert_called_once_with("hello", max_new_tokens=10)


def test_generate_structured_forwards_to_the_real_provider():
    hf = _make_wrapper()
    hf.provider.generate_structured.return_value = {"key": "value"}

    result = hf.generate_structured("hello")

    assert result == {"key": "value"}
    hf.provider.generate_structured.assert_called_once_with("hello")


def test_generate_typed_forwards_schema_and_max_retries():
    hf = _make_wrapper()
    fake_schema = object()
    hf.provider.generate_typed.return_value = "typed result"

    result = hf.generate_typed("hello", fake_schema, max_retries=5)

    assert result == "typed result"
    hf.provider.generate_typed.assert_called_once_with(
        "hello", fake_schema, max_retries=5
    )


def test_generate_structured_raises_clear_error_when_unavailable():
    hf = _make_wrapper(available=False)
    with pytest.raises(ProcessingError, match="HuggingFace LLM provider not available"):
        hf.generate_structured("hello")


def test_generate_typed_raises_clear_error_when_unavailable():
    hf = _make_wrapper(available=False)
    with pytest.raises(ProcessingError, match="HuggingFace LLM provider not available"):
        hf.generate_typed("hello", object())
