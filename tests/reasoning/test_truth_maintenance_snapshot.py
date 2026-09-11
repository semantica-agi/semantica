"""Snapshot isolation and versioning tests for TruthMaintenanceSession."""

from dataclasses import FrozenInstanceError

import pytest
from semantica.reasoning import FactSupport, Rule, TruthMaintenanceSession
from semantica.utils.exceptions import ValidationError


def test_snapshot_is_detached_after_retraction():
    session = TruthMaintenanceSession(rules=[])
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    before = session.snapshot()
    session.apply(retractions=["s1"])
    assert before.version == 1
    assert before.facts == frozenset({"A(x)"})
    assert before.active_supports == (FactSupport("s1", "A(x)"),)
    assert session.snapshot().facts == frozenset()
    with pytest.raises(FrozenInstanceError):
        before.version = 42


def test_empty_session_snapshot():
    session = TruthMaintenanceSession(rules=[])
    snapshot = session.snapshot()
    assert snapshot.version == 0
    assert snapshot.facts == frozenset()
    assert snapshot.active_supports == ()


def test_snapshot_supports_are_sorted_by_support_id():
    session = TruthMaintenanceSession(rules=[])
    session.apply(
        assertions=[
            FactSupport("s3", "C(x)"),
            FactSupport("s1", "A(x)"),
            FactSupport("s2", "B(x)"),
        ]
    )
    snapshot = session.snapshot()
    assert [support.support_id for support in snapshot.active_supports] == [
        "s1",
        "s2",
        "s3",
    ]


def test_support_replacement_changes_version_and_supports_not_facts():
    session = TruthMaintenanceSession(rules=[])
    session.apply(assertions=[FactSupport("old", "A(x)")])
    session.apply(
        assertions=[FactSupport("new", "A(x)")], retractions=["old"]
    )
    snapshot = session.snapshot()
    assert snapshot.version == 2
    assert snapshot.facts == frozenset({"A(x)"})
    assert snapshot.active_supports == (FactSupport("new", "A(x)"),)


def test_noop_apply_keeps_version_and_snapshot():
    session = TruthMaintenanceSession(rules=[])
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    before = session.snapshot()
    delta = session.apply()  # empty batch is a no-op
    assert delta.version == before.version
    after = session.snapshot()
    assert after.version == before.version
    assert after.facts == before.facts
    assert after.active_supports == before.active_supports


def test_failed_apply_leaves_snapshot_unchanged():
    session = TruthMaintenanceSession(rules=[])
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    before = session.snapshot()
    with pytest.raises(ValidationError):
        session.apply(retractions=["s1", 42])  # malformed retraction id
    after = session.snapshot()
    assert after.version == before.version
    assert after.facts == before.facts
    assert after.active_supports == before.active_supports


def test_snapshot_includes_derived_facts():
    session = TruthMaintenanceSession(
        rules=[Rule("ab", "ab", ["A(?x)"], "B(?x)")]
    )
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    snapshot = session.snapshot()
    assert snapshot.facts == frozenset({"A(x)", "B(x)"})
    assert snapshot.active_supports == (FactSupport("s1", "A(x)"),)


def test_snapshot_detached_from_mutation_of_returned_collections():
    session = TruthMaintenanceSession(rules=[])
    session.apply(assertions=[FactSupport("s1", "A(x)")])
    snapshot = session.snapshot()
    # facts is a frozenset, active_supports is a tuple: both immutable by
    # construction; verify a later apply does not reflect into the snapshot.
    session.apply(retractions=["s1"])
    session.apply(assertions=[FactSupport("s2", "B(x)")])
    assert snapshot.facts == frozenset({"A(x)"})
    assert snapshot.active_supports == (FactSupport("s1", "A(x)"),)
    assert snapshot.version == 1