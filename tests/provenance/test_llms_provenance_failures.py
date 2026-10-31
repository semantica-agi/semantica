"""Failed generations must leave one entry and preserve the raised exception."""

from datetime import datetime
from unittest.mock import Mock

import pytest
from pydantic import BaseModel

import semantica.llms.llms_provenance as wrappers
from semantica.utils.exceptions import ProcessingError


class _Answer(BaseModel):
    answer: str


# The generate() options each wrapper records on a successful call, which a
# failed call must record too.
WRAPPERS = [
    (
        "GroqLLMWithProvenance",
        "semantica.llms.groq.Groq",
        {"temperature": 0.2, "max_tokens": 7, "top_p": 0.9},
    ),
    (
        "OpenAILLMWithProvenance",
        "semantica.llms.openai.OpenAI",
        {"temperature": 0.2, "max_tokens": 7},
    ),
    (
        "HuggingFaceLLMWithProvenance",
        "semantica.llms.huggingface.HuggingFaceLLM",
        {"max_length": 64, "temperature": 0.2},
    ),
    (
        "LiteLLMWithProvenance",
        "semantica.llms.litellm.LiteLLM",
        {"provider": "openai"},
    ),
]
METHODS = ["generate", "generate_structured", "generate_typed"]


@pytest.mark.parametrize("wrapper_name, target, sampling", WRAPPERS)
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("enabled", [True, False])
def test_failed_call_is_tracked_and_reraised(
    monkeypatch, wrapper_name, target, sampling, method, enabled
):
    llm = Mock(model="test-model")
    error = ValueError("upstream error details")
    invoke = getattr(llm, method)
    invoke.side_effect = error
    monkeypatch.setattr(target, Mock(return_value=llm))
    wrapper = getattr(wrappers, wrapper_name)(
        provenance=enabled, agent_id="test-agent", is_automated=False
    )
    options = {
        "generate": sampling,
        "generate_structured": {},
        "generate_typed": {"schema": _Answer, "max_retries": 2},
    }[method]

    with pytest.raises(ValueError) as caught:
        getattr(wrapper, method)("question", **options)

    assert caught.value is error
    assert invoke.call_count == 1
    if not enabled:
        assert wrapper._prov_manager is None
        return

    entries = wrapper._prov_manager.audit_log(format="json")
    assert len(entries) == 1
    entry = entries[0]
    assert entry["entity_type"] == "llm_generation"
    assert entry["agent_id"] == "test-agent"
    assert entry["is_automated"] is False
    started = datetime.fromisoformat(entry["activity_started_at_time"])
    ended = datetime.fromisoformat(entry["activity_ended_at_time"])
    assert ended >= started
    metadata = entry["metadata"]
    assert metadata["error"] == "ValueError"
    assert "upstream error details" not in str(entry)
    assert metadata["model"] == "test-model"
    assert metadata["prompt_preview"] == "question"
    assert metadata["response_preview"] is None
    assert metadata["latency_seconds"] >= 0
    if method == "generate":
        for name, value in sampling.items():
            assert metadata[name] == value
    else:
        assert metadata["generation_mode"] == method.removeprefix("generate_")
    if method == "generate_typed":
        assert metadata["max_retries"] == 2
    assert wrapper._prov_manager.verify_chain()["valid"] is True


@pytest.mark.parametrize("wrapper_name, target, sampling", WRAPPERS)
@pytest.mark.parametrize("method", METHODS)
def test_audit_write_failure_does_not_replace_the_llm_error(
    monkeypatch, wrapper_name, target, sampling, method
):
    llm = Mock(model="test-model")
    error = ValueError("upstream error details")
    getattr(llm, method).side_effect = error
    monkeypatch.setattr(target, Mock(return_value=llm))
    wrapper = getattr(wrappers, wrapper_name)(provenance=True)
    wrapper._prov_manager.track_entity = Mock(side_effect=OSError("disk full"))
    options = {
        "generate": sampling,
        "generate_structured": {},
        "generate_typed": {"schema": _Answer, "max_retries": 2},
    }[method]

    with pytest.raises(ValueError) as caught:
        getattr(wrapper, method)("question", **options)

    assert caught.value is error
    assert wrapper._prov_manager.track_entity.call_count == 1


@pytest.mark.parametrize("method", METHODS)
def test_litellm_client_failure_reaches_audit_log(monkeypatch, method):
    import semantica.llms.litellm as litellm_module

    completion = Mock(side_effect=TimeoutError("request timed out"))
    instructor = Mock()
    instructor.from_litellm.return_value.chat.completions.create = completion
    monkeypatch.setattr(litellm_module, "LITELLM_AVAILABLE", True)
    monkeypatch.setattr(litellm_module, "completion", completion)
    monkeypatch.setattr(litellm_module, "safe_import", lambda name: (instructor, True))
    wrapper = wrappers.LiteLLMWithProvenance(
        provenance=True, model="openai/gpt-4o-mini", api_key="test-key"
    )
    options = (
        {"schema": _Answer, "max_retries": 1} if method == "generate_typed" else {}
    )

    with pytest.raises(ProcessingError):
        getattr(wrapper, method)("question", **options)

    assert completion.call_count == 1
    entries = wrapper._prov_manager.audit_log(format="json")
    assert len(entries) == 1
    assert entries[0]["metadata"]["error"] == "ProcessingError"
