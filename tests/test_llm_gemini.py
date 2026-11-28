"""Tests for the Gemini LLM provider wrapper (semantica.llms.Gemini)."""

import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from semantica.llms import Gemini
from semantica.utils.exceptions import ProcessingError


def test_construction_stores_model_and_api_key():
    gemini = Gemini(model="gemini-pro", api_key="fake-key")
    assert gemini.model == "gemini-pro"
    assert gemini.api_key == "fake-key"


def test_is_available_false_with_no_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gemini = Gemini(api_key=None)
    assert gemini.is_available() is False


def test_generate_raises_clear_error_when_unavailable(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gemini = Gemini(api_key=None)
    with pytest.raises(ProcessingError, match="Gemini provider not available"):
        gemini.generate("hello")


def test_generate_forwards_to_the_real_provider_when_available():
    gemini = Gemini(api_key="fake-key")
    gemini.provider = MagicMock()
    gemini.provider.is_available.return_value = True
    gemini.provider.generate.return_value = "a fake response"

    result = gemini.generate("hello", temperature=0.5)

    assert result == "a fake response"
    gemini.provider.generate.assert_called_once_with("hello", temperature=0.5)


def test_generate_structured_forwards_to_the_real_provider():
    gemini = Gemini(api_key="fake-key")
    gemini.provider = MagicMock()
    gemini.provider.is_available.return_value = True
    gemini.provider.generate_structured.return_value = {"key": "value"}

    result = gemini.generate_structured("hello")

    assert result == {"key": "value"}
    gemini.provider.generate_structured.assert_called_once_with("hello")


def test_per_call_model_override_forwarded_for_both_methods():
    gemini = Gemini(api_key="fake-key")
    gemini.provider = MagicMock()
    gemini.provider.is_available.return_value = True

    gemini.generate("hello", model="gemini-1.5-flash")
    gemini.generate_structured("hello", model="gemini-1.5-flash")

    gemini.provider.generate.assert_called_once_with("hello", model="gemini-1.5-flash")
    gemini.provider.generate_structured.assert_called_once_with(
        "hello", model="gemini-1.5-flash"
    )


def test_generate_typed_forwards_schema_and_max_retries():
    gemini = Gemini(api_key="fake-key")
    gemini.provider = MagicMock()
    gemini.provider.is_available.return_value = True
    fake_schema = object()
    gemini.provider.generate_typed.return_value = "typed result"

    result = gemini.generate_typed("hello", fake_schema, max_retries=5)

    assert result == "typed result"
    gemini.provider.generate_typed.assert_called_once_with(
        "hello", fake_schema, max_retries=5
    )


def test_generate_structured_raises_clear_error_when_unavailable(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gemini = Gemini(api_key=None)
    with pytest.raises(ProcessingError, match="Gemini provider not available"):
        gemini.generate_structured("hello")


def test_generate_typed_raises_clear_error_when_unavailable(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gemini = Gemini(api_key=None)
    with pytest.raises(ProcessingError, match="Gemini provider not available"):
        gemini.generate_typed("hello", object())


def test_generate_structured_passes_through_list_return():
    """generate_structured() must propagate a top-level JSON array unchanged."""
    gemini = Gemini(api_key="fake-key")
    gemini.provider = MagicMock()
    gemini.provider.is_available.return_value = True
    gemini.provider.generate_structured.return_value = [{"id": 1}, {"id": 2}]

    result = gemini.generate_structured("return a list")

    assert result == [{"id": 1}, {"id": 2}]
    assert isinstance(result, list)


# Not served by the Gemini API any more.
# https://ai.google.dev/gemini-api/docs/deprecations
SHUT_DOWN_GEMINI_MODELS = {
    "gemini-pro",
    "gemini-1.0-pro",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
    "gemini-2.0-flash",
}


def test_default_gemini_model_is_not_shut_down():
    from semantica.semantic_extract.providers import DEFAULT_GEMINI_MODEL

    assert DEFAULT_GEMINI_MODEL not in SHUT_DOWN_GEMINI_MODELS


def test_gemini_wrapper_and_provider_share_the_default_model():
    from semantica.semantic_extract.providers import (
        DEFAULT_GEMINI_MODEL,
        GeminiProvider,
    )

    gemini = Gemini(api_key="fake-key")

    assert gemini.model == DEFAULT_GEMINI_MODEL
    assert gemini.provider.model == DEFAULT_GEMINI_MODEL
    assert GeminiProvider(api_key="fake-key").model == DEFAULT_GEMINI_MODEL


REPO_ROOT = Path(__file__).resolve().parents[1]

# Matches `model="..."`, `model='...'` and YAML-style `model: ...`, with any
# provider route in front of the ID (gemini/, vertex_ai/, openrouter/google/, ...).
GEMINI_MODEL_EXAMPLE = re.compile(
    r"""\bmodel\s*[=:]\s*['"]?(?:[\w.-]+/)*(gemini-[\w.-]*\w)"""
)


def _is_shut_down(model: str) -> bool:
    # Covers pinned versions (-001), aliases (-latest) and variants (-exp, -lite).
    return any(
        model == retired or model.startswith(retired + "-")
        for retired in SHUT_DOWN_GEMINI_MODELS
    )


def _gemini_doc_guides() -> list[Path]:
    guides = [REPO_ROOT / "README.md"]
    for folder in ("docs", "integrations"):
        guides.extend(sorted((REPO_ROOT / folder).rglob("*.md")))
    return guides


def _check_gemini_examples(guides: list[Path]) -> None:
    models: dict[str, set[str]] = {}
    for guide in guides:
        for model in GEMINI_MODEL_EXAMPLE.findall(guide.read_text(encoding="utf-8")):
            models.setdefault(model, set()).add(str(guide))
    retired = {
        model: sorted(paths) for model, paths in models.items() if _is_shut_down(model)
    }
    assert models, "No Gemini model examples found"
    assert not retired, f"Retired Gemini model examples: {retired}"


def test_gemini_examples_do_not_use_retired_model_ids() -> None:
    _check_gemini_examples(_gemini_doc_guides())


@pytest.mark.parametrize(
    "example",
    [
        'Agent(model="gemini/gemini-2.0-flash")',
        'Agent(model="gemini-2.0-flash-001")',
        'LiteLLM(model="vertex_ai/gemini-1.5-pro-002")',
        'LiteLLM(model="gemini-1.5-pro-latest")',
        'LiteLLM(model="gemini-2.0-flash-exp")',
        'LiteLLM(model="vertex_ai_beta/gemini-2.0-flash")',
        'LiteLLM(model="openrouter/google/gemini-1.5-flash")',
        "model: gemini-2.0-flash",
    ],
)
def test_gemini_example_guard_rejects_retired_routes_and_versions(
    tmp_path: Path, example: str
) -> None:
    guide = tmp_path / "guide.md"
    guide.write_text(f'Agent(model="gemini-3.8-flash")\n{example}\n', encoding="utf-8")

    with pytest.raises(AssertionError, match="Retired Gemini model examples"):
        _check_gemini_examples([guide])


def test_gemini_example_guard_accepts_current_model(tmp_path: Path) -> None:
    guide = tmp_path / "guide.md"
    guide.write_text(
        'Agent(model="gemini-3.8-flash")\nmodel: vertex_ai/gemini-3.8-flash\n',
        encoding="utf-8",
    )

    _check_gemini_examples([guide])
