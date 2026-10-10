"""Event-controlled regressions for backend/mirror operation ordering (#1907)."""

import copy
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from semantica.context.erasure import (
    STATUS_ERASED,
    STATUS_FAILED,
    STATUS_UNSUPPORTED,
    ErasureCoordinator,
)
from semantica.vector_store import VectorStore

VECTOR_ID = "vec_0"
OLD_VECTOR = np.array([1.0, 0.0, 0.0], dtype=np.float32)
NEW_VECTOR = np.array([0.0, 1.0, 0.0], dtype=np.float32)
UPDATED_VECTOR = np.array([0.0, 0.0, 1.0], dtype=np.float32)
OLD_METADATA = {"version": "old"}
NEW_METADATA = {"version": "new"}
UPDATED_METADATA = {"version": "updated"}
TIMEOUT = 5


class _ObservedOperationLock:
    """Signal contention so the test can schedule a blocked competitor.

    Before the fix the guard is unused, and the competitor signals completion
    instead. Both cases let the test release the paused backend without sleeps
    or a timing-dependent negative assertion.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self.contended = threading.Event()

    def __enter__(self):
        if not self._lock.acquire(blocking=False):
            self.contended.set()
            self._lock.acquire()
        return self

    def __exit__(self, *exc):
        self._lock.release()


class _Backend:
    """A real record store that can pause after a mutation or index write."""

    def __init__(self):
        self.vectors = {}
        self.metadata = {}
        self.pause_operation = None
        self.paused = threading.Event()
        self.resume = threading.Event()
        self.before_operation = lambda: None

    def _pause(self, operation):
        if operation == self.pause_operation:
            self.pause_operation = None
            self.paused.set()
            assert self.resume.wait(TIMEOUT), "paused backend was not released"

    def add_vectors(self, vectors, metadata=None, ids=None):
        self.before_operation()
        for vector_id, vector, meta in zip(ids, vectors, metadata):
            self.vectors[vector_id] = vector.copy()
            self.metadata[vector_id] = copy.deepcopy(meta)
        self._pause("store")
        return ids

    def delete_vectors(self, ids):
        self.before_operation()
        for vector_id in ids:
            self.vectors.pop(vector_id, None)
            self.metadata.pop(vector_id, None)
        self._pause("delete")
        return {"deleted": True}

    def update(self, ids, vectors, metadata=None):
        self.before_operation()
        for vector_id, vector in zip(ids, vectors):
            if vector_id in self.vectors:
                self.vectors[vector_id] = vector.copy()
        if metadata is not None:
            for vector_id, meta in zip(ids, metadata):
                if vector_id in self.metadata:
                    self.metadata[vector_id] = copy.deepcopy(meta)
        self._pause("update")
        return True

    def save_index(self, path):
        self.before_operation()
        data = {
            "vectors": {key: vector.tolist() for key, vector in self.vectors.items()},
            "metadata": self.metadata,
        }
        Path(path).write_text(json.dumps(data), encoding="utf-8")
        self._pause("save")

    def load_index(self, path):
        self.before_operation()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.vectors = {
            key: np.array(vector, dtype=np.float32)
            for key, vector in data["vectors"].items()
        }
        self.metadata = data["metadata"]
        self._pause("load")


def _make_store():
    with patch.object(VectorStore, "_init_backend_store"):
        store = VectorStore(backend="faiss", dimension=3)
    backend = _Backend()
    store._backend_store = backend
    store._operation_lock = _ObservedOperationLock()
    store.store_vectors([OLD_VECTOR], [OLD_METADATA], ids=[VECTOR_ID])
    return store, backend


def _mutate(store, operation):
    if operation == "store":
        return store.store_vectors([NEW_VECTOR], [NEW_METADATA], ids=[VECTOR_ID])
    if operation == "update":
        return store.update_vectors([VECTOR_ID], [UPDATED_VECTOR], [UPDATED_METADATA])
    if operation == "erase":
        receipt = ErasureCoordinator(vector_store=store).erase_entity(VECTOR_ID)
        assert receipt.stores["vectors"]["status"] == STATUS_ERASED
        return receipt
    assert operation == "delete"
    return store.delete_vectors([VECTOR_ID])


def _overlap(store, backend, paused_operation, first, second):
    """Run the competitor after backend I/O but before mirror publication."""
    backend.pause_operation = paused_operation
    competitor_ready = store._operation_lock.contended
    competitor_ready.clear()

    def compete():
        try:
            return second()
        finally:
            competitor_ready.set()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(first)
        try:
            assert backend.paused.wait(TIMEOUT), "first operation did not pause"
            second_future = executor.submit(compete)
            assert competitor_ready.wait(TIMEOUT), "competitor did not run"
        finally:
            backend.resume.set()
        return first_future.result(TIMEOUT), second_future.result(TIMEOUT)


def _assert_records(store, backend, expected):
    assert set(store.vectors) == set(backend.vectors) == set(expected)
    assert set(store.metadata) == set(backend.metadata) == set(expected)
    for vector_id, (vector, metadata) in expected.items():
        np.testing.assert_array_equal(store.vectors[vector_id], vector)
        np.testing.assert_array_equal(backend.vectors[vector_id], vector)
        assert store.metadata[vector_id] == backend.metadata[vector_id] == metadata


def _expected(operation):
    if operation in ("delete", "erase"):
        return {}
    if operation == "store":
        return {VECTOR_ID: (NEW_VECTOR, NEW_METADATA)}
    assert operation == "update"
    return {VECTOR_ID: (UPDATED_VECTOR, UPDATED_METADATA)}


def _assert_saved(path, expected):
    reloaded, backend = _make_store()
    reloaded.load(str(path))
    _assert_records(reloaded, backend, expected)


@pytest.mark.parametrize("deletion", ["delete", "erase"])
@pytest.mark.parametrize("first_operation", ["delete", "store"])
def test_same_id_insert_and_delete_follow_backend_order(deletion, first_operation):
    store, backend = _make_store()
    first = deletion if first_operation == "delete" else "store"
    second = "store" if first_operation == "delete" else deletion

    _overlap(
        store,
        backend,
        first_operation,
        lambda: _mutate(store, first),
        lambda: _mutate(store, second),
    )

    _assert_records(store, backend, _expected(second))


@pytest.mark.parametrize("backend_name", ["faiss", "sqlite"])
@pytest.mark.parametrize("deletion", ["delete", "erase"])
@pytest.mark.parametrize("first_operation", ["delete", "store"])
def test_real_backend_insert_and_delete_order(
    tmp_path, backend_name, deletion, first_operation
):
    pytest.importorskip("faiss" if backend_name == "faiss" else "sqlite_vec")
    config = (
        {"db_path": str(tmp_path / "vectors.db")} if backend_name == "sqlite" else {}
    )
    with patch("semantica.vector_store.vector_store.EmbeddingGenerator"):
        store = VectorStore(
            backend=backend_name,
            dimension=3,
            **config,
        )
    store._operation_lock = _ObservedOperationLock()
    backend = store._backend_store
    gate = _Backend()
    first = deletion if first_operation == "delete" else "store"
    second = "store" if first_operation == "delete" else deletion
    if first_operation == "delete":
        store.store_vectors([OLD_VECTOR], [OLD_METADATA], ids=[VECTOR_ID])
        method_name = "delete_vectors" if backend_name == "faiss" else "delete"
    else:
        method_name = "add_vectors" if backend_name == "faiss" else "add"
    original = getattr(backend, method_name)

    def mutate_then_pause(*args, **kwargs):
        result = original(*args, **kwargs)
        gate._pause(first_operation)
        return result

    try:
        with patch.object(backend, method_name, mutate_then_pause):
            _overlap(
                store,
                gate,
                first_operation,
                lambda: _mutate(store, first),
                lambda: _mutate(store, second),
            )

        assert set(store.vectors) == set(store.metadata) == set(_expected(second))
        if second == "store":
            np.testing.assert_array_equal(store.vectors[VECTOR_ID], NEW_VECTOR)
            np.testing.assert_array_equal(backend.get_vector(VECTOR_ID), NEW_VECTOR)
            assert store.metadata[VECTOR_ID] == NEW_METADATA
            assert backend.get_metadata(VECTOR_ID) == NEW_METADATA
        else:
            assert backend.get_vector(VECTOR_ID) is None
            assert backend.get_metadata(VECTOR_ID) is None
    finally:
        if backend_name == "sqlite":
            backend.close()


@pytest.mark.parametrize("first_operation", ["store", "update"])
def test_same_id_insert_and_update_follow_backend_order(first_operation):
    store, backend = _make_store()
    second = "update" if first_operation == "store" else "store"

    _overlap(
        store,
        backend,
        first_operation,
        lambda: _mutate(store, first_operation),
        lambda: _mutate(store, second),
    )

    _assert_records(store, backend, _expected(second))


@pytest.mark.parametrize("mutation", ["store", "delete", "erase", "update"])
def test_save_waits_for_backend_mutation_and_mirror_publication(tmp_path, mutation):
    store, backend = _make_store()

    _overlap(
        store,
        backend,
        "delete" if mutation == "erase" else mutation,
        lambda: _mutate(store, mutation),
        lambda: store.save(str(tmp_path)),
    )

    _assert_records(store, backend, _expected(mutation))
    _assert_saved(tmp_path, _expected(mutation))


@pytest.mark.parametrize("mutation", ["store", "delete", "erase", "update"])
def test_mutation_waits_for_index_and_mirror_to_be_saved(tmp_path, mutation):
    store, backend = _make_store()

    _overlap(
        store,
        backend,
        "save",
        lambda: store.save(str(tmp_path)),
        lambda: _mutate(store, mutation),
    )

    _assert_records(store, backend, _expected(mutation))
    _assert_saved(tmp_path, {VECTOR_ID: (OLD_VECTOR, OLD_METADATA)})


def test_load_waits_for_an_inflight_mutation(tmp_path):
    store, backend = _make_store()
    store.save(str(tmp_path))

    _overlap(
        store,
        backend,
        "store",
        lambda: _mutate(store, "store"),
        lambda: store.load(str(tmp_path)),
    )

    _assert_records(store, backend, {VECTOR_ID: (OLD_VECTOR, OLD_METADATA)})


def test_backend_io_does_not_hold_the_mirror_lock(tmp_path):
    store, backend = _make_store()

    def probe_mirror_lock():
        acquired = store._inmemory_lock.acquire(blocking=False)
        if acquired:
            store._inmemory_lock.release()
        return acquired

    with ThreadPoolExecutor(max_workers=1) as executor:

        def assert_unlocked():
            assert executor.submit(probe_mirror_lock).result(TIMEOUT)

        backend.before_operation = assert_unlocked
        _mutate(store, "store")
        _mutate(store, "update")
        store.save(str(tmp_path))
        _mutate(store, "delete")
        store.load(str(tmp_path))
        _mutate(store, "erase")


class _InmemoryIndexer(_Backend):
    def create_index(self, vectors, ids):
        self.vectors = {
            vector_id: vector.copy() for vector_id, vector in zip(ids, vectors)
        }


def _make_inmemory_store(indexer):
    with (
        patch(
            "semantica.vector_store.vector_store.VectorIndexer", return_value=indexer
        ),
        patch("semantica.vector_store.vector_store.VectorRetriever"),
        patch("semantica.vector_store.vector_store.EmbeddingGenerator"),
    ):
        store = VectorStore(backend="inmemory", dimension=3)
    store._operation_lock = _ObservedOperationLock()
    return store


def test_inmemory_save_keeps_index_and_mirror_in_the_same_state(tmp_path):
    indexer = _InmemoryIndexer()
    store = _make_inmemory_store(indexer)
    assert store.store_vectors([OLD_VECTOR], [OLD_METADATA]) == [VECTOR_ID]

    _overlap(
        store,
        indexer,
        "save",
        lambda: store.save(str(tmp_path)),
        lambda: store.update_vectors([VECTOR_ID], [NEW_VECTOR], [NEW_METADATA]),
    )

    np.testing.assert_array_equal(store.vectors[VECTOR_ID], NEW_VECTOR)
    assert store.metadata[VECTOR_ID] == NEW_METADATA
    reloaded_indexer = _InmemoryIndexer()
    reloaded = _make_inmemory_store(reloaded_indexer)
    reloaded.load(str(tmp_path))
    np.testing.assert_array_equal(reloaded.vectors[VECTOR_ID], OLD_VECTOR)
    np.testing.assert_array_equal(reloaded_indexer.vectors[VECTOR_ID], OLD_VECTOR)
    assert reloaded.metadata[VECTOR_ID] == OLD_METADATA


@pytest.mark.parametrize(
    "result,accepted",
    [
        (None, True),
        (0, True),
        ({"deleted": True}, True),
        (False, False),
        ({"deleted": False}, False),
        ({"status": "UpdateStatus.FAILED"}, False),
    ],
)
def test_erasure_preserves_backend_result_handling(result, accepted):
    store, backend = _make_store()
    delete = backend.delete_vectors

    def delete_with_result(ids):
        if accepted:
            delete(ids)
        return result

    backend.delete_vectors = delete_with_result
    receipt = ErasureCoordinator(vector_store=store).erase_entity(VECTOR_ID)

    assert receipt.stores["vectors"]["status"] == (
        STATUS_ERASED if accepted else STATUS_FAILED
    )
    if isinstance(result, dict):
        assert receipt.stores["vectors"]["backend_result"] == result
    _assert_records(
        store, backend, {} if accepted else {VECTOR_ID: (OLD_VECTOR, OLD_METADATA)}
    )


@pytest.mark.parametrize(
    "error,status",
    [
        (NotImplementedError("unsupported"), STATUS_UNSUPPORTED),
        (RuntimeError("backend failed"), STATUS_FAILED),
    ],
)
def test_failed_erasure_keeps_the_mirror_and_releases_the_guard(error, status):
    store, backend = _make_store()

    with patch.object(backend, "delete_vectors", side_effect=error):
        receipt = ErasureCoordinator(vector_store=store).erase_entity(VECTOR_ID)
    assert receipt.stores["vectors"]["status"] == status
    _assert_records(store, backend, {VECTOR_ID: (OLD_VECTOR, OLD_METADATA)})

    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(_mutate, store, "store").result(TIMEOUT)
    _assert_records(store, backend, _expected("store"))
