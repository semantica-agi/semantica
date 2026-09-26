"""Immutable value types shared by the grounded context stack.

These types describe a single consistent read of a truth maintenance source:
the stamp identifying it, the facts and supports it exposes, the registered
artifacts validated against it, and the assembled context that results. Every
type is frozen, stores only immutable members and validates its own shape, so
callers cannot smuggle mutable metadata into a result meant to describe one
fixed view.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from semantica.reasoning import FactSupport
from semantica.reasoning._truth_maintenance_validation import validate_fact_text
from semantica.utils.exceptions import ValidationError

__all__ = [
    "ArtifactInvalidationReport",
    "ArtifactRegistrySnapshot",
    "ContextBlock",
    "ContextCitation",
    "ContextDependencies",
    "ContextReadView",
    "Exclusion",
    "GroundedArtifact",
    "GroundedContext",
    "SnapshotStamp",
]

SOURCE_KINDS = frozenset({"session", "temporal"})
READ_KINDS = frozenset({"live", "historical"})
ARTIFACT_KINDS = frozenset({"summary", "citation"})
VALIDITY_POLICIES = frozenset({"snapshot", "dependencies"})
EXCLUSION_REASONS = (
    "missing_annotation",
    "invalid_annotation",
    "wrong_namespace",
    "missing_fact",
    "missing_support",
    "unknown_artifact",
    "content_mismatch",
    "snapshot_mismatch",
    "invalid_citation",
    "budget_exceeded",
)


def _word(value: Any, name: str) -> str:
    """Return a non-empty identifier that carries no surrounding whitespace."""
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be a string, got {type(value).__name__}")
    if not value or value != value.strip():
        raise ValidationError(f"{name} must be non-empty and stripped, got {value!r}")
    return value


def _choice(value: Any, name: str, allowed: Iterable[str]) -> str:
    if _word(value, name) not in allowed:
        raise ValidationError(f"{name} must be one of {sorted(allowed)}, got {value!r}")
    return value


def _content(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{name} must be a non-empty string")
    return value


def _counter(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{name} must be an integer, got {type(value).__name__}")
    if value < 0:
        raise ValidationError(f"{name} must not be negative, got {value}")
    return value


def _moment(value: Any, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValidationError(f"{name} must be a datetime, got {type(value).__name__}")
    if value.utcoffset() is None:
        raise ValidationError(f"{name} must be timezone aware")
    return value.astimezone(timezone.utc)


def _unset(value: Any, name: str, source_kind: str) -> None:
    if value is not None:
        raise ValidationError(f"{name} does not belong to a {source_kind} stamp")


def _members(values: Any, name: str) -> tuple[Any, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ValidationError(f"{name} must be an iterable of values")
    return tuple(values)


def _word_set(values: Any, name: str) -> frozenset[str]:
    return frozenset(_word(item, f"{name} entry") for item in _members(values, name))


def _fact_set(values: Any, name: str) -> frozenset[str]:
    return frozenset(validate_fact_text(item) for item in _members(values, name))


def _word_tuple(values: Any, name: str) -> tuple[str, ...]:
    items = tuple(_word(item, f"{name} entry") for item in _members(values, name))
    if len(set(items)) != len(items):
        raise ValidationError(f"{name} must not repeat an entry")
    return items


def _typed_tuple(values: Any, name: str, expected: type) -> tuple[Any, ...]:
    items = _members(values, name)
    for item in items:
        if not isinstance(item, expected):
            raise ValidationError(
                f"{name} must contain {expected.__name__} values, "
                f"got {type(item).__name__}"
            )
    return items


def _instance(value: Any, name: str, expected: type) -> Any:
    if not isinstance(value, expected):
        raise ValidationError(
            f"{name} must be a {expected.__name__}, got {type(value).__name__}"
        )
    return value


@dataclass(frozen=True)
class SnapshotStamp:
    """Identity of one consistent read of a truth maintenance source."""

    namespace: str
    source_kind: str
    version: int | None = None
    graph_revision: int | None = None
    valid_at: datetime | None = None
    known_at: datetime | None = None
    provider_id: str | None = None

    def __post_init__(self) -> None:
        _word(self.namespace, "namespace")
        if self.provider_id is not None:
            _word(self.provider_id, "provider_id")
        _choice(self.source_kind, "source_kind", SOURCE_KINDS)
        if self.source_kind == "session":
            _counter(self.version, "version")
            _unset(self.graph_revision, "graph_revision", "session")
            _unset(self.valid_at, "valid_at", "session")
            _unset(self.known_at, "known_at", "session")
            return
        _unset(self.version, "version", "temporal")
        _counter(self.graph_revision, "graph_revision")
        object.__setattr__(self, "valid_at", _moment(self.valid_at, "valid_at"))
        object.__setattr__(self, "known_at", _moment(self.known_at, "known_at"))


@dataclass(frozen=True)
class ContextReadView:
    """Facts and supports read from one stamped source view.

    ``read_kind`` is a freshness policy rather than part of the cache identity:
    the same graph revision and the same pair of coordinates describe the same
    semantic slice whether it was reached by a live or a historical read.
    """

    stamp: SnapshotStamp
    read_kind: str
    facts: frozenset[str]
    active_supports: tuple[FactSupport, ...]

    def __post_init__(self) -> None:
        _instance(self.stamp, "stamp", SnapshotStamp)
        _choice(self.read_kind, "read_kind", READ_KINDS)
        if self.read_kind == "historical" and self.stamp.source_kind != "temporal":
            raise ValidationError("historical reads require a temporal stamp")
        object.__setattr__(self, "facts", _fact_set(self.facts, "facts"))
        object.__setattr__(
            self,
            "active_supports",
            _typed_tuple(self.active_supports, "active_supports", FactSupport),
        )

    @property
    def support_ids(self) -> frozenset[str]:
        """IDs of the supports that are active in this view."""
        return frozenset(support.support_id for support in self.active_supports)


@dataclass(frozen=True)
class ContextDependencies:
    """Positive facts and supports a piece of content relies on."""

    required_facts: frozenset[str] = frozenset()
    required_support_ids: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "required_facts", _fact_set(self.required_facts, "required_facts")
        )
        object.__setattr__(
            self,
            "required_support_ids",
            _word_set(self.required_support_ids, "required_support_ids"),
        )

    def __bool__(self) -> bool:
        return bool(self.required_facts or self.required_support_ids)


@dataclass(frozen=True)
class Exclusion:
    """A single object kept out of a view, with a stable machine reason."""

    object_id: str
    reason: str

    def __post_init__(self) -> None:
        _word(self.object_id, "object_id")
        _choice(self.reason, "reason", EXCLUSION_REASONS)


@dataclass(frozen=True)
class ArtifactInvalidationReport:
    """Availability changes observed while aligning a registry to a view."""

    stamp: SnapshotStamp
    invalidated_ids: tuple[str, ...] = ()
    reactivated_ids: tuple[str, ...] = ()
    exclusions: tuple[Exclusion, ...] = ()

    def __post_init__(self) -> None:
        _instance(self.stamp, "stamp", SnapshotStamp)
        object.__setattr__(
            self,
            "invalidated_ids",
            _word_tuple(self.invalidated_ids, "invalidated_ids"),
        )
        object.__setattr__(
            self,
            "reactivated_ids",
            _word_tuple(self.reactivated_ids, "reactivated_ids"),
        )
        object.__setattr__(
            self, "exclusions", _typed_tuple(self.exclusions, "exclusions", Exclusion)
        )
        overlap = set(self.invalidated_ids) & set(self.reactivated_ids)
        if overlap:
            raise ValidationError(
                "an artifact cannot be invalidated and reactivated at once: "
                f"{sorted(overlap)}"
            )

    def __bool__(self) -> bool:
        return bool(self.invalidated_ids or self.reactivated_ids)


@dataclass(frozen=True)
class GroundedArtifact:
    """One immutable content version registered against a read view."""

    artifact_id: str
    kind: str
    content: str
    dependencies: ContextDependencies
    built_from: SnapshotStamp
    validity_policy: str = "snapshot"
    citation_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _word(self.artifact_id, "artifact_id")
        _choice(self.kind, "kind", ARTIFACT_KINDS)
        _content(self.content, "content")
        _instance(self.dependencies, "dependencies", ContextDependencies)
        _instance(self.built_from, "built_from", SnapshotStamp)
        _choice(self.validity_policy, "validity_policy", VALIDITY_POLICIES)
        object.__setattr__(
            self, "citation_ids", _word_tuple(self.citation_ids, "citation_ids")
        )
        if self.artifact_id in self.citation_ids:
            raise ValidationError("an artifact must not cite itself")


@dataclass(frozen=True)
class ArtifactRegistrySnapshot:
    """Detached copy of every artifact registered in one namespace."""

    namespace: str
    revision: int
    artifacts: tuple[GroundedArtifact, ...] = ()

    def __post_init__(self) -> None:
        _word(self.namespace, "namespace")
        _counter(self.revision, "revision")
        object.__setattr__(
            self,
            "artifacts",
            _typed_tuple(self.artifacts, "artifacts", GroundedArtifact),
        )
        ids = [artifact.artifact_id for artifact in self.artifacts]
        if len(set(ids)) != len(ids):
            raise ValidationError("artifacts must not repeat an artifact_id")

    def get(self, artifact_id: str) -> GroundedArtifact | None:
        """Return the registered artifact with this ID, or ``None``."""
        _word(artifact_id, "artifact_id")
        for artifact in self.artifacts:
            if artifact.artifact_id == artifact_id:
                return artifact
        return None


@dataclass(frozen=True)
class ContextBlock:
    """One body passage admitted into an assembled context."""

    block_id: str
    content: str
    source: str | None = None
    citation_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _word(self.block_id, "block_id")
        _content(self.content, "content")
        if self.source is not None:
            _content(self.source, "source")
        object.__setattr__(
            self, "citation_ids", _word_tuple(self.citation_ids, "citation_ids")
        )


@dataclass(frozen=True)
class ContextCitation:
    """A structured reference rendered beneath the assembled body."""

    label: str
    artifact_id: str
    content: str
    support_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _word(self.label, "label")
        _word(self.artifact_id, "artifact_id")
        _content(self.content, "content")
        object.__setattr__(
            self, "support_ids", _word_tuple(self.support_ids, "support_ids")
        )
        if not self.support_ids:
            raise ValidationError("a citation must name at least one support")


@dataclass(frozen=True)
class GroundedContext:
    """Assembled text plus the exact view and registry revision behind it."""

    text: str
    blocks: tuple[ContextBlock, ...]
    citations: tuple[ContextCitation, ...]
    stamp: SnapshotStamp
    artifact_revision: int
    exclusions: tuple[Exclusion, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise ValidationError("text must be a string")
        object.__setattr__(
            self, "blocks", _typed_tuple(self.blocks, "blocks", ContextBlock)
        )
        object.__setattr__(
            self,
            "citations",
            _typed_tuple(self.citations, "citations", ContextCitation),
        )
        _instance(self.stamp, "stamp", SnapshotStamp)
        _counter(self.artifact_revision, "artifact_revision")
        object.__setattr__(
            self,
            "exclusions",
            _typed_tuple(self.exclusions, "exclusions", Exclusion),
        )
