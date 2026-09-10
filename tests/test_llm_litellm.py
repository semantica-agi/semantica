"""Tests for the LiteLLM provider wrapper (semantica.llms.LiteLLM).

Unlike the other wrappers, LiteLLM does not sit on a ``BaseProvider`` - it calls
``litellm.completion`` directly - so ``generate_typed()`` has its own
implementation: it uses ``instructor`` when that package is importable, and
otherwise falls back to a validate-and-retry loop on top of
``generate_structured()``. Which path runs depends only on whether ``instructor``
imports, so every test here pins that explicitly via ``safe_import``.
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


@pytest.fixture
def without_instructor(monkeypatch):
    """Force ``safe_import("instructor")`` to report unavailable.

    Without this the selected code path would depend on whether ``instructor``
    happens to be installed in the test environment (it is part of the repo's
    all-extras set), so the manual-fallback tests would not reliably exercise
    the fallback.
    """
    real = litellm_module.safe_import
    monkeypatch.setattr(
        litellm_module,
        "safe_import",
        lambda name, *a, **k: (None, False) if name == "instructor" else real(name, *a, **k),
    )


def _with_instructor(monkeypatch, fake_client):
    """Point ``safe_import("instructor")`` at a fake instructor module."""
    fake_instructor = MagicMock()
    fake_instructor.from_litellm.return_value = fake_client
    real = litellm_module.safe_import
    monkeypatch.setattr(
        litellm_module,
        "safe_import",
        lambda name, *a, **k: (fake_instructor, True)
        if name == "instructor"
        else real(name, *a, **k),
    )
    return fake_instructor


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


# --- preferred path: instructor is available -------------------------------


def test_generate_typed_prefers_instructor_when_available(litellm_available, monkeypatch):
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _Point(x=3, y=4)
    _with_instructor(monkeypatch, fake_client)

    llm = LiteLLM(model="openai/gpt-4o", api_key="k")
    llm.generate_structured = MagicMock()  # must not be touched on this path

    result = llm.generate_typed("give me a point", _Point, max_retries=2)

    assert result == _Point(x=3, y=4)
    llm.generate_structured.assert_not_called()
    _, kwargs = fake_client.chat.completions.create.call_args
    assert kwargs["response_model"] is _Point
    assert kwargs["max_retries"] == 2
    assert kwargs["model"] == "openai/gpt-4o"


def test_generate_typed_surfaces_instructor_completion_error(litellm_available, monkeypatch):
    """A failing completion request is raised, not retried through the manual loop."""
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = RuntimeError("401 unauthorized")
    _with_instructor(monkeypatch, fake_client)

    llm = LiteLLM(model="openai/gpt-4o", api_key="k")
    llm.generate_structured = MagicMock()

    with pytest.raises(ProcessingError, match="LiteLLM typed generation failed"):
        llm.generate_typed("give me a point", _Point)

    llm.generate_structured.assert_not_called()


# --- fallback path: instructor is not available ----------------------------


def test_generate_typed_validates_structured_output(litellm_available, without_instructor):
    llm = LiteLLM(model="openai/gpt-4o")
    llm.generate_structured = MagicMock(return_value={"x": 1, "y": 2})

    result = llm.generate_typed("give me a point", _Point)

    assert isinstance(result, _Point)
    assert (result.x, result.y) == (1, 2)
    llm.generate_structured.assert_called_once()


def test_generate_typed_retries_then_raises_on_bad_output(litellm_available, without_instructor):
    llm = LiteLLM(model="openai/gpt-4o")
    llm.generate_structured = MagicMock(return_value={"x": "not-an-int"})

    with pytest.raises(ProcessingError, match="LiteLLM typed generation failed"):
        llm.generate_typed("give me a point", _Point, max_retries=2)

    assert llm.generate_structured.call_count == 2
    # The retry must feed the validation error back into the prompt.
    first_prompt = llm.generate_structured.call_args_list[0].args[0]
    retry_prompt = llm.generate_structured.call_args_list[1].args[0]
    assert first_prompt == "give me a point"
    assert "did not match the required" in retry_prompt
