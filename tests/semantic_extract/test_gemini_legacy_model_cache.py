"""Regression tests for the legacy-SDK model-instance cache on ``GeminiProvider``.

When the new ``google.genai`` package is unavailable, ``GeminiProvider`` falls
back to the legacy ``google.generativeai`` package, whose ``GenerativeModel``
binds its model name at construction time and whose API key lives in
module-level state (``genai.configure()``).

``GeminiProvider._legacy_client_for()`` therefore keeps a per-instance cache
keyed by model name, so a repeated per-call ``model=`` override reuses one
``GenerativeModel`` instead of rebuilding it on every request, and re-asserts
``genai.configure(api_key=...)`` with this provider's own key before each use.

PR #1488 (issue #1268) locked in *which* model a per-call override resolves to.
These tests cover what it did not: that the resolved instance is built once and
cached, and that the cache and credentials stay isolated per provider instance
(issue #1269).
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from semantica.semantic_extract.providers import GeminiProvider

CONSTRUCTION_MODEL = "gemini-pro"
OVERRIDE_MODEL = "gemini-1.5-flash"
OTHER_MODEL = "gemini-1.5-pro"
JSON_TEXT = '{"answer": 42}'


def _make_provider(api_key="fake-key", model=CONSTRUCTION_MODEL):
    """A GeminiProvider on the legacy path with the real SDK bootstrap skipped."""
    with patch.object(GeminiProvider, "_init_client", return_value=None):
        provider = GeminiProvider(api_key=api_key, model=model)
    provider._use_new_genai = False
    provider.client = MagicMock(name="construction client")
    return provider


@pytest.fixture
def fake_legacy_genai(monkeypatch):
    """Install a stand-in ``google.generativeai`` module.

    Unlike the fake in ``test_gemini_model_override``, ``GenerativeModel`` here
    does **not** cache internally: it returns a fresh mock every call and records
    every model name it was asked to build, so a test can tell whether the
    provider rebuilt a model or served it from its own cache. ``configure`` is a
    plain mock so credential re-assertion is observable.
    """
    module = MagicMock()
    module.build_calls = []

    def build_model(name):
        module.build_calls.append(name)
        model = MagicMock(name=f"GenerativeModel({name})#{len(module.build_calls)}")
        response = MagicMock()
        response.text = JSON_TEXT
        model.generate_content.return_value = response
        return model

    module.GenerativeModel.side_effect = build_model
    monkeypatch.setitem(sys.modules, "google.generativeai", module)
    return module


class TestLegacyModelCacheReuse:
    """``_legacy_client_for()`` builds each per-call model once, then caches it."""

    def test_repeated_override_builds_one_generative_model(self, fake_legacy_genai):
        provider = _make_provider()

        provider.generate("hello", model=OVERRIDE_MODEL)
        provider.generate("hello", model=OVERRIDE_MODEL)
        provider.generate_structured("hello", model=OVERRIDE_MODEL)

        assert fake_legacy_genai.build_calls == [OVERRIDE_MODEL]
        assert list(provider._legacy_model_cache) == [OVERRIDE_MODEL]

    def test_cache_hit_returns_the_same_instance(self, fake_legacy_genai):
        provider = _make_provider()

        first = provider._legacy_client_for(OVERRIDE_MODEL)
        second = provider._legacy_client_for(OVERRIDE_MODEL)

        assert first is second
        assert first is provider._legacy_model_cache[OVERRIDE_MODEL]
        assert fake_legacy_genai.build_calls == [OVERRIDE_MODEL]

    def test_distinct_overrides_are_cached_separately(self, fake_legacy_genai):
        provider = _make_provider()

        provider.generate("hello", model=OVERRIDE_MODEL)
        provider.generate("hello", model=OTHER_MODEL)
        provider.generate("hello", model=OVERRIDE_MODEL)

        assert fake_legacy_genai.build_calls == [OVERRIDE_MODEL, OTHER_MODEL]
        assert set(provider._legacy_model_cache) == {OVERRIDE_MODEL, OTHER_MODEL}
        assert (
            provider._legacy_model_cache[OVERRIDE_MODEL]
            is not provider._legacy_model_cache[OTHER_MODEL]
        )

    def test_default_model_is_not_cached_or_rebuilt(self, fake_legacy_genai):
        provider = _make_provider(model=CONSTRUCTION_MODEL)
        construction_client = provider.client

        provider.generate("hello")
        provider.generate("hello", model=CONSTRUCTION_MODEL)

        assert fake_legacy_genai.build_calls == []
        assert provider._legacy_model_cache == {}
        assert construction_client.generate_content.call_count == 2


class TestLegacyModelCacheIsolation:
    """The cache and the legacy SDK's module-level key stay per-instance."""

    def test_configure_reasserted_with_this_key_before_every_call(
        self, fake_legacy_genai
    ):
        provider = _make_provider(api_key="key-A")

        provider.generate("hello", model=OVERRIDE_MODEL)
        provider.generate("hello", model=OVERRIDE_MODEL)  # cache hit still re-asserts

        assert fake_legacy_genai.configure.call_count == 2
        for call in fake_legacy_genai.configure.call_args_list:
            assert call.kwargs == {"api_key": "key-A"}

    def test_two_instances_keep_separate_caches_and_keys(self, fake_legacy_genai):
        provider_a = _make_provider(api_key="key-A")
        provider_b = _make_provider(api_key="key-B")

        provider_a.generate("hello", model=OVERRIDE_MODEL)
        provider_b.generate("hello", model=OVERRIDE_MODEL)

        # Same model name, but each instance built and cached its own object.
        assert fake_legacy_genai.build_calls == [OVERRIDE_MODEL, OVERRIDE_MODEL]
        assert (
            provider_a._legacy_model_cache[OVERRIDE_MODEL]
            is not provider_b._legacy_model_cache[OVERRIDE_MODEL]
        )
        assert fake_legacy_genai.configure.call_args_list[-2].kwargs == {
            "api_key": "key-A"
        }
        assert fake_legacy_genai.configure.call_args_list[-1].kwargs == {
            "api_key": "key-B"
        }
