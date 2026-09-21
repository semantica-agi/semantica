"""Public value types for truth maintenance.

These dataclasses are the public API surface of
:class:`semantica.reasoning.TruthMaintenanceSession`.  All collections are
immutable (tuples and frozensets) so snapshots returned by the session can
never be mutated by later updates.
"""

from dataclasses import dataclass
from typing import FrozenSet, Tuple

__all__ = [
    "Derivation",
    "FactExplanation",
    "FactSupport",
    "MaintenanceDelta",
    "TruthMaintenanceSnapshot",
]


@dataclass(frozen=True)
class FactSupport:
    """An explicitly asserted fact identified by a lifetime-stable ID."""

    support_id: str
    fact: str


@dataclass(frozen=True)
class Derivation:
    """A single rule application that concludes one fact from premises."""

    rule_id: str
    conclusion: str
    premises: Tuple[str, ...]
    bindings: Tuple[Tuple[str, str], ...]


@dataclass(frozen=True)
class FactExplanation:
    """Everything known about why a fact currently holds."""

    fact: str
    active: bool
    explicit_support_ids: Tuple[str, ...]
    derivations: Tuple[Derivation, ...]


@dataclass(frozen=True)
class MaintenanceDelta:
    """Net effect of one ``apply`` batch, observed after commit."""

    version: int
    added_facts: FrozenSet[str]
    removed_facts: FrozenSet[str]
    added_supports: Tuple[FactSupport, ...]
    removed_supports: Tuple[FactSupport, ...]


@dataclass(frozen=True)
class TruthMaintenanceSnapshot:
    """Immutable, detached view of one committed session state.

    Returned by :meth:`TruthMaintenanceSession.snapshot`.  The collections
    and support records are copies detached from live session state, so
    later ``apply`` batches never change an existing snapshot.
    """

    version: int
    facts: FrozenSet[str]
    active_supports: Tuple[FactSupport, ...]


@dataclass(frozen=True)
class _RuleSnapshot:
    """Internal immutable copy of the subset of Rule the session relies on.

    Snapshots are taken at session construction so later mutation of the
    original ``Rule`` objects never changes session behavior.
    """

    rule_id: str
    conditions: Tuple[str, ...]
    conclusion: str
    # Parsed view of conditions: tuple of (predicate, terms).
    parsed_conditions: Tuple[Tuple[str, Tuple[str, ...]], ...]
    parsed_conclusion: Tuple[str, Tuple[str, ...]]
    head_variables: FrozenSet[str]
    body_variables: FrozenSet[str]
    order: Tuple[int, str]