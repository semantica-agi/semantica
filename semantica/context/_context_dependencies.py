"""Pure dependency validation shared by filters and grounded assemblers.

This module owns the exact annotation schema first introduced by the
``TruthMaintenanceContextFilter``: every caller must validate candidates and
artifacts through the same rules instead of growing a second semantics. The
helpers are deliberately private; only the reason-code entry points are
consumed inside the package.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from semantica.context.grounded_context_types import (
    ArtifactRegistrySnapshot,
    ContextReadView,
    GroundedArtifact,
)
from semantica.reasoning._truth_maintenance_validation import validate_fact_text
from semantica.utils.exceptions import ValidationError

_ANNOTATION_SCHEMA_VERSION = 1
_ANNOTATION_KEYS = frozenset(
    {
        "schema_version",
        "session_id",
        "required_facts",
        "required_support_ids",
    }
)


def _validated_dependencies(
    annotation: Any,
) -> tuple[frozenset, frozenset, str]:
    """Validate a ``truth_maintenance`` annotation and normalize its sets.

    Returns the normalized ``(facts, support_ids, declared_session_id)``
    triple. Any violation of the schema raises ``ValueError``; comparing the
    declared session id against the expected namespace is the caller's job so
    that shared code can report ``wrong_namespace`` distinctly.
    """

    if not isinstance(annotation, dict):
        raise ValueError("truth_maintenance annotation must be a dict")
    keys = set(annotation.keys())
    if keys != set(_ANNOTATION_KEYS):
        raise ValueError(
            "truth_maintenance annotation must contain exactly "
            "schema_version, session_id, required_facts, "
            "required_support_ids"
        )

    schema_version = annotation["schema_version"]
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        raise ValueError("schema_version must be an integer")
    if schema_version != _ANNOTATION_SCHEMA_VERSION:
        raise ValueError("unsupported truth_maintenance schema_version")

    session_id = annotation["session_id"]
    if (
        not isinstance(session_id, str)
        or not session_id
        or session_id.strip() != session_id
    ):
        raise ValueError(
            "session_id must be a non-empty string without surrounding whitespace"
        )

    raw_facts = annotation["required_facts"]
    raw_supports = annotation["required_support_ids"]
    for raw_value in (raw_facts, raw_supports):
        if not isinstance(raw_value, list):
            raise ValueError("dependency lists must be lists")
    if not raw_facts and not raw_supports:
        raise ValueError("at least one required fact or support id must be declared")

    facts = set()
    for raw_fact in raw_facts:
        if not isinstance(raw_fact, str):
            raise ValueError("required_facts entries must be strings")
        try:
            facts.add(validate_fact_text(raw_fact))
        except ValidationError as exc:
            raise ValueError(f"invalid required fact: {exc.message}") from exc

    support_ids = set()
    for raw_support in raw_supports:
        if not isinstance(raw_support, str):
            raise ValueError("required_support_ids entries must be strings")
        if not raw_support or raw_support.strip() != raw_support:
            raise ValueError(
                "support ids must be non-empty strings without surrounding whitespace"
            )
        support_ids.add(raw_support)

    return frozenset(facts), frozenset(support_ids), session_id


def _attachment_metadata(member: Any) -> Any:
    """Return the metadata dict of a graph attachments member."""

    if not isinstance(member, dict):
        raise ValueError("graph attachments must be dicts")
    metadata = member.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("graph attachments must carry a metadata dict")
    return metadata


def _validated_attachments(
    attachments: Any,
) -> tuple[frozenset, frozenset, tuple[str, ...]]:
    """Validate attachment annotations and accumulate their dependencies."""

    facts: set = set()
    support_ids: set = set()
    namespaces = []
    if not isinstance(attachments, Sequence) or isinstance(
        attachments, (str, bytes, bytearray)
    ):
        raise ValueError("graph attachments must be lists")
    for member in attachments:
        metadata = _attachment_metadata(member)
        member_facts, member_supports, member_namespace = _validated_dependencies(
            metadata.get("truth_maintenance")
        )
        facts.update(member_facts)
        support_ids.update(member_supports)
        namespaces.append(member_namespace)
    return frozenset(facts), frozenset(support_ids), tuple(namespaces)


def evaluate_candidate(candidate: Any, *, view: ContextReadView) -> str | None:
    """Return the exclusion reason for ``candidate`` against ``view``.

    ``None`` means the candidate is grounded on the given read view. Caller
    mistakes (non-``RetrievedContext`` candidates, non-``ContextReadView``
    views) raise ``ValidationError``; candidate-level problems return a stable
    reason code ordered schema → namespace → facts → supports. Stale
    ``truth_maintenance_validation`` stamps on the candidate are never
    consulted: only the supplied view is authoritative.
    """

    from .context_retriever import RetrievedContext

    if not isinstance(candidate, RetrievedContext):
        raise ValidationError(
            "candidate must be a RetrievedContext instance",
            validation_context={"candidate_type": type(candidate).__name__},
        )
    if not isinstance(view, ContextReadView):
        raise ValidationError(
            "view must be a ContextReadView instance",
            validation_context={"view_type": type(view).__name__},
        )

    metadata = candidate.metadata
    if not isinstance(metadata, dict):
        return "missing_annotation"
    if "truth_maintenance" not in metadata:
        return "missing_annotation"
    annotation = metadata["truth_maintenance"]

    try:
        root_facts, root_supports, root_namespace = _validated_dependencies(annotation)
        entity_facts, entity_supports, entity_ns = _validated_attachments(
            candidate.related_entities
        )
        rel_facts, rel_supports, rel_ns = _validated_attachments(
            candidate.related_relationships
        )
    except ValueError:
        return "invalid_annotation"

    namespace = view.stamp.namespace
    for declared in (root_namespace,) + entity_ns + rel_ns:
        if declared != namespace:
            return "wrong_namespace"

    required_facts = root_facts | entity_facts | rel_facts
    required_supports = root_supports | entity_supports | rel_supports
    active_ids = frozenset(s.support_id for s in view.active_supports)
    if not required_facts.issubset(view.facts):
        return "missing_fact"
    if not required_supports.issubset(active_ids):
        return "missing_support"
    return None


def _artifact_reason(
    artifact: GroundedArtifact,
    *,
    registry: ArtifactRegistrySnapshot,
    view: ContextReadView,
) -> str | None:
    """Return the exclusion reason for a registered artifact on ``view``."""

    stamp = view.stamp
    if (
        artifact.built_from.namespace != stamp.namespace
        or artifact.built_from.source_kind != stamp.source_kind
    ):
        return "wrong_namespace"
    if not artifact.dependencies.required_facts.issubset(view.facts):
        return "missing_fact"
    if not artifact.dependencies.required_support_ids.issubset(view.support_ids):
        return "missing_support"
    if artifact.validity_policy == "snapshot" and artifact.built_from != stamp:
        return "snapshot_mismatch"
    for cited_id in artifact.citation_ids:
        cited = registry.get(cited_id)
        if cited is None:
            return "invalid_citation"
        if _artifact_reason(cited, registry=registry, view=view) is not None:
            return "invalid_citation"
    return None


def evaluate_artifact(
    artifact_id: str,
    *,
    registry: ArtifactRegistrySnapshot,
    view: ContextReadView,
) -> str | None:
    """Return the exclusion reason for a registered artifact against ``view``.

    ``None`` means the artifact is available on the given read view. The
    evaluation is pure: it never consults any cached eligibility and re-derives
    the verdict from the registry content and the view alone. Caller mistakes
    (bad identifier, wrong container types) raise ``ValidationError``.
    """

    if (
        not isinstance(artifact_id, str)
        or not artifact_id
        or artifact_id.strip() != artifact_id
    ):
        raise ValidationError(
            "artifact_id must be a non-empty string without surrounding " "whitespace",
            validation_context={"artifact_id": artifact_id},
        )
    if not isinstance(registry, ArtifactRegistrySnapshot):
        raise ValidationError(
            "registry must be an ArtifactRegistrySnapshot instance",
            validation_context={"registry_type": type(registry).__name__},
        )
    if not isinstance(view, ContextReadView):
        raise ValidationError(
            "view must be a ContextReadView instance",
            validation_context={"view_type": type(view).__name__},
        )
    artifact = registry.get(artifact_id)
    if artifact is None:
        return "unknown_artifact"
    return _artifact_reason(artifact, registry=registry, view=view)
