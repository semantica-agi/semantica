"""Normalization and temporal selection for explicitly annotated graph evidence."""

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..kg.temporal_model import TemporalBound, parse_temporal_value
from ..kg.temporal_reasoning import TemporalInterval, TemporalReasoningEngine
from ..utils.exceptions import TemporalValidationError, ValidationError
from ._truth_maintenance_validation import parse_atom, validate_fact_text
from .truth_maintenance_types import FactSupport

_BEGINNING = datetime.min.replace(tzinfo=timezone.utc)
_ENGINE = TemporalReasoningEngine()
_MISSING = object()


def timestamp(value: Any, field: str) -> datetime:
    """Parse an explicit query/bound time, without consulting the wall clock."""
    if value is None or isinstance(value, bool):
        raise TemporalValidationError(f"{field} requires an explicit timestamp")
    try:
        return parse_temporal_value(value)
    except (ValueError, TypeError, OverflowError, OSError) as exc:
        raise TemporalValidationError(f"Invalid {field}") from exc


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValidationError(f"{field} must be a nonempty, trimmed string")
    return value


def _end(value: Any, field: str) -> Optional[datetime]:
    if value is None or value is TemporalBound.OPEN or value == "OPEN":
        return None
    return timestamp(value, field)


@dataclass(frozen=True)
class Window:
    valid_from: datetime
    valid_until: Optional[datetime]
    recorded_at: datetime
    superseded_at: Optional[datetime]

    def active(self, valid_at: datetime, known_at: datetime) -> bool:
        return _ENGINE.active_at(
            TemporalInterval(self.valid_from, self.valid_until or TemporalBound.OPEN),
            valid_at,
        ) and _ENGINE.active_at(
            TemporalInterval(
                self.recorded_at, self.superseded_at or TemporalBound.OPEN
            ),
            known_at,
        )


@dataclass(frozen=True)
class Evidence:
    support: FactSupport
    source: str
    target: str
    relation_type: Optional[str]
    window: Window


@dataclass
class Projection:
    entities: Dict[str, Window]
    evidence: Dict[str, Evidence]

    def validate_update(
        self, previous: "Projection", rule_arities: Dict[str, int]
    ) -> None:
        """Retain revision identities and validate even currently inactive facts."""
        if previous.evidence and not previous.entities and self.entities:
            raise ValidationError(
                "Cannot add endpoint constraints to relationship-only history"
            )
        for key, old in previous.entities.items():
            if key not in self.entities:
                raise ValidationError(f"Cannot drop retained entity: {key}")
            _validate_window_revision(old, self.entities[key], key)
        for key, old in previous.evidence.items():
            new = self.evidence.get(key)
            if new is None:
                raise ValidationError(f"Cannot drop retained support: {key}")
            if replace(new, window=old.window) != old:
                raise ValidationError(
                    f"Use a new support_id for changed evidence: {key}"
                )
            _validate_window_revision(old.window, new.window, key)
        arities = dict(rule_arities)
        for record in self.evidence.values():
            predicate, terms = parse_atom(record.support.fact)
            arity = len(terms)
            if predicate in arities and arities[predicate] != arity:
                raise ValidationError(f"Conflicting arity for predicate: {predicate}")
            arities[predicate] = arity

    def select(self, valid_at: datetime, known_at: datetime) -> Dict[str, FactSupport]:
        active_entities = {
            key
            for key, window in self.entities.items()
            if window.active(valid_at, known_at)
        }
        return {
            key: record.support
            for key, record in sorted(self.evidence.items())
            if record.window.active(valid_at, known_at)
            and (
                not self.entities
                or (
                    record.source in active_entities
                    and record.target in active_entities
                )
            )
        }


def _validate_window_revision(old: Window, new: Window, key: str) -> None:
    if replace(new, superseded_at=old.superseded_at) != old:
        raise ValidationError(f"Cannot rewrite historical temporal fields: {key}")
    if old.superseded_at is not None and old.superseded_at != new.superseded_at:
        raise ValidationError(f"Cannot change a closed transaction interval: {key}")


def _bound(record: Dict[str, Any], field: str, *, open_ended: bool) -> Any:
    """Resolve one bound from the canonical field and from exported containers.

    ``ContextGraph.to_kg_dict()`` keeps properties other than the valid-time
    bounds inside ``metadata`` (and, for entities, ``properties``), so a bound
    that a caller supplied is only visible there. Duplicates are accepted when
    they denote the same instant and rejected when they disagree.
    """
    resolved: Any = _MISSING
    for container in (record, record.get("metadata"), record.get("properties")):
        if not isinstance(container, dict):
            continue
        value = container.get(field)
        if value is None:
            continue
        parsed = _end(value, field) if open_ended else timestamp(value, field)
        if resolved is not _MISSING and parsed != resolved:
            raise TemporalValidationError(f"Conflicting {field} values")
        resolved = parsed
    return resolved


def _window(record: Dict[str, Any], *, require_recorded: bool) -> Window:
    start = _bound(record, "valid_from", open_ended=False)
    until = _bound(record, "valid_until", open_ended=True)
    recorded = _bound(record, "recorded_at", open_ended=False)
    superseded = _bound(record, "superseded_at", open_ended=True)
    if require_recorded and recorded is _MISSING:
        raise TemporalValidationError("Managed evidence requires recorded_at")
    window = Window(
        _BEGINNING if start is _MISSING else start,
        None if until is _MISSING else until,
        _BEGINNING if recorded is _MISSING else recorded,
        None if superseded is _MISSING else superseded,
    )
    for lower, upper in (
        (window.valid_from, window.valid_until),
        (window.recorded_at, window.superseded_at),
    ):
        if upper is not None and upper <= lower:
            raise TemporalValidationError("Temporal intervals must have start < end")
    return window


def _endpoint(relationship: Dict[str, Any], field: str) -> str:
    """Resolve an endpoint from the short key or the canonical exported key.

    ``ContextGraph.to_kg_dict()`` emits ``source_id`` and ``target_id``, while
    hand-written graphs commonly use ``source`` and ``target``. Both are
    accepted; supplying both with different values is rejected rather than
    silently resolved by precedence.
    """
    short = relationship.get(field)
    canonical = relationship.get(f"{field}_id")
    if short is not None and canonical is not None and short != canonical:
        raise ValidationError(f"Conflicting {field} and {field}_id values")
    return _identifier(short if short is not None else canonical, field)


def normalize_graph(graph: Dict[str, Any]) -> Projection:
    """Copy only explicit evidence and endpoint lifetimes into detached values."""
    if not isinstance(graph, dict):
        raise ValidationError("graph must be an entities/relationships dictionary")
    entities = graph.get("entities", [])
    relationships = graph.get("relationships", [])
    if not isinstance(entities, list) or not isinstance(relationships, list):
        raise ValidationError("entities and relationships must be lists")
    projection = Projection({}, {})
    for entity in entities:
        if not isinstance(entity, dict):
            raise ValidationError("Each entity must be a dictionary")
        key = _identifier(entity.get("id"), "entity id")
        if key in projection.entities:
            raise ValidationError(f"Duplicate entity id: {key}")
        projection.entities[key] = _window(entity, require_recorded=False)
    for relationship in relationships:
        if not isinstance(relationship, dict):
            raise ValidationError("Each relationship must be a dictionary")
        metadata = relationship.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValidationError("Relationship metadata must be a dictionary")
        if "truth_maintenance" not in metadata:
            continue
        annotation = metadata["truth_maintenance"]
        if not isinstance(annotation, dict) or set(annotation) != {
            "support_id",
            "fact",
        }:
            raise ValidationError("truth_maintenance requires support_id and fact")
        support_id = _identifier(annotation["support_id"], "support_id")
        if support_id in projection.evidence:
            raise ValidationError(f"Duplicate support_id: {support_id}")
        support = FactSupport(support_id, validate_fact_text(annotation["fact"]))
        source = _endpoint(relationship, "source")
        target = _endpoint(relationship, "target")
        if projection.entities and (
            source not in projection.entities or target not in projection.entities
        ):
            raise ValidationError(f"Unknown endpoint for support {support_id}")
        relation_type = relationship.get("type")
        if relation_type is not None:
            relation_type = _identifier(relation_type, "relationship type")
        projection.evidence[support_id] = Evidence(
            support,
            source,
            target,
            relation_type,
            _window(relationship, require_recorded=True),
        )
    return projection
