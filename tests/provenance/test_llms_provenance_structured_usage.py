"""Structured and typed usage must survive parsing and validation."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import BaseModel

import semantica.llms.litellm as litellm_module
import semantica.semantic_extract.providers as providers
from semantica.llms.llms_provenance import (
    GroqLLMWithProvenance,
    LiteLLMWithProvenance,
    OpenAILLMWithProvenance,
)


# "usage" and "cost" fields check that payload keys are never read as token counts.
class Answer(BaseModel):
    answer: int
    usage: str
    cost: int


PAYLOAD = {"answer": 42, "usage": "payload", "cost": 7}
TOKENS = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


@pytest.fixture(params=["openai", "groq", "litellm", "litellm_dict"])
def backend(request, monkeypatch):
    name = request.param
    completion = Mock()
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=completion))
    )
    if name.startswith("litellm"):
        monkeypatch.setattr(litellm_module, "LITELLM_AVAILABLE", True)
        monkeypatch.setattr(litellm_module, "completion", completion)
        wrapper_type = LiteLLMWithProvenance
    else:
        provider, wrapper_type = {
            "openai": (providers.OpenAIProvider, OpenAILLMWithProvenance),
            "groq": (providers.GroqProvider, GroqLLMWithProvenance),
        }[name]
        monkeypatch.setattr(provider, "_init_client", lambda self: None)
    wrapper = wrapper_type(provenance=False, model="test", api_key="test-key")
    if not name.startswith("litellm"):
        wrapper._llm.provider.client = client
    wrapper.provenance = True
    wrapper._prov_manager = SimpleNamespace(track_entity=Mock())
    return name, wrapper, completion, client


def _reply(name, payload, has_usage, prose=False, typed=False):
    content = json.dumps(payload)
    if prose:
        content = f"Result: {content}\nDone."
    reply = {
        "id": "test",
        "created": 0,
        "model": "test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
    }
    if has_usage:
        reply["usage"] = TOKENS.copy()
    if name == "litellm_dict":
        return reply
    if typed:
        reply["choices"][0]["message"]["tool_calls"] = [
            {
                "id": "call_test",
                "type": "function",
                "function": {"name": "Answer", "arguments": content},
            }
        ]
        reply = pytest.importorskip("openai.types.chat").ChatCompletion.model_validate(
            reply
        )
    else:
        reply = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(**TOKENS) if has_usage else None,
        )
    if name == "litellm" and has_usage:
        object.__setattr__(reply, "_hidden_params", {"response_cost": 0.002})
    return reply


def _assert_metadata(backend, has_usage):
    name, wrapper, _, _ = backend
    calls = wrapper._prov_manager.track_entity.call_args_list
    assert len(calls) == 1
    metadata = calls[0].kwargs["metadata"]
    if has_usage:
        assert {key: metadata[key] for key in TOKENS} == TOKENS
    else:
        assert not TOKENS.keys() & metadata.keys()
    if name == "litellm" and has_usage:
        assert metadata["total_cost"] == 0.002
    else:
        assert "total_cost" not in metadata


@pytest.mark.parametrize("has_usage", [True, False])
@pytest.mark.parametrize("shape", ["dict", "list", "prose"])
def test_structured_usage(backend, has_usage, shape):
    name, wrapper, completion, _ = backend
    payload = [PAYLOAD] if shape == "list" else PAYLOAD
    completion.return_value = _reply(name, payload, has_usage, shape == "prose")

    result = wrapper.generate_structured("Return JSON")

    assert isinstance(result, type(payload))
    assert result == payload
    assert json.dumps(result) == json.dumps(payload)
    _assert_metadata(backend, has_usage)


@pytest.mark.parametrize("has_usage", [True, False])
@pytest.mark.parametrize("path", ["structured", "text", "retry", "instructor"])
def test_typed_usage(backend, monkeypatch, has_usage, path):
    name, wrapper, completion, client = backend
    if name.startswith("litellm") and path == "text":
        pytest.skip("LiteLLM's manual fallback uses structured generation only")
    if name == "litellm_dict" and path == "instructor":
        pytest.skip("Instructor requires an SDK response object")
    if path == "instructor":
        instructor = pytest.importorskip("instructor")
        client = pytest.importorskip("openai").OpenAI(api_key="test-key")
        monkeypatch.setattr(client.chat.completions, "create", completion)
        monkeypatch.setattr(
            instructor,
            "from_provider",
            lambda **kwargs: instructor.from_openai(client, mode=instructor.Mode.JSON),
        )
    else:
        monkeypatch.setattr(providers, "instructor", None)
        monkeypatch.setattr(litellm_module, "safe_import", lambda _: (None, False))
    reply = _reply(name, PAYLOAD, has_usage, typed=path == "instructor")
    if path == "text":
        completion.side_effect = [ValueError("JSON mode unsupported"), reply]
    elif path == "retry":
        completion.side_effect = [_reply(name, {}, True), reply]
        monkeypatch.setattr("time.sleep", lambda _: None)
    else:
        completion.return_value = reply

    result = wrapper.generate_typed("Return JSON", Answer, max_retries=2)

    assert isinstance(result, Answer)
    assert result.model_dump() == PAYLOAD
    assert json.loads(result.model_dump_json()) == PAYLOAD
    assert completion.call_count == (2 if path in ("text", "retry") else 1)
    _assert_metadata(backend, has_usage)
