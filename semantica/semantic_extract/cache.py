"""
Result Caching Module

This module provides caching mechanisms for extraction results to avoid redundant
computations and API calls. It implements an LRU (Least Recently Used) cache
with Time-To-Live (TTL) support.

Key Features:
    - LRU Caching: Evicts least recently used items when cache is full
    - TTL Support: Expires items after a configurable duration
    - Namespaced Caching: Separate caches for entities, relations, and triplets
    - Hash-based Keys: Uses stable hashing for text and parameters
    - Pluggable Backends: In-memory (default) or persistent (sqlite), selected
      without changing the ``ExtractionCache`` public API

Classes:
    - ExtractionCache: Main cache manager (owns key derivation + public API)
    - CacheBackend: Storage backend interface (owns persistence/expiry/eviction)
    - InMemoryBackend: Thread-safe in-memory LRU + TTL backend (historical default)
    - SqliteCacheBackend: Persistent backend backed by the stdlib ``sqlite3``
    - CacheItem: Container for cached data with metadata

Author: Semantica Contributors
License: MIT
"""

import copy
import dataclasses
import os
import stat
import time
import hashlib
import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from threading import Lock

from ..utils.logging import get_logger
from .types import Entity, Relation, Triplet

# The namespaces ExtractionCache manages. Kept as a module constant so backends
# and get_stats() agree on the set without hard-coding it in several places.
NAMESPACES = ("entities", "relations", "triplets")


# ---------------------------------------------------------------------------
# Default SQLite serialization codec (JSON-based, safe)
#
# The codec handles the three concrete value types stored by ExtractionCache:
#   List[Entity], List[Relation], List[Triplet]
#
# Dataclass instances are encoded as the *exact* two-key envelope:
#   {"__dc__": "<ClassName>", "fields": {<field>: <encoded-value>, ...}}
#
# A dict is treated as a codec envelope **only** when it has exactly these
# two keys and "fields" is itself a dict.  Any other dict — including one
# that merely happens to carry a ``__dc__`` key among other keys — falls
# through to the plain-dict path unchanged.  This means user metadata can
# freely contain ``__dc__``, ``__type__``, or any other key without risk of
# silent reconstruction or data loss.
#
# Plain dicts are encoded by recursing into their values without adding any
# wrapper, so their keys are never mistaken for envelope markers.
#
# All field values (str, int, float, bool, None, dict-of-primitives) are
# JSON-native, so no Python-specific serialisation is required.
# ---------------------------------------------------------------------------

# Sentinel frozenset used by _decode_value to recognise the exact envelope shape.
_ENVELOPE_KEYS = frozenset({"__dc__", "fields"})


def _encode_value(value: Any) -> Any:
    """Recursively encode *value* to a JSON-safe representation.

    Dataclass instances are represented as the exact two-key envelope
    ``{"__dc__": "<ClassName>", "fields": {…}}``.
    Lists are encoded element-wise.
    Plain dicts are encoded by recursing into their values — no wrapper is
    added, so user metadata keys (including ``__dc__`` or ``__type__``) are
    never reinterpreted by the decoder.
    Everything else is returned unchanged (it must already be
    JSON-serialisable; non-serialisable values surface as a ``TypeError``
    from ``json.dumps``, which ``SqliteCacheBackend.set`` already handles).
    """
    if isinstance(value, list):
        return [_encode_value(item) for item in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        # Encode as the exact two-key envelope so _decode_value can
        # unambiguously distinguish codec output from user data.
        return {
            "__dc__": type(value).__name__,
            "fields": {
                f.name: _encode_value(getattr(value, f.name))
                for f in dataclasses.fields(value)
            },
        }
    if isinstance(value, dict):
        # Recurse into dict values so nested dataclasses inside metadata are
        # also encoded.  Do NOT add any wrapper: the dict's own keys must be
        # preserved exactly and must never be confused with envelope markers.
        return {k: _encode_value(v) for k, v in value.items()}
    # Primitive — returned as-is.
    return value


def _is_envelope(raw: dict) -> bool:
    """Return True iff *raw* is the exact two-key dataclass envelope written
    by :func:`_encode_value`.

    The guard requires **all** of:
    - exactly two keys: ``__dc__`` and ``fields``
    - ``fields`` is a ``dict``

    Any dict with more keys (or without ``fields`` being a dict) is treated
    as ordinary user data, even if it contains a ``__dc__`` key.
    """
    return (
        raw.keys() == _ENVELOPE_KEYS
        and isinstance(raw.get("fields"), dict)
    )


def _decode_value(raw: Any) -> Any:
    """Reconstruct Python objects from the JSON-decoded representation.

    Dicts that satisfy the exact envelope shape ``{"__dc__": str,
    "fields": dict}`` (and nothing else) are dataclass envelopes written by
    :func:`_encode_value` and are reconstructed as the corresponding type.
    Any dict that merely *contains* a ``__dc__`` key among other keys falls
    through to the plain-dict path and is returned with all keys intact.
    Lists are decoded element-wise.
    Primitives are returned as-is.
    """
    if isinstance(raw, list):
        return [_decode_value(item) for item in raw]
    if isinstance(raw, dict) and _is_envelope(raw):
        # Exact codec envelope — reconstruct the dataclass.
        type_tag = raw["__dc__"]
        fields = {k: _decode_value(v) for k, v in raw["fields"].items()}
        if type_tag == "Entity":
            return Entity(**fields)
        if type_tag == "Relation":
            return Relation(**fields)
        if type_tag == "Triplet":
            return Triplet(**fields)
        # Unknown tag from a future codec version — return the decoded fields
        # dict so callers get the data rather than an opaque envelope.
        return fields
    if isinstance(raw, dict):
        # Plain dict (e.g. user metadata): recurse into values so any codec
        # envelopes nested inside are decoded, but preserve all keys —
        # including ``__dc__`` or ``__type__`` — unchanged.
        return {k: _decode_value(v) for k, v in raw.items()}
    # Primitive (str, int, float, bool, None) — returned as-is.
    return raw


def _cache_serialize(value: Any) -> bytes:
    """Default SQLite cache serializer.  Converts *value* to UTF-8 JSON bytes.

    Safe to deserialize from an untrusted file because ``json.loads`` does
    not execute arbitrary code.
    """
    return json.dumps(_encode_value(value), ensure_ascii=False).encode("utf-8")


def _cache_deserialize(data: bytes) -> Any:
    """Default SQLite cache deserializer.  Reconstructs Python objects from
    the UTF-8 JSON bytes produced by :func:`_cache_serialize`.

    Note: JSON has no tuple type, so any tuple-valued metadata field is
    returned as a list after a round-trip.  All values stored by the
    production extraction pipeline are str/int/float/bool/None, so this
    does not affect normal operation.
    """
    return _decode_value(json.loads(data.decode("utf-8")))


class CacheItem:
    """Container for cached data with metadata.

    Holds the value exactly as passed by the caller of ``__init__``.  It is
    the responsibility of the owner (``InMemoryBackend``) to pass an already-
    isolated snapshot so that the stored value is immune to mutation of the
    object the original caller passed to ``set()``.
    """

    def __init__(self, value: Any, ttl: Optional[int] = None):
        self.value = value
        self.timestamp = time.time()
        self.ttl = ttl

    def is_expired(self) -> bool:
        """Check if item has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl


class CacheBackend(ABC):
    """Storage backend for :class:`ExtractionCache`.

    A backend owns persistence, expiry and eviction for opaque
    ``(namespace, key) -> value`` entries. ``ExtractionCache`` owns key
    derivation (the stable SHA-256 hash over text + params) and the public
    API, so backends never see raw text or generation parameters — only the
    already-hashed key. This keeps the key policy in one place and lets a
    backend be swapped (in-memory vs persistent) with no behavioral change to
    callers.
    """

    @abstractmethod
    def get(self, namespace: str, key: str) -> Optional[Any]:
        """Return the cached value or ``None`` if missing/expired."""

    @abstractmethod
    def set(self, namespace: str, key: str, value: Any, ttl: Optional[int]) -> None:
        """Store ``value`` under ``(namespace, key)`` with an optional TTL (seconds)."""

    @abstractmethod
    def clear(self, namespace: Optional[str] = None) -> None:
        """Clear one namespace, or all namespaces when ``namespace`` is ``None``."""

    @abstractmethod
    def stats(self, namespace: str) -> Dict[str, int]:
        """Return backend statistics for ``namespace``.

        Must include at least ``size`` (stored entries) and ``max_size`` (the
        backend's own eviction limit) so callers see the limit actually in
        effect rather than a facade default. Implementations may add more keys.
        """

    def size(self, namespace: str) -> int:
        """Convenience: number of stored entries in ``namespace``."""
        return int(self.stats(namespace).get("size", 0))


class InMemoryBackend(CacheBackend):
    """Thread-safe in-memory LRU + TTL backend — the historical default.

    Preserves the original storage layout: one ``OrderedDict`` per namespace
    guarded by its own lock, LRU eviction at ``max_size``, and per-item TTL
    expiry checked lazily on read.
    """

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._caches: Dict[str, "OrderedDict[str, CacheItem]"] = {
            ns: OrderedDict() for ns in NAMESPACES
        }
        self._locks: Dict[str, Lock] = {ns: Lock() for ns in NAMESPACES}

    # Sentinel distinguishing "no entry under this key" from a stored None.
    _MISSING = object()

    def get(self, namespace: str, key: str) -> Optional[Any]:
        if namespace not in self._caches:
            return None

        # Phase 1: look up the stored snapshot under the lock.  Only the
        # reference is captured here so lock hold-time is O(1) regardless of
        # value size.  The deepcopy happens in phase 2, outside the lock.
        snapshot = self._MISSING
        with self._locks[namespace]:
            cache = self._caches[namespace]
            item = cache.get(key)
            if item is None:
                return None
            if item.is_expired():
                del cache[key]
                return None
            cache.move_to_end(key)  # mark as recently used
            snapshot = item.value

        # Phase 2: return a caller-owned copy.  deepcopy is done outside the
        # lock so a large result does not block concurrent reads on the same
        # namespace.  If the stored snapshot cannot be copied (e.g. a value
        # that slipped through CacheItem's own fallback), treat it as a miss
        # and evict rather than surface a corrupt object.
        try:
            return copy.deepcopy(snapshot)
        except Exception:
            with self._locks[namespace]:
                self._caches[namespace].pop(key, None)
            return None

    def set(self, namespace: str, key: str, value: Any, ttl: Optional[int]) -> None:
        if namespace not in self._caches:
            return

        # Prepare the cache-owned snapshot BEFORE acquiring the lock so that
        # a large deepcopy does not hold the namespace lock and block
        # concurrent readers (mirroring the get() two-phase design).
        # If deepcopy fails the value is stored as-is: the writer's result
        # still caches, and get() will treat the uncopyable entry as a miss
        # (evict + return None) rather than returning an aliased mutable value.
        try:
            snapshot = copy.deepcopy(value)
        except Exception:
            snapshot = value

        with self._locks[namespace]:
            cache = self._caches[namespace]
            if key in cache:
                cache.move_to_end(key)
            cache[key] = CacheItem(snapshot, ttl)
            if len(cache) > self.max_size:
                cache.popitem(last=False)  # evict least recently used

    def clear(self, namespace: Optional[str] = None) -> None:
        if namespace is not None:
            if namespace in self._caches:
                with self._locks[namespace]:
                    self._caches[namespace].clear()
        else:
            for ns in self._caches:
                with self._locks[ns]:
                    self._caches[ns].clear()

    def stats(self, namespace: str) -> Dict[str, int]:
        cache = self._caches.get(namespace)
        return {
            "size": len(cache) if cache is not None else 0,
            "max_size": self.max_size,
        }


class SqliteCacheBackend(CacheBackend):
    """Persistent cache backend backed by the standard-library ``sqlite3``.

    Unlike :class:`InMemoryBackend`, entries survive a process restart, so a
    fresh process (CI job, notebook kernel, batch worker, extraction
    subprocess) reuses previous results instead of re-paying every LLM call.

    **Default serialization.** Values are stored as UTF-8 JSON with a thin
    tagged-envelope codec that reconstructs :class:`~semantica.semantic_extract.types.Entity`,
    :class:`~semantica.semantic_extract.types.Relation`, and
    :class:`~semantica.semantic_extract.types.Triplet` instances transparently.
    JSON is not executable, so a tampered cache file cannot achieve arbitrary
    code execution through the default deserializer.

    **Custom serializer/deserializer.** Pass explicit ``serializer`` and
    ``deserializer`` callables to override the default codec.  If you supply
    ``pickle.dumps`` / ``pickle.loads`` you accept full responsibility for the
    trust model: ``pickle`` deserializes arbitrary Python objects and a
    file an attacker can write is a remote-code-execution vector.

    **File security.** The backend creates the database file **atomically**
    with ``0o600`` (``O_CREAT | O_EXCL``, no validate-then-open window) and,
    when reusing an existing file, rejects symlinks, non-regular files, and
    files owned by another user — raising so the caller falls back to the
    in-memory backend.

    Concurrency/reliability: TTL and LRU (by last access) mirror
    :class:`InMemoryBackend`. A ``busy_timeout`` plus bounded retry handles
    cross-process lock contention; every sqlite failure rolls back within the
    same lock scope and is contained — reads degrade to a miss and writes to a
    skipped update, never aborting extraction.

    Cache-key invalidation is owned by :class:`ExtractionCache`: the key is a
    SHA-256 over the input text and parameters (provider, model, generation
    params, ...), so changing any of them yields a different key and old entries
    are simply bypassed rather than served stale — including after a model
    upgrade. There is no schema-version stamp; if a serialized value's shape
    changes incompatibly, point ``cache_path`` at a fresh file (or ``clear()``).
    """

    def __init__(
        self,
        db_path: str,
        max_size: int = 1000,
        serializer: Callable[[Any], bytes] = _cache_serialize,
        deserializer: Callable[[bytes], Any] = _cache_deserialize,
        busy_timeout: float = 5.0,
        max_retries: int = 3,
        retry_backoff: float = 0.05,
    ):
        self.max_size = max_size
        self._serialize = serializer
        self._deserialize = deserializer
        self._busy_timeout = busy_timeout
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._lock = threading.Lock()
        self.logger = get_logger("extraction_cache.sqlite")

        if db_path == ":memory:":
            self.db_path = ":memory:"
        else:
            # Expand "~" and make absolute exactly once (a "~/..." path must be
            # expanded before it reaches sqlite). Do NOT resolve() — that would
            # follow a symlinked final component we specifically want to reject.
            self.db_path = os.path.abspath(os.path.expanduser(db_path))
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._create_or_validate_secure_file(self.db_path)

        self._conn = sqlite3.connect(
            self.db_path, check_same_thread=False, timeout=self._busy_timeout
        )
        self._conn.execute(f"PRAGMA busy_timeout={int(self._busy_timeout * 1000)}")
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:  # e.g. :memory: does not support WAL
            pass
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache ("
            "  namespace TEXT NOT NULL,"
            "  key TEXT NOT NULL,"
            "  value BLOB NOT NULL,"
            "  expires_at REAL,"
            "  last_access REAL NOT NULL,"
            "  PRIMARY KEY (namespace, key)"
            ")"
        )
        # Index supporting the LRU eviction scan (ORDER BY last_access per ns).
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cache_lru "
            "ON cache (namespace, last_access)"
        )
        self._conn.commit()

    def _create_or_validate_secure_file(self, path: str) -> None:
        """Create the db file atomically with ``0o600``, or validate an existing one.

        Using ``O_CREAT | O_EXCL`` closes the TOCTOU/permission window of a
        validate-then-open-then-chmod sequence: a fresh file exists with private
        permissions from the very first moment. An existing file is only reused
        if it is a regular (non-symlink) file owned by the current user.
        """
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            return  # freshly created, private
        except FileExistsError:
            pass  # fall through to validate the existing file

        try:
            info = os.lstat(path)  # lstat: do not follow a symlinked final path
        except OSError as exc:
            raise PermissionError(f"Cannot stat cache database {path}: {exc}")

        if stat.S_ISLNK(info.st_mode):
            raise PermissionError(f"Refusing to use symlinked cache database: {path}")
        if not stat.S_ISREG(info.st_mode):
            raise PermissionError(f"Cache database is not a regular file: {path}")
        if hasattr(os, "getuid") and info.st_uid != os.getuid():  # POSIX only
            raise PermissionError(
                f"Refusing to use cache database owned by another user: {path}"
            )

    def _rollback_locked(self) -> None:
        """Roll back the current transaction. Caller MUST hold ``self._lock``
        so a later request cannot commit over a failed one on the shared conn."""
        try:
            self._conn.rollback()
        except sqlite3.Error:
            pass

    def _write_locked(self, operation: Callable[[sqlite3.Connection], None]) -> bool:
        """Run a write ``operation`` + commit under the lock, rolling back within
        the same lock scope on failure. Retries on 'database is locked' with
        bounded backoff (sleeping outside the lock). Returns success."""
        last_exc: Optional[sqlite3.Error] = None
        for attempt in range(self._max_retries):
            retryable = False
            with self._lock:
                try:
                    operation(self._conn)
                    self._conn.commit()
                    return True
                except sqlite3.OperationalError as exc:
                    self._rollback_locked()
                    last_exc = exc
                    retryable = "locked" in str(exc).lower()
                except sqlite3.Error as exc:
                    self._rollback_locked()
                    last_exc = exc
            if not retryable or attempt == self._max_retries - 1:
                break
            time.sleep(self._retry_backoff * (2**attempt))
        self.logger.warning(f"sqlite cache write failed (skipped): {last_exc}")
        return False

    def get(self, namespace: str, key: str) -> Optional[Any]:
        now = time.time()
        with self._lock:
            try:
                row = self._conn.execute(
                    "SELECT value, expires_at FROM cache WHERE namespace=? AND key=?",
                    (namespace, key),
                ).fetchone()
            except sqlite3.Error as exc:
                self._rollback_locked()
                self.logger.warning(f"sqlite cache read failed (miss): {exc}")
                return None
            if row is None:
                return None
            value_blob, expires_at = row
            # ttl=0 -> expires_at == now: treat as expired (use <=), matching the
            # in-memory backend.
            if expires_at is not None and expires_at <= now:
                try:
                    self._conn.execute(
                        "DELETE FROM cache WHERE namespace=? AND key=?",
                        (namespace, key),
                    )
                    self._conn.commit()
                except sqlite3.Error as exc:
                    self._rollback_locked()
                    self.logger.warning(f"sqlite expired-entry cleanup failed: {exc}")
                return None

        # Deserialize OUTSIDE the lock but BEFORE bumping last_access: a
        # corrupt/incompatible row must not stay "recently used" (which would
        # keep it from being evicted), and must be dropped.
        try:
            value = self._deserialize(value_blob)
        except Exception as exc:
            self.logger.warning(
                f"Failed to deserialize cached value; dropping row: {exc}"
            )
            with self._lock:
                try:
                    self._conn.execute(
                        "DELETE FROM cache WHERE namespace=? AND key=?",
                        (namespace, key),
                    )
                    self._conn.commit()
                except sqlite3.Error:
                    self._rollback_locked()
            return None

        with self._lock:
            try:
                self._conn.execute(
                    "UPDATE cache SET last_access=? WHERE namespace=? AND key=?",
                    (now, namespace, key),
                )
                self._conn.commit()
            except sqlite3.Error as exc:  # non-fatal: value is already in hand
                self._rollback_locked()
                self.logger.debug(f"sqlite last_access update failed: {exc}")
        return value

    def set(self, namespace: str, key: str, value: Any, ttl: Optional[int]) -> None:
        now = time.time()
        # ttl=0 must expire immediately (parity with InMemoryBackend), so guard
        # on "is None" rather than truthiness.
        expires_at = now + ttl if ttl is not None else None
        try:
            blob = self._serialize(value)
        except Exception as exc:  # unserializable value — skip caching, never crash
            self.logger.warning(f"Failed to serialize value for caching: {exc}")
            return

        def operation(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT INTO cache (namespace, key, value, expires_at, last_access) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(namespace, key) DO UPDATE SET "
                "  value=excluded.value,"
                "  expires_at=excluded.expires_at,"
                "  last_access=excluded.last_access",
                (namespace, key, blob, expires_at, now),
            )
            count = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE namespace=?", (namespace,)
            ).fetchone()[0]
            if count > self.max_size:
                conn.execute(
                    "DELETE FROM cache WHERE rowid IN ("
                    "  SELECT rowid FROM cache WHERE namespace=? "
                    "  ORDER BY last_access ASC LIMIT ?"
                    ")",
                    (namespace, count - self.max_size),
                )

        self._write_locked(operation)

    def clear(self, namespace: Optional[str] = None) -> None:
        def operation(conn: sqlite3.Connection) -> None:
            if namespace is None:
                conn.execute("DELETE FROM cache")
            else:
                conn.execute("DELETE FROM cache WHERE namespace=?", (namespace,))

        self._write_locked(operation)

    def stats(self, namespace: str) -> Dict[str, int]:
        with self._lock:
            try:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM cache WHERE namespace=?", (namespace,)
                ).fetchone()
                size = int(row[0]) if row else 0
            except sqlite3.Error as exc:
                self._rollback_locked()
                self.logger.warning(f"sqlite cache stats failed: {exc}")
                size = 0
        return {"size": size, "max_size": self.max_size}

    def close(self) -> None:
        """Close the underlying connection (safe to call more than once)."""
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass


class ExtractionCache:
    """
    LRU Cache for extraction results.

    Owns stable key derivation and the public ``get``/``set``/``clear`` API;
    delegates storage to a pluggable :class:`CacheBackend`. Defaults to a
    thread-safe in-memory backend, preserving the original behavior. Pass a
    persistent backend (e.g. :class:`SqliteCacheBackend`) to survive restarts.
    """

    def __init__(
        self,
        max_size: int = 1000,
        ttl: int = 3600,
        backend: Optional[CacheBackend] = None,
    ):
        """
        Initialize the cache.

        Args:
            max_size: Maximum number of items to store per namespace (used by
                the default in-memory backend)
            ttl: Time to live in seconds (default 1 hour)
            backend: Storage backend. Defaults to :class:`InMemoryBackend`.
        """
        self.max_size = max_size
        self.ttl = ttl
        self.logger = get_logger("extraction_cache")
        self.enabled = True
        self._backend: CacheBackend = (
            backend if backend is not None else InMemoryBackend(max_size=max_size)
        )

    # Backward-compat: some callers/tests reach into the historical internal
    # attributes. Proxy them to the backend when it exposes them (the default
    # in-memory backend does); otherwise present empty mappings.
    @property
    def _caches(self) -> Dict[str, Any]:
        return getattr(self._backend, "_caches", {})

    @property
    def _locks(self) -> Dict[str, Any]:
        return getattr(self._backend, "_locks", {})

    def _generate_key(self, text: str, **params) -> str:
        """
        Generate a stable cache key based on text and parameters.

        Note: Sensitive parameters like 'api_key' are excluded from the cache key
        to prevent security risks and ensure cache sharing where appropriate.
        """
        # Filter out sensitive keys. Exact-match (not substring) so legitimate
        # params such as "max_tokens" are never dropped.
        sensitive_keys = {
            "api_key",
            "apikey",
            "api_secret",
            "token",
            "access_token",
            "refresh_token",
            "session_token",
            "bearer_token",
            "password",
            "secret",
            "client_secret",
            "private_key",
            "auth",
            "authorization",
            "credential",
            "credentials",
        }
        filtered_params = {
            k: v for k, v in params.items() if k.lower() not in sensitive_keys
        }

        # Create a stable string representation of params
        # Sort keys to ensure consistent ordering
        param_str = json.dumps(filtered_params, sort_keys=True, default=str)

        # Combine text and params
        content = f"{text}|{param_str}"

        # Return hash (SHA-256 for better security than MD5)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def get(self, namespace: str, text: str, **params) -> Optional[Any]:
        """
        Retrieve item from cache.

        Args:
            namespace: Cache namespace ("entities", "relations", "triplets")
            text: Input text used for extraction
            **params: Extraction parameters used

        Returns:
            Cached result or None if not found/expired
        """
        if not self.enabled:
            return None

        if namespace not in NAMESPACES:
            return None

        key = self._generate_key(text, **params)
        return self._backend.get(namespace, key)

    def set(self, namespace: str, text: str, value: Any, **params) -> None:
        """
        Add item to cache.

        Args:
            namespace: Cache namespace
            text: Input text
            value: Result to cache
            **params: Extraction parameters
        """
        if not self.enabled:
            return

        if namespace not in NAMESPACES:
            self.logger.warning(f"Unknown cache namespace: {namespace}")
            return

        key = self._generate_key(text, **params)
        self._backend.set(namespace, key, value, self.ttl)

    def clear(self, namespace: Optional[str] = None):
        """Clear cache(s)."""
        self._backend.clear(namespace)

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """Get cache statistics (delegated to the backend so the reported
        ``max_size`` reflects the limit actually in effect)."""
        return {ns: dict(self._backend.stats(ns)) for ns in NAMESPACES}


# Global cache instance
extraction_cache = ExtractionCache()
