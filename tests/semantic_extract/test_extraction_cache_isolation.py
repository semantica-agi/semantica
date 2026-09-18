"""Regression tests: ExtractionCache hands out caller-owned values.

get() used to return the stored list by reference, and CacheItem kept the
very list the caller passed to set().  Every extraction result is
post-processed in place by its callers — weighted-confidence reblending in
NERExtractor, boundary correction, ensemble merges — so the cached entities
themselves were rewritten, and each later cache hit returned already-mutated
objects.  calculate_weighted_confidence is not idempotent (each application
blends the blended value again: 0.6 -> 0.775 -> 0.8625 -> 0.90625 ...), so
the corruption compounded per hit.

The contract pinned here: values cross the InMemoryBackend boundary only as
deep copies, in both directions.  SqliteCacheBackend already provides value
isolation through pickle serialization/deserialization.
"""

from __future__ import annotations

import copy
import threading
from unittest.mock import MagicMock, patch

import pytest

from semantica.semantic_extract.cache import ExtractionCache, InMemoryBackend
from semantica.semantic_extract.types import Entity
from semantica.semantic_extract import methods
from semantica.semantic_extract.schemas import EntitiesResponse, EntityOut


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_entity(text: str = "Apple Inc.", confidence: float = 0.6) -> Entity:
    return Entity(
        text=text,
        label="ORG",
        start_char=0,
        end_char=10,
        confidence=confidence,
        metadata={},
    )


def fresh_cache() -> ExtractionCache:
    return ExtractionCache(max_size=10, ttl=3600)


# ---------------------------------------------------------------------------
# Direction A: mutating the value passed to set() after the call
# ---------------------------------------------------------------------------

def test_mutating_set_input_after_storing_does_not_affect_cached_value():
    """The cache must not retain a reference to the caller's list."""
    cache = fresh_cache()
    original = [make_entity()]
    cache.set("entities", "text", original, provider="p")

    original[0].confidence = 0.99   # mutate the stored object
    original.append(make_entity(text="INJECTED"))  # mutate the list

    stored = cache.get("entities", "text", provider="p")
    assert stored is not None
    assert len(stored) == 1, "appending to the original must not grow the cached list"
    assert stored[0].confidence == 0.6, "in-place field mutation must not reach the cache"


# ---------------------------------------------------------------------------
# Direction B: mutating the value returned by get()
# ---------------------------------------------------------------------------

def test_mutating_get_result_does_not_affect_subsequent_gets():
    """Callers may mutate what get() returns without poisoning the cache."""
    cache = fresh_cache()
    cache.set("entities", "text", [make_entity()], provider="p")

    first = cache.get("entities", "text", provider="p")
    first[0].confidence = 0.123
    first.append(make_entity(text="INJECTED"))

    second = cache.get("entities", "text", provider="p")
    assert len(second) == 1, "a rogue append must not persist across get() calls"
    assert second[0].confidence == 0.6, "an in-place field rewrite must not persist"


# ---------------------------------------------------------------------------
# Two consecutive gets must be independently mutable objects
# ---------------------------------------------------------------------------

def test_consecutive_gets_return_independent_objects():
    cache = fresh_cache()
    cache.set("entities", "text", [make_entity()], provider="p")

    first = cache.get("entities", "text", provider="p")
    second = cache.get("entities", "text", provider="p")

    # Top-level list must be distinct
    assert first is not second
    # The entity objects inside must also be distinct copies
    assert first[0] is not second[0]


# ---------------------------------------------------------------------------
# End-to-end: real extraction path does not allow cache-hit mutation to
# poison the next call
# ---------------------------------------------------------------------------

def test_reblending_returned_entity_does_not_poison_next_cache_hit():
    """NERExtractor applies calculate_weighted_confidence in-place after a
    cache hit.  Without value isolation every hit would compound the blend;
    with it each caller gets a pristine copy."""
    methods._result_cache.clear()
    text = "Apple Inc. was founded by Steve Jobs."

    def run_extract():
        with patch("semantica.semantic_extract.methods.create_provider") as mock_create:
            provider = MagicMock()
            provider.is_available.return_value = True
            provider.generate_typed.return_value = EntitiesResponse(
                entities=[
                    EntityOut(
                        text="Apple Inc.",
                        label="ORG",
                        start=0,
                        end=10,
                        confidence=0.6,
                    )
                ]
            )
            mock_create.return_value = provider
            return methods.extract_entities_llm(text, provider="openai", silent_fail=False)

    first = run_extract()
    pristine_confidence = first[0].confidence

    # Simulate the in-place post-processing any caller (e.g. NERExtractor) applies.
    first[0].confidence = 0.42
    first[0].start_char = 999

    second = run_extract()  # this is a cache hit
    assert second[0].confidence == pristine_confidence, (
        "a cache hit must return the pristine extraction, not the previous "
        "caller's mutations"
    )
    assert second[0].start_char != 999


# ---------------------------------------------------------------------------
# Uncopyable values: set() falls back to storing as-is; get() treats the
# entry as a miss and evicts it rather than failing the extraction
# ---------------------------------------------------------------------------

class _Uncopyable:
    """A value that raises on deepcopy, simulating a non-serialisable object."""

    def __deepcopy__(self, memo):
        raise TypeError("cannot deepcopy me")


def test_uncopyable_value_stored_as_is_in_cacheitem():
    """When deepcopy fails at set()-time, the value is stored raw (not lost)."""
    backend = InMemoryBackend(max_size=10)
    sentinel = _Uncopyable()
    # Use backend directly so we can inspect internals without going through
    # ExtractionCache's key-derivation layer.
    backend.set("entities", "key-u", [sentinel], ttl=3600)

    with backend._locks["entities"]:
        entries = list(backend._caches["entities"].values())

    assert len(entries) == 1, "uncopyable value must still be stored"
    assert any(sentinel is item for item in entries[0].value), (
        "the stored snapshot must be the original object when deepcopy fails"
    )


def test_uncopyable_value_is_a_miss_not_an_extraction_failure():
    """get() on a stored-as-is uncopyable entry must return None, not raise."""
    cache = fresh_cache()
    cache.set("entities", "u", [_Uncopyable()], provider="p")

    result = cache.get("entities", "u", provider="p")
    assert result is None, "an uncopyable cached value must degrade to a miss"


def test_uncopyable_entry_is_evicted_and_subsequent_entries_still_served():
    """After evicting a corrupt entry the cache keeps serving other keys."""
    cache = fresh_cache()
    cache.set("entities", "u", [_Uncopyable()], provider="p")
    cache.set("entities", "ok", [make_entity()], provider="p")

    assert cache.get("entities", "u", provider="p") is None  # triggers eviction

    ok = cache.get("entities", "ok", provider="p")
    assert ok is not None
    assert ok[0].confidence == 0.6


# ---------------------------------------------------------------------------
# Lock hold-time: deepcopy must happen OUTSIDE the namespace lock so a large
# hit value does not block concurrent readers on the same namespace
# ---------------------------------------------------------------------------

def test_get_deepcopy_happens_outside_namespace_lock():
    """While one thread is blocked mid-deepcopy on a large get() result, a
    second thread reading a *different* key from the same namespace must
    complete without waiting — i.e. the lock is not held during the copy."""
    backend = InMemoryBackend(max_size=10)

    big = ["x" * 10_000 for _ in range(50)]
    backend.set("entities", "big", list(big), ttl=3600)
    backend.set("entities", "small", [make_entity("s")], ttl=3600)

    big_copy_started = threading.Event()
    release_big_copy = threading.Event()
    original_deepcopy = copy.deepcopy

    def size_aware_copy(v, memo=None):
        # Only intercept the large value to pause mid-copy.
        if isinstance(v, list) and sum(
            len(x) for x in v if isinstance(x, str)
        ) > 100_000:
            big_copy_started.set()
            release_big_copy.wait(timeout=10)
        return original_deepcopy(v)

    small_result: list = []

    def big_reader():
        with patch.object(copy, "deepcopy", side_effect=size_aware_copy):
            backend.get("entities", "big")

    def small_reader():
        small_result.append(backend.get("entities", "small"))

    t_big = threading.Thread(target=big_reader)
    t_big.start()

    assert big_copy_started.wait(timeout=5), "big-value copy must have started"

    t_small = threading.Thread(target=small_reader)
    t_small.start()
    t_small.join(timeout=1.5)
    small_done = not t_small.is_alive()

    release_big_copy.set()
    t_big.join(timeout=10)

    assert not t_big.is_alive(), "big reader must finish after release"
    assert small_done, (
        "the namespace lock must be free while the big value is being copied; "
        "the small-key read must complete independently"
    )
    assert small_result and small_result[0] is not None


def test_set_deepcopy_happens_outside_namespace_lock():
    """While one thread is blocked mid-deepcopy on a large set() value, a
    second thread *reading* a different key from the same namespace must
    complete without waiting — i.e. the lock is not held during set()'s copy."""
    backend = InMemoryBackend(max_size=10)

    # Pre-populate a small key so the reader has something to fetch.
    backend.set("entities", "small", [make_entity("s")], ttl=3600)

    big = ["x" * 10_000 for _ in range(50)]

    big_copy_started = threading.Event()
    release_big_copy = threading.Event()
    original_deepcopy = copy.deepcopy

    def size_aware_copy(v, memo=None):
        if isinstance(v, list) and sum(
            len(x) for x in v if isinstance(x, str)
        ) > 100_000:
            big_copy_started.set()
            release_big_copy.wait(timeout=10)
        return original_deepcopy(v)

    small_result: list = []

    def big_writer():
        with patch.object(copy, "deepcopy", side_effect=size_aware_copy):
            backend.set("entities", "big", list(big), ttl=3600)

    def small_reader():
        small_result.append(backend.get("entities", "small"))

    t_big = threading.Thread(target=big_writer)
    t_big.start()

    assert big_copy_started.wait(timeout=5), "big-value set() copy must have started"

    t_small = threading.Thread(target=small_reader)
    t_small.start()
    t_small.join(timeout=1.5)
    small_done = not t_small.is_alive()

    release_big_copy.set()
    t_big.join(timeout=10)

    assert not t_big.is_alive(), "big writer must finish after release"
    assert small_done, (
        "the namespace lock must be free while set() is deep-copying; "
        "a concurrent get() on a different key must complete independently"
    )
    assert small_result and small_result[0] is not None
