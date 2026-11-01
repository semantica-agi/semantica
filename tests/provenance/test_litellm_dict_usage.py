"""LiteLLM dict replies must retain token counts through the public wrapper."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import semantica.llms.litellm as litellm_module
from semantica.llms.llms_provenance import LiteLLMWithProvenance


@pytest.mark.parametrize("shape", ["choices", "content"])
@pytest.mark.parametrize(
    "usage, prompt_tokens, completion_tokens",
    [
        ({"prompt_tokens": 3, "completion_tokens": 4}, 3, 4),
        ({"prompt_tokens": 3, "completion_tokens": 0}, 3, 0),
        ({"prompt_tokens": 3}, 3, None),
        ({}, None, None),
        (None, None, None),
        (SimpleNamespace(prompt_tokens=3, completion_tokens=4), 3, 4),
    ],
)
def test_generate_records_dict_response_usage(
    monkeypatch, shape, usage, prompt_tokens, completion_tokens
):
    response = {"usage": usage}
    if shape == "choices":
        response["choices"] = [{"message": {"content": "answer"}}]
    else:
        response["content"] = "answer"
    completion = Mock(return_value=response)
    monkeypatch.setattr(litellm_module, "LITELLM_AVAILABLE", True)
    monkeypatch.setattr(litellm_module, "completion", completion)
    wrapper = LiteLLMWithProvenance(
        provenance=True, model="openai/gpt-4o-mini", api_key="test-key"
    )

    result = wrapper.generate("question")

    assert isinstance(result, str)
    assert result == "answer"
    completion.assert_called_once_with(
        model="openai/gpt-4o-mini",
        messages=[{"role": "user", "content": "question"}],
        api_key="test-key",
    )
    entries = wrapper._prov_manager.audit_log(format="json")
    assert len(entries) == 1
    metadata = entries[0]["metadata"]
    assert metadata["response_preview"] == "answer"
    assert metadata["prompt_tokens"] == prompt_tokens
    assert metadata["completion_tokens"] == completion_tokens
