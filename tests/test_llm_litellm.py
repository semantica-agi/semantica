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


def _with_instructor_init_failure(monkeypatch, error=None):
    """Point ``safe_import("instructor")`` at a module whose ``from_litellm()`` raises.

    Simulates instructor being importable but unable to wrap this LiteLLM
    ``completion`` (e.g. an incompatible instructor/litellm version pairing).
    """
    fake_instructor = MagicMock()
    fake_instructor.from_litellm.side_effect = error or RuntimeError("incompatible client")
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


def test_generate_typed_falls_back_when_instructor_init_fails(litellm_available, monkeypatch):
    """Regression test: instructor is installed but from_litellm() raises - this
    must fall through to the manual loop and still succeed, not propagate the
    init failure or skip generation."""
    fake_instructor = _with_instructor_init_failure(monkeypatch)

    llm = LiteLLM(model="openai/gpt-4o")
    llm.generate_structured = MagicMock(return_value={"x": 5, "y": 6})

    result = llm.generate_typed("give me a point", _Point)

    assert isinstance(result, _Point)
    assert (result.x, result.y) == (5, 6)
    fake_instructor.from_litellm.assert_called_once()
    llm.generate_structured.assert_called_once()


# --- fallback path: instructor is not available -----------------------------


def test_generate_typed_validates_structured_output(litellm_available, without_instructor):
    llm = LiteLLM(model="openai/gpt-4o")
    llm.generate_structured = MagicMock(return_value={"x": 1, "y": 2})

    result = llm.generate_typed("give me a point", _Point)

    assert isinstance(result, _Point)
    assert (result.x, result.y) == (1, 2)
    llm.generate_structured.assert_called_once()


def test_generate_typed_retries_then_raises_on_bad_output(
    litellm_available, without_instructor, monkeypatch
):
    sleep_calls = []
    monkeypatch.setattr(litellm_module.time, "sleep", sleep_calls.append)

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
    # Backs off between attempts (but not after the last one) - mirrors
    # BaseProvider's fallback loop instead of hammering the API immediately.
    assert sleep_calls == [1]


# --- generate_structured list-return and array-fallback tests ---------------


def test_generate_structured_passes_through_list_return(litellm_available, monkeypatch):
    """When the model returns a top-level JSON array, generate_structured() must
    return a list, not raise or truncate."""
    fake_message = MagicMock()
    fake_message.content = '[{"id": 1}, {"id": 2}]'
    fake_choice = MagicMock()
    fake_choice.message = fake_message
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]
    monkeypatch.setattr(litellm_module, "completion", lambda **kw: fake_response)

    llm = LiteLLM(model="openai/gpt-4o", api_key="k")
    result = llm.generate_structured("return a list")

    assert result == [{"id": 1}, {"id": 2}]
    assert isinstance(result, list)


def test_generate_structured_array_fallback_extracts_list_from_prose(
    litellm_available, monkeypatch
):
    """When json.loads() fails (due to surrounding prose) and the JSON is an array,
    the regex fallback must still extract and return the list."""
    fake_message = MagicMock()
    fake_message.content = 'Here is the data: [{"id": 1}, {"id": 2}] as requested.'
    fake_choice = MagicMock()
    fake_choice.message = fake_message
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]
    monkeypatch.setattr(litellm_module, "completion", lambda **kw: fake_response)

    llm = LiteLLM(model="openai/gpt-4o", api_key="k")
    result = llm.generate_structured("return a list")

    assert result == [{"id": 1}, {"id": 2}]
    assert isinstance(result, list)


def test_generate_structured_prefers_earlier_json_boundary(litellm_available, monkeypatch):
    """When both an array and an object appear in the text, the one that starts
    first should be extracted."""
    fake_message = MagicMock()
    # Array comes first, object appears later
    fake_message.content = 'Result: [{"x": 1}] and also {"note": "extra"}'
    fake_choice = MagicMock()
    fake_choice.message = fake_message
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]
    monkeypatch.setattr(litellm_module, "completion", lambda **kw: fake_response)

    llm = LiteLLM(model="openai/gpt-4o", api_key="k")
    result = llm.generate_structured("mixed")

    assert result == [{"x": 1}]
    assert isinstance(result, list)


# --- Qodo finding #1 regression: misleading brackets before valid JSON ------


def _make_litellm_with_response(monkeypatch, content: str) -> "LiteLLM":
    """Return a LiteLLM instance whose completion call returns *content*."""
    fake_message = MagicMock()
    fake_message.content = content
    fake_choice = MagicMock()
    fake_choice.message = fake_message
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]
    monkeypatch.setattr(litellm_module, "completion", lambda **kw: fake_response)
    return LiteLLM(model="openai/gpt-4o", api_key="k")


def test_generate_structured_misleading_array_before_object(litellm_available, monkeypatch):
    """Regression for Qodo finding #1: prose containing [not JSON] before a
    valid JSON object must return the object, not raise ProcessingError."""
    llm = _make_litellm_with_response(
        monkeypatch, 'Intro [not JSON] then {"ok": 1}'
    )
    result = llm.generate_structured("test")
    assert result == {"ok": 1}
    assert isinstance(result, dict)


def test_generate_structured_misleading_object_before_array(litellm_available, monkeypatch):
    """Misleading {...} prose (not valid JSON) before a valid JSON array must
    return the array."""
    llm = _make_litellm_with_response(
        monkeypatch, "note {broken then [1, 2, 3]"
    )
    result = llm.generate_structured("test")
    assert result == [1, 2, 3]
    assert isinstance(result, list)


def test_generate_structured_nested_json_object(litellm_available, monkeypatch):
    """Nested objects must not confuse the bracket scanner."""
    llm = _make_litellm_with_response(
        monkeypatch, 'Result: {"a": {"b": [1, 2]}, "c": 3}'
    )
    result = llm.generate_structured("test")
    assert result == {"a": {"b": [1, 2]}, "c": 3}


def test_generate_structured_bracket_in_string_value(litellm_available, monkeypatch):
    """A closing bracket inside a string literal must not end the JSON early."""
    llm = _make_litellm_with_response(
        monkeypatch, '{"msg": "array: [1,2]", "val": 42}'
    )
    result = llm.generate_structured("test")
    assert result == {"msg": "array: [1,2]", "val": 42}
