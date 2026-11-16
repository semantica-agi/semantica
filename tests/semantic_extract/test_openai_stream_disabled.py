"""OpenAI requests are always sent non-streaming.

The response parsers read ``response.choices[0]`` off a complete response, so
the provider sends ``stream=False`` explicitly rather than relying on the
endpoint's default (a custom gateway may stream when ``stream`` is omitted),
and a caller cannot override it.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from semantica.semantic_extract import providers
from semantica.semantic_extract.providers import OpenAIProvider


class _Point(BaseModel):
    x: int
    y: int


def _provider(content: str, base_url=None) -> OpenAIProvider:
    with patch.object(OpenAIProvider, "_init_client", return_value=None):
        provider = OpenAIProvider(api_key="fake", base_url=base_url)
    client = MagicMock()
    client.chat.completions.create.return_value.choices[0].message.content = content
    provider.client = client
    return provider


@pytest.mark.parametrize("caller_stream", [None, True])
def test_generate_sends_stream_false(caller_stream):
    provider = _provider("result")
    kwargs = {} if caller_stream is None else {"stream": caller_stream}

    assert provider.generate("prompt", **kwargs) == "result"

    call_kwargs = provider.client.chat.completions.create.call_args.kwargs
    assert call_kwargs["stream"] is False


@pytest.mark.parametrize("base_url", [None, "https://gateway.example/v1"])
@pytest.mark.parametrize("caller_stream", [None, True])
def test_generate_structured_sends_stream_false(caller_stream, base_url):
    provider = _provider('{"a": 1}', base_url=base_url)
    kwargs = {} if caller_stream is None else {"stream": caller_stream}

    assert provider.generate_structured("prompt", **kwargs) == {"a": 1}

    call_kwargs = provider.client.chat.completions.create.call_args.kwargs
    assert call_kwargs["stream"] is False


@pytest.mark.parametrize("caller_stream", [None, True])
def test_generate_typed_sends_stream_false(monkeypatch, caller_stream):
    provider = _provider("unused", base_url="https://gateway.example/v1")
    typed_client = MagicMock()
    typed_client.chat.completions.create.return_value = _Point(x=1, y=2)
    fake_instructor = MagicMock()
    fake_instructor.from_openai.return_value = typed_client
    monkeypatch.setattr(providers, "instructor", fake_instructor)
    kwargs = {} if caller_stream is None else {"stream": caller_stream}

    assert provider.generate_typed("prompt", _Point, **kwargs) == _Point(x=1, y=2)

    call_kwargs = typed_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["stream"] is False
