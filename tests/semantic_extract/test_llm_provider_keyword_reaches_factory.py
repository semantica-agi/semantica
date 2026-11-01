"""#1914: the generative-provider keywords an extractor is built with have to
reach the provider factory.

The documented examples passed a constructed provider as ``llm_provider=``.
Extractors do not take an instance: the keyword is forwarded to the provider
factory, where it only lands in the new provider's inert ``config`` mapping, so
the extractor runs against the backend named by ``provider`` instead. The
configuration that is actually read is ``provider``, ``llm_model`` and
``api_key``, so these tests assert on the ``create_provider`` call itself
rather than on constructor attributes -- a constructor-only check passes even
when nothing is forwarded.

``TripletExtractor`` is covered too because it builds its own NER and relation
stages from its shared config, which is where a keyword that survives the
constructor can still be lost on the way down.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from semantica.semantic_extract import methods
from semantica.semantic_extract.cache import ExtractionCache
from semantica.semantic_extract.types import Entity
from semantica.semantic_extract.schemas import (
    EntitiesResponse,
    EntityOut,
    RelationOut,
    RelationsResponse,
    TripletOut,
    TripletsResponse,
)

MODEL = "llama-3.3-70b-versatile"
KEY = "test-key-1914"


def _typed_provider() -> MagicMock:
    """A provider double that answers whichever schema it is handed."""
    provider = MagicMock()
    provider.is_available.return_value = True

    def generate_typed(prompt, schema=None, **kwargs):
        if schema is RelationsResponse:
            return RelationsResponse(
                relations=[
                    RelationOut(
                        subject="Ada Lovelace",
                        predicate="worked_with",
                        object="Charles Babbage",
                    )
                ]
            )
        if schema is TripletsResponse:
            return TripletsResponse(
                triplets=[
                    TripletOut(
                        subject="Ada Lovelace",
                        predicate="worked_with",
                        object="Charles Babbage",
                    )
                ]
            )
        return EntitiesResponse(
            entities=[
                EntityOut(text="Ada Lovelace", label="PERSON", start=0, end=12),
                EntityOut(text="Charles Babbage", label="PERSON", start=28, end=43),
            ]
        )

    provider.generate_typed.side_effect = generate_typed
    return provider


@pytest.fixture
def factory(monkeypatch):
    """Patch the factory the methods module calls, over a cache of our own.

    The cache keys on provider and model, so a leftover entry from another
    test would answer before ``create_provider`` is reached. The module-level
    cache is swapped for a fresh in-memory one rather than cleared: with the
    sqlite backend configured it is persistent, and clearing it would discard
    entries that have nothing to do with this file. ``monkeypatch`` puts the
    original back.
    """
    monkeypatch.setattr(methods, "_result_cache", ExtractionCache(max_size=16))
    for env in ("GROQ_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    with patch("semantica.semantic_extract.methods.create_provider") as mock_create:
        mock_create.return_value = _typed_provider()
        yield mock_create


def _calls(factory):
    return [(c.args, c.kwargs) for c in factory.call_args_list]


def test_ner_extractor_forwards_provider_model_and_key(factory):
    from semantica.semantic_extract import NERExtractor

    extractor = NERExtractor(
        method="llm",
        provider="groq",
        llm_model=MODEL,
        api_key=KEY,
    )
    extractor.extract_entities("Ada Lovelace corresponded with Charles Babbage.")

    assert factory.call_count >= 1, "the LLM method never built a provider"
    args, kwargs = _calls(factory)[0]
    assert args[0] == "groq"
    assert kwargs["model"] == MODEL
    assert kwargs["api_key"] == KEY


def test_llm_provider_instance_is_not_used(factory):
    """``llm_provider=`` reaches the factory as a keyword and stays inert."""
    from semantica.semantic_extract import NERExtractor

    instance = MagicMock(name="provider-instance")
    extractor = NERExtractor(
        method="llm",
        provider="groq",
        llm_model=MODEL,
        api_key=KEY,
        llm_provider=instance,
    )
    extractor.extract_entities("Ada Lovelace built the first algorithm.")

    instance.generate_typed.assert_not_called()
    instance.generate.assert_not_called()
    assert factory.call_count >= 1
    args, kwargs = _calls(factory)[0]
    assert args[0] == "groq", "the instance replaced the configured backend"
    # Forwarded, not filtered out: it is handed to the factory like any other
    # unknown keyword and ends up in the provider's config mapping.
    assert kwargs.get("llm_provider") is instance


def test_relation_extractor_forwards_provider_model_and_key(factory):
    from semantica.semantic_extract import RelationExtractor

    extractor = RelationExtractor(
        method="llm",
        provider="groq",
        llm_model=MODEL,
        api_key=KEY,
    )
    extractor.extract_relations(
        "Ada Lovelace corresponded with Charles Babbage.",
        [
            Entity(
                text="Ada Lovelace",
                label="PERSON",
                start_char=0,
                end_char=12,
                confidence=0.9,
            ),
            Entity(
                text="Charles Babbage",
                label="PERSON",
                start_char=31,
                end_char=46,
                confidence=0.9,
            ),
        ],
    )

    assert factory.call_count >= 1
    args, kwargs = _calls(factory)[0]
    assert args[0] == "groq"
    assert kwargs["model"] == MODEL
    assert kwargs["api_key"] == KEY


def test_triplet_extractor_internal_stages_use_the_configured_provider(factory):
    """TripletExtractor builds NER and relation extractors from its shared
    config. Every provider it ends up constructing -- its own stage and the
    two it delegates to -- has to be the configured one, or part of the run
    silently falls back to the ``openai`` default."""
    from semantica.semantic_extract import TripletExtractor

    extractor = TripletExtractor(
        method="llm",
        provider="groq",
        llm_model=MODEL,
        api_key=KEY,
    )
    extractor.extract_triplets("Ada Lovelace corresponded with Charles Babbage.")

    calls = _calls(factory)
    assert len(calls) >= 2, (
        "expected the internal NER/relation stages to build providers too, "
        f"saw {len(calls)}"
    )
    for args, kwargs in calls:
        assert args[0] == "groq"
        assert kwargs["model"] == MODEL
        assert kwargs["api_key"] == KEY


def test_model_keyword_does_not_reach_the_internal_stages(factory):
    """Why the examples use ``llm_model``: ``model`` configures the triplet
    stage's own call, but it is stripped from the shared config before the NER
    and relation stages are built, so those two run without a model. Pinned as
    the current behaviour, which is what the documentation now states."""
    from semantica.semantic_extract import TripletExtractor

    extractor = TripletExtractor(
        method="llm",
        provider="groq",
        model=MODEL,
        api_key=KEY,
    )
    extractor.extract_triplets("Ada Lovelace corresponded with Charles Babbage.")

    models = {kwargs.get("model") for _, kwargs in _calls(factory)}
    assert MODEL in models, "`model` was expected to configure the triplet stage"
    assert None in models, (
        "a stage was expected to be built without a model; if this now fails, "
        "`model` reaches every stage and the docs note can be dropped"
    )
