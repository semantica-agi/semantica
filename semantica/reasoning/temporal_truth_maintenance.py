"""Opt-in projection of bitemporal graph evidence into managed reasoning."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, FrozenSet, Iterable, Optional, Tuple

from ..utils.exceptions import ValidationError
from ._temporal_support_projection import Projection, normalize_graph, timestamp
from ._truth_maintenance_validation import (
    build_rule_snapshots,
    validate_fact_text,
)
from .reasoner import Rule
from .truth_maintenance import TruthMaintenanceSession
from .truth_maintenance_types import (
    FactExplanation,
    FactSupport,
    MaintenanceDelta,
)

__all__ = ["TemporalTruthMaintenanceAdapter", "TemporalFactSnapshot"]


@dataclass(frozen=True)
class TemporalFactSnapshot:
    """Detached closure for one pair of temporal coordinates and graph revision."""

    valid_at: datetime
    known_at: datetime
    graph_revision: int
    facts: FrozenSet[str]
    active_supports: Tuple[FactSupport, ...]
    explanations: Tuple[FactExplanation, ...]

    def explain(self, fact: str) -> FactExplanation:
        canonical = validate_fact_text(fact)
        for explanation in self.explanations:
            if explanation.fact == canonical:
                return explanation
        return FactExplanation(canonical, False, (), ())


class TemporalTruthMaintenanceAdapter:
    """Maintain a live closure over explicitly annotated temporal relationships.

    Both ``valid_at`` (when a fact applies) and ``known_at`` (when its evidence
    was known) are explicit. Intervals are half-open with full datetime
    precision. Calls must be serialized by the caller. No background scheduler,
    storage client, graph mutation, or language-model call is performed.
    """

    def __init__(self, *, rules: Iterable[Rule]):
        if isinstance(rules, (str, bytes)):
            raise ValidationError("rules must be an iterable of Rule objects")
        try:
            self._rules = deepcopy(tuple(rules))
        except TypeError as exc:
            raise ValidationError("rules must be an iterable of Rule objects") from exc
        self._session = TruthMaintenanceSession(rules=self._rules)
        _, self._rule_arities = build_rule_snapshots(self._rules)
        self._projection = Projection({}, {})
        self._active_supports: Dict[str, FactSupport] = {}
        self._graph_revision = 0
        self._valid_at: Optional[datetime] = None
        self._known_at: Optional[datetime] = None

    @property
    def facts(self) -> FrozenSet[str]:
        return self._session.facts

    @property
    def version(self) -> int:
        """PR1 support-set version; a clock-only change need not increment it."""
        return self._session.version

    @property
    def graph_revision(self) -> int:
        """Revision of retained normalized evidence, including inactive records."""
        return self._graph_revision

    @property
    def valid_at(self) -> Optional[datetime]:
        return self._valid_at

    @property
    def known_at(self) -> Optional[datetime]:
        return self._known_at

    def explain(self, fact: str) -> FactExplanation:
        return self._session.explain(fact)

    def sync(
        self,
        graph: Dict[str, Any],
        *,
        valid_at: Any,
        known_at: Any,
    ) -> MaintenanceDelta:
        """Ingest evidence history and atomically update the selected supports."""
        projection = normalize_graph(graph)
        projection.validate_update(self._projection, self._rule_arities)
        return self._apply(projection, valid_at=valid_at, known_at=known_at)

    def advance(self, *, valid_at: Any, known_at: Any) -> MaintenanceDelta:
        """Explicitly move the live temporal coordinates over retained evidence."""
        return self._apply(self._projection, valid_at=valid_at, known_at=known_at)

    def _apply(
        self,
        projection: Projection,
        *,
        valid_at: Any,
        known_at: Any,
    ) -> MaintenanceDelta:
        valid_time = timestamp(valid_at, "valid_at")
        known_time = timestamp(known_at, "known_at")
        selected = projection.select(valid_time, known_time)
        delta = self._session.apply(
            assertions=[
                value
                for key, value in selected.items()
                if key not in self._active_supports
            ],
            retractions=sorted(set(self._active_supports) - set(selected)),
        )
        self._graph_revision += projection != self._projection
        self._projection = projection
        self._active_supports = selected
        self._valid_at = valid_time
        self._known_at = known_time
        return delta

    def query_at(self, *, valid_at: Any, known_at: Any) -> TemporalFactSnapshot:
        """Recompute a historical closure without changing the live session."""
        valid_time = timestamp(valid_at, "valid_at")
        known_time = timestamp(known_at, "known_at")
        selected = self._projection.select(valid_time, known_time)
        historical = TruthMaintenanceSession(rules=self._rules)
        historical.apply(assertions=selected.values())
        return TemporalFactSnapshot(
            valid_time,
            known_time,
            self._graph_revision,
            historical.facts,
            tuple(selected.values()),
            tuple(historical.explain(fact) for fact in sorted(historical.facts)),
        )
