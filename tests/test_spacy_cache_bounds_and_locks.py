"""Bounded, call-serialized spaCy model cache — regression tests.

Background
----------
The cache used to retain every model it ever loaded for the life of the
process (each spaCy Language is hundreds of MB), and it handed the SAME
Language object to every caller while batch extraction fans out over a
ThreadPoolExecutor — spaCy pipelines are not safe to invoke from concurrent
threads.

This file tests:
  - LRU eviction at MAX_SPACY_MODELS_CACHED
  - Per-model call serialization
  - Parallelism across different models
  - The single-lock design's correctness under concurrent load
  - The spacy-not-installed guard
"""

import sys
import os
import threading
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from semantica.semantic_extract import methods
from semantica.semantic_extract.methods import (
    MAX_SPACY_MODELS_CACHED,
    clear_spacy_model_cache,
    run_spacy_text,
    spacy_pipeline_guard,
    _spacy_model_cache,
)


def make_spacy_mock():
    """Return a minimal spaCy mock whose .load() returns a distinct nlp per name."""
    mock = MagicMock()
    mock.load = MagicMock(side_effect=lambda name: MagicMock(name=f"nlp-{name}"))
    return mock


class TestBoundedCache(unittest.TestCase):
    def setUp(self):
        clear_spacy_model_cache()

    def tearDown(self):
        clear_spacy_model_cache()

    def test_cache_evicts_beyond_the_bound(self):
        spacy = make_spacy_mock()
        with patch.object(methods, "spacy", spacy):
            for i in range(MAX_SPACY_MODELS_CACHED + 2):
                with spacy_pipeline_guard(f"model_{i}"):
                    pass
        self.assertLessEqual(
            len(_spacy_model_cache), MAX_SPACY_MODELS_CACHED,
            f"cache must stay bounded at {MAX_SPACY_MODELS_CACHED} entries",
        )
        self.assertNotIn("model_0", _spacy_model_cache, "oldest entry must be evicted first")

    def test_recently_used_entries_survive(self):
        """LRU: touching model_0 before overflow keeps it alive; model_1 is evicted."""
        spacy = make_spacy_mock()
        with patch.object(methods, "spacy", spacy):
            for i in range(MAX_SPACY_MODELS_CACHED):
                with spacy_pipeline_guard(f"model_{i}"):
                    pass
            # Re-touch the oldest; overflow should evict model_1 (now the true LRU).
            with spacy_pipeline_guard("model_0"):
                pass
            with spacy_pipeline_guard("model_new"):
                pass
        self.assertIn("model_0", _spacy_model_cache)
        self.assertNotIn("model_1", _spacy_model_cache)

    def test_bound_never_exceeded_under_concurrent_load(self):
        """The single-lock design must not allow concurrent inserts to temporarily
        break the cache bound — something the old lockless fast-path could do.

        The patch is applied in the outer (test) thread so that all worker threads
        share one stable mock for the entire test. Patching per-thread would race:
        a thread exiting its patch context could restore the real spacy module while
        another thread is mid-load, causing sporadic OSError from the real spacy.
        """
        spacy = make_spacy_mock()
        errors = []

        def load_model(i):
            try:
                with spacy_pipeline_guard(f"concurrent_model_{i}"):
                    # While holding the call lock, snapshot cache size.
                    size = len(_spacy_model_cache)
                    if size > MAX_SPACY_MODELS_CACHED:
                        errors.append(
                            f"cache size {size} exceeded bound at model_{i}"
                        )
            except Exception as exc:
                errors.append(str(exc))

        n_threads = MAX_SPACY_MODELS_CACHED * 3
        with patch.object(methods, "spacy", spacy):
            threads = [
                threading.Thread(target=load_model, args=(i,))
                for i in range(n_threads)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(errors, [], f"cache bound violated under concurrent load: {errors}")
        self.assertLessEqual(len(_spacy_model_cache), MAX_SPACY_MODELS_CACHED)

    def test_spacy_not_installed_raises_import_error(self):
        """_load_spacy_entry must raise ImportError if spacy is None, not AttributeError."""
        with patch.object(methods, "spacy", None):
            with self.assertRaises(ImportError):
                with spacy_pipeline_guard("any_model"):
                    pass


class TestPerModelSerialization(unittest.TestCase):
    def setUp(self):
        clear_spacy_model_cache()

    def tearDown(self):
        clear_spacy_model_cache()

    def test_concurrent_calls_on_one_model_never_overlap(self):
        """The per-model call lock must prevent concurrent nlp(text) on the same Language."""
        overlaps = []
        active = []
        state_lock = threading.Lock()

        def slow_nlp(text):
            with state_lock:
                active.append(text)
                if len(active) > 1:
                    overlaps.append(list(active))
            import time
            time.sleep(0.05)
            with state_lock:
                active.pop()
            return MagicMock(name=f"doc-{text}")

        spacy = MagicMock()
        spacy.load = MagicMock(return_value=MagicMock(side_effect=slow_nlp))
        with patch.object(methods, "spacy", spacy):
            threads = [
                threading.Thread(target=lambda i=i: run_spacy_text("m", f"t{i}"))
                for i in range(4)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(
            overlaps, [],
            "concurrent calls on the same model must be serialized by the per-model lock",
        )

    def test_different_models_run_in_parallel(self):
        """Two different models must be callable simultaneously (per-model, not global lock)."""
        entered = threading.Barrier(2, timeout=5)

        def blocking_nlp(text):
            # Both threads must reach this point simultaneously to clear the barrier.
            # If a single global lock were used, the second thread would be blocked
            # waiting for the first to finish, and the barrier would time out.
            entered.wait()
            return MagicMock()

        spacy = MagicMock()
        spacy.load = MagicMock(return_value=MagicMock(side_effect=blocking_nlp))
        with patch.object(methods, "spacy", spacy):
            threads = [
                threading.Thread(target=lambda n=n: run_spacy_text(n, "t"))
                for n in ("model_a", "model_b")
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)
                if t.is_alive():
                    for alive in threads:
                        alive.join(timeout=1)
                    self.fail(
                        "Barrier timed out — different models must run concurrently, "
                        "not serialize on a single global lock"
                    )


if __name__ == "__main__":
    unittest.main()
