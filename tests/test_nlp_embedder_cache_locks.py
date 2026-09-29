"""Concurrency regression tests for _nlp_cache and _embedder_cache.

Background
----------
Both caches used an unsynchronized check-then-act pattern:

    if _nlp_cache:
        return _nlp_cache
    _nlp_cache = spacy.load(...)        # ← no lock: multiple threads load

This means concurrent threads could each pass the truthiness check and each
independently call spacy.load() / TextEmbedder(), wasting CPU and memory.
For _nlp_cache the hazard was worse: after initialization, nlp(text) was
called directly on the shared Language object with no serialization, violating
spaCy's documented requirement that a Language instance is not concurrently
callable from multiple threads.

The fix:
  _nlp_cache_lock      — module-level Lock; held across the check + load
  _nlp_call_lock       — module-level Lock; held across every nlp(text) call
  _embedder_cache_lock — module-level Lock; held across the check + construct
  _LOAD_FAILED         — sentinel stored after a failed attempt so subsequent
                         callers return None without re-attempting the load

These tests verify all three invariants in the style of the existing
tests/test_spacy_cache_bounds_and_locks.py.
"""

import os
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from semantica.semantic_extract import methods
from semantica.semantic_extract.methods import (
    _LOAD_FAILED,
    get_nlp_model,
    get_text_embedder,
)

import semantica.embeddings.text_embedder as _te_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_nlp_cache():
    """Drop the cached nlp model so the next call must reload it."""
    methods._nlp_cache = None


def _reset_embedder_cache():
    """Drop the cached embedder so the next call must rebuild it."""
    methods._embedder_cache = None


def _make_spacy_mock(load_counter: list, sleep: float = 0.05):
    """Return a spaCy mock whose .load() increments *load_counter* while sleeping."""
    nlp_mock = MagicMock()
    nlp_mock.vocab.vectors.shape = (100, 96)  # non-empty so vector path is taken

    def slow_load(name, **kw):
        time.sleep(sleep)           # GIL is released inside time.sleep
        load_counter.append(1)
        return nlp_mock

    spacy_mock = MagicMock()
    spacy_mock.util.is_package.return_value = True
    spacy_mock.load.side_effect = slow_load
    return spacy_mock, nlp_mock


def _make_embedder_class(construct_counter: list, sleep: float = 0.05):
    """Return a TextEmbedder replacement class that records constructions."""
    class SlowEmbedder:
        def __init__(self, model_name, normalize):
            time.sleep(sleep)       # GIL released; other threads can run
            construct_counter.append(1)

        def embed_batch(self, texts):
            return [[0.0] * 8 for _ in texts]

    return SlowEmbedder


# ---------------------------------------------------------------------------
# _nlp_cache initialization
# ---------------------------------------------------------------------------

class TestNlpCacheInitialization(unittest.TestCase):

    def setUp(self):
        _reset_nlp_cache()

    def tearDown(self):
        _reset_nlp_cache()

    def test_nlp_model_loaded_exactly_once_under_concurrent_load(self):
        """_nlp_cache_lock must prevent more than one spacy.load() call even
        when many threads race to initialize simultaneously."""
        load_counter = []
        spacy_mock, _ = _make_spacy_mock(load_counter, sleep=0.05)
        n_threads = 8
        barrier = threading.Barrier(n_threads)
        errors = []

        def worker():
            try:
                barrier.wait()          # all threads start at the same instant
                with patch.object(methods, "spacy", spacy_mock), \
                     patch.object(methods, "SPACY_AVAILABLE", True):
                    get_nlp_model()
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"unexpected exceptions: {errors}")
        self.assertEqual(
            len(load_counter), 1,
            f"spacy.load() must be called exactly once; called {len(load_counter)} times",
        )

    def test_nlp_model_is_not_none_after_concurrent_init(self):
        """All threads must agree on a non-None _nlp_cache after the race."""
        load_counter = []
        spacy_mock, expected_nlp = _make_spacy_mock(load_counter)
        results = []

        def worker():
            with patch.object(methods, "spacy", spacy_mock), \
                 patch.object(methods, "SPACY_AVAILABLE", True):
                results.append(get_nlp_model())

        threads = [threading.Thread(target=worker) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertTrue(
            all(r is expected_nlp for r in results),
            "every thread must receive the same Language instance",
        )

    def test_failed_nlp_load_attempted_exactly_once_under_concurrent_load(self):
        """When spacy.load() fails, _LOAD_FAILED is stored so all waiting
        threads return None immediately without each retrying the load.
        spacy.load() must be attempted exactly once, not once per thread."""
        load_counter = []

        def failing_load(name, **kw):
            time.sleep(0.05)
            load_counter.append(1)
            raise OSError("model not found")

        spacy_mock = MagicMock()
        spacy_mock.util.is_package.return_value = True
        spacy_mock.load.side_effect = failing_load

        n_threads = 8
        barrier = threading.Barrier(n_threads)
        errors = []
        results = []

        def worker():
            try:
                barrier.wait()
                with patch.object(methods, "spacy", spacy_mock), \
                     patch.object(methods, "SPACY_AVAILABLE", True):
                    results.append(get_nlp_model())
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"unexpected exceptions: {errors}")
        # All threads must get None back (no crash).
        self.assertTrue(
            all(r is None for r in results),
            f"failed load must return None to all callers; got: {results}",
        )
        # The expensive load must only have been attempted once even with
        # the fallback en_core_web_sm path also being tried — total attempts
        # across all model names in one pass is ≤ 4 (lg, md, sm, fallback sm).
        # Critically it must NOT be n_threads * attempts_per_pass.
        self.assertLessEqual(
            len(load_counter),
            4,  # at most one pass through the model preference list
            f"spacy.load() must only be tried once (across all model names); "
            f"tried {len(load_counter)} times with {n_threads} threads",
        )
        # And _nlp_cache must hold _LOAD_FAILED so subsequent callers skip
        # the load entirely without touching the lock for long.
        self.assertIs(
            methods._nlp_cache,
            _LOAD_FAILED,
            "_nlp_cache must be set to _LOAD_FAILED after a failed load",
        )


# ---------------------------------------------------------------------------
# _embedder_cache initialization
# ---------------------------------------------------------------------------

class TestEmbedderCacheInitialization(unittest.TestCase):

    def setUp(self):
        _reset_embedder_cache()

    def tearDown(self):
        _reset_embedder_cache()

    def test_embedder_constructed_exactly_once_under_concurrent_load(self):
        """_embedder_cache_lock must prevent multiple TextEmbedder constructions
        when threads race to initialize simultaneously.

        The patch is applied in the outer (test) thread so that all worker
        threads share one stable mock — exactly the pattern used by
        test_bound_never_exceeded_under_concurrent_load in
        test_spacy_cache_bounds_and_locks.py.  This avoids the per-thread
        patching race where one thread's context-manager exit can restore the
        real class while another thread is mid-construction.
        """
        construct_counter = []
        SlowEmbedder = _make_embedder_class(construct_counter, sleep=0.05)
        n_threads = 8
        barrier = threading.Barrier(n_threads)
        errors = []

        def worker():
            try:
                barrier.wait()
                get_text_embedder()
            except Exception as exc:
                errors.append(str(exc))

        with patch.object(_te_mod, "TextEmbedder", SlowEmbedder):
            _reset_embedder_cache()     # ensure cold start inside the patch
            threads = [threading.Thread(target=worker) for _ in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(errors, [], f"unexpected exceptions: {errors}")
        self.assertEqual(
            len(construct_counter), 1,
            f"TextEmbedder must be constructed exactly once; "
            f"constructed {len(construct_counter)} times",
        )

    def test_embedder_constructed_exactly_once_via_module_patch(self):
        """Second independent verification using a different sleep duration
        so the race window is wide enough to catch an unguarded implementation."""
        construct_counter = []
        SlowEmbedder = _make_embedder_class(construct_counter, sleep=0.08)
        n_threads = 8
        barrier = threading.Barrier(n_threads)
        errors = []

        def worker():
            try:
                barrier.wait()
                get_text_embedder()
            except Exception as exc:
                errors.append(str(exc))

        with patch.object(_te_mod, "TextEmbedder", SlowEmbedder):
            _reset_embedder_cache()
            threads = [threading.Thread(target=worker) for _ in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(errors, [], f"unexpected exceptions: {errors}")
        self.assertEqual(
            len(construct_counter), 1,
            f"TextEmbedder must be constructed exactly once; "
            f"constructed {len(construct_counter)} times",
        )

    def test_failed_embedder_construction_attempted_exactly_once(self):
        """When TextEmbedder() raises, _LOAD_FAILED is stored so all waiting
        threads return None without each retrying the construction."""
        construct_counter = []

        class FailingEmbedder:
            def __init__(self, model_name, normalize):
                time.sleep(0.05)
                construct_counter.append(1)
                raise RuntimeError("embedder unavailable")

        n_threads = 8
        barrier = threading.Barrier(n_threads)
        errors = []
        results = []

        def worker():
            try:
                barrier.wait()
                results.append(get_text_embedder())
            except Exception as exc:
                errors.append(str(exc))

        with patch.object(_te_mod, "TextEmbedder", FailingEmbedder):
            _reset_embedder_cache()
            threads = [threading.Thread(target=worker) for _ in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(errors, [], f"unexpected exceptions: {errors}")
        self.assertTrue(
            all(r is None for r in results),
            f"failed construction must return None to all callers; got: {results}",
        )
        self.assertEqual(
            len(construct_counter), 1,
            f"TextEmbedder() must only be attempted once; "
            f"attempted {len(construct_counter)} times with {n_threads} threads",
        )
        self.assertIs(
            methods._embedder_cache,
            _LOAD_FAILED,
            "_embedder_cache must be set to _LOAD_FAILED after a failed construction",
        )


# ---------------------------------------------------------------------------
# _nlp_call_lock: concurrent nlp(text) calls must not overlap
# ---------------------------------------------------------------------------

class TestNlpCallSerialization(unittest.TestCase):

    def setUp(self):
        _reset_nlp_cache()
        methods._embedder_cache = _LOAD_FAILED  # disable embedder stage

    def tearDown(self):
        _reset_nlp_cache()
        methods._embedder_cache = None

    def test_concurrent_nlp_calls_never_overlap(self):
        """_nlp_call_lock must prevent concurrent nlp(text) invocations on the
        shared Language object.  This mirrors test_concurrent_calls_on_one_model_never_overlap
        from test_spacy_cache_bounds_and_locks.py.

        The mocked nlp() uses a barrier-style overlap detector: if two calls
        run simultaneously the 'active' list will contain more than one entry.
        The test also asserts that nlp() was actually invoked — it must not
        pass vacuously.
        """
        overlaps = []
        active = []
        state_lock = threading.Lock()
        nlp_call_count = []

        def slow_nlp_call(text):
            with state_lock:
                active.append(text)
                if len(active) > 1:
                    overlaps.append(list(active))
                nlp_call_count.append(text)
            time.sleep(0.05)
            with state_lock:
                active.pop()
            doc = MagicMock()
            doc.vector_norm = 1.0
            doc.similarity.return_value = 0.5
            return doc

        nlp_mock = MagicMock()
        nlp_mock.vocab.vectors.shape = (100, 96)
        nlp_mock.side_effect = slow_nlp_call

        spacy_mock = MagicMock()
        spacy_mock.util.is_package.return_value = True
        spacy_mock.load.return_value = nlp_mock

        n_threads = 5

        with patch.object(methods, "spacy", spacy_mock), \
             patch.object(methods, "SPACY_AVAILABLE", True):
            # Pre-load the cache so the race is only on the call, not on init.
            get_nlp_model()

            from semantica.semantic_extract.methods import find_best_match_index

            barrier = threading.Barrier(n_threads)
            errors = []

            def worker(i):
                try:
                    barrier.wait()
                    # _embedder_cache is _LOAD_FAILED (set in setUp) so the
                    # embedding stage (3) is always skipped, guaranteeing every
                    # thread reaches the vector-similarity stage (4) that holds
                    # _nlp_call_lock.
                    find_best_match_index(f"query_{i}", ["alpha", "beta", "gamma"])
                except Exception as exc:
                    errors.append(str(exc))

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(errors, [], f"unexpected exceptions: {errors}")
        self.assertGreater(
            len(nlp_call_count), 0,
            "nlp() must have been called — test must not pass vacuously",
        )
        self.assertEqual(
            overlaps, [],
            f"concurrent nlp(text) calls detected — _nlp_call_lock is broken: {overlaps}",
        )


if __name__ == "__main__":
    unittest.main()
