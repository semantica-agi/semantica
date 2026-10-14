"""Regression tests for what the LLM provenance wrappers actually record.

Two gaps in the wrappers let calls go untracked or tracked without their
usage/cost:

* ``generate_structured`` / ``generate_typed`` fell through ``__getattr__`` to
  the wrapped LLM, so those calls produced no provenance entry at all.
* ``generate`` read token counts and cost off the returned value, but the
  providers returned a plain ``str``, so ``prompt_tokens`` / ``completion_tokens``
  / ``total_cost`` were always ``None``.

These tests drive the wrappers with a stub LLM and a recording provenance
manager so they stay offline and assert on the recorded metadata directly.
A second group drives the providers themselves with a canned client, so a
provider that stops carrying usage/cost turns the suite red.
"""

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from semantica.llms.llms_provenance import (
    GroqLLMWithProvenance,
    LiteLLMWithProvenance,
)
from semantica.semantic_extract.providers import (
    GroqProvider,
    OpenAIProvider,
    ResponseText,
)


class _RecordingProvenanceManager:
    """Capture the kwargs of every ``track_entity`` call."""

    def __init__(self):
        self.calls = []

    def track_entity(self, **kwargs):
        self.calls.append(kwargs)


class _StubLLM:
    """Minimal stand-in for a wrapped provider class."""

    model = "stub-model"

    def __init__(self, response=None, structured=None, typed=None):
        self._response = response
        self._structured = structured
        self._typed = typed

    def generate(self, prompt, **kwargs):
        return self._response

    def generate_structured(self, prompt, **kwargs):
        return self._structured

    def generate_typed(self, prompt, schema, max_retries=3, **kwargs):
        return self._typed


def _wrapper_with(llm):
    """Build a Groq wrapper wired to *llm* and a recording provenance manager."""
    wrapper = GroqLLMWithProvenance(provenance=False)
    recorder = _RecordingProvenanceManager()
    wrapper.provenance = True
    wrapper._prov_manager = recorder
    wrapper._llm = llm
    return wrapper, recorder


class TestStructuredAndTypedAreTracked:
    """Structured/typed calls must produce a provenance entry."""

    def test_generate_structured_records_entry(self):
        wrapper, recorder = _wrapper_with(
            _StubLLM(structured={"answer": 42})
        )

        result = wrapper.generate_structured("question")

        assert result == {"answer": 42}
        assert len(recorder.calls) == 1
        assert recorder.calls[0]["metadata"]["generation_mode"] == "structured"

    def test_generate_typed_records_entry(self):
        wrapper, recorder = _wrapper_with(_StubLLM(typed="validated"))

        result = wrapper.generate_typed("question", schema=object)

        assert result == "validated"
        assert len(recorder.calls) == 1
        metadata = recorder.calls[0]["metadata"]
        assert metadata["generation_mode"] == "typed"
        assert metadata["max_retries"] == 3

    def test_calls_are_tracked_independently(self):
        wrapper, recorder = _wrapper_with(
            _StubLLM(structured={"a": 1}, typed="b")
        )

        wrapper.generate_structured("first")
        wrapper.generate_typed("second", schema=object)

        assert len(recorder.calls) == 2
        modes = [c["metadata"]["generation_mode"] for c in recorder.calls]
        assert modes == ["structured", "typed"]
        assert recorder.calls[0]["entity_id"] != recorder.calls[1]["entity_id"]

    def test_untracked_when_provenance_disabled(self):
        wrapper = GroqLLMWithProvenance(provenance=False)
        wrapper._llm = _StubLLM(structured={"a": 1})

        # No provenance manager is set, so the call must still succeed.
        assert wrapper.generate_structured("q") == {"a": 1}


class TestUsageAndCostPropagate:
    """Token counts and cost must reach the recorded metadata."""

    def test_generate_records_tokens_and_cost(self):
        response = ResponseText(
            "the answer",
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            cost=0.002,
        )
        wrapper, recorder = _wrapper_with(_StubLLM(response=response))

        result = wrapper.generate("question")

        assert result == "the answer"
        assert len(recorder.calls) == 1
        metadata = recorder.calls[0]["metadata"]
        assert metadata["prompt_tokens"] == 10
        assert metadata["completion_tokens"] == 5
        assert metadata["total_tokens"] == 15
        assert metadata["total_cost"] == 0.002

    def test_zero_completion_tokens_still_sums(self):
        response = ResponseText(
            "",
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=0),
        )
        wrapper, recorder = _wrapper_with(_StubLLM(response=response))

        wrapper.generate("question")

        metadata = recorder.calls[0]["metadata"]
        assert metadata["completion_tokens"] == 0
        assert metadata["total_tokens"] == 10

    def test_generate_without_usage_metadata_stays_none(self):
        wrapper, recorder = _wrapper_with(_StubLLM(response=ResponseText("plain")))

        wrapper.generate("question")

        metadata = recorder.calls[0]["metadata"]
        assert metadata["prompt_tokens"] is None
        assert metadata["completion_tokens"] is None
        assert metadata["total_cost"] is None


class TestResponseText:
    """``ResponseText`` must behave like ``str`` while carrying metadata."""

    def test_is_a_string(self):
        text = ResponseText("hello")
        assert isinstance(text, str)
        assert text == "hello"
        assert text.upper() == "HELLO"

    def test_defaults(self):
        text = ResponseText("hello")
        assert text.usage is None
        assert text.cost is None

    def test_carries_usage_and_cost(self):
        usage = SimpleNamespace(prompt_tokens=1, completion_tokens=2)
        text = ResponseText("hi", usage=usage, cost=0.5)
        assert text.usage is usage
        assert text.cost == 0.5


@pytest.mark.parametrize(
    "wrapper_name",
    [
        "GroqLLMWithProvenance",
        "OpenAILLMWithProvenance",
        "HuggingFaceLLMWithProvenance",
        "LiteLLMWithProvenance",
    ],
)
def test_all_wrappers_expose_structured_and_typed(wrapper_name):
    """Every wrapper must override both structured entry points."""
    import semantica.llms.llms_provenance as module

    wrapper_cls = getattr(module, wrapper_name)
    assert "generate_structured" in wrapper_cls.__dict__
    assert "generate_typed" in wrapper_cls.__dict__


@pytest.mark.parametrize(
    "wrapper_name",
    [
        "GroqLLMWithProvenance",
        "OpenAILLMWithProvenance",
        "HuggingFaceLLMWithProvenance",
        "LiteLLMWithProvenance",
    ],
)
def test_unset_llm_raises_attribute_error_not_recursion(wrapper_name):
    """A wrapper whose ``_llm`` was never set must not recurse in __getattr__."""
    import semantica.llms.llms_provenance as module

    wrapper = object.__new__(getattr(module, wrapper_name))

    with pytest.raises(AttributeError):
        wrapper.some_missing_attribute


def test_copy_of_wrapper_does_not_recurse():
    """copy.copy() probes attributes before _llm exists on the new object."""
    import copy

    wrapper = GroqLLMWithProvenance(provenance=False)
    wrapper._llm = _StubLLM(response="ok")

    clone = copy.copy(wrapper)

    assert clone.generate("q") == "ok"


class _FakeCompletions:
    """Only the ``chat.completions.create`` surface the providers use."""

    def __init__(self, response):
        self._response = response

    def create(self, **kwargs):
        return self._response


class _FakeChat:
    def __init__(self, response):
        self.completions = _FakeCompletions(response)


class _FakeClient:
    """Stand-in for an OpenAI/Groq client, backed by a canned response."""

    def __init__(self, response):
        self.chat = _FakeChat(response)


def _chat_response(content):
    # OpenAI and Groq responses report usage but no cost.
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


class TestProvidersCarryUsageAndCost:
    """The fix lives in the providers, so drive them rather than a stub."""

    def test_openai_provider_returns_response_text(self):
        provider = OpenAIProvider(api_key="test-key")
        provider.client = _FakeClient(_chat_response("hello"))

        result = provider.generate("question")

        assert isinstance(result, ResponseText)
        assert result == "hello"
        assert result.usage is not None
        assert result.usage.prompt_tokens == 10

    def test_groq_provider_returns_response_text(self):
        provider = GroqProvider(api_key="test-key")
        provider.client = _FakeClient(_chat_response("hi"))

        result = provider.generate("question")

        assert isinstance(result, ResponseText)
        assert result == "hi"
        assert result.usage is not None

    def test_wrapper_records_usage_from_real_provider(self):
        provider = GroqProvider(api_key="test-key")
        provider.client = _FakeClient(_chat_response("hello"))
        wrapper, recorder = _wrapper_with(provider)

        result = wrapper.generate("question")

        assert result == "hello"
        metadata = recorder.calls[0]["metadata"]
        assert metadata["prompt_tokens"] == 10
        assert metadata["completion_tokens"] == 5
        assert metadata["total_tokens"] == 15

    def test_litellm_returns_response_text_with_cost(self, monkeypatch):
        import semantica.llms.litellm as litellm_module

        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))],
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=4),
            _hidden_params={"response_cost": 0.007},
        )
        monkeypatch.setattr(litellm_module, "LITELLM_AVAILABLE", True)
        monkeypatch.setattr(litellm_module, "completion", lambda **kwargs: response)

        llm = litellm_module.LiteLLM(model="openai/gpt-4o")
        result = llm.generate("question")

        assert isinstance(result, ResponseText)
        assert result == "answer"
        assert result.usage is not None
        assert result.cost == 0.007
        # The rest of _hidden_params (api_base, response headers) is not kept.
        assert not hasattr(result, "_hidden_params")

    def test_litellm_missing_response_cost_is_none(self, monkeypatch):
        import semantica.llms.litellm as litellm_module

        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))],
            usage=None,
            _hidden_params={"api_base": "https://example.invalid"},
        )
        monkeypatch.setattr(litellm_module, "LITELLM_AVAILABLE", True)
        monkeypatch.setattr(litellm_module, "completion", lambda **kwargs: response)

        result = litellm_module.LiteLLM(model="openai/gpt-4o").generate("question")

        assert result == "answer"
        assert result.cost is None


class TestNoneReplyStaysNone:
    """A reply with no text (tool call, refusal, content filter) stays ``None``."""

    @pytest.mark.parametrize("provider_cls", [OpenAIProvider, GroqProvider])
    def test_none_reply_stays_none(self, provider_cls):
        provider = provider_cls(api_key="test-key")
        provider.client = _FakeClient(_chat_response(None))

        assert provider.generate("question") is None

    def test_litellm_none_reply_stays_none(self, monkeypatch):
        import semantica.llms.litellm as litellm_module

        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))],
            usage=None,
            _hidden_params={},
        )
        monkeypatch.setattr(litellm_module, "LITELLM_AVAILABLE", True)
        monkeypatch.setattr(litellm_module, "completion", lambda **kwargs: response)

        llm = litellm_module.LiteLLM(model="openai/gpt-4o")

        assert llm.generate("question") is None

    def test_wrapper_records_none_reply_without_stringifying(self):
        wrapper, recorder = _wrapper_with(_StubLLM(response=None))

        assert wrapper.generate("question") is None
        metadata = recorder.calls[0]["metadata"]
        assert metadata["response_preview"] is None
        assert metadata["prompt_tokens"] is None


class _Answer(BaseModel):
    text: str
    confidence: float


class TestStructuredAndTypedPreviews:
    """Structured/typed previews must serialize the whole result."""

    def test_typed_model_with_text_field_records_full_json(self):
        answer = _Answer(text="short", confidence=0.9)
        wrapper, recorder = _wrapper_with(_StubLLM(typed=answer))

        assert wrapper.generate_typed("question", schema=_Answer) is answer
        preview = recorder.calls[0]["metadata"]["response_preview"]
        assert preview == answer.model_dump_json()

    def test_structured_dict_records_json(self):
        wrapper, recorder = _wrapper_with(_StubLLM(structured={"answer": 42}))

        wrapper.generate_structured("question")

        preview = recorder.calls[0]["metadata"]["response_preview"]
        assert preview == '{"answer": 42}'

    def test_long_structured_preview_is_truncated(self):
        wrapper, recorder = _wrapper_with(
            _StubLLM(structured={"items": list(range(500))})
        )

        wrapper.generate_structured("question")

        assert len(recorder.calls[0]["metadata"]["response_preview"]) == 200

    def test_none_result_records_none(self):
        wrapper, recorder = _wrapper_with(_StubLLM(structured=None))

        assert wrapper.generate_structured("question") is None
        assert recorder.calls[0]["metadata"]["response_preview"] is None


def test_litellm_wrapper_reads_cost_from_response_text(monkeypatch):
    monkeypatch.setattr("semantica.llms.litellm.LITELLM_AVAILABLE", True)
    wrapper = LiteLLMWithProvenance(provenance=False, model="openai/gpt-4o")
    recorder = _RecordingProvenanceManager()
    wrapper.provenance = True
    wrapper._prov_manager = recorder
    wrapper._llm = _StubLLM(
        response=ResponseText(
            "answer",
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=4),
            cost=0.007,
        )
    )

    wrapper.generate("question")

    assert recorder.calls[0]["metadata"]["total_cost"] == 0.007
