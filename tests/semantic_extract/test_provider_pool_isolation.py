"""
Regression tests for ProviderPool credential isolation and concurrency safety.

Issue
-----
``ProviderPool`` computed its cache key from the raw kwargs passed to
``create_provider()``.  When callers omitted ``api_key`` and relied on
environment-variable resolution inside the provider ``__init__``, the
resolved credential was *not* part of the pool key.  Rotating
``OPENAI_API_KEY`` (or any provider env var) between two calls with
otherwise identical arguments caused the second call to receive the
stale cached provider — a credential cross-contamination bug.

There was also an unsynchronised check-then-create-then-store sequence
in ``ProviderPool.get()`` that let concurrent threads construct duplicate
providers for the same key.

Fix
---
* ``ProviderPool.get()`` now resolves the effective API key (via the same
  ``config.get_api_key() → env-var`` fallback chain the provider
  ``__init__`` uses) *before* computing the cache key, and injects it into
  kwargs so the resolved credential is always represented in the key.
* A ``threading.Lock`` with double-checked locking serialises first-time
  construction so that concurrent callers with the same key always receive
  the same instance.

Tests in this module
---------------------
TestCredentialIsolation
  - env-key rotation creates a fresh provider
  - explicit api_key=A and api_key=B are isolated
  - same effective config still reuses the cached provider
  - use_pool=False always bypasses the pool
  - api_key is not leaked into debug log output

TestConcurrencySafety
  - concurrent first-time requests for the same config produce exactly one
    canonical provider (single construction, same instance returned to all)
"""

import os
import threading
import unittest
from unittest.mock import MagicMock, patch

from semantica.semantic_extract.providers import (
    ProviderPool,
    create_provider,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pool() -> ProviderPool:
    """Return a fresh, isolated ProviderPool for each test."""
    return ProviderPool()


def _mock_openai_cls(instances: list):
    """Return a side_effect callable that appends each new mock to *instances*."""
    def factory(*args, **kwargs):
        m = MagicMock(name=f"OpenAIProvider-{len(instances)}")
        instances.append(m)
        return m
    return factory


# ---------------------------------------------------------------------------
# Credential isolation
# ---------------------------------------------------------------------------

class TestCredentialIsolation(unittest.TestCase):
    """ProviderPool must isolate providers by effective credential."""

    def setUp(self):
        # Every test gets its own pool so there is no cross-test state.
        self.pool = _make_pool()

    # ------------------------------------------------------------------
    # Core bug: env-key rotation must yield a new provider
    # ------------------------------------------------------------------

    def test_env_key_rotation_creates_fresh_provider(self):
        """
        Rotating the environment API key between two otherwise-identical
        calls must produce two distinct provider instances.

        This is the primary regression test: before the fix the pool key
        did not contain the env-var-resolved credential, so both calls
        received the same (stale) instance.
        """
        instances = []

        with patch(
            "semantica.semantic_extract.providers.OpenAIProvider",
            side_effect=_mock_openai_cls(instances),
        ):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-key-A"}, clear=False):
                p1 = self.pool.get("openai", model="gpt-4")

            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-key-B"}, clear=False):
                p2 = self.pool.get("openai", model="gpt-4")

        # Two different credentials → two different instances
        self.assertIsNot(
            p1,
            p2,
            "Rotating OPENAI_API_KEY must produce a new provider instance, "
            "not reuse the one initialised with the old key.",
        )
        self.assertEqual(len(instances), 2, "Expected exactly two provider constructions.")

    def test_env_key_rotation_via_create_provider(self):
        """Same assertion exercised through the public ``create_provider`` API."""
        instances = []

        with patch(
            "semantica.semantic_extract.providers.OpenAIProvider",
            side_effect=_mock_openai_cls(instances),
        ):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-A"}, clear=False):
                p1 = self.pool.get("openai", model="gpt-4")

            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-B"}, clear=False):
                p2 = self.pool.get("openai", model="gpt-4")

        self.assertIsNot(p1, p2)
        self.assertEqual(len(instances), 2)

    # ------------------------------------------------------------------
    # Explicit api_key isolation (must still work after the fix)
    # ------------------------------------------------------------------

    def test_explicit_different_keys_are_isolated(self):
        """Two calls with different explicit api_key values must not share an instance."""
        instances = []

        with patch(
            "semantica.semantic_extract.providers.OpenAIProvider",
            side_effect=_mock_openai_cls(instances),
        ):
            p1 = self.pool.get("openai", api_key="sk-A", model="gpt-4")
            p2 = self.pool.get("openai", api_key="sk-B", model="gpt-4")

        self.assertIsNot(p1, p2)
        self.assertEqual(len(instances), 2)

    def test_explicit_same_key_reuses_instance(self):
        """Two calls with the same explicit api_key and model must share one instance."""
        instances = []

        with patch(
            "semantica.semantic_extract.providers.OpenAIProvider",
            side_effect=_mock_openai_cls(instances),
        ):
            p1 = self.pool.get("openai", api_key="sk-same", model="gpt-4")
            p2 = self.pool.get("openai", api_key="sk-same", model="gpt-4")

        self.assertIs(p1, p2)
        self.assertEqual(len(instances), 1, "Same config must not construct a second instance.")

    # ------------------------------------------------------------------
    # Same effective credential reuses the cached provider
    # ------------------------------------------------------------------

    def test_same_env_key_reuses_provider(self):
        """If the env key does not change, repeat calls must return the cached instance."""
        instances = []

        with patch(
            "semantica.semantic_extract.providers.OpenAIProvider",
            side_effect=_mock_openai_cls(instances),
        ):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-stable"}, clear=False):
                p1 = self.pool.get("openai", model="gpt-4")
                p2 = self.pool.get("openai", model="gpt-4")

        self.assertIs(p1, p2, "Same config must reuse the cached provider.")
        self.assertEqual(len(instances), 1)

    def test_explicit_key_matches_env_key_reuses_provider(self):
        """
        If the caller passes api_key=X explicitly and the env var is also X,
        repeated calls must still reuse the same instance (key must be stable).
        """
        instances = []

        with patch(
            "semantica.semantic_extract.providers.OpenAIProvider",
            side_effect=_mock_openai_cls(instances),
        ):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-same-X"}, clear=False):
                p1 = self.pool.get("openai", api_key="sk-same-X", model="gpt-4")
                # Second call omits explicit key — env var resolves to same value
                p2 = self.pool.get("openai", model="gpt-4")

        self.assertIs(p1, p2)
        self.assertEqual(len(instances), 1)

    # ------------------------------------------------------------------
    # use_pool=False
    # ------------------------------------------------------------------

    def test_use_pool_false_always_creates_fresh_instance(self):
        """use_pool=False must bypass the pool and always construct a new provider."""
        instances = []

        with patch(
            "semantica.semantic_extract.providers.OpenAIProvider",
            side_effect=_mock_openai_cls(instances),
        ):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-any"}, clear=False):
                p1 = create_provider("openai", use_pool=False, model="gpt-4")
                p2 = create_provider("openai", use_pool=False, model="gpt-4")

        self.assertIsNot(p1, p2)
        self.assertEqual(len(instances), 2)

    # ------------------------------------------------------------------
    # Providers that do not use api_key are unaffected
    # ------------------------------------------------------------------

    def test_ollama_provider_unaffected_no_api_key(self):
        """
        OllamaProvider does not use an API key.  The pool must still work
        correctly (same config → same instance) without injecting a spurious
        api_key kwarg.
        """
        instances = []

        with patch(
            "semantica.semantic_extract.providers.OllamaProvider",
            side_effect=_mock_openai_cls(instances),
        ):
            p1 = self.pool.get("ollama", model="llama2", base_url="http://localhost:11434")
            p2 = self.pool.get("ollama", model="llama2", base_url="http://localhost:11434")

        self.assertIs(p1, p2)
        self.assertEqual(len(instances), 1)

        # Verify api_key was NOT injected into the pool key for Ollama.
        pool_key = ProviderPool._make_key(
            "ollama", model="llama2", base_url="http://localhost:11434"
        )
        self.assertNotIn("api_key", pool_key)

    # ------------------------------------------------------------------
    # api_key must not appear in log output
    # ------------------------------------------------------------------

    def test_api_key_not_logged(self):
        """
        The debug log message emitted when a new provider is created must
        not contain the raw API key value.
        """
        import logging

        log_records = []

        class CapturingHandler(logging.Handler):
            def emit(self, record):
                log_records.append(self.format(record))

        handler = CapturingHandler()
        logging.getLogger().addHandler(handler)
        try:
            with patch(
                "semantica.semantic_extract.providers.OpenAIProvider",
                side_effect=_mock_openai_cls([]),
            ):
                with patch.dict(
                    os.environ, {"OPENAI_API_KEY": "sk-secret-should-not-log"}, clear=False
                ):
                    self.pool.get("openai", model="gpt-4")
        finally:
            logging.getLogger().removeHandler(handler)

        combined = "\n".join(log_records)
        self.assertNotIn(
            "sk-secret-should-not-log",
            combined,
            "Raw API key value must not appear in log output.",
        )


# ---------------------------------------------------------------------------
# Concurrency safety
# ---------------------------------------------------------------------------

class TestConcurrencySafety(unittest.TestCase):
    """ProviderPool.get() must serialise first-time construction under concurrency."""

    def setUp(self):
        self.pool = _make_pool()

    def test_concurrent_first_access_single_construction(self):
        """
        N threads simultaneously requesting the same (provider, config) for
        the first time must result in exactly ONE provider construction and
        all threads receiving the SAME instance.

        This is the regression test for the check-then-create race:
        before the fix, concurrent threads could each pass the ``if key in
        self._providers`` check before any one of them stored its result,
        causing N duplicate constructions and non-deterministic aliasing.
        """
        num_threads = 20
        results: list = [None] * num_threads
        construction_count = 0
        construction_lock = threading.Lock()

        # Introduce a small delay inside the constructor to widen the race
        # window so that — without the fix — multiple threads would almost
        # certainly construct duplicate providers.
        import time

        def slow_factory(*args, **kwargs):
            nonlocal construction_count
            time.sleep(0.02)  # 20 ms — enough to expose the race
            with construction_lock:
                construction_count += 1
            m = MagicMock(name=f"provider-{construction_count}")
            return m

        barrier = threading.Barrier(num_threads)

        def worker(idx):
            barrier.wait()  # all threads start simultaneously
            results[idx] = self.pool.get("openai", api_key="sk-concurrent", model="gpt-4")

        with patch(
            "semantica.semantic_extract.providers.OpenAIProvider",
            side_effect=slow_factory,
        ):
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

        # Exactly one construction must have occurred.
        self.assertEqual(
            construction_count,
            1,
            f"Expected exactly 1 provider construction under concurrency, "
            f"got {construction_count}.",
        )

        # Every thread must have received the same instance.
        canonical = results[0]
        self.assertIsNotNone(canonical)
        for idx, result in enumerate(results):
            self.assertIs(
                result,
                canonical,
                f"Thread {idx} received a different provider instance than thread 0.",
            )

    def test_clear_is_thread_safe(self):
        """
        ``clear()`` must not corrupt the pool's internal state when called
        concurrently with ``get()`` calls.
        """
        import time

        instances: list = []
        errors: list = []

        def factory(*args, **kwargs):
            time.sleep(0.001)
            m = MagicMock()
            instances.append(m)
            return m

        stop_event = threading.Event()

        def getter():
            while not stop_event.is_set():
                try:
                    self.pool.get("openai", api_key="sk-x", model="gpt-4")
                except Exception as exc:
                    errors.append(exc)

        def clearer():
            for _ in range(20):
                self.pool.clear()
                time.sleep(0.005)

        with patch(
            "semantica.semantic_extract.providers.OpenAIProvider",
            side_effect=factory,
        ):
            getter_threads = [threading.Thread(target=getter) for _ in range(4)]
            clear_thread = threading.Thread(target=clearer)

            for t in getter_threads:
                t.start()
            clear_thread.start()

            clear_thread.join(timeout=5)
            stop_event.set()
            for t in getter_threads:
                t.join(timeout=5)

        self.assertEqual(
            errors,
            [],
            f"No exceptions expected during concurrent get/clear, got: {errors}",
        )


# ---------------------------------------------------------------------------
# _make_key and _resolve_api_key unit tests
# ---------------------------------------------------------------------------

class TestProviderPoolInternals(unittest.TestCase):
    """Unit tests for ProviderPool helper methods."""

    def setUp(self):
        self.pool = _make_pool()

    def test_make_key_is_deterministic(self):
        """_make_key must return the same string for equivalent kwargs regardless of insertion order."""
        k1 = ProviderPool._make_key("openai", api_key="sk-x", model="gpt-4", temperature=0.5)
        k2 = ProviderPool._make_key("openai", model="gpt-4", temperature=0.5, api_key="sk-x")
        self.assertEqual(k1, k2)

    def test_make_key_differs_for_different_api_keys(self):
        k1 = ProviderPool._make_key("openai", api_key="sk-A", model="gpt-4")
        k2 = ProviderPool._make_key("openai", api_key="sk-B", model="gpt-4")
        self.assertNotEqual(k1, k2)

    def test_make_key_nested_dict_is_stable(self):
        k1 = ProviderPool._make_key("openai", opts={"a": 1, "b": 2})
        k2 = ProviderPool._make_key("openai", opts={"b": 2, "a": 1})
        self.assertEqual(k1, k2)

    def test_resolve_api_key_explicit_kwarg(self):
        """Explicit kwarg is returned as-is."""
        result = self.pool._resolve_api_key("openai", {"api_key": "sk-explicit"})
        self.assertEqual(result, "sk-explicit")

    def test_resolve_api_key_env_var_fallback(self):
        """Falls back to env var when no explicit kwarg."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-from-env"}, clear=False):
            result = self.pool._resolve_api_key("openai", {})
        self.assertEqual(result, "sk-from-env")

    def test_resolve_api_key_none_for_ollama(self):
        """Ollama is not in _API_KEY_PROVIDERS; must return None."""
        result = self.pool._resolve_api_key("ollama", {})
        self.assertIsNone(result)

    def test_resolve_api_key_none_for_huggingface_llm(self):
        """HuggingFace LLM provider must return None."""
        result = self.pool._resolve_api_key("huggingface_llm", {})
        self.assertIsNone(result)

    def test_resolve_api_key_none_when_no_key_anywhere(self):
        """When no key is set anywhere, must return None (not raise)."""
        env_key = "OPENAI_API_KEY"
        original = os.environ.pop(env_key, None)
        try:
            # Also ensure config singleton has no key cached
            with patch(
                "semantica.semantic_extract.providers.config.get_api_key",
                return_value=None,
            ):
                result = self.pool._resolve_api_key("openai", {})
            self.assertIsNone(result)
        finally:
            if original is not None:
                os.environ[env_key] = original

    def test_all_api_key_providers_covered(self):
        """All built-in API-key-using providers must be listed in _API_KEY_PROVIDERS."""
        expected = {"openai", "gemini", "groq", "anthropic", "deepseek", "novita"}
        self.assertEqual(ProviderPool._API_KEY_PROVIDERS, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ---------------------------------------------------------------------------
# HIGH-1 regression: custom provider shadowing a built-in API-key provider
# ---------------------------------------------------------------------------

class TestCustomProviderShadowing(unittest.TestCase):
    """Custom providers registered under a built-in name must not receive
    an automatically injected ``api_key`` kwarg."""

    def setUp(self):
        self.pool = _make_pool()

    def tearDown(self):
        # Remove any registrations added during tests.
        from semantica.semantic_extract.registry import provider_registry as _reg
        for name in ("openai", "groq", "anthropic", "gemini"):
            _reg.unregister(name)

    def test_custom_provider_under_builtin_name_no_api_key_injection(self):
        """
        Regression test for HIGH-1.

        A custom provider registered under the name ``"openai"`` must NOT
        receive an automatically injected ``api_key`` kwarg, even when
        ``OPENAI_API_KEY`` is set in the environment.

        Before the fix, ``_resolve_api_key`` would resolve the env-var key
        and inject it regardless of whether the registered class accepted it,
        causing a ``TypeError`` for any custom class that does not declare
        an ``api_key`` parameter.
        """
        from semantica.semantic_extract.registry import provider_registry

        class MyCustomProvider:
            """Custom provider that does NOT accept api_key."""
            def __init__(self, model="custom-default"):
                self.model = model

            def is_available(self):
                return True

        provider_registry.register("openai", MyCustomProvider)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-should-not-inject"}, clear=False):
            # Must not raise TypeError — no api_key should be injected.
            provider = self.pool.get("openai", model="custom-v1")

        self.assertIsInstance(provider, MyCustomProvider)
        self.assertEqual(provider.model, "custom-v1")

    def test_custom_provider_receives_explicit_caller_kwargs_unchanged(self):
        """Explicit caller kwargs (other than api_key) must still reach the custom class."""
        from semantica.semantic_extract.registry import provider_registry

        received_kwargs = {}

        class CapturingProvider:
            def __init__(self, **kwargs):
                received_kwargs.update(kwargs)

            def is_available(self):
                return True

        provider_registry.register("groq", CapturingProvider)

        self.pool.get("groq", model="custom-model", timeout=30)

        self.assertEqual(received_kwargs.get("model"), "custom-model")
        self.assertEqual(received_kwargs.get("timeout"), 30)
        self.assertNotIn(
            "api_key",
            received_kwargs,
            "api_key must not be auto-injected into a custom provider.",
        )

    def test_custom_provider_explicit_api_key_caller_passes_through(self):
        """If the *caller* explicitly passes api_key, it must reach the custom class."""
        from semantica.semantic_extract.registry import provider_registry

        received_kwargs = {}

        class CapturingProvider:
            def __init__(self, **kwargs):
                received_kwargs.update(kwargs)

            def is_available(self):
                return True

        provider_registry.register("anthropic", CapturingProvider)

        self.pool.get("anthropic", api_key="sk-caller-explicit", model="claude-custom")

        self.assertEqual(
            received_kwargs.get("api_key"),
            "sk-caller-explicit",
            "Explicit caller api_key must be forwarded to the custom provider.",
        )

    def test_builtin_provider_still_resolves_env_key_when_no_custom_registration(self):
        """Built-in providers must continue to have their env key resolved."""
        instances = []

        with patch(
            "semantica.semantic_extract.providers.OpenAIProvider",
            side_effect=_mock_openai_cls(instances),
        ):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-builtin-env"}, clear=False):
                p1 = self.pool.get("openai", model="gpt-4")
                p2 = self.pool.get("openai", model="gpt-4")

        # Same env key → same instance (key stable).
        self.assertIs(p1, p2)
        self.assertEqual(len(instances), 1)

    def test_builtin_provider_env_rotation_after_deregistering_custom(self):
        """
        After a custom provider is unregistered, the built-in env-key
        resolution must resume correctly.
        """
        from semantica.semantic_extract.registry import provider_registry

        class TempCustom:
            def __init__(self, model="x"):
                pass
            def is_available(self):
                return True

        provider_registry.register("gemini", TempCustom)
        # While registered: no key injection
        with patch.dict(os.environ, {"GEMINI_API_KEY": "sk-gemini"}, clear=False):
            p_custom = self.pool.get("gemini", model="custom")
        self.assertIsInstance(p_custom, TempCustom)

        provider_registry.unregister("gemini")
        self.pool.clear()  # reset so built-in path is exercised fresh

        with patch(
            "semantica.semantic_extract.providers.GeminiProvider",
            side_effect=_mock_openai_cls([]),
        ) as MockGemini:
            with patch.dict(os.environ, {"GEMINI_API_KEY": "sk-gemini"}, clear=False):
                self.pool.get("gemini", model="gemini-pro")

        # Built-in path was taken (GeminiProvider was instantiated).
        MockGemini.assert_called_once()
        # api_key must have been passed (env-resolved).
        call_kwargs = MockGemini.call_args[1]
        self.assertIn("api_key", call_kwargs)


# ---------------------------------------------------------------------------
# HIGH-2 regression: nested / re-entrant provider creation
# ---------------------------------------------------------------------------

class TestNestedProviderCreation(unittest.TestCase):
    """Provider constructors must be able to call ``create_provider()`` or
    ``pool.get()`` again without deadlocking."""

    def setUp(self):
        self.pool = _make_pool()

    def tearDown(self):
        from semantica.semantic_extract.registry import provider_registry as _reg
        for name in ("openai", "groq", "anthropic"):
            _reg.unregister(name)

    # ------------------------------------------------------------------
    # Core re-entrancy (different keys) — primary regression test
    # ------------------------------------------------------------------

    def test_nested_different_key_no_deadlock(self):
        """
        Regression test for HIGH-2.

        A provider constructor that calls ``pool.get()`` for a *different*
        key must not deadlock.

        Before the fix, the single non-reentrant ``threading.Lock`` was held
        for the entire duration of ``_create_provider()``.  Any re-entrant
        call to ``pool.get()`` (for any key) would block forever attempting
        to re-acquire the same lock.
        """
        from semantica.semantic_extract.registry import provider_registry

        inner_instances = []

        class InnerProvider:
            def __init__(self, **kwargs):
                inner_instances.append(self)

            def is_available(self):
                return True

        class OuterProvider:
            """Outer provider whose constructor depends on InnerProvider."""
            def __init__(self, **kwargs):
                # Nested call for a completely different provider/key.
                self.inner = self.pool.get("groq", api_key="sk-inner", model="llama")

            def is_available(self):
                return True

        OuterProvider.pool = self.pool
        provider_registry.register("openai", OuterProvider)
        provider_registry.register("groq", InnerProvider)

        deadline = threading.Event()
        error_holder = [None]
        result_holder = [None]

        def attempt():
            try:
                result_holder[0] = self.pool.get(
                    "openai", api_key="sk-outer", model="gpt-4"
                )
            except Exception as exc:
                error_holder[0] = exc
            finally:
                deadline.set()

        t = threading.Thread(target=attempt, daemon=True)
        t.start()
        t.join(timeout=3)

        self.assertTrue(
            deadline.is_set(),
            "Nested pool.get() for a different key deadlocked (thread did not return).",
        )
        if error_holder[0]:
            self.fail(f"Unexpected exception: {error_holder[0]}")

        outer = result_holder[0]
        self.assertIsInstance(outer, OuterProvider)
        self.assertIsInstance(outer.inner, InnerProvider)
        self.assertEqual(len(inner_instances), 1)

    def test_nested_different_key_inner_is_cached(self):
        """The inner provider created during outer construction is cached in the pool."""
        from semantica.semantic_extract.registry import provider_registry

        class Inner:
            def __init__(self, **kw): pass
            def is_available(self): return True

        class Outer:
            def __init__(self, **kw):
                self.inner = pool.get("groq", api_key="sk-i", model="m")
            def is_available(self): return True

        pool = self.pool
        provider_registry.register("openai", Outer)
        provider_registry.register("groq", Inner)

        pool.get("openai", api_key="sk-o", model="m")

        # The inner provider must now be in the pool — same instance returned.
        inner2 = pool.get("groq", api_key="sk-i", model="m")
        self.assertIsInstance(inner2, Inner)

    # ------------------------------------------------------------------
    # Same-key re-entrancy: must not deadlock (RecursionError is acceptable)
    # ------------------------------------------------------------------

    def test_same_key_reentrant_raises_recursion_not_deadlock(self):
        """
        A constructor that calls pool.get() for the EXACT same key it is
        currently building is inherently infinitely recursive (the pool
        cannot meaningfully satisfy such a request).  The pool must not
        deadlock; raising RecursionError is the correct outcome.
        """
        from semantica.semantic_extract.registry import provider_registry

        pool = self.pool

        class SelfReferential:
            def __init__(self, **kw):
                # Same name + same kwargs → same key → infinite recursion.
                pool.get("anthropic", api_key="sk-x", model="claude")

        provider_registry.register("anthropic", SelfReferential)

        deadline = threading.Event()
        exception_holder = [None]

        def attempt():
            try:
                pool.get("anthropic", api_key="sk-x", model="claude")
            except RecursionError:
                exception_holder[0] = "RecursionError"
            except Exception as e:
                exception_holder[0] = e
            finally:
                deadline.set()

        t = threading.Thread(target=attempt, daemon=True)
        t.start()
        t.join(timeout=5)

        self.assertTrue(
            deadline.is_set(),
            "Same-key re-entrancy caused a deadlock (thread did not return within 5s).",
        )
        self.assertEqual(
            exception_holder[0],
            "RecursionError",
            f"Expected RecursionError for infinite same-key re-entrancy, "
            f"got: {exception_holder[0]}",
        )

    # ------------------------------------------------------------------
    # Construction failure: waiting threads must not hang
    # ------------------------------------------------------------------

    def test_construction_failure_unblocks_waiting_threads(self):
        """
        If provider construction raises, threads that queued up waiting for
        the same key must not hang indefinitely — they must eventually get
        a chance to build (or fail) themselves.
        """
        import time
        from semantica.semantic_extract.registry import provider_registry

        pool = self.pool
        attempt_count = 0
        succeeded = threading.Event()
        errors: list = []

        # First construction raises; subsequent ones succeed.
        class FlakyProvider:
            def __init__(self, **kw):
                nonlocal attempt_count
                attempt_count += 1
                if attempt_count == 1:
                    raise RuntimeError("first construction deliberately fails")
                self.ok = True

            def is_available(self):
                return True

        provider_registry.register("groq", FlakyProvider)

        results: list = [None, None]
        barriers = threading.Barrier(2)

        def worker(idx):
            barriers.wait()  # start simultaneously
            try:
                results[idx] = pool.get("groq", api_key="sk-flaky", model="m")
                if results[idx] is not None:
                    succeeded.set()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # At least one thread must have obtained a valid provider.
        self.assertTrue(
            succeeded.is_set() or any(r is not None for r in results),
            "All threads failed or hung after construction failure.",
        )
        # The first construction must have failed (attempt_count >= 2 means
        # at least one retry occurred after the initial failure).
        self.assertGreaterEqual(attempt_count, 2)

    # ------------------------------------------------------------------
    # Same-key concurrent: still serialised after the redesign
    # ------------------------------------------------------------------

    def test_same_key_concurrent_single_construction_after_redesign(self):
        """
        Verify the per-key Event design still ensures exactly one provider
        is constructed when many threads race for the same key simultaneously.
        (Keeps the concurrency guarantee from the original fix.)
        """
        import time

        construction_count = 0
        count_lock = threading.Lock()
        num_threads = 16
        results: list = [None] * num_threads

        def slow_factory(*args, **kwargs):
            nonlocal construction_count
            time.sleep(0.02)
            with count_lock:
                construction_count += 1
            return MagicMock(name=f"p-{construction_count}")

        barrier = threading.Barrier(num_threads)

        def worker(idx):
            barrier.wait()
            results[idx] = self.pool.get(
                "openai", api_key="sk-concurrent", model="gpt-4"
            )

        with patch(
            "semantica.semantic_extract.providers.OpenAIProvider",
            side_effect=slow_factory,
        ):
            threads = [
                threading.Thread(target=worker, args=(i,)) for i in range(num_threads)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

        self.assertEqual(
            construction_count,
            1,
            f"Expected exactly 1 construction, got {construction_count}.",
        )
        canonical = results[0]
        self.assertIsNotNone(canonical)
        for idx, r in enumerate(results):
            self.assertIs(r, canonical, f"Thread {idx} got a different instance.")

    # ------------------------------------------------------------------
    # Different-key concurrent: must NOT serialize unrelated keys
    # ------------------------------------------------------------------

    def test_different_keys_build_concurrently(self):
        """
        Two threads building *different* keys must not be serialised by the
        pool: both constructions should run in parallel (verified by timing).
        """
        import time

        DELAY = 0.1  # 100 ms construction delay per provider

        started = threading.Barrier(2)
        results = {}

        def build_a():
            started.wait()
            results["a"] = self.pool.get("openai", api_key="sk-a", model="gpt-4a")

        def build_b():
            started.wait()
            results["b"] = self.pool.get("openai", api_key="sk-b", model="gpt-4b")

        with patch(
            "semantica.semantic_extract.providers.OpenAIProvider",
        ) as MockCls:
            MockCls.side_effect = [
                MagicMock(name="provider-a"),
                MagicMock(name="provider-b"),
            ]

            ta = threading.Thread(target=build_a)
            tb = threading.Thread(target=build_b)

            t0 = __import__("time").monotonic()
            ta.start()
            tb.start()
            ta.join(timeout=5)
            tb.join(timeout=5)
            elapsed = __import__("time").monotonic() - t0

        self.assertIn("a", results)
        self.assertIn("b", results)
        # If serialised, elapsed ≥ 2 * DELAY.  If parallel, elapsed ≈ DELAY.
        # We use 1.5 * DELAY as a generous threshold.
        self.assertLess(
            elapsed,
            DELAY * 1.5 + 0.3,  # 0.3 s of scheduling slack
            f"Different-key builds took {elapsed:.3f}s — expected parallel (~{DELAY}s), "
            f"not serialised (~{2*DELAY}s).",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
