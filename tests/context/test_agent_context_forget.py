"""Regression tests for issue #1597.

``AgentContext.forget(days_old=N)`` is documented as "Delete memories older
than N days", but it filtered on ``start_date`` (a lower bound), so
``clear_memory`` deleted memories *newer* than the cutoff and kept the
stale ones — the exact opposite of the contract.
"""

from datetime import datetime, timedelta, timezone

import pytest

from semantica.context import AgentContext, ContextGraph
from semantica.vector_store import VectorStore


def _context() -> AgentContext:
    # retention_days=None: the store-time retention purge would otherwise
    # delete the deliberately-aged fixture on insert.
    return AgentContext(
        vector_store=VectorStore(backend="inmemory", dimension=64),
        knowledge_graph=ContextGraph(),
        retention_days=None,
        decision_tracking=False,
        kg_algorithms=False,
        vector_store_features=False,
    )


def test_forget_days_old_deletes_old_and_keeps_new():
    """forget(days_old=90) must purge stale memories, not recent ones.

    Fails before the fix: the 100-day-old memory survives and the fresh
    one is deleted.
    """
    ctx = _context()
    old_id = ctx._memory.store(
        "old memory",
        timestamp=datetime.now(timezone.utc) - timedelta(days=100),
    )
    new_id = ctx._memory.store(
        "new memory",
        timestamp=datetime.now(timezone.utc),
    )

    deleted = ctx.forget(days_old=90)

    assert deleted == 1
    assert ctx.get_memory(old_id) is None
    assert ctx.get_memory(new_id) is not None


def test_forget_days_old_boundary_keeps_everything_recent():
    """With no stale memories, forget(days_old=N) deletes nothing."""
    ctx = _context()
    fresh_id = ctx._memory.store(
        "fresh memory",
        timestamp=datetime.now(timezone.utc),
    )

    assert ctx.forget(days_old=90) == 0
    assert ctx.get_memory(fresh_id) is not None


def test_forget_negative_days_old_is_rejected():
    """A negative age would build a future cutoff and wipe recent memories."""
    ctx = _context()
    fresh_id = ctx._memory.store(
        "fresh memory",
        timestamp=datetime.now(timezone.utc),
    )

    with pytest.raises(ValueError, match="days_old must be non-negative"):
        ctx.forget(days_old=-1)
    assert ctx.get_memory(fresh_id) is not None
