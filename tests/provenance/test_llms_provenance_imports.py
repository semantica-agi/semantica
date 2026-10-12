"""Regression tests for the LLM provenance wrappers' import resolution.

Each ``*WithProvenance`` wrapper imports the LLM class it wraps lazily, inside
``__init__``, from a module path that had drifted from the real one
(``.groq_llm`` / ``.openai_llm`` / ``.huggingface_llm`` / ``.lite_llm``).  A
wrong path is invisible until the wrapper is instantiated, and the surrounding
suites guard those instantiations with ``pytest.skip``, so the breakage never
reached CI.

These tests do not skip: if a wrapper cannot resolve the class it wraps, the
test fails.  The providers behind those classes are stubbed so the suite stays
offline and does not require the optional ``groq`` / ``litellm`` packages.
"""


class _StubProvider:
    """Stand-in for the ``*Provider`` a wrapper's target class constructs."""

    def __init__(self, *args, **kwargs):
        pass


class TestGroqWrapper:
    """GroqLLMWithProvenance must resolve the Groq class it wraps."""

    def test_instantiates_and_wraps_groq(self, monkeypatch):
        monkeypatch.setattr("semantica.llms.groq.GroqProvider", _StubProvider)
        from semantica.llms.groq import Groq
        from semantica.llms.llms_provenance import GroqLLMWithProvenance

        wrapper = GroqLLMWithProvenance(provenance=False)
        assert isinstance(wrapper._llm, Groq)


class TestOpenAIWrapper:
    """OpenAILLMWithProvenance must resolve the OpenAI class it wraps."""

    def test_instantiates_and_wraps_openai(self, monkeypatch):
        monkeypatch.setattr("semantica.llms.openai.OpenAIProvider", _StubProvider)
        from semantica.llms.openai import OpenAI
        from semantica.llms.llms_provenance import OpenAILLMWithProvenance

        wrapper = OpenAILLMWithProvenance(provenance=False)
        assert isinstance(wrapper._llm, OpenAI)


class TestHuggingFaceWrapper:
    """HuggingFaceLLMWithProvenance must resolve the class it wraps."""

    def test_instantiates_and_wraps_huggingface(self, monkeypatch):
        # The real provider loads a transformer model during construction.
        monkeypatch.setattr(
            "semantica.llms.huggingface.HuggingFaceLLMProvider", _StubProvider
        )
        from semantica.llms.huggingface import HuggingFaceLLM
        from semantica.llms.llms_provenance import HuggingFaceLLMWithProvenance

        wrapper = HuggingFaceLLMWithProvenance(provenance=False)
        assert isinstance(wrapper._llm, HuggingFaceLLM)


class TestLiteLLMWrapper:
    """LiteLLMWithProvenance must resolve the LiteLLM class it wraps."""

    def test_instantiates_and_wraps_litellm(self, monkeypatch):
        # LiteLLM refuses to construct when its optional package is absent; the
        # wrapper only needs the class object, so let it through.
        monkeypatch.setattr("semantica.llms.litellm.LITELLM_AVAILABLE", True)
        from semantica.llms.litellm import LiteLLM
        from semantica.llms.llms_provenance import LiteLLMWithProvenance

        # `model` is a required argument of LiteLLM; omitting it raises.
        wrapper = LiteLLMWithProvenance(provenance=False, model="openai/gpt-4o-mini")
        assert isinstance(wrapper._llm, LiteLLM)
