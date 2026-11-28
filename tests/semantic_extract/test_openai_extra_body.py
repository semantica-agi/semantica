"""Extra request fields for OpenAI-compatible endpoints.

``extra_body`` is forwarded on plain, structured and typed generation.  The
caller's dictionary is copied rather than modified, and a ``stream`` key in it
cannot turn the request into a streaming one.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from semantica.semantic_extract import methods, providers
from semantica.semantic_extract.providers import OpenAIProvider
from semantica.semantic_extract.schemas import EntitiesResponse


class _Point(BaseModel):
    x: int
    y: int


def _provider(content: str = "result", base_url=None, **kwargs) -> OpenAIProvider:
    with patch.object(OpenAIProvider, "_init_client", return_value=None):
        provider = OpenAIProvider(api_key="fake", base_url=base_url, **kwargs)
    client = MagicMock()
    client.chat.completions.create.return_value.choices[0].message.content = content
    provider.client = client
    return provider


def _call_kwargs(provider: OpenAIProvider):
    return provider.client.chat.completions.create.call_args.kwargs


def test_generate_forwards_extra_body():
    provider = _provider()
    body = {"custom_option": {"enabled": True}}

    provider.generate("prompt", extra_body=body)

    call_kwargs = _call_kwargs(provider)
    assert call_kwargs["extra_body"] == {"custom_option": {"enabled": True}}
    assert call_kwargs["stream"] is False


@pytest.mark.parametrize("base_url", [None, "https://gateway.example/v1"])
def test_generate_structured_forwards_extra_body(base_url):
    provider = _provider('{"a": 1}', base_url=base_url)

    assert provider.generate_structured("prompt", extra_body={"custom": 1}) == {"a": 1}

    call_kwargs = _call_kwargs(provider)
    assert call_kwargs["extra_body"] == {"custom": 1}
    assert call_kwargs["stream"] is False


def test_generate_typed_forwards_extra_body(monkeypatch):
    provider = _provider(base_url="https://gateway.example/v1")
    typed_client = MagicMock()
    typed_client.chat.completions.create.return_value = _Point(x=1, y=2)
    fake_instructor = MagicMock()
    fake_instructor.from_openai.return_value = typed_client
    monkeypatch.setattr(providers, "instructor", fake_instructor)

    assert provider.generate_typed(
        "prompt", _Point, extra_body={"custom": 1}
    ) == _Point(x=1, y=2)

    call_kwargs = typed_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["extra_body"] == {"custom": 1}
    assert call_kwargs["stream"] is False


def test_provider_level_extra_body_is_used():
    provider = _provider(extra_body={"team": "alpha"})

    provider.generate("prompt")

    assert _call_kwargs(provider)["extra_body"] == {"team": "alpha"}


def test_per_call_extra_body_overrides_provider_level():
    provider = _provider(extra_body={"team": "alpha"})

    provider.generate("prompt", extra_body={"team": "beta"})

    assert _call_kwargs(provider)["extra_body"] == {"team": "beta"}


def test_caller_dictionary_is_not_modified():
    provider = _provider()
    body = {"custom": {"nested": [1]}, "stream": True}

    provider.generate("prompt", extra_body=body)

    assert body == {"custom": {"nested": [1]}, "stream": True}
    call_kwargs = _call_kwargs(provider)
    assert call_kwargs["extra_body"] == {"custom": {"nested": [1]}}
    assert call_kwargs["stream"] is False


def test_non_dict_extra_body_is_rejected():
    provider = _provider()

    with pytest.raises(ValueError, match="extra_body"):
        provider.generate("prompt", extra_body="not-a-dict")


def test_non_dict_provider_level_extra_body_is_rejected():
    with patch.object(OpenAIProvider, "_init_client", return_value=None):
        with pytest.raises(ValueError, match="extra_body"):
            OpenAIProvider(api_key="fake", extra_body=[("custom", 1)])


def test_generation_cache_params_include_extra_body():
    params = methods._generation_cache_params(
        {"extra_body": {"custom": 1}, "api_key": "secret"}
    )

    assert params == {"extra_body": {"custom": 1}}


def test_cache_keys_differ_for_different_extra_body():
    first = methods._result_cache._generate_key("same text", extra_body={"a": 1})
    second = methods._result_cache._generate_key("same text", extra_body={"a": 2})

    assert first != second


def test_extra_body_reaches_the_serialized_request():
    openai = pytest.importorskip("openai")
    httpx = pytest.importorskip("httpx")
    import json

    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 0,
                "model": "test-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
        )

    client = openai.OpenAI(
        api_key="fake",
        base_url="https://gateway.example/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with patch.object(OpenAIProvider, "_init_client", return_value=None):
        provider = OpenAIProvider(api_key="fake", base_url="https://gateway.example/v1")
    provider.client = client

    provider.generate(
        "prompt", extra_body={"custom_option": {"enabled": True}, "stream": True}
    )

    assert captured["body"]["custom_option"] == {"enabled": True}
    assert captured["body"]["stream"] is False


def test_extractor_forwards_extra_body_to_the_provider(monkeypatch):
    fake_provider = MagicMock()
    fake_provider.is_available.return_value = True
    fake_provider.generate_typed.return_value = EntitiesResponse(entities=[])
    captured = {}

    def fake_create_provider(name, model=None, **kwargs):
        captured["kwargs"] = kwargs
        return fake_provider

    monkeypatch.setattr(methods, "create_provider", fake_create_provider)
    methods._result_cache.clear("entities")

    methods.extract_entities_llm(
        "A unique sentence for the extra_body forwarding test.",
        provider="openai",
        model="test-model",
        extra_body={"custom_option": {"enabled": True}},
    )

    assert captured["kwargs"]["extra_body"] == {"custom_option": {"enabled": True}}
    call_kwargs = fake_provider.generate_typed.call_args.kwargs
    assert call_kwargs["extra_body"] == {"custom_option": {"enabled": True}}
