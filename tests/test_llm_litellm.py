"""Tests for the LiteLLM provider wrapper (semantica.llms.LiteLLM).

Unlike the other wrappers, LiteLLM does not sit on a ``BaseProvider`` - it calls
``litellm.completion`` directly - so ``generate_typed()`` has its own
implementation (instructor when available, otherwise a validate-and-retry loop
on top of ``generate_structured()``). These tests exercise the fallback loop,
which is what runs when instructor is not installed.
"""

from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

import semantica.llms.litellm as litellm_module
from semantica.llms.litellm import LiteLLM
from semantica.utils.exceptions import ProcessingError


class _Point(BaseModel):
    x: int
    y: int


@pytest.fixture
def litellm_available(monkeypatch):
    """Pretend the litellm library is installed."""
    monkeypatch.setattr(litellm_module, "LITELLM_AVAILABLE", True)
    monkeypatch.setattr(litellm_module, "completion", MagicMock(), raising=False)


def test_construction_raises_without_litellm_installed(monkeypatch):
    monkeypatch.setattr(litellm_module, "LITELLM_AVAILABLE", False)
    with pytest.raises(ProcessingError, match="LiteLLM library not installed"):
        LiteLLM(model="openai/gpt-4o")


def test_construction_stores_model_and_api_key(litellm_available):
    llm = LiteLLM(model="openai/gpt-4o", api_key="fake-key")
    assert llm.model == "openai/gpt-4o"
    assert llm.api_key == "fake-key"


def test_generate_typed_raises_when_unavailable(litellm_available, monkeypatch):
    llm = LiteLLM(model="openai/gpt-4o")
    monkeypatch.setattr(litellm_module, "LITELLM_AVAILABLE", False)
    with pytest.raises(ProcessingError, match="LiteLLM library not installed"):
        llm.generate_typed("hello", _Point)


def test_generate_typed_validates_structured_output(litellm_available):
    llm = LiteLLM(model="openai/gpt-4o")
    llm.generate_structured = MagicMock(return_value={"x": 1, "y": 2})

    result = llm.generate_typed("give me a point", _Point)

    assert isinstance(result, _Point)
    assert (result.x, result.y) == (1, 2)
    llm.generate_structured.assert_called_once()


def test_generate_typed_retries_then_raises_on_bad_output(litellm_available):
    llm = LiteLLM(model="openai/gpt-4o")
    llm.generate_structured = MagicMock(return_value={"x": "not-an-int"})

    with pytest.raises(ProcessingError, match="typed generation failed after 2 attempts"):
        llm.generate_typed("give me a point", _Point, max_retries=2)

    assert llm.generate_structured.call_count == 2
