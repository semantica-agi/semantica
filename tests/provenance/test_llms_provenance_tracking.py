"""Regression tests for what the LLM provenance wrappers actually record.

Four gaps in the wrappers let calls go untracked, tracked without their
usage/cost, tracked under the wrong model, or not tracked at all:

* ``generate_structured`` / ``generate_typed`` fell through ``__getattr__`` to
  the wrapped LLM, so those calls produced no provenance entry at all.
* ``generate`` read token counts and cost off the returned value, but the
  providers returned a plain ``str``, so ``prompt_tokens`` / ``completion_tokens``
  / ``total_cost`` were always ``None``.
* Every entry named the model the wrapper was constructed with, so a call that
  passed its own ``model=`` was recorded under a model it never used (#2051).
* A per-call ``model=`` that is not a string reached the metadata verbatim, so
  the storage layer could not serialize it: the write was rolled back and the
  entry was never stored (#2051).

These tests drive the wrappers with a stub LLM and a recording provenance
manager so they stay offline and assert on the recorded metadata directly.
One test drives a real ``ProvenanceManager`` over a sqlite file in ``tmp_path``
to prove the entry is really written, still offline. A second group drives the
providers themselves with a canned client, so a provider that stops carrying
usage/cost turns the suite red.
"""

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from semantica.llms.llms_provenance import (
    GroqLLMWithProvenance,
    HuggingFaceLLMWithProvenance,
    LiteLLMWithProvenance,
    OpenAILLMWithProvenance,
)
from semantica.provenance import ProvenanceManager
from semantica.semantic_extract.providers import (
    GroqProvider,
    OpenAIProvider,
    ResponseText,
)

_WRAPPER_CLASSES = {
    "GroqLLMWithProvenance": GroqLLMWithProvenance,
    "OpenAILLMWithProvenance": OpenAILLMWithProvenance,
    "HuggingFaceLLMWithProvenance": HuggingFaceLLMWithProvenance,
    "LiteLLMWithProvenance": LiteLLMWithProvenance,
}
_WRAPPER_NAMES = list(_WRAPPER_CLASSES)

# The HuggingFace provider loads its model in its constructor and its generate
# reads only the generation options, so a per-call ``model`` is ignored and the
# constructor model is the one the call actually used.
_HONOURS_PER_CALL_MODEL = {
    "GroqLLMWithProvenance": True,
    "OpenAILLMWithProvenance": True,
    "HuggingFaceLLMWithProvenance": False,
    "LiteLLMWithProvenance": True,
}


def _expected_model(wrapper_name, per_call="per-call-model"):
    """The model an entry should name for *wrapper_name*."""
    return per_call if _HONOURS_PER_CALL_MODEL[wrapper_name] else "constructor-model"


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


class _StubProvider:
    """Stand-in for the provider class a wrapper constructs."""

    def __init__(self, *args, **kwargs):
        pass


def _wrapper_for(wrapper_name, monkeypatch, constructor_model="constructor-model"):
    """Build *wrapper_name* around a stub, with a known constructor model.

    Each wrapper imports the class it wraps lazily, inside ``__init__``, so
    the optional providers are stubbed here: the real HuggingFace provider
    loads a transformer model while constructing, and LiteLLM refuses to
    construct without the optional ``litellm`` package.
    """
    if wrapper_name == "HuggingFaceLLMWithProvenance":
        monkeypatch.setattr(
            "semantica.llms.huggingface.HuggingFaceLLMProvider", _StubProvider
        )
    if wrapper_name == "LiteLLMWithProvenance":
        monkeypatch.setattr("semantica.llms.litellm.LITELLM_AVAILABLE", True)

    wrapper = _WRAPPER_CLASSES[wrapper_name](provenance=False, model=constructor_model)
    recorder = _RecordingProvenanceManager()
    wrapper.provenance = True
    wrapper._prov_manager = recorder
    wrapper._llm = _StubLLM(
        response="answer", structured={"answer": 42}, typed="validated"
    )
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


class TestRecordedModelFollowsTheCall:
    """A recorded entry must name the model the call actually used (#2051)."""

    @pytest.mark.parametrize("wrapper_name", _WRAPPER_NAMES)
    def test_per_call_model_is_recorded(self, wrapper_name, monkeypatch):
        """The entry names the model the call used, not the constructor's."""
        wrapper, recorder = _wrapper_for(wrapper_name, monkeypatch)

        wrapper.generate("question", model="per-call-model")

        assert recorder.calls[0]["metadata"]["model"] == _expected_model(wrapper_name)

    @pytest.mark.parametrize("wrapper_name", _WRAPPER_NAMES)
    def test_call_without_a_model_records_the_constructor_model(
        self, wrapper_name, monkeypatch
    ):
        """A call that names no model keeps the constructor's model."""
        wrapper, recorder = _wrapper_for(wrapper_name, monkeypatch)

        wrapper.generate("question")

        assert recorder.calls[0]["metadata"]["model"] == "constructor-model"

    @pytest.mark.parametrize("wrapper_name", _WRAPPER_NAMES)
    def test_structured_path_records_the_per_call_model(
        self, wrapper_name, monkeypatch
    ):
        """The structured path reaches the recorder and names the same model."""
        wrapper, recorder = _wrapper_for(wrapper_name, monkeypatch)

        wrapper.generate_structured("question", model="per-call-model")

        assert recorder.calls[0]["metadata"]["model"] == _expected_model(wrapper_name)

    @pytest.mark.parametrize("wrapper_name", _WRAPPER_NAMES)
    def test_typed_path_records_the_per_call_model(self, wrapper_name, monkeypatch):
        """The typed path reaches the recorder and names the same model."""
        wrapper, recorder = _wrapper_for(wrapper_name, monkeypatch)

        wrapper.generate_typed("question", schema=object, model="per-call-model")

        assert recorder.calls[0]["metadata"]["model"] == _expected_model(wrapper_name)

    def test_huggingface_records_the_model_its_provider_loaded(self, monkeypatch):
        """HF loads its model at construction, so a per-call value never runs."""
        wrapper, recorder = _wrapper_for("HuggingFaceLLMWithProvenance", monkeypatch)

        wrapper.generate("question", model="per-call-model")

        assert recorder.calls[0]["metadata"]["model"] == "constructor-model"

    @pytest.mark.parametrize("wrapper_name", _WRAPPER_NAMES)
    def test_none_model_falls_back_to_the_constructor_model(
        self, wrapper_name, monkeypatch
    ):
        """A per-call ``model=None`` names no model, so the constructor's is kept."""
        wrapper, recorder = _wrapper_for(wrapper_name, monkeypatch)

        wrapper.generate("question", model=None)

        assert recorder.calls[0]["metadata"]["model"] == "constructor-model"

    @pytest.mark.parametrize("wrapper_name", _WRAPPER_NAMES)
    def test_empty_model_falls_back_to_the_constructor_model(
        self, wrapper_name, monkeypatch
    ):
        """An empty model name is not a model, so the constructor's is recorded."""
        wrapper, recorder = _wrapper_for(wrapper_name, monkeypatch)

        wrapper.generate("question", model="")

        assert recorder.calls[0]["metadata"]["model"] == "constructor-model"

    def test_only_the_model_field_changes(self, monkeypatch):
        """No other recorded field may move when a per-call model is used."""
        wrapper, recorder = _wrapper_for("GroqLLMWithProvenance", monkeypatch)

        wrapper.generate("question")
        wrapper.generate("question", model="per-call-model")

        first, second = (call["metadata"] for call in recorder.calls)
        assert first["model"] == "constructor-model"
        assert second["model"] == "per-call-model"
        # The model is the one field that must differ; the latency moves on
        # its own between any two calls.
        ignored = {"model", "latency_seconds"}
        assert {k: v for k, v in first.items() if k not in ignored} == {
            k: v for k, v in second.items() if k not in ignored
        }


class TestTheRecorderResolvesTheModel:
    """The shared recorder, not the call sites, decides what is recorded."""

    def test_the_recorder_records_the_model_it_is_handed(self, monkeypatch):
        """A direct recorder call records the model it was given."""
        wrapper, recorder = _wrapper_for("GroqLLMWithProvenance", monkeypatch)

        wrapper._track_llm_call(
            call_id="c1", prompt="p", response="r", model="direct-model"
        )

        assert recorder.calls[0]["metadata"]["model"] == "direct-model"

    @pytest.mark.parametrize(
        "model",
        [None, "", "   "],
        ids=["none", "empty", "whitespace"],
    )
    def test_the_recorder_falls_back_for_a_value_that_names_no_model(
        self, model, monkeypatch
    ):
        """The recorder itself falls back; the call sites do not decide."""
        wrapper, recorder = _wrapper_for("GroqLLMWithProvenance", monkeypatch)

        wrapper._track_llm_call(call_id="c2", prompt="p", response="r", model=model)

        assert recorder.calls[0]["metadata"]["model"] == "constructor-model"

    def test_the_recorder_falls_back_for_a_value_that_is_not_a_string(
        self, monkeypatch
    ):
        """A model that is not a string never reaches the recorded metadata."""
        wrapper, recorder = _wrapper_for("GroqLLMWithProvenance", monkeypatch)

        wrapper._track_llm_call(call_id="c3", prompt="p", response="r", model=object())

        assert recorder.calls[0]["metadata"]["model"] == "constructor-model"


class TestAModelThatNamesNoModelFallsBack:
    """A per-call model that names no model never becomes the recorded one."""

    @pytest.mark.parametrize(
        "model",
        [None, "", "   ", 0, False, object()],
        ids=["none", "empty", "whitespace", "zero", "false", "object"],
    )
    @pytest.mark.parametrize("wrapper_name", _WRAPPER_NAMES)
    def test_a_value_that_names_no_model_falls_back(
        self, wrapper_name, model, monkeypatch
    ):
        """Every value that names no model records the constructor's model."""
        wrapper, recorder = _wrapper_for(wrapper_name, monkeypatch)

        wrapper.generate("question", model=model)

        recorded = recorder.calls[0]["metadata"]["model"]
        assert recorded == "constructor-model"
        assert isinstance(recorded, str)

    def test_a_non_string_model_never_reaches_the_metadata(self, monkeypatch):
        """The raw value is dropped, so nothing unserializable is recorded."""
        wrapper, recorder = _wrapper_for("GroqLLMWithProvenance", monkeypatch)
        unserializable = object()

        wrapper.generate("question", model=unserializable)

        metadata = recorder.calls[0]["metadata"]
        assert metadata["model"] == "constructor-model"
        assert unserializable not in metadata.values()

    def test_a_non_serializable_model_still_writes_the_entry(self, tmp_path):
        """The entry survives a model the storage layer cannot serialize."""
        wrapper = GroqLLMWithProvenance(provenance=False, model="constructor-model")
        manager = ProvenanceManager(storage_path=str(tmp_path / "provenance.db"))
        wrapper.provenance = True
        wrapper._prov_manager = manager
        wrapper._llm = _StubLLM(response="answer")

        wrapper.generate("question", model=object())

        stored = manager.storage.retrieve_all(entity_type="llm_generation")
        assert len(stored) == 1
        assert stored[0].metadata["model"] == "constructor-model"


class _RaisingLLM(_StubLLM):
    """A stub whose generation entry points raise, to drive the failure path."""

    def generate(self, prompt, **kwargs):
        raise RuntimeError("provider failed")


class TestFailedCallsRecordTheModelTheyWereGiven:
    """A failed call names the model it asked for, not the constructor's."""

    @pytest.mark.parametrize("wrapper_name", _WRAPPER_NAMES)
    def test_failed_generate_records_the_per_call_model(
        self, wrapper_name, monkeypatch
    ):
        wrapper, recorder = _wrapper_for(wrapper_name, monkeypatch)
        wrapper._llm = _RaisingLLM()

        with pytest.raises(RuntimeError):
            wrapper.generate("question", model="per-call-model")

        assert recorder.calls, "no entry was recorded for the failed call"
        assert recorder.calls[0]["metadata"]["model"] == _expected_model(wrapper_name)

    @pytest.mark.parametrize("wrapper_name", _WRAPPER_NAMES)
    def test_failed_generate_without_a_model_keeps_the_constructor_model(
        self, wrapper_name, monkeypatch
    ):
        wrapper, recorder = _wrapper_for(wrapper_name, monkeypatch)
        wrapper._llm = _RaisingLLM()

        with pytest.raises(RuntimeError):
            wrapper.generate("question")

        assert recorder.calls[0]["metadata"]["model"] == "constructor-model"
