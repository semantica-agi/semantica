"""Unit tests for ExtractionCache pluggable backends (in-memory + sqlite)."""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import sqlite3
import stat
import subprocess
import sys

import pytest

from semantica.semantic_extract import (
    CacheBackend,
    ExtractionCache,
    InMemoryBackend,
    SqliteCacheBackend,
)
from semantica.semantic_extract.types import Entity, Relation, Triplet


# ---------------------------------------------------------------------------
# ExtractionCache + default in-memory backend (behavior parity)
# ---------------------------------------------------------------------------


def test_default_backend_is_in_memory():
    cache = ExtractionCache()
    assert isinstance(cache._backend, InMemoryBackend)
    assert isinstance(cache._backend, CacheBackend)


def test_get_set_roundtrip():
    cache = ExtractionCache()
    assert cache.get("entities", "hello") is None
    cache.set("entities", "hello", [{"name": "X"}])
    assert cache.get("entities", "hello") == [{"name": "X"}]


def test_sensitive_params_excluded_from_key():
    cache = ExtractionCache()
    cache.set("entities", "hi", ["v"], provider="openai", api_key="secret-1")
    # A different api_key/token must not change the key -> still a hit.
    assert cache.get("entities", "hi", provider="openai", api_key="secret-2") == ["v"]


def test_different_params_produce_different_keys():
    cache = ExtractionCache()
    cache.set("entities", "hi", ["a"], model="gpt-4")
    assert cache.get("entities", "hi", model="gpt-4o") is None
    assert cache.get("entities", "hi", model="gpt-4") == ["a"]


def test_disabled_cache_is_noop():
    cache = ExtractionCache()
    cache.enabled = False
    cache.set("entities", "hi", ["a"])
    assert cache.get("entities", "hi") is None


def test_unknown_namespace_is_ignored():
    cache = ExtractionCache()
    cache.set("nope", "hi", ["a"])  # warns, stores nothing
    assert cache.get("nope", "hi") is None


def test_get_stats_structure():
    cache = ExtractionCache(max_size=42)
    cache.set("entities", "a", [1])
    stats = cache.get_stats()
    assert set(stats) == {"entities", "relations", "triplets"}
    assert stats["entities"] == {"size": 1, "max_size": 42}


def test_get_stats_reports_injected_backend_limit(tmp_path):
    # get_stats() must reflect the injected backend's real eviction limit,
    # not the facade default.
    cache = ExtractionCache(backend=SqliteCacheBackend(_db(tmp_path), max_size=2))
    assert cache.get_stats()["entities"]["max_size"] == 2
    cache._backend.close()


def test_backward_compat_caches_proxy():
    # Existing callers/tests reach into ._caches / ._locks; keep that working.
    cache = ExtractionCache()
    cache.set("entities", "a", [1])
    assert "entities" in cache._caches
    assert len(cache._caches["entities"]) == 1
    assert "entities" in cache._locks
    cache._caches["entities"].clear()
    assert cache.get_stats()["entities"]["size"] == 0


# ---------------------------------------------------------------------------
# InMemoryBackend directly
# ---------------------------------------------------------------------------


def test_in_memory_ttl_expiry():
    backend = InMemoryBackend()
    backend.set("entities", "k", "v", ttl=-1)  # already expired
    assert backend.get("entities", "k") is None


def test_in_memory_ttl_none_never_expires():
    backend = InMemoryBackend()
    backend.set("entities", "k", "v", ttl=None)
    assert backend.get("entities", "k") == "v"


def test_in_memory_lru_eviction():
    backend = InMemoryBackend(max_size=2)
    backend.set("entities", "a", 1, ttl=None)
    backend.set("entities", "b", 2, ttl=None)
    backend.get("entities", "a")  # 'a' now most-recently-used
    backend.set("entities", "c", 3, ttl=None)  # evicts LRU -> 'b'
    assert backend.size("entities") == 2
    assert backend.get("entities", "b") is None
    assert backend.get("entities", "a") == 1
    assert backend.get("entities", "c") == 3


def test_zero_ttl_expires_immediately_on_both_backends(tmp_path):
    mem = InMemoryBackend()
    mem.set("entities", "k", "v", ttl=0)
    assert mem.get("entities", "k") is None

    sq = SqliteCacheBackend(_db(tmp_path))
    sq.set("entities", "k", "v", ttl=0)
    assert sq.get("entities", "k") is None
    sq.close()


# ---------------------------------------------------------------------------
# SqliteCacheBackend
# ---------------------------------------------------------------------------


def _db(tmp_path):
    return str(tmp_path / "cache.sqlite3")


def test_sqlite_roundtrip_and_size(tmp_path):
    backend = SqliteCacheBackend(_db(tmp_path))
    assert backend.get("entities", "k") is None
    backend.set("entities", "k", {"x": 1}, ttl=None)
    assert backend.get("entities", "k") == {"x": 1}
    assert backend.size("entities") == 1
    backend.close()


def test_sqlite_persists_across_restart(tmp_path):
    path = _db(tmp_path)
    cache = ExtractionCache(backend=SqliteCacheBackend(path))
    cache.set("entities", "hello", [{"name": "X"}], provider="openai", model="gpt-4")
    cache._backend.close()

    # Simulate a fresh process: new backend + new cache over the same file.
    reopened = ExtractionCache(backend=SqliteCacheBackend(path))
    assert reopened.get("entities", "hello", provider="openai", model="gpt-4") == [
        {"name": "X"}
    ]
    reopened._backend.close()


def test_sqlite_ttl_expiry(tmp_path):
    backend = SqliteCacheBackend(_db(tmp_path))
    backend.set("entities", "k", "v", ttl=-1)  # already expired
    assert backend.get("entities", "k") is None
    backend.close()


def test_sqlite_lru_eviction_bounds_size(tmp_path):
    backend = SqliteCacheBackend(_db(tmp_path), max_size=2)
    for k in ("a", "b", "c"):
        backend.set("entities", k, k, ttl=None)
    assert backend.size("entities") == 2
    backend.close()


def test_sqlite_clear(tmp_path):
    backend = SqliteCacheBackend(_db(tmp_path))
    backend.set("entities", "a", 1, ttl=None)
    backend.set("relations", "b", 2, ttl=None)
    backend.clear("entities")
    assert backend.size("entities") == 0
    assert backend.size("relations") == 1
    backend.clear()
    assert backend.size("relations") == 0
    backend.close()


def test_sqlite_custom_json_serializer(tmp_path):
    backend = SqliteCacheBackend(
        _db(tmp_path),
        serializer=lambda v: json.dumps(v).encode("utf-8"),
        deserializer=lambda b: json.loads(b.decode("utf-8")),
    )
    backend.set("entities", "k", {"a": [1, 2, 3]}, ttl=None)
    assert backend.get("entities", "k") == {"a": [1, 2, 3]}
    backend.close()


def test_sqlite_unserializable_value_is_skipped(tmp_path):
    backend = SqliteCacheBackend(
        _db(tmp_path),
        serializer=lambda v: json.dumps(v).encode("utf-8"),  # can't encode a set
        deserializer=lambda b: json.loads(b.decode("utf-8")),
    )
    backend.set("entities", "k", {1, 2, 3}, ttl=None)  # not JSON-serializable
    assert backend.get("entities", "k") is None  # skipped, no crash
    backend.close()


def test_sqlite_corrupt_payload_is_dropped(tmp_path):
    # serializer writes bytes the default pickle deserializer can't load.
    backend = SqliteCacheBackend(_db(tmp_path), serializer=lambda v: b"not-a-pickle")
    backend.set("entities", "k", "v", ttl=None)
    assert backend.get("entities", "k") is None
    # A corrupt row must be evicted, not left occupying capacity.
    assert backend.size("entities") == 0
    backend.close()


def test_sqlite_home_relative_path_is_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows expanduser
    backend = SqliteCacheBackend("~/nested/cache.sqlite3")
    backend.set("entities", "k", "v", ttl=None)
    assert backend.get("entities", "k") == "v"
    assert (tmp_path / "nested" / "cache.sqlite3").exists()
    backend.close()


def test_stable_fingerprint_is_process_independent():
    # Finding: relation/triplet cache keys must not depend on the built-in
    # process-randomized hash(). The deterministic fingerprint must be equal
    # across interpreters started with different PYTHONHASHSEED values.
    code = (
        "from semantica.semantic_extract.methods import _stable_fingerprint;"
        "print(_stable_fingerprint(['b', 'a', 'c']))"
    )
    out0 = subprocess.check_output(
        [sys.executable, "-c", code], env={**os.environ, "PYTHONHASHSEED": "0"}
    ).strip()
    out1 = subprocess.check_output(
        [sys.executable, "-c", code], env={**os.environ, "PYTHONHASHSEED": "1"}
    ).strip()
    assert out0 and out0 == out1


def _mp_writer(db_path, namespace, count):
    """Top-level worker (picklable) for the concurrency test."""
    from semantica.semantic_extract import SqliteCacheBackend as _Backend

    backend = _Backend(db_path)
    for i in range(count):
        backend.set(namespace, f"k{i}", {"v": i}, ttl=None)
    backend.close()


def test_sqlite_concurrent_workers_share_one_file(tmp_path):
    # Overlapping workers write distinct namespaces to the same file; the DB
    # must stay valid and every entry reusable afterwards.
    path = _db(tmp_path)
    ctx = mp.get_context("spawn")
    procs = [
        ctx.Process(target=_mp_writer, args=(path, ns, 20))
        for ns in ("entities", "relations", "triplets")
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(60)
    for p in procs:
        assert p.exitcode == 0

    reader = SqliteCacheBackend(path)
    for ns in ("entities", "relations", "triplets"):
        assert reader.size(ns) == 20
        assert reader.get(ns, "k5") == {"v": 5}
    reader.close()


# ---------------------------------------------------------------------------
# Security & reliability of the persistent file
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not hasattr(os, "getuid"), reason="POSIX permissions only")
def test_sqlite_new_db_created_private(tmp_path):
    path = _db(tmp_path)
    backend = SqliteCacheBackend(path)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600  # created 0o600 atomically, no widen-then-chmod window
    backend.close()


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_sqlite_rejects_symlinked_db(tmp_path):
    target = tmp_path / "target.sqlite3"
    target.write_bytes(b"")
    link = tmp_path / "link.sqlite3"
    os.symlink(target, link)
    with pytest.raises(PermissionError):
        SqliteCacheBackend(str(link))


def test_sqlite_write_error_is_contained(tmp_path):
    # A sqlite failure on write must be rolled back and swallowed (skipped
    # update), never propagated into the caller.
    backend = SqliteCacheBackend(_db(tmp_path))

    class _BoomConn:
        def __init__(self):
            self.rolled_back = False

        def execute(self, *a, **k):
            raise sqlite3.OperationalError("boom")

        def commit(self):
            raise AssertionError("commit must not run after a failed op")

        def rollback(self):
            self.rolled_back = True

    boom = _BoomConn()
    backend._conn = boom
    backend.set("entities", "k", "v", ttl=None)  # must not raise
    assert boom.rolled_back  # rollback happened (inside the lock scope)
    assert backend.get("entities", "k") is None  # read failure -> miss


def test_sqlite_read_error_is_contained(tmp_path):
    backend = SqliteCacheBackend(_db(tmp_path))

    class _BoomConn:
        def execute(self, *a, **k):
            raise sqlite3.OperationalError("boom")

        def rollback(self):
            pass

    backend._conn = _BoomConn()
    assert backend.get("entities", "k") is None  # miss, no crash


# ---------------------------------------------------------------------------
# Config-driven selection (methods.configure_cache)
# ---------------------------------------------------------------------------


def test_configure_cache_switches_backend(tmp_path):
    from semantica.semantic_extract import methods

    try:
        cache = methods.configure_cache(backend="sqlite", path=_db(tmp_path))
        assert isinstance(cache._backend, SqliteCacheBackend)
        assert methods._result_cache is cache
        cache.set("entities", "hi", ["v"])
        assert cache.get("entities", "hi") == ["v"]
    finally:
        # Restore the default in-memory global cache for other tests
        # (configure_cache closes the sqlite backend and mutates in place).
        methods.config.set_optimization(cache_path=None)
        methods.configure_cache(backend="memory")


# ---------------------------------------------------------------------------
# Security regression tests — issue #1668
# (safe default serialization: JSON codec, not pickle)
# ---------------------------------------------------------------------------


def _make_entity(
    text: str = "Apple Inc.",
    label: str = "ORG",
    start_char: int = 0,
    end_char: int = 10,
    confidence: float = 0.9,
    metadata: "dict | None" = None,
) -> Entity:
    return Entity(
        text=text,
        label=label,
        start_char=start_char,
        end_char=end_char,
        confidence=confidence,
        metadata=metadata if metadata is not None else {},
    )


def test_default_serializer_is_not_pickle(tmp_path):
    """The default SqliteCacheBackend must not use pickle.dumps / pickle.loads."""
    import pickle as _pickle

    backend = SqliteCacheBackend(_db(tmp_path))
    assert backend._serialize is not _pickle.dumps, (
        "default serializer must not be pickle.dumps"
    )
    assert backend._deserialize is not _pickle.loads, (
        "default deserializer must not be pickle.loads"
    )
    backend.close()


def test_sqlite_roundtrip_entity(tmp_path):
    """List[Entity] including None confidence and non-empty metadata survives a
    serialize → store → reload → deserialize cycle with the default codec."""
    backend = SqliteCacheBackend(_db(tmp_path))

    entities = [
        _make_entity(
            text="OpenAI",
            label="ORG",
            start_char=0,
            end_char=6,
            confidence=0.95,
            metadata={"provider": "openai", "extraction_method": "llm_typed"},
        ),
        _make_entity(
            text="Sam Altman",
            label="PERSON",
            start_char=10,
            end_char=20,
            confidence=None,  # explicitly absent confidence
            metadata={"confidence_source": "unavailable"},
        ),
    ]

    backend.set("entities", "k", entities, ttl=None)
    result = backend.get("entities", "k")

    assert result is not None
    assert len(result) == 2

    e0 = result[0]
    assert isinstance(e0, Entity)
    assert e0.text == "OpenAI"
    assert e0.label == "ORG"
    assert e0.start_char == 0
    assert e0.end_char == 6
    assert e0.confidence == 0.95
    assert e0.metadata == {"provider": "openai", "extraction_method": "llm_typed"}

    e1 = result[1]
    assert isinstance(e1, Entity)
    assert e1.text == "Sam Altman"
    assert e1.confidence is None  # None must round-trip, not become 0.0
    assert e1.metadata == {"confidence_source": "unavailable"}

    backend.close()


def test_sqlite_roundtrip_relation_with_nested_entities(tmp_path):
    """List[Relation] with nested Entity subject/object and temporal metadata
    survives the full codec round-trip including nested dataclass reconstruction."""
    backend = SqliteCacheBackend(_db(tmp_path))

    subj = _make_entity("Apple", "ORG", 0, 5, 0.9)
    obj = _make_entity("Beats", "ORG", 10, 15, 0.85)
    relations = [
        Relation(
            subject=subj,
            predicate="acquired",
            object=obj,
            confidence=0.97,
            context="Apple acquired Beats.",
            metadata={
                "provider": "openai",
                "model": "gpt-4",
                "extraction_method": "llm_typed",
                "valid_from": "2014-05-01",
                "valid_until": None,
                "temporal_confidence": 0.9,
                "temporal_source_text": "May 2014",
            },
        )
    ]

    backend.set("relations", "k", relations, ttl=None)
    result = backend.get("relations", "k")

    assert result is not None
    assert len(result) == 1

    r = result[0]
    assert isinstance(r, Relation)
    assert r.predicate == "acquired"
    assert r.confidence == 0.97
    assert r.context == "Apple acquired Beats."

    # Nested Entity reconstruction
    assert isinstance(r.subject, Entity)
    assert r.subject.text == "Apple"
    assert r.subject.label == "ORG"
    assert r.subject.confidence == 0.9

    assert isinstance(r.object, Entity)
    assert r.object.text == "Beats"
    assert r.object.confidence == 0.85

    # Temporal metadata (str, None, float values)
    assert r.metadata["valid_from"] == "2014-05-01"
    assert r.metadata["valid_until"] is None
    assert r.metadata["temporal_confidence"] == 0.9

    backend.close()


def test_sqlite_roundtrip_triplet(tmp_path):
    """List[Triplet] survives the default codec round-trip."""
    backend = SqliteCacheBackend(_db(tmp_path))

    triplets = [
        Triplet(
            subject="Apple",
            predicate="founded_by",
            object="Steve Jobs",
            confidence=0.99,
            metadata={
                "provider": "openai",
                "model": "gpt-4",
                "extraction_method": "llm_typed",
            },
        )
    ]

    backend.set("triplets", "k", triplets, ttl=None)
    result = backend.get("triplets", "k")

    assert result is not None
    assert len(result) == 1

    t = result[0]
    assert isinstance(t, Triplet)
    assert t.subject == "Apple"
    assert t.predicate == "founded_by"
    assert t.object == "Steve Jobs"
    assert t.confidence == 0.99
    assert t.metadata["extraction_method"] == "llm_typed"

    backend.close()


def test_sqlite_persists_entity_across_backend_instances(tmp_path):
    """Entity dataclass fields must survive close() + re-open (persistence
    regression for the new JSON codec)."""
    path = _db(tmp_path)

    entities = [
        _make_entity(
            text="Google",
            label="ORG",
            start_char=0,
            end_char=6,
            confidence=0.88,
            metadata={"extraction_method": "llm_typed", "synthetic": False},
        )
    ]

    first = SqliteCacheBackend(path)
    first.set("entities", "persist_key", entities, ttl=None)
    first.close()

    second = SqliteCacheBackend(path)
    result = second.get("entities", "persist_key")
    second.close()

    assert result is not None
    assert len(result) == 1
    e = result[0]
    assert isinstance(e, Entity)
    assert e.text == "Google"
    assert e.label == "ORG"
    assert e.confidence == 0.88
    assert e.metadata["synthetic"] is False


def test_legacy_pickle_row_is_treated_as_miss(tmp_path):
    """A BLOB written by pickle.dumps (legacy format) must be treated as a
    cache miss by the new default JSON deserializer.  It must NOT be passed
    to pickle.loads and must NOT raise — the row must be silently evicted."""
    import pickle as _pickle

    path = _db(tmp_path)

    # Use the new-default backend to create the schema.
    setup = SqliteCacheBackend(path)
    setup.close()

    # Bypass the backend and inject a pickle-serialized value directly.
    legacy_blob = _pickle.dumps({"x": 1})
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT OR REPLACE INTO cache"
        " (namespace, key, value, expires_at, last_access)"
        " VALUES (?, ?, ?, NULL, 0.0)",
        ("entities", "legacy_key", legacy_blob),
    )
    conn.commit()
    conn.close()

    # Re-open with the new default backend — must return None, not crash.
    backend = SqliteCacheBackend(path)
    result = backend.get("entities", "legacy_key")
    assert result is None, "legacy pickle row must be a miss, not an exception"
    # The corrupt row must be evicted, not left in the table.
    assert backend.size("entities") == 0, "legacy pickle row must be evicted"
    backend.close()


def test_malicious_pickle_payload_does_not_execute(tmp_path):
    """A crafted pickle payload injected directly into the DB BLOB must NOT
    execute through the default deserializer.

    The payload's __reduce__ would create a sentinel file if pickle.loads were
    called on it.  We assert the sentinel does NOT exist after backend.get(),
    confirming the JSON decoder never handed the bytes to pickle.
    """
    import pickle as _pickle

    sentinel = tmp_path / "PWNED"

    class _MaliciousPayload:
        """Pickle payload that creates a sentinel file on deserialization."""

        def __reduce__(self):
            # Would execute: open(str(sentinel), "w").close()
            return (open, (str(sentinel), "w"))

    path = _db(tmp_path)

    # Create the schema via the safe backend.
    setup = SqliteCacheBackend(path)
    setup.close()

    # Inject the malicious pickle bytes directly into the BLOB column.
    malicious_blob = _pickle.dumps(_MaliciousPayload())
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT OR REPLACE INTO cache"
        " (namespace, key, value, expires_at, last_access)"
        " VALUES (?, ?, ?, NULL, 0.0)",
        ("entities", "evil_key", malicious_blob),
    )
    conn.commit()
    conn.close()

    # Re-open with the new default backend and attempt to read the row.
    backend = SqliteCacheBackend(path)
    result = backend.get("entities", "evil_key")
    backend.close()

    # The sentinel must NOT have been created — payload was never executed.
    assert not sentinel.exists(), (
        "Malicious pickle payload executed through the default deserializer "
        "(sentinel file was created). pickle.loads must not be in the default path."
    )
    # The result must be a miss (JSON decode failed cleanly).
    assert result is None, "malicious row must be returned as a miss"


def test_custom_pickle_serializer_escape_hatch(tmp_path):
    """Users who explicitly supply pickle.dumps / pickle.loads as the
    serializer/deserializer must still get correct round-trip behaviour.
    The escape hatch must not be broken by this security fix."""
    import pickle as _pickle

    backend = SqliteCacheBackend(
        _db(tmp_path),
        serializer=_pickle.dumps,
        deserializer=_pickle.loads,
    )

    entities = [
        _make_entity(
            text="Microsoft",
            label="ORG",
            start_char=0,
            end_char=9,
            confidence=0.92,
            metadata={"extraction_method": "llm_typed"},
        )
    ]

    backend.set("entities", "k", entities, ttl=None)
    result = backend.get("entities", "k")

    assert result is not None
    assert len(result) == 1
    assert isinstance(result[0], Entity)
    assert result[0].text == "Microsoft"
    assert result[0].confidence == 0.92
    backend.close()



def test_metadata_dict_with_dunder_type_key_is_not_misreconstructed(tmp_path):
    """Metadata dicts whose ``__type__`` value matches a recognised dataclass
    name (``Entity``, ``Relation``, ``Triplet``) must NOT be reconstructed as
    a dataclass — they must round-trip as plain dicts.  The containing cache
    row must NOT be evicted (i.e. the result must not be a miss).

    This is the primary regression test for the codec-ambiguity fix: the
    encoder must use a private marker key (``__dc__``) for its own envelopes
    so that user-controlled ``__type__`` values in metadata are never
    interpreted as dispatch signals.
    """
    # Three independent backends, one per namespace, so each case is
    # isolated and size assertions are unambiguous.

    # --- entities namespace: metadata.__type__ == "Entity" ---
    b_ent = SqliteCacheBackend(_db(tmp_path) + ".ent")
    b_ent.set(
        "entities",
        "k",
        [
            _make_entity(
                text="Collision",
                label="ORG",
                start_char=0,
                end_char=9,
                confidence=0.7,
                metadata={
                    "__type__": "Entity",   # recognised name — must stay a dict
                    "text": "inner",
                    "label": "FAKE",
                    "start_char": 0,
                    "end_char": 5,
                    "confidence": 0.5,
                    "metadata": {},
                    "extra": "should survive",
                },
            )
        ],
        ttl=None,
    )
    result_ent = b_ent.get("entities", "k")
    # Row must NOT have been evicted.
    assert b_ent.size("entities") == 1, (
        "row was evicted — Entity __type__ in metadata caused deserialization failure"
    )
    b_ent.close()

    assert result_ent is not None, "__type__=Entity in metadata must not cause a miss"
    assert len(result_ent) == 1
    e = result_ent[0]
    assert isinstance(e, Entity), "outer item must be an Entity"
    assert e.text == "Collision"
    assert isinstance(e.metadata, dict), "metadata must remain a plain dict"
    assert e.metadata["__type__"] == "Entity", "__type__ key must be preserved"
    assert e.metadata["extra"] == "should survive"

    # --- relations namespace: metadata.__type__ == "Relation" ---
    b_rel = SqliteCacheBackend(_db(tmp_path) + ".rel")
    subj = _make_entity("A", "ORG", 0, 1, 0.9)
    obj = _make_entity("B", "ORG", 2, 3, 0.8)
    b_rel.set(
        "relations",
        "k",
        [
            Relation(
                subject=subj,
                predicate="knows",
                object=obj,
                confidence=0.9,
                context="ctx",
                metadata={
                    "__type__": "Relation",  # recognised name — must stay a dict
                    "subject": "not a real subject",
                    "predicate": "collision",
                    "note": "plain value",
                },
            )
        ],
        ttl=None,
    )
    result_rel = b_rel.get("relations", "k")
    assert b_rel.size("relations") == 1, (
        "row was evicted — Relation __type__ in metadata caused deserialization failure"
    )
    b_rel.close()

    assert result_rel is not None, "__type__=Relation in metadata must not cause a miss"
    assert len(result_rel) == 1
    r = result_rel[0]
    assert isinstance(r, Relation), "outer item must be a Relation"
    assert r.predicate == "knows"
    assert isinstance(r.metadata, dict), "metadata must remain a plain dict"
    assert r.metadata["__type__"] == "Relation", "__type__ key must be preserved"
    assert r.metadata["note"] == "plain value"

    # --- triplets namespace: metadata.__type__ == "Triplet" ---
    b_tri = SqliteCacheBackend(_db(tmp_path) + ".tri")
    b_tri.set(
        "triplets",
        "k",
        [
            Triplet(
                subject="S",
                predicate="P",
                object="O",
                confidence=0.95,
                metadata={
                    "__type__": "Triplet",  # recognised name — must stay a dict
                    "subject": "collision",
                    "predicate": "collision",
                    "object": "collision",
                    "note": "plain value",
                },
            )
        ],
        ttl=None,
    )
    result_tri = b_tri.get("triplets", "k")
    assert b_tri.size("triplets") == 1, (
        "row was evicted — Triplet __type__ in metadata caused deserialization failure"
    )
    b_tri.close()

    assert result_tri is not None, "__type__=Triplet in metadata must not cause a miss"
    assert len(result_tri) == 1
    t = result_tri[0]
    assert isinstance(t, Triplet), "outer item must be a Triplet"
    assert t.predicate == "P"
    assert isinstance(t.metadata, dict), "metadata must remain a plain dict"
    assert t.metadata["__type__"] == "Triplet", "__type__ key must be preserved"
    assert t.metadata["note"] == "plain value"


def test_metadata_dict_with_dunder_dc_key_is_not_misreconstructed(tmp_path):
    """A metadata dict containing a ``__dc__`` key must NOT be treated as a
    codec envelope — it must round-trip as a plain dict with all keys intact.

    The codec guard requires the *exact* two-key shape ``{"__dc__", "fields"}``
    with ``fields`` being a dict.  Any dict that merely *contains* ``__dc__``
    among other keys falls through to the plain-dict path unchanged.

    This mirrors ``test_metadata_dict_with_dunder_type_key_is_not_misreconstructed``
    but targets the current envelope marker rather than the legacy one.
    """
    # --- __dc__ without a "fields" peer (unknown-value case) ---
    b1 = SqliteCacheBackend(_db(tmp_path) + ".dc1")
    b1.set(
        "entities",
        "k",
        [
            _make_entity(
                text="Probe1",
                label="ORG",
                start_char=0,
                end_char=6,
                confidence=0.8,
                metadata={
                    "__dc__": "note",       # present but no "fields" sibling
                    "source": "manual",
                },
            )
        ],
        ttl=None,
    )
    r1 = b1.get("entities", "k")
    assert b1.size("entities") == 1, (
        "row evicted — __dc__ without 'fields' in metadata caused failure"
    )
    b1.close()

    assert r1 is not None, "__dc__ without 'fields' in metadata must not cause a miss"
    assert isinstance(r1[0], Entity)
    assert r1[0].text == "Probe1"
    assert isinstance(r1[0].metadata, dict), "metadata must remain a plain dict"
    assert r1[0].metadata["__dc__"] == "note", "__dc__ key must be preserved"
    assert r1[0].metadata["source"] == "manual"

    # --- __dc__ + "fields" present but with additional keys (not exact shape) ---
    b2 = SqliteCacheBackend(_db(tmp_path) + ".dc2")
    b2.set(
        "entities",
        "k",
        [
            _make_entity(
                text="Probe2",
                label="ORG",
                start_char=0,
                end_char=6,
                confidence=0.8,
                metadata={
                    "__dc__": "Entity",     # recognised name
                    "fields": {"text": "inner"},
                    "extra_key": "extra",   # third key breaks the exact-shape guard
                },
            )
        ],
        ttl=None,
    )
    r2 = b2.get("entities", "k")
    assert b2.size("entities") == 1, (
        "row evicted — __dc__+fields+extra_key in metadata caused failure"
    )
    b2.close()

    assert r2 is not None, "__dc__+fields+extra_key in metadata must not cause a miss"
    assert isinstance(r2[0], Entity)
    assert r2[0].text == "Probe2"
    assert isinstance(r2[0].metadata, dict), "metadata must remain a plain dict"
    assert r2[0].metadata["__dc__"] == "Entity", "__dc__ key must be preserved"
    assert r2[0].metadata["fields"] == {"text": "inner"}, "fields key must be preserved"
    assert r2[0].metadata["extra_key"] == "extra"
